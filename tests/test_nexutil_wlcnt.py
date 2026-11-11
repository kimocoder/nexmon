#!/usr/bin/env python3
"""Unit tests for nexutil's wl_cnt reader and decoder.

The ioctl is injected, so the NEX_GET_WL_CNT failure/fallback path and the
append-only v9/v10 layout handling are exercised without a device.
"""

import ctypes
import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WLCNT_SRC = ROOT / "utilities/nexutil/nexutil_wlcnt.c"
IOCTL_HEADER = ROOT / "patches/include/nexioctls.h"

IOCTL_FN = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
    ctypes.c_int, ctypes.c_bool,
)


def _ioctl_number(name):
    text = IOCTL_HEADER.read_text(errors="replace")
    match = re.search(rf"#define\s+{name}\s+(\d+)", text)
    if not match:
        raise RuntimeError(f"{name} not found in nexioctls.h")
    return int(match.group(1))


class TestNexutilWlCnt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("gcc"):
            raise unittest.SkipTest("gcc not found")

        cls.tmp = tempfile.TemporaryDirectory(prefix="nexmon-wlcnt-")
        tmp = Path(cls.tmp.name)
        cls.so_path = tmp / "libnexutil_wlcnt.so"
        subprocess.run(
            [
                "gcc", "-shared", "-fPIC", "-std=gnu11", "-O2",
                str(WLCNT_SRC),
                f"-I{ROOT / 'utilities/nexutil'}",
                f"-I{ROOT / 'utilities/nexutil/include'}",
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

        cls.read = cls.lib.nexutil_read_wl_counters
        cls.read.argtypes = [IOCTL_FN, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
        cls.read.restype = ctypes.c_int

        cls.print_cnt = cls.lib.nexutil_print_wl_counters
        cls.print_cnt.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
        cls.print_cnt.restype = ctypes.c_int

        cls.nex_get_wl_cnt = _ioctl_number("NEX_GET_WL_CNT")
        cls.wlc_get_var = 262

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _capture(self, payload):
        buf = ctypes.create_string_buffer(2048)
        calls = []

        def stub(_nexio, cmd, data, length, _set):
            calls.append((cmd, length))
            if cmd == self.wlc_get_var:
                self.assertEqual(ctypes.string_at(data, 9), b"counters\x00")
                ctypes.memmove(data, payload, min(len(payload), length))
                return 0
            return -1

        cb = IOCTL_FN(stub)
        ret = self.read(cb, None, buf, len(buf))
        return ret, calls, buf

    def _print(self, buf):
        out = Path(self.tmp.name) / f"{self.id()}-out.txt"
        err = Path(self.tmp.name) / f"{self.id()}-err.txt"
        fout = self.libc.fopen(str(out).encode(), b"w")
        ferr = self.libc.fopen(str(err).encode(), b"w")
        self.assertIsNotNone(fout)
        self.assertIsNotNone(ferr)
        try:
            ret = self.print_cnt(buf, len(buf), fout, ferr)
            self.libc.fflush(fout)
            self.libc.fflush(ferr)
        finally:
            self.libc.fclose(fout)
            self.libc.fclose(ferr)
        return ret, out.read_text(), err.read_text()

    @staticmethod
    def _v10_payload():
        words = [0] * (848 // 4)
        # version and length share the first 32-bit word
        words[0] = 10 | (848 << 16)
        words[1] = 1234          # txframe
        words[5] = 45            # txctl
        words[-1] = 0xDEADBEEF   # v10 tail field
        return struct.pack("<212I", *words)

    def test_uses_counters_iovar_first(self):
        ret, calls, buf = self._capture(self._v10_payload())
        self.assertEqual(ret, 0)
        self.assertEqual([c[0] for c in calls], [self.wlc_get_var])

        ret, out, err = self._print(buf)
        self.assertEqual(ret, 0)
        self.assertIn("version: 10", out)
        self.assertIn("length: 848", out)
        self.assertIn("txframe: 1234", out)
        self.assertIn("txctl: 45", out)
        self.assertIn("field_211: 3735928559", out)
        self.assertIn("decodes the first 812 bytes", out)
        self.assertEqual(err, "")

    def test_falls_back_to_custom_ioctl(self):
        payload = self._v10_payload()
        calls = []

        def stub(_nexio, cmd, data, length, _set):
            calls.append(cmd)
            if cmd == self.nex_get_wl_cnt:
                ctypes.memmove(data, payload, min(len(payload), length))
                return 0
            return -1

        cb = IOCTL_FN(stub)
        buf = ctypes.create_string_buffer(2048)
        self.assertEqual(self.read(cb, None, buf, len(buf)), 0)
        self.assertEqual(calls, [self.wlc_get_var, self.nex_get_wl_cnt])

        ret, out, _ = self._print(buf)
        self.assertEqual(ret, 0)
        self.assertIn("txframe: 1234", out)

    def test_rejects_invalid_length(self):
        payload = bytearray(2048)
        struct.pack_into("<HH", payload, 0, 10, 4096)
        buf = ctypes.create_string_buffer(bytes(payload), 2048)

        ret, out, err = self._print(buf)
        self.assertEqual(ret, -1)
        self.assertIn("invalid wl counter length 4096", err)

    def test_reports_both_paths_failing(self):
        def stub(_nexio, cmd, data, length, _set):
            return -1

        cb = IOCTL_FN(stub)
        buf = ctypes.create_string_buffer(2048)
        self.assertEqual(self.read(cb, None, buf, len(buf)), -1)


if __name__ == "__main__":
    unittest.main()