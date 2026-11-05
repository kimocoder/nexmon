#!/usr/bin/env python3
"""Unit tests for nexutil's capability reporting, including the failure path.

The ioctl is injected, so the "firmware has no NEX_GET_CAPABILITIES" branch is
exercised without a device.
"""
import ctypes
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPS_SRC = ROOT / "utilities/nexutil/nexutil_capabilities.c"
CAPS_HEADER = ROOT / "patches/include/nexioctls.h"

IOCTL_FN = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
    ctypes.c_int, ctypes.c_bool,
)


def _nex_get_capabilities():
    text = CAPS_HEADER.read_text(errors="replace")
    match = re.search(r"#define\s+NEX_GET_CAPABILITIES\s+(\d+)", text)
    if not match:
        raise RuntimeError("NEX_GET_CAPABILITIES not found in nexioctls.h")
    return int(match.group(1))


class TestNexutilCapabilities(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("gcc"):
            raise unittest.SkipTest("gcc not found")

        cls.tmp = tempfile.TemporaryDirectory(prefix="nexmon-caps-")
        tmp = Path(cls.tmp.name)
        cls.so_path = tmp / "libnexutil_caps.so"
        subprocess.run(
            [
                "gcc", "-shared", "-fPIC", "-std=gnu11", "-O2",
                str(CAPS_SRC),
                f"-I{ROOT / 'utilities/nexutil'}",
                f"-I{ROOT / 'patches/include'}",
                "-o", str(cls.so_path),
            ],
            check=True,
            timeout=30,
        )

        cls.lib = ctypes.CDLL(str(cls.so_path))
        cls.libc = ctypes.CDLL(None)
        cls.libc.fopen.restype = ctypes.c_void_p
        cls.libc.fopen.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        cls.libc.fclose.argtypes = [ctypes.c_void_p]
        cls.libc.fflush.argtypes = [ctypes.c_void_p]

        cls.report = cls.lib.nexutil_report_capabilities
        cls.report.argtypes = [IOCTL_FN, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        cls.report.restype = ctypes.c_int

        cls.cmd = _nex_get_capabilities()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _run(self, stub):
        tmp = Path(self.tmp.name)
        out_path = tmp / f"{self.id()}-out.txt"
        err_path = tmp / f"{self.id()}-err.txt"
        for p in (out_path, err_path):
            p.write_text("")

        fout = self.libc.fopen(str(out_path).encode(), b"w")
        ferr = self.libc.fopen(str(err_path).encode(), b"w")
        self.assertIsNotNone(fout)
        self.assertIsNotNone(ferr)
        try:
            rc = self.report(stub, None, fout, ferr)
            self.libc.fflush(fout)
            self.libc.fflush(ferr)
        finally:
            self.libc.fclose(fout)
            self.libc.fclose(ferr)

        return rc, out_path.read_text(), err_path.read_text()

    def test_failure_path_when_firmware_lacks_capabilities(self):
        """nexutil -G must exit non-zero and name the failure on old firmware."""
        calls = []

        @IOCTL_FN
        def stub(nexio, cmd, buf, length, is_set):
            calls.append((cmd, length, is_set))
            return -1

        rc, out, err = self._run(stub)

        self.assertEqual(rc, -1)
        self.assertEqual(out, "")
        self.assertIn("ERR: could not get capabilities", err)
        self.assertEqual(calls, [(self.cmd, 4, False)])

    def test_success_path_prints_all_bits(self):
        @IOCTL_FN
        def stub(nexio, cmd, buf, length, is_set):
            ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint32))[0] = 0x7
            return 0

        rc, out, _err = self._run(stub)

        self.assertEqual(rc, 0)
        self.assertIn("capabilities: 0x7", out)
        self.assertIn("monitor mode:    yes", out)
        self.assertIn("radiotap:        yes", out)
        self.assertIn("frame injection: yes", out)
        self.assertNotIn("unknown bits", out)

    def test_unknown_bits_are_reported(self):
        @IOCTL_FN
        def stub(nexio, cmd, buf, length, is_set):
            ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint32))[0] = 0x9
            return 0

        rc, out, _err = self._run(stub)

        self.assertEqual(rc, 0)
        self.assertIn("capabilities: 0x9", out)
        self.assertIn("radiotap:        no", out)
        self.assertIn("unknown bits:    0x8", out)

    def test_null_arguments_are_rejected(self):
        @IOCTL_FN
        def stub(nexio, cmd, buf, length, is_set):
            return 0

        self.assertEqual(self.report(stub, None, None, None), -1)


if __name__ == "__main__":
    unittest.main()