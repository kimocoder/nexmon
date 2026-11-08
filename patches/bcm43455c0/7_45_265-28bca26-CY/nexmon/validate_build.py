#!/usr/bin/env python3
"""Backward-compatibility forwarding stub for retired validate_build.py.

Firmware build validation has been generalized across all targets in
buildtools/scripts/validate_firmware.py.
"""

import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEXMON_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
VALIDATE_SCRIPT = os.path.join(
    NEXMON_ROOT, "buildtools", "scripts", "validate_firmware.py"
)


def main() -> int:
    cmd = [sys.executable, VALIDATE_SCRIPT, "--patch-dir", SCRIPT_DIR] + sys.argv[1:]
    res = subprocess.run(cmd)
    return res.returncode


if __name__ == "__main__":
    sys.exit(main())
