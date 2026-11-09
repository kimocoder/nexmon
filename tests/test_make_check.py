"""Regression coverage for local validation gates and failure propagation."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MakeCheckTests(unittest.TestCase):
    def test_check_runs_ci_gates_and_propagates_failures(self):
        """Execute the real check recipe with a recording Python replacement."""
        gates = [
            "-m unittest discover -s tests -v",
            "buildtools/scripts/validate_firmware.py patches/bcm43455c0/7_45_265-28bca26-CY/nexmon",
            "buildtools/scripts/check_drivers.py --check",
            "buildtools/scripts/sync_constants.py --check",
            "buildtools/scripts/validate_firmware.py --check-wrapper",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recorder = root / "record.py"
            log = root / "calls"
            fail = root / "fail"
            recorder.write_text(
                "from pathlib import Path\nimport sys\n"
                f"log = Path({str(log)!r})\nfail = Path({str(fail)!r})\n"
                "command = ' '.join(sys.argv[1:])\n"
                "with log.open('a') as output: output.write(command + '\\n')\n"
                "sys.exit(1 if fail.exists() and fail.read_text() == command else 0)\n"
            )
            for failing_gate in [None, *gates[-2:]]:
                with self.subTest(failing_gate=failing_gate):
                    log.unlink(missing_ok=True)
                    if failing_gate:
                        fail.write_text(failing_gate)
                    result = subprocess.run(
                        ["make", "--no-print-directory", "-f", str(ROOT / "Makefile"),
                         "check", "NEXMON_SETUP_ENV=1", f"PYTHON={sys.executable} {recorder}"],
                        cwd=root, capture_output=True, text=True, timeout=15,
                    )
                    expected = gates if failing_gate is None else gates[:gates.index(failing_gate) + 1]
                    self.assertEqual(log.read_text().splitlines(), expected)
                    self.assertEqual(result.returncode == 0, failing_gate is None, result.stdout + result.stderr)
