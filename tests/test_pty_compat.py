#!/usr/bin/env python3
"""Host tests for socat's openpty() implementation used on Android."""

import ctypes
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPENPTY = ROOT / "utilities/socat/openpty.c"


class OpenptyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not sys.platform.startswith("linux"):
            raise unittest.SkipTest("openpty() implementation is Linux-specific")
        if shutil.which("gcc") is None:
            raise unittest.SkipTest("gcc not available")

        cls.tmp = tempfile.TemporaryDirectory(prefix="nexmon-openpty-")
        so_path = Path(cls.tmp.name) / "libopenpty_test.so"
        subprocess.run(
            [
                "gcc", "-shared", "-fPIC", "-std=gnu11", "-O2",
                "-D_GNU_SOURCE",
                str(OPENPTY), "-o", str(so_path),
            ],
            check=True,
            timeout=30,
        )
        cls.lib = ctypes.CDLL(str(so_path))
        cls.lib.openpty.argtypes = [
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        cls.lib.openpty.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _openpty(self, ws=None):
        master = ctypes.c_int(-1)
        slave = ctypes.c_int(-1)
        name = ctypes.create_string_buffer(128)
        rc = self.lib.openpty(
            ctypes.byref(master),
            ctypes.byref(slave),
            name,
            None,
            ctypes.byref(ws) if ws is not None else None,
        )
        return rc, master.value, slave.value, name.value

    def test_openpty_returns_usable_pair(self):
        rc, master, slave, name = self._openpty()
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(master, 0)
        self.assertGreaterEqual(slave, 0)
        self.assertTrue(name.startswith(b"/dev/pts/"), name)
        try:
            os.write(master, b"hello\n")
            self.assertIn(b"hello", os.read(slave, 6))
        finally:
            os.close(master)
            os.close(slave)

    def test_openpty_applies_window_size(self):
        ws = struct.pack("HHHH", 40, 132, 0, 0)
        ws_buf = ctypes.create_string_buffer(ws, len(ws))
        rc, master, slave, _name = self._openpty(ws_buf)
        self.assertEqual(rc, 0)
        try:
            readback = ctypes.create_string_buffer(len(ws))
            import fcntl
            import termios
            fcntl.ioctl(slave, termios.TIOCGWINSZ, readback, True)
            self.assertEqual(readback.raw, ws)
        finally:
            os.close(master)
            os.close(slave)


if __name__ == "__main__":
    unittest.main()