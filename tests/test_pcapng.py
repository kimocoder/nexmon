#!/usr/bin/env python3
"""Unit tests for python/pynexmon/pcapng.py (Wireshark PCAP-NG and PCAP CSI Exporter)."""

from io import BytesIO
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

NEXMON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(NEXMON_ROOT, "python"))

from pynexmon.csi import CSIPacket
from pynexmon.pcapng import (
    CSIPcapNGWriter,
    CSIPcapWriter,
    LINKTYPE_IEEE802_11_RADIOTAP,
    PCAP_MAGIC_USEC,
    PCAPNG_IDB_MAGIC,
    PCAPNG_SHB_MAGIC,
    _parse_mac_address,
    build_ieee80211_qos_data_frame,
    build_radiotap_header,
    chanspec_to_frequency_mhz,
    csi_packet_to_radiotap_frame,
    export_csi_to_pcap,
    export_csi_to_pcapng,
)


def _make_dummy_csi_packet(
    seq: int = 1,
    mac: str = "00:11:22:33:44:55",
    chanspec: int = 0x1809,
    tsft_us: int = 123456789,
    num_subcarriers: int = 64,
) -> CSIPacket:
    raw_iq = [(i * 2, -i * 3) for i in range(num_subcarriers)]
    return CSIPacket(
        magic=0x11111111,
        src_mac=mac,
        seq=seq,
        core=1,
        spatial_stream=0,
        chanspec=chanspec,
        chip_id=0x4345,
        raw_iq=raw_iq,
        timestamp=1700000000.123456,
        tsft_us=tsft_us,
    )


class TestPcapNGAndRadiotap(unittest.TestCase):
    """Test suite for IEEE 802.11 Radiotap packaging and PCAP/PCAP-NG export."""

    def test_parse_mac_address(self):
        self.assertEqual(_parse_mac_address("00:11:22:33:44:55"), b"\x00\x11\x22\x33\x44\x55")
        self.assertEqual(_parse_mac_address("aa:bb:cc:dd:ee:ff"), b"\xaa\xbb\xcc\xdd\xee\xff")
        # Invalid MAC returns broadcast
        self.assertEqual(_parse_mac_address("invalid-mac"), b"\xff\xff\xff\xff\xff\xff")
        self.assertEqual(_parse_mac_address("00:11:22"), b"\xff\xff\xff\xff\xff\xff")

    def test_chanspec_to_frequency_mhz(self):
        # 2.4 GHz channel 1 = 2412, channel 6 = 2437, channel 11 = 2462, channel 14 = 2484
        self.assertEqual(chanspec_to_frequency_mhz(1), 2412)
        self.assertEqual(chanspec_to_frequency_mhz(6), 2437)
        self.assertEqual(chanspec_to_frequency_mhz(11), 2462)
        self.assertEqual(chanspec_to_frequency_mhz(14), 2484)
        # 5 GHz channel 36 = 5180, channel 149 = 5745
        self.assertEqual(chanspec_to_frequency_mhz(36), 5180)
        self.assertEqual(chanspec_to_frequency_mhz(149), 5745)
        self.assertEqual(chanspec_to_frequency_mhz(0x1809), 2452)  # 2.4GHz ch 9

    def test_build_radiotap_header(self):
        hdr = build_radiotap_header(tsft_us=1000000, freq_mhz=2437, is_5ghz=False)
        self.assertEqual(len(hdr), 24)
        version, pad, length, present = struct.unpack_from("<BBHI", hdr, 0)
        self.assertEqual(version, 0)
        self.assertEqual(pad, 0)
        self.assertEqual(length, 24)
        self.assertEqual(present, (1 << 0) | (1 << 1) | (1 << 3))

        # Check TSFT at offset 8
        tsft = struct.unpack_from("<Q", hdr, 8)[0]
        self.assertEqual(tsft, 1000000)

        # Check frequency at offset 18
        freq = struct.unpack_from("<H", hdr, 18)[0]
        self.assertEqual(freq, 2437)

    def test_build_ieee80211_qos_data_frame(self):
        payload = b"test payload"
        frame = build_ieee80211_qos_data_frame(
            src_mac="00:11:22:33:44:55",
            dst_mac="66:77:88:99:aa:bb",
            seq=10,
            payload=payload,
        )
        self.assertEqual(len(frame), 26 + len(payload))
        fc, duration, a1, a2, a3, seq_ctrl, qos_ctrl = struct.unpack("<HH6s6s6sHH", frame[:26])
        self.assertEqual(fc, 0x0088)
        self.assertEqual(a1, b"\x66\x77\x88\x99\xaa\xbb")
        self.assertEqual(a2, b"\x00\x11\x22\x33\x44\x55")
        self.assertEqual(a3, b"\x00\x11\x22\x33\x44\x55")
        self.assertEqual(seq_ctrl, (10 & 0x0FFF) << 4)
        self.assertEqual(qos_ctrl, 0)
        self.assertEqual(frame[26:], payload)

    def test_csi_packet_to_radiotap_frame(self):
        pkt = _make_dummy_csi_packet(seq=42, mac="00:11:22:33:44:55", chanspec=6, tsft_us=999888)
        frame = csi_packet_to_radiotap_frame(pkt)

        # 24B radiotap + 26B 802.11 QoS header + 18B CSI header + 64*4B IQ data
        expected_len = 24 + 26 + 18 + (64 * 4)
        self.assertEqual(len(frame), expected_len)

        # Verify CSI method matches
        frame_method = pkt.to_radiotap_frame()
        self.assertEqual(frame, frame_method)

    def test_pcapng_writer_memory_stream(self):
        buf = BytesIO()
        writer = CSIPcapNGWriter(buf, if_name="mon0")

        # Initial write has SHB (28B) + IDB (20B + options + 4B tail = 40B)
        self.assertGreater(buf.tell(), 50)

        pkt1 = _make_dummy_csi_packet(seq=1)
        pkt2 = _make_dummy_csi_packet(seq=2)
        writer.write_packet(pkt1)
        writer.write_packet(pkt2)

        self.assertEqual(writer.packet_count, 2)
        raw_bytes = buf.getvalue()

        # Check SHB magic
        shb_magic = struct.unpack_from("<I", raw_bytes, 0)[0]
        self.assertEqual(shb_magic, PCAPNG_SHB_MAGIC)

        # Check IDB magic
        idb_offset = 28
        idb_magic = struct.unpack_from("<I", raw_bytes, idb_offset)[0]
        self.assertEqual(idb_magic, PCAPNG_IDB_MAGIC)

    def test_classic_pcap_writer_memory_stream(self):
        buf = BytesIO()
        writer = CSIPcapWriter(buf)

        self.assertEqual(buf.tell(), 24)
        magic, major, minor, tz, sigfigs, snaplen, linktype = struct.unpack("<IHHiIII", buf.getvalue()[:24])
        self.assertEqual(magic, PCAP_MAGIC_USEC)
        self.assertEqual(major, 2)
        self.assertEqual(minor, 4)
        self.assertEqual(linktype, LINKTYPE_IEEE802_11_RADIOTAP)

        pkt = _make_dummy_csi_packet(seq=1)
        writer.write_packet(pkt)
        self.assertEqual(writer.packet_count, 1)

    def test_export_convenience_functions_and_disk_files(self):
        packets = [_make_dummy_csi_packet(seq=i) for i in range(5)]
        with tempfile.TemporaryDirectory() as tmpdir:
            pcapng_file = os.path.join(tmpdir, "csi_export.pcapng")
            pcap_file = os.path.join(tmpdir, "csi_export.pcap")

            n_ng = export_csi_to_pcapng(packets, pcapng_file, if_name="wlan0mon")
            self.assertEqual(n_ng, 5)
            self.assertTrue(os.path.exists(pcapng_file))
            self.assertGreater(os.path.getsize(pcapng_file), 500)

            n_classic = export_csi_to_pcap(packets, pcap_file)
            self.assertEqual(n_classic, 5)
            self.assertTrue(os.path.exists(pcap_file))
            self.assertGreater(os.path.getsize(pcap_file), 500)

            # Validate with capinfos / tshark if available
            if shutil.which("capinfos"):
                res = subprocess.run(["capinfos", pcapng_file], stdout=subprocess.PIPE, text=True, check=True)
                self.assertIn("Number of packets:   5", res.stdout)
                self.assertIn("802.11 plus radiotap radio header", res.stdout)

                res_c = subprocess.run(["capinfos", pcap_file], stdout=subprocess.PIPE, text=True, check=True)
                self.assertIn("Number of packets:   5", res_c.stdout)
                self.assertIn("802.11 plus radiotap radio header", res_c.stdout)

            if shutil.which("tshark"):
                res_ts = subprocess.run(
                    ["tshark", "-r", pcapng_file, "-T", "fields", "-e", "wlan.sa", "-e", "radiotap.channel.freq"],
                    stdout=subprocess.PIPE,
                    text=True,
                    check=True,
                )
                lines = [line.strip() for line in res_ts.stdout.strip().splitlines() if line.strip()]
                self.assertEqual(len(lines), 5)
                for line in lines:
                    self.assertIn("00:11:22:33:44:55", line)


if __name__ == "__main__":
    unittest.main()
