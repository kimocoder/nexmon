#!/usr/bin/env python3
"""Unit tests ensuring IOCTL and capability constants remain single-sourced."""

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import pynexmon  # noqa: E402
from pynexmon import nexmon  # noqa: E402

NEXIOCTLS_H = ROOT / "patches/include/nexioctls.h"
CAPABILITIES_H = ROOT / "patches/include/capabilities.h"
PYNEXMON_PY = ROOT / "python/pynexmon/nexmon.py"
NEXUTIL_JAVA = ROOT / "app/app/src/main/java/de/tu_darmstadt/seemoo/nexmon/utils/Nexutil.java"
SYNC_SCRIPT = ROOT / "buildtools/scripts/sync_constants.py"


def _parse_c_defines(path: Path) -> dict[str, int]:
    defs: dict[str, int] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^\s*#define\s+([A-Za-z0-9_]+)\s+(.+?)(?:/\*.*|//.*)?$", line)
            if not m:
                continue
            name, raw_expr = m.group(1), m.group(2).strip()
            clean_expr = re.sub(r"/\*.*?\*/", "", raw_expr).strip()
            clean_expr = re.sub(r"//.*$", "", clean_expr).strip()
            try:
                val = eval(clean_expr, {"__builtins__": None}, {})  # noqa: S307
                if isinstance(val, int):
                    defs[name] = val
            except (ValueError, SyntaxError, TypeError, NameError):
                pass
    return defs


def _parse_java_constants(path: Path) -> dict[str, int]:
    defs: dict[str, int] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^\s*public\s+final\s+static\s+int\s+([A-Za-z0-9_]+)\s*=\s*(.+?);", line)
            if not m:
                continue
            name, raw_expr = m.group(1), m.group(2).strip()
            try:
                val = eval(raw_expr, {"__builtins__": None}, {})  # noqa: S307
                if isinstance(val, int):
                    defs[name] = val
            except (ValueError, SyntaxError, TypeError, NameError):
                pass
    return defs


class TestIoctlCapabilitiesConstants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c_ioctls = _parse_c_defines(NEXIOCTLS_H)
        cls.c_caps = _parse_c_defines(CAPABILITIES_H)
        cls.java_defs = _parse_java_constants(NEXUTIL_JAVA)

    def test_nex_ioctls_match_between_c_and_python(self):
        """Every NEX_* define in nexioctls.h must match python/pynexmon/nexmon.py."""
        nex_in_c = {k: v for k, v in self.c_ioctls.items() if k.startswith("NEX_")}
        self.assertGreaterEqual(len(nex_in_c), 32)
        for name, expected_val in nex_in_c.items():
            self.assertTrue(
                hasattr(nexmon, name),
                f"nexmon.py is missing IOCTL constant {name} (expected {expected_val})",
            )
            actual_val = getattr(nexmon, name)
            self.assertEqual(
                actual_val,
                expected_val,
                f"nexmon.{name}={actual_val} does not match nexioctls.h ({expected_val})",
            )
            self.assertTrue(
                hasattr(pynexmon, name),
                f"pynexmon.__init__ failed to re-export {name}",
            )

    def test_capabilities_match_between_c_and_python(self):
        """Every NEX_CAP_* define in capabilities.h must match python/pynexmon."""
        cap_in_c = {k: v for k, v in self.c_caps.items() if k.startswith("NEX_CAP_")}
        self.assertEqual(len(cap_in_c), 3)
        for name, expected_val in cap_in_c.items():
            self.assertTrue(
                hasattr(nexmon, name),
                f"nexmon.py is missing capability constant {name}",
            )
            self.assertEqual(getattr(nexmon, name), expected_val)
            self.assertTrue(
                hasattr(pynexmon, name),
                f"pynexmon.__init__ failed to re-export {name}",
            )
            self.assertEqual(getattr(pynexmon, name), expected_val)

    def test_nex_ioctls_match_between_c_and_java(self):
        """Every NEX_* define in nexioctls.h must match Nexutil.java."""
        nex_in_c = {k: v for k, v in self.c_ioctls.items() if k.startswith("NEX_")}
        for name, expected_val in nex_in_c.items():
            self.assertIn(
                name,
                self.java_defs,
                f"Nexutil.java is missing IOCTL constant {name}",
            )
            self.assertEqual(
                self.java_defs[name],
                expected_val,
                f"Nexutil.{name}={self.java_defs[name]} does not match nexioctls.h ({expected_val})",
            )

    def test_capabilities_match_between_c_and_java(self):
        """Every NEX_CAP_* define in capabilities.h must match Nexutil.java."""
        cap_in_c = {k: v for k, v in self.c_caps.items() if k.startswith("NEX_CAP_")}
        for name, expected_val in cap_in_c.items():
            self.assertIn(
                name,
                self.java_defs,
                f"Nexutil.java is missing capability constant {name}",
            )
            self.assertEqual(
                self.java_defs[name],
                expected_val,
                f"Nexutil.{name}={self.java_defs[name]} does not match capabilities.h ({expected_val})",
            )

    def test_wlc_ioctls_match_c_headers(self):
        """WLC_* IOCTLs in Python and Java must match nexioctls.h."""
        wlc_in_c = {k: v for k, v in self.c_ioctls.items() if k.startswith("WLC_")}
        # Check Python
        for attr in dir(nexmon):
            if attr.startswith("WLC_"):
                self.assertIn(attr, wlc_in_c, f"Unknown WLC constant in nexmon.py: {attr}")
                self.assertEqual(getattr(nexmon, attr), wlc_in_c[attr])

        # Check Java
        for name, val in self.java_defs.items():
            if name.startswith("WLC_"):
                self.assertIn(name, wlc_in_c, f"Unknown WLC constant in Nexutil.java: {name}")
                self.assertEqual(val, wlc_in_c[name])

    def test_critical_ioctl_values_no_regression(self):
        """Guard against the specific divergent constants found in the audit."""
        # 408 is NEX_INJECT_FRAME, NOT 401 (401 is NEX_WRITE_TO_CONSOLE)
        self.assertEqual(pynexmon.NEX_INJECT_FRAME, 408)
        self.assertEqual(pynexmon.NEX_WRITE_TO_CONSOLE, 401)
        self.assertEqual(self.java_defs["NEX_INJECT_FRAME"], 408)
        self.assertEqual(self.java_defs["NEX_WRITE_TO_CONSOLE"], 401)

        # 410/411 are SECURITYCOOKIE, NOT 404/405 (404/405 are PHYREG)
        self.assertEqual(pynexmon.NEX_GET_SECURITYCOOKIE, 410)
        self.assertEqual(pynexmon.NEX_SET_SECURITYCOOKIE, 411)
        self.assertEqual(pynexmon.NEX_GET_PHYREG, 404)
        self.assertEqual(pynexmon.NEX_SET_PHYREG, 405)
        self.assertEqual(self.java_defs["NEX_GET_SECURITYCOOKIE"], 410)
        self.assertEqual(self.java_defs["NEX_SET_SECURITYCOOKIE"], 411)
        self.assertEqual(self.java_defs["NEX_GET_PHYREG"], 404)
        self.assertEqual(self.java_defs["NEX_SET_PHYREG"], 405)

        # 412 is NEX_GET_WL_CNT, NOT 407 (407 is NEX_WRITE_OBJMEM)
        self.assertEqual(pynexmon.NEX_GET_WL_CNT, 412)
        self.assertEqual(pynexmon.NEX_WRITE_OBJMEM, 407)
        self.assertEqual(self.java_defs["NEX_GET_WL_CNT"], 412)
        self.assertEqual(self.java_defs["NEX_WRITE_OBJMEM"], 407)

        # Capabilities bitmask values
        self.assertEqual(pynexmon.NEX_CAP_MONITOR_MODE, 1)
        self.assertEqual(pynexmon.NEX_CAP_MONITOR_MODE_RADIOTAP, 2)
        self.assertEqual(pynexmon.NEX_CAP_FRAME_INJECTION, 4)
        self.assertEqual(self.java_defs["NEX_CAP_MONITOR_MODE"], 1)
        self.assertEqual(self.java_defs["NEX_CAP_MONITOR_MODE_RADIOTAP"], 2)
        self.assertEqual(self.java_defs["NEX_CAP_FRAME_INJECTION"], 4)

    def test_sync_script_check_passes(self):
        """The sync_constants.py CLI verification must pass cleanly."""
        res = subprocess.run(
            [sys.executable, str(SYNC_SCRIPT), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0, f"sync_constants.py failed:\n{res.stderr}\n{res.stdout}")
        self.assertIn("SUCCESS", res.stdout)


if __name__ == "__main__":
    unittest.main()
