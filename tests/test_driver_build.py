#!/usr/bin/env python3
"""Regression test suite for kernel driver trees, syntax integrity, and Kbuild compilation."""

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "buildtools" / "scripts"))

import check_drivers  # noqa: E402


class TestKernelDriverBuildAndIntegrity(unittest.TestCase):
    """Test suite ensuring all driver trees maintain comment/syntax integrity and Kbuild compatibility."""

    def test_all_driver_trees_pass_syntax_and_comment_checks(self):
        """All 14 driver trees in patches/driver/ must pass comment and preprocessor syntax checks."""
        total_files, total_errors, all_errors = check_drivers.check_all_drivers()
        self.assertGreater(total_files, 500, "Expected at least 500 driver source/header files")
        if all_errors:
            error_details = []
            for path, errs in all_errors.items():
                error_details.append(f"{path.relative_to(ROOT)}: {'; '.join(errs)}")
            self.fail("Driver syntax errors detected:\n" + "\n".join(error_details))
        self.assertEqual(total_errors, 0)

    def test_nested_driver_sources_are_checked_and_counted(self):
        """Both directory and repository scans must include nested C and headers."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            driver = root / "brcmfmac_6.6.y-nexmon"
            nested = driver / "include" / "nested"
            nested.mkdir(parents=True)
            good = driver / "core.c"
            bad_header = nested / "broken.h"
            bad_source = nested / "broken.c"
            good.write_text("int value;\n")
            bad_header.write_text("#ifdef UNCLOSED\n")
            bad_source.write_text("/* unclosed comment\n")
            (nested / "ignored.txt").write_text("/* ignored\n")
            errors = check_drivers.check_driver_directory(driver)
            self.assertEqual(set(errors), {bad_header, bad_source})
            count, error_count, all_errors = check_drivers.check_all_drivers(root)
            self.assertEqual(count, 3)
            self.assertEqual(error_count, 2)
            self.assertEqual(all_errors, errors)
            result = subprocess.run(
                [sys.executable, str(ROOT / "buildtools/scripts/check_drivers.py"),
                 "--check", "--driver-dir", str(driver)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Checking syntax for 3 files", result.stdout)
            self.assertIn(str(bad_header), result.stdout)
            self.assertIn(str(bad_source), result.stdout)

    def test_legacy_ci_requires_firmware_artifacts(self):
        """Legacy firmware CI must fail instead of silently skipping missing builds."""
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        legacy = workflow.split("\n  legacy-firmware:", 1)[1]
        legacy = re.split(r"\n  [A-Za-z0-9_-]+:", legacy, maxsplit=1)[0]
        # Match the validation command with its shell continuation lines.
        command = legacy.split("python3 buildtools/scripts/validate_firmware.py", 1)[1]
        command = command.split("\n\n", 1)[0]
        self.assertIn("--patch-dir patches/${{ matrix.dir }}/${{ matrix.subdir }}", command)
        self.assertIn("--require", command)

    def test_broken_comment_regression_detected(self):
        """Regression test for core.c:739-741: stray */ outside comments must be caught immediately."""
        broken_src = (
            "void brcmf_netif_mon_rx(struct brcmf_if *ifp, struct sk_buff *skb)\n"
            "{\n"
            "\t/* NOTE: 4-byte HW status trimmed safely if present */\n"
            "\t * skb->len underflow if the frame is shorter than expected.\n"
            "\t */\n"
            "\tif (skb->len >= 4)\n"
            "\t\tskb_trim(skb, skb->len - 4);\n"
            "}\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as tf:
            tf.write(broken_src)
            tf_path = Path(tf.name)

        try:
            errs = check_drivers.validate_driver_file(tf_path)
            self.assertTrue(any("Stray closing comment delimiter" in e for e in errs),
                            f"Expected stray */ error, got: {errs}")
        finally:
            tf_path.unlink(missing_ok=True)

    def test_unclosed_comment_detected(self):
        """Unclosed /* block comments reaching EOF must be caught."""
        unclosed_src = (
            "int foo(void) {\n"
            "    /* this comment never ends\n"
            "    return 42;\n"
            "}\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as tf:
            tf.write(unclosed_src)
            tf_path = Path(tf.name)

        try:
            errs = check_drivers.validate_driver_file(tf_path)
            self.assertTrue(any("Unclosed block comment" in e for e in errs),
                            f"Expected unclosed comment error, got: {errs}")
        finally:
            tf_path.unlink(missing_ok=True)

    def test_unmatched_preprocessor_detected(self):
        """Unclosed #ifdef or stray #endif directives must be caught."""
        bad_preproc = (
            "#ifdef FOO\n"
            "int a = 1;\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as tf:
            tf.write(bad_preproc)
            tf_path = Path(tf.name)

        try:
            errs = check_drivers.validate_driver_file(tf_path)
            self.assertTrue(any("Unclosed #ifdef" in e for e in errs),
                            f"Expected unclosed #ifdef error, got: {errs}")
        finally:
            tf_path.unlink(missing_ok=True)

    def test_kbuild_compilation_if_kernel_headers_present(self):
        """If Linux kernel build/headers are available, the matching driver must compile cleanly."""
        if os.environ.get("SKIP_KBUILD_TEST") == "1" or os.environ.get("FAST_TESTS") == "1":
            self.skipTest("Skipping kbuild compilation test (SKIP_KBUILD_TEST/FAST_TESTS requested)")

        kdir = check_drivers.find_kernel_build_dir()
        if not kdir:
            self.skipTest("No Linux kernel build tree available on this host")

        kver = check_drivers.detect_kernel_version(kdir)
        if not kver:
            self.skipTest(f"Could not determine kernel version from {kdir}")

        major, minor = kver
        target_dir = ROOT / "patches" / "driver" / f"brcmfmac_{major}.{minor}.y-nexmon"
        if not target_dir.is_dir():
            self.skipTest(f"No driver tree matching host kernel {major}.{minor}")

        success, output = check_drivers.compile_driver_kbuild(target_dir, kdir)
        self.assertTrue(success, f"Kbuild compilation failed for {target_dir.name}:\n{output}")

    def test_cli_invocation_check_flag(self):
        """CLI invocation with --check must pass with returncode 0."""
        res = subprocess.run(
            [sys.executable, str(ROOT / "buildtools" / "scripts" / "check_drivers.py"), "--check"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(res.returncode, 0, f"check_drivers.py failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("PASSED", res.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
