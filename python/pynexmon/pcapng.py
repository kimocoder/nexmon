"""Wireshark PCAP-NG and PCAP exporter for Nexmon CSI frames.

Encapsulates Nexmon Channel State Information (CSI) frames into standard IEEE 802.11
Radiotap frames (DLT_IEEE802_11_RADIO / LinkType 127) and writes compliant PCAP-NG
(PCAP Next Generation) or classic PCAP files.

Allows engineers and researchers to inspect subcarrier amplitudes, phases, TSF hardware
timestamps, and channel allocations directly inside Wireshark or tshark without custom
plotting pipelines.
"""

from pathlib import Path
import struct
import time
from typing import Any, BinaryIO, Iterable, Union

# DLT / LinkType for 802.11 with Radiotap header
LINKTYPE_IEEE802_11_RADIOTAP = 127

# PCAP-NG Block Types
PCAPNG_SHB_MAGIC = 0x0A0D0D0A  # Section Header Block
PCAPNG_IDB_MAGIC = 0x00000001  # Interface Description Block
PCAPNG_EPB_MAGIC = 0x00000006  # Enhanced Packet Block
PCAPNG_BYTE_ORDER_MAGIC = 0x1A2B3C4D  # Little-endian

# Classic PCAP Magic (Microsecond resolution)
PCAP_MAGIC_USEC = 0xA1B2C3D4

# Radiotap Present Flags
RADIOTAP_TSFT = 1 << 0
RADIOTAP_FLAGS = 1 << 1
RADIOTAP_CHANNEL = 1 << 3

# Radiotap Channel Spectrum Flags
IEEE80211_CHAN_2GHZ = 0x0040
IEEE80211_CHAN_5GHZ = 0x0080
IEEE80211_CHAN_OFDM = 0x0100


def _parse_mac_address(mac_str: str) -> bytes:
    """Convert a colon-separated MAC string to 6 raw bytes."""
    parts = mac_str.strip().split(":")
    if len(parts) != 6:
        return b"\xff\xff\xff\xff\xff\xff"
    try:
        return bytes(int(p, 16) for p in parts)
    except ValueError:
        return b"\xff\xff\xff\xff\xff\xff"


def chanspec_to_frequency_mhz(chanspec: int) -> int:
    """Calculate radio carrier frequency in MHz from Broadcom chanspec."""
    channel = chanspec & 0x00FF
    band_bits = chanspec & 0xC000

    # 2.4 GHz band
    if band_bits == 0x1000 or (band_bits == 0 and channel <= 14):
        if channel == 14:
            return 2484
        return 2407 + channel * 5

    # 5 GHz band (channel numbers >= 36)
    if band_bits == 0x2000 or channel >= 36:
        return 5000 + channel * 5

    return 2412  # Fallback to Channel 1 (2412 MHz)


def build_radiotap_header(
    tsft_us: int,
    freq_mhz: int,
    is_5ghz: bool = False,
) -> bytes:
    """Build a compliant IEEE 802.11 Radiotap header.

    Fields included:
      - Bit 0: TSFT (8 bytes, 8-byte aligned)
      - Bit 1: Flags (1 byte, 1-byte aligned)
      - Bit 3: Channel (4 bytes: freq_mhz + flags, 2-byte aligned)

    Header Layout:
      [0..1]:   version=0, pad=0 (2B)
      [2..3]:   it_len=24 (2B)
      [4..7]:   it_present (4B)
      [8..15]:  tsft_us (8B, aligned to 8)
      [16]:     flags=0 (1B, aligned to 1)
      [17]:     pad=0 (1B, aligns channel to 2 bytes)
      [18..19]: freq_mhz (2B, aligned to 2)
      [20..21]: channel_flags (2B)
      [22..23]: header trailing padding (2B, aligns whole header to 4 bytes)
    """
    it_version = 0
    it_pad = 0
    it_len = 24  # Total length padded to 4-byte boundary
    it_present = RADIOTAP_TSFT | RADIOTAP_FLAGS | RADIOTAP_CHANNEL

    chan_flags = (IEEE80211_CHAN_5GHZ if is_5ghz else IEEE80211_CHAN_2GHZ) | IEEE80211_CHAN_OFDM

    hdr = struct.pack(
        "<BBHI Q B B HH H",
        it_version,
        it_pad,
        it_len,
        it_present,
        tsft_us & 0xFFFFFFFFFFFFFFFF,
        0,  # flags
        0,  # pad for channel alignment
        freq_mhz & 0xFFFF,
        chan_flags & 0xFFFF,
        0,  # trailing pad
    )
    return hdr


def build_ieee80211_qos_data_frame(
    src_mac: str,
    dst_mac: str = "ff:ff:ff:ff:ff:ff",
    seq: int = 0,
    payload: bytes = b"",
) -> bytes:
    """Construct an IEEE 802.11 QoS Data frame encapsulating Nexmon CSI payload.

    Layout (26 bytes 802.11 header):
      - Frame Control: 0x0088 (Data, QoS Data, To-DS=0, From-DS=0)
      - Duration: 0x0000
      - Address 1 (Receiver / Destination): dst_mac (6 bytes)
      - Address 2 (Transmitter / Source): src_mac (6 bytes)
      - Address 3 (BSSID): src_mac (6 bytes)
      - Sequence Control: (seq & 0x0fff) << 4 (2 bytes)
      - QoS Control: 0x0000 (2 bytes)
      - Payload: Nexmon CSI binary payload
    """
    frame_control = 0x0088
    duration = 0x0000
    addr1 = _parse_mac_address(dst_mac)
    addr2 = _parse_mac_address(src_mac)
    addr3 = _parse_mac_address(src_mac)
    seq_ctrl = (seq & 0x0FFF) << 4
    qos_ctrl = 0x0000

    hdr = struct.pack("<HH6s6s6sHH", frame_control, duration, addr1, addr2, addr3, seq_ctrl, qos_ctrl)
    return hdr + payload


def csi_packet_to_radiotap_frame(packet: Any, dst_mac: str = "ff:ff:ff:ff:ff:ff") -> bytes:
    """Convert a CSIPacket into a full IEEE 802.11 Radiotap capture frame.

    Args:
        packet: CSIPacket instance from pynexmon.csi.
        dst_mac: Destination MAC address (default broadcast).

    Returns:
        Bytes representing Radiotap header + 802.11 QoS Data header + CSI payload.
    """
    # Determine timestamp in microseconds
    if getattr(packet, "tsft_us", None) is not None:
        ts_us = int(packet.tsft_us)
    elif getattr(packet, "timestamp", None) is not None:
        ts_us = int(packet.timestamp * 1_000_000)
    else:
        ts_us = int(time.time() * 1_000_000)

    # Determine channel and spectrum
    chanspec = getattr(packet, "chanspec", 0)
    freq_mhz = chanspec_to_frequency_mhz(chanspec)
    is_5ghz = freq_mhz >= 4900

    radiotap = build_radiotap_header(tsft_us=ts_us, freq_mhz=freq_mhz, is_5ghz=is_5ghz)

    # Build raw CSI payload bytes
    # Header: magic(4) + src_mac(6) + seq(2) + core/spatial(2) + chanspec(2) + chip_id(2) = 18 bytes
    mac_bytes = _parse_mac_address(getattr(packet, "src_mac", "00:00:00:00:00:00"))
    core_spatial = ((getattr(packet, "core", 0) & 0xFF) << 8) | (getattr(packet, "spatial_stream", 0) & 0xFF)

    csi_hdr = struct.pack(
        "<I6sHHHH",
        getattr(packet, "magic", 0x11111111),
        mac_bytes,
        getattr(packet, "seq", 0) & 0xFFFF,
        core_spatial & 0xFFFF,
        chanspec & 0xFFFF,
        getattr(packet, "chip_id", 0) & 0xFFFF,
    )

    # Pack raw IQ samples (int16 pairs)
    raw_iq = getattr(packet, "raw_iq", [])
    if raw_iq:
        iq_parts = []
        for i_val, q_val in raw_iq:
            iq_parts.append(struct.pack("<hh", int(i_val), int(q_val)))
        iq_bytes = b"".join(iq_parts)
    else:
        iq_bytes = b""

    payload = csi_hdr + iq_bytes
    dot11_frame = build_ieee80211_qos_data_frame(
        src_mac=getattr(packet, "src_mac", "00:00:00:00:00:00"),
        dst_mac=dst_mac,
        seq=getattr(packet, "seq", 0),
        payload=payload,
    )

    return radiotap + dot11_frame


class CSIPcapNGWriter:
    """High-performance PCAP-NG writer for Nexmon CSI frames.

    Emits Section Header Block (SHB), Interface Description Block (IDB) configured for
    DLT_IEEE802_11_RADIO, and Enhanced Packet Blocks (EPB) for each CSI frame.
    """

    def __init__(
        self,
        target: Union[str, Path, BinaryIO],
        if_name: str = "mon0",
        snaplen: int = 65535,
    ):
        if isinstance(target, (str, Path)):
            self._file: BinaryIO = open(target, "wb")
            self._owns_file = True
        else:
            self._file = target
            self._owns_file = False

        self.if_name = if_name
        self.snaplen = snaplen
        self._packet_count = 0

        self._write_section_header()
        self._write_interface_description()

    def _write_section_header(self):
        """Write Section Header Block (SHB) with 32-bit boundary alignment."""
        block_type = PCAPNG_SHB_MAGIC
        byte_order_magic = PCAPNG_BYTE_ORDER_MAGIC
        major_version = 1
        minor_version = 0
        section_length = 0xFFFFFFFFFFFFFFFF  # Unspecified length

        block_len = 28  # 4 + 4 + 4 + 2 + 2 + 8 + 4
        shb = struct.pack(
            "<IIIHHQI",
            block_type,
            block_len,
            byte_order_magic,
            major_version,
            minor_version,
            section_length,
            block_len,
        )
        self._file.write(shb)

    def _write_interface_description(self):
        """Write Interface Description Block (IDB) for 802.11 Radiotap."""
        block_type = PCAPNG_IDB_MAGIC
        link_type = LINKTYPE_IEEE802_11_RADIOTAP
        reserved = 0
        snaplen = self.snaplen

        # Option: if_name (code 2)
        name_bytes = self.if_name.encode("utf-8")
        name_len = len(name_bytes)
        name_pad = (4 - (name_len % 4)) % 4
        opt_if_name = struct.pack("<HH", 2, name_len) + name_bytes + (b"\x00" * name_pad)

        # Option: if_tsresol (code 9, value 6 for microsecond resolution)
        opt_tsresol = struct.pack("<HH B B B B", 9, 1, 6, 0, 0, 0)

        # Option: end of options (code 0)
        opt_end = struct.pack("<HH", 0, 0)

        options = opt_if_name + opt_tsresol + opt_end
        block_len = 20 + len(options)

        idb_header = struct.pack("<IIHHI", block_type, block_len, link_type, reserved, snaplen)
        idb_tail = struct.pack("<I", block_len)
        self._file.write(idb_header + options + idb_tail)

    def write_packet(self, packet: Any, dst_mac: str = "ff:ff:ff:ff:ff:ff"):
        """Write a CSIPacket as an Enhanced Packet Block (EPB)."""
        frame_bytes = csi_packet_to_radiotap_frame(packet, dst_mac=dst_mac)
        cap_len = len(frame_bytes)
        orig_len = cap_len

        # Timestamp in microseconds
        if getattr(packet, "tsft_us", None) is not None:
            ts_us = int(packet.tsft_us)
        elif getattr(packet, "timestamp", None) is not None:
            ts_us = int(packet.timestamp * 1_000_000)
        else:
            ts_us = int(time.time() * 1_000_000)

        ts_high = (ts_us >> 32) & 0xFFFFFFFF
        ts_low = ts_us & 0xFFFFFFFF

        pad_len = (4 - (cap_len % 4)) % 4
        padded_frame = frame_bytes + (b"\x00" * pad_len)

        block_type = PCAPNG_EPB_MAGIC
        block_len = 32 + len(padded_frame)

        epb_hdr = struct.pack(
            "<IIIIIII",
            block_type,
            block_len,
            0,  # Interface ID 0
            ts_high,
            ts_low,
            cap_len,
            orig_len,
        )
        epb_tail = struct.pack("<I", block_len)

        self._file.write(epb_hdr + padded_frame + epb_tail)
        self._packet_count += 1

    def write_packets(self, packets: Iterable[Any], dst_mac: str = "ff:ff:ff:ff:ff:ff") -> int:
        """Write multiple CSIPackets to the PCAP-NG file. Returns count written."""
        count = 0
        for p in packets:
            self.write_packet(p, dst_mac=dst_mac)
            count += 1
        return count

    def flush(self):
        """Flush buffered bytes to disk."""
        self._file.flush()

    def close(self):
        """Close underlying file."""
        if self._owns_file and not self._file.closed:
            self._file.flush()
            self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def packet_count(self) -> int:
        return self._packet_count


class CSIPcapWriter:
    """Classic PCAP writer (LinkType 105) for backward compatibility."""

    def __init__(
        self,
        target: Union[str, Path, BinaryIO],
        snaplen: int = 65535,
    ):
        if isinstance(target, (str, Path)):
            self._file: BinaryIO = open(target, "wb")
            self._owns_file = True
        else:
            self._file = target
            self._owns_file = False

        self.snaplen = snaplen
        self._packet_count = 0

        # Write 24-byte classic PCAP header
        # magic(4), v_major(2), v_minor(2), thiszone(4), sigfigs(4), snaplen(4), network(4)
        pcap_hdr = struct.pack(
            "<IHHiIII",
            PCAP_MAGIC_USEC,
            2,
            4,
            0,
            0,
            self.snaplen,
            LINKTYPE_IEEE802_11_RADIOTAP,
        )
        self._file.write(pcap_hdr)

    def write_packet(self, packet: Any, dst_mac: str = "ff:ff:ff:ff:ff:ff"):
        """Write a single CSIPacket to classic PCAP."""
        frame_bytes = csi_packet_to_radiotap_frame(packet, dst_mac=dst_mac)
        cap_len = len(frame_bytes)

        if getattr(packet, "tsft_us", None) is not None:
            ts_us = int(packet.tsft_us)
            sec = ts_us // 1_000_000
            usec = ts_us % 1_000_000
        elif getattr(packet, "timestamp", None) is not None:
            t = float(packet.timestamp)
            sec = int(t)
            usec = int((t - sec) * 1_000_000)
        else:
            t = time.time()
            sec = int(t)
            usec = int((t - sec) * 1_000_000)

        # 16-byte record header: sec(4), usec(4), cap_len(4), orig_len(4)
        rec_hdr = struct.pack("<IIII", sec, usec, cap_len, cap_len)
        self._file.write(rec_hdr + frame_bytes)
        self._packet_count += 1

    def write_packets(self, packets: Iterable[Any], dst_mac: str = "ff:ff:ff:ff:ff:ff") -> int:
        count = 0
        for p in packets:
            self.write_packet(p, dst_mac=dst_mac)
            count += 1
        return count

    def flush(self):
        self._file.flush()

    def close(self):
        if self._owns_file and not self._file.closed:
            self._file.flush()
            self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def packet_count(self) -> int:
        return self._packet_count


def export_csi_to_pcapng(packets: Iterable[Any], output_path: Union[str, Path], if_name: str = "mon0") -> int:
    """Export a collection of CSIPacket objects to a PCAP-NG file.

    Args:
        packets: Iterable of CSIPacket objects.
        output_path: Path to destination .pcapng file.
        if_name: Network interface name recorded in the capture.

    Returns:
        Number of frames successfully written.
    """
    with CSIPcapNGWriter(output_path, if_name=if_name) as writer:
        return writer.write_packets(packets)


def export_csi_to_pcap(packets: Iterable[Any], output_path: Union[str, Path]) -> int:
    """Export a collection of CSIPacket objects to a classic PCAP file.

    Args:
        packets: Iterable of CSIPacket objects.
        output_path: Path to destination .pcap file.

    Returns:
        Number of frames successfully written.
    """
    with CSIPcapWriter(output_path) as writer:
        return writer.write_packets(packets)
