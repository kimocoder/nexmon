#!/usr/bin/env python3
"""Regression tests for Phase 4 Tooling & Build Scripts Hardening."""

from collections import deque
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestPhase4FirmwareZstdSupport(unittest.TestCase):
    """Verify nexfirmware methods support .zst compressed firmware."""

    def setUp(self):
        try:
            import zstandard
            self.zstd = zstandard
        except ImportError:
            self.zstd = None

    def test_read_firmware_blob_zst(self):
        import nexfirmware
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = Path(tmp) / "fw.bin"
            raw_bytes = b"BCM43455c0\x00" * 200
            raw_path.write_bytes(raw_bytes)

            data_raw = nexfirmware.read_firmware_blob(raw_path)
            self.assertEqual(data_raw, raw_bytes)

            if self.zstd is not None:
                zst_path = Path(tmp) / "fw.bin.zst"
                cctx = self.zstd.ZstdCompressor()
                zst_path.write_bytes(cctx.compress(raw_bytes))

                data_zst = nexfirmware.read_firmware_blob(zst_path)
                self.assertEqual(data_zst, raw_bytes)


class TestPhase4ToolchainScripts(unittest.TestCase):
    """Verify getdefine.sh and getsectionaddr.sh handle hyphenated CC prefix."""

    def test_getdefine_with_hyphenated_cc(self):
        script = ROOT / "buildtools/scripts/getdefine.sh"
        self.assertTrue(script.exists())
        # Run with CC="arm-none-eabi-"
        env = dict(os.environ, CC="arm-none-eabi-", NEXMON_ROOT=str(ROOT))
        res = subprocess.run(
            ["bash", str(script), "CHIP_VER_BCM4339"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "1")

    def test_getdefine_with_standard_cc(self):
        script = ROOT / "buildtools/scripts/getdefine.sh"
        env = dict(os.environ, CC="gcc", NEXMON_ROOT=str(ROOT))
        res = subprocess.run(
            ["bash", str(script), "CHIP_VER_BCM4339"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "1")

    def test_getsectionaddr_script_syntax(self):
        script = ROOT / "buildtools/scripts/getsectionaddr.sh"
        self.assertTrue(script.exists())
        res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)


class TestPhase4B43AssemblerBitfields(unittest.TestCase):
    """Verify b43 assemblers validate jump target ranges and mask operands."""

    def test_b43_unified_source_has_bounds_check(self):
        main_c = (ROOT / "buildtools/b43-unified/assembler/main.c").read_text()
        self.assertIn("exceeds maximum bitfield range", main_c)
        self.assertIn("c->operands[2].u.operand & 0xFFFULL", main_c)
        self.assertIn("c->operands[2].u.operand & 0x1FFFULL", main_c)
        self.assertIn("c->operands[2].u.operand & 0x3FFFULL", main_c)
        self.assertIn("c->operands[2].u.operand & 0x7FFFULL", main_c)

    def test_b43_legacy_assemblers_have_bounds_check(self):
        for path in [
            ROOT / "buildtools/b43/assembler/main.c",
            ROOT / "buildtools/b43-v2/assembler/main.c",
            ROOT / "buildtools/b43-v3/assembler/main.c",
        ]:
            text = path.read_text()
            self.assertIn("exceeds maximum bitfield range", text, f"{path} missing bounds check")
            self.assertIn("& 0xFFFULL", text, f"{path} missing 0xFFF mask")
            self.assertIn("& 0x1FFFULL", text, f"{path} missing 0x1FFF mask")


class TestPhase4PythonNetlinkAndNexmon(unittest.TestCase):
    """Verify pynexmon Netlink CSI packet buffering and NexmonDevice cleanup."""

    def test_netlink_csi_pending_packets_queue(self):
        from python.pynexmon.csi import NetlinkCSIReceiver, CSIPacket
        rcv = NetlinkCSIReceiver()
        self.assertIsInstance(rcv._pending_packets, deque)
        self.assertEqual(len(rcv._pending_packets), 0)

        # Enqueue mock packets
        pkt1 = CSIPacket(
            magic=0x1111,
            src_mac="00:11:22:33:44:55",
            seq=1,
            core=0,
            spatial_stream=0,
            chanspec=0x1000,
            chip_id=0x4345,
            raw_iq=[(1, 1), (2, 2)],
        )
        pkt2 = CSIPacket(
            magic=0x2222,
            src_mac="00:11:22:33:44:56",
            seq=2,
            core=0,
            spatial_stream=0,
            chanspec=0x1000,
            chip_id=0x4345,
            raw_iq=[(3, 3), (4, 4)],
        )
        rcv._pending_packets.extend([pkt1, pkt2])

        # recv() should pop first pending packet without calling socket
        self.assertEqual(rcv.recv(), pkt1)
        self.assertEqual(rcv.recv(), pkt2)
        self.assertEqual(len(rcv._pending_packets), 0)

    def test_nexmon_device_del_calls_close(self):
        from python.pynexmon.nexmon import NexmonDevice
        from unittest.mock import MagicMock

        dev = NexmonDevice.__new__(NexmonDevice)
        mock_lib = MagicMock()
        dev._bindings = MagicMock()
        dev._bindings.lib = mock_lib
        dev._handle = 0x12345678

        # Calling __del__ directly should free the handle
        dev.__del__()
        mock_lib.nex_free.assert_called_once_with(0x12345678)
        self.assertIsNone(dev._handle)


class TestPhase4ToolingScripts(unittest.TestCase):
    """Verify check_drivers.py and sync_constants.py fixes."""

    def test_check_drivers_detects_unclosed_string(self):
        from buildtools.scripts.check_drivers import validate_driver_file
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write('int main() { char *s = "unterminated;\n')
            f_path = Path(f.name)
        try:
            errors = validate_driver_file(f_path)
            self.assertTrue(any("Unterminated string literal" in err for err in errors))
        finally:
            f_path.unlink(missing_ok=True)

    def test_sync_constants_lambda_sub(self):
        from buildtools.scripts.sync_constants import replace_or_insert_block
        text = "BEGIN\nold content with \\1 backref\nEND"
        new_content = "new content with \\g<1> and \\2 special characters"
        result = replace_or_insert_block(text, "BEGIN", "END", f"BEGIN\n{new_content}\nEND")
        self.assertIn("new content with \\g<1> and \\2 special characters", result)


class TestPhase4MonitorModeScript(unittest.TestCase):
    """Verify monitor-mode.sh syntax and flag reading."""

    def test_monitor_mode_bash_syntax(self):
        script = ROOT / "monitor-mode.sh"
        res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)

    def test_monitor_mode_flags_parsing(self):
        script_text = (ROOT / "monitor-mode.sh").read_text()
        self.assertIn('flags=$(cat "/sys/class/net/$STA/flags" 2>/dev/null || echo 0)', script_text)
        self.assertIn('$(( ${flags:-0} & 1 ))', script_text)


class TestPhase4P2PortabilityAndTelemetry(unittest.TestCase):
    """Verify P2 improvements: udptunnel ethertype, statistics opt-out, and setup_env."""

    def test_udptunnel_ethertype_htons(self):
        udptunnel_c = ROOT / "patches/common/udptunnel.c"
        text = udptunnel_c.read_text(errors="replace")
        self.assertIn(".type = HTONS(0x0800)", text)
        self.assertNotIn(".type = 0x0008", text)

    def test_statistics_env_opt_out(self):
        stats_mk = ROOT / "patches/common/statistics.mk"
        text = stats_mk.read_text(errors="replace")
        self.assertIn("NEXMON_DISABLE_STATISTICS", text)
        self.assertIn("DO_NOT_TRACK", text)

    def test_setup_env_zsh_and_cleanup(self):
        setup_env = ROOT / "setup_env.sh"
        text = setup_env.read_text(errors="replace")
        self.assertIn("ZSH_VERSION", text)
        self.assertIn("unset OLD_PWD", text)

    def test_ucodeext_endian_independent_write(self):
        ucodeext_c = ROOT / "buildtools/ucode_extractor/ucodeext.c"
        text = ucodeext_c.read_text(errors="replace")
        self.assertIn("unsigned char out[8];", text)
        self.assertNotIn("fwrite(&a, sizeof(uint32_t)", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
