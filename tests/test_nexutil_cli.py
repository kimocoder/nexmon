#!/usr/bin/env python3
"""Unit tests for nexutil platform detection and auto-buffer sizing."""

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEXUTIL_BIN = ROOT / "utilities" / "nexutil" / "nexutil"


class TestNexutilCli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.has_nexutil = NEXUTIL_BIN.is_file() and os.access(NEXUTIL_BIN, os.X_OK)

    def setUp(self):
        if not self.has_nexutil:
            self.skipTest("nexutil binary not built or not executable")

    def test_nexutil_platform_detection(self):
        """Verify that nexutil -V detects the real hardware model on Linux."""
        res = subprocess.run(
            [str(NEXUTIL_BIN), "-V"],
            capture_output=True,
            text=True
        )
        if res.returncode == 0:
            self.assertNotIn("platform             | firmware                         | vendorid | deviceid | radiorev   | chipnum | chiprev | chippackage | corerev | boardid | boardvendor | boardrev | driverrev | ucoderev  | bus | phytype | phyrev | anarev | nvramrev\n-------------------- | -------------------------------- | -------- | -------- | ---------- | ------- | ------- | ----------- | ------- | ------- | ----------- | -------- | --------- | --------- | --- | ------- | ------ | ------ | --------\nunknown", res.stdout)
            self.assertIn("Raspberry Pi", res.stdout)

    def test_nexutil_auto_buffer_sizing(self):
        """Verify that custom queries default to 256 bytes when -l is not given."""
        res_default = subprocess.run(
            [str(NEXUTIL_BIN), "-g", "400"],
            capture_output=True,
            text=True
        )
        if res_default.returncode == 0:
            lines = res_default.stdout.strip().splitlines()
            # 256 bytes dumped at 16 bytes per line = 16 lines
            self.assertGreaterEqual(len(lines), 16)

        res_explicit = subprocess.run(
            [str(NEXUTIL_BIN), "-g", "400", "-l", "4"],
            capture_output=True,
            text=True
        )
        if res_explicit.returncode == 0:
            lines = res_explicit.stdout.strip().splitlines()
            # 4 bytes dumped = 1 line
            self.assertEqual(len(lines), 1)

    def test_nexutil_hop_help_options(self):
        """Verify that nexutil --help documents the in-daemon channel hopper options."""
        res = subprocess.run([str(NEXUTIL_BIN), "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("--hop", res.stdout)
        self.assertIn("--interval", res.stdout)
        self.assertIn("--hop-count", res.stdout)
        self.assertIn("--quiet", res.stdout)

    def test_nexutil_hop_invalid_channels(self):
        """Verify that invalid channels are rejected cleanly."""
        res = subprocess.run([str(NEXUTIL_BIN), "--hop", "invalid_ch"], capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("ERR: invalid hop channels 'invalid_ch'", res.stderr)

    def test_nexutil_hop_invalid_interval(self):
        """Verify that invalid interval (<= 0) is rejected cleanly."""
        res = subprocess.run([str(NEXUTIL_BIN), "--hop", "1,6,11", "--interval", "0"], capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("ERR: invalid interval '0'", res.stderr)

    def test_nexutil_hop_conflict_with_chanspec(self):
        """Verify that specifying both -k and -H is rejected."""
        res = subprocess.run([str(NEXUTIL_BIN), "--chanspec=1", "--hop=1,6,11"], capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("ERR: cannot combine --chanspec (-k) with --hop (-H)", res.stderr)

    def test_optional_argument_before_option(self):
        """-M 0 -l 32 must not be rejected as an extra positional argument."""
        res = subprocess.run(
            [str(NEXUTIL_BIN), "-I", "wlan0", "-M", "0", "-l", "32"],
            capture_output=True, text=True)
        self.assertNotIn("Too many arguments", res.stderr)

    def test_write_shm_without_value_rejected(self):
        res = subprocess.run(
            [str(NEXUTIL_BIN), "-I", "wlan0", "-W"],
            capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("offset given without a value", res.stderr)

    def test_write_template_without_value_rejected(self):
        res = subprocess.run(
            [str(NEXUTIL_BIN), "-I", "wlan0", "-Y"],
            capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("offset given without a value", res.stderr)

    def test_zero_buffer_length_rejected(self):
        res = subprocess.run(
            [str(NEXUTIL_BIN), "-I", "wlan0", "-g", "400", "-l", "0"],
            capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("invalid -l length '0'", res.stderr)

    def test_raw_and_base64_output_conflict(self):
        res = subprocess.run(
            [str(NEXUTIL_BIN), "-I", "wlan0", "-g", "400", "-R", "-r"],
            capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("base64 (-R) or raw (-r)", res.stderr)


if __name__ == "__main__":
    unittest.main()
