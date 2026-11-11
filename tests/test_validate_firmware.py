#!/usr/bin/env python3
"""Unit tests for buildtools/scripts/validate_firmware.py."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

NEXMON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(NEXMON_ROOT, "buildtools", "scripts"))

from validate_firmware import DefinitionParser, FirmwareValidator


class TestDefinitionParser(unittest.TestCase):
    def test_parse_definitions_bcm43455c0(self):
        def_path = os.path.join(NEXMON_ROOT, "firmwares", "bcm43455c0", "7_45_265-28bca26-CY", "definitions.mk")
        if not os.path.isfile(def_path):
            self.skipTest("Firmware definitions.mk not found")

        defs = DefinitionParser.parse_file(def_path)
        self.assertEqual(defs.get("RAMSTART"), 0x198000)
        self.assertEqual(defs.get("RAMSIZE"), 0xC8000)
        self.assertEqual(defs.get("HNDRTE_RECLAIM_0_END"), 0x22CAD4)
        self.assertEqual(defs.get("PATCHSIZE"), 0x4000)
        # Arithmetic evaluation check: 0x22CAD4 - 0x4000 = 0x228AD4
        self.assertEqual(defs.get("PATCHSTART"), 0x228AD4)
        self.assertEqual(defs.get("RAM_FILE"), "cyfmac43455-sdio-standard.bin")

    def test_parse_definitions_bcm4339(self):
        def_path = os.path.join(NEXMON_ROOT, "firmwares", "bcm4339", "6_37_34_43", "definitions.mk")
        if not os.path.isfile(def_path):
            self.skipTest("Firmware definitions.mk not found")

        defs = DefinitionParser.parse_file(def_path)
        self.assertEqual(defs.get("RAMSTART"), 0x180000)
        self.assertEqual(defs.get("HNDRTE_RECLAIM_0_END"), 0x2092F0)
        self.assertEqual(defs.get("PATCHSIZE"), 0x4000)
        self.assertEqual(defs.get("PATCHSTART"), 0x2052F0)

    def test_parse_nonexistent_file(self):
        defs = DefinitionParser.parse_file("/tmp/nonexistent_defs.mk")
        self.assertEqual(defs, {})


class TestFirmwareValidator(unittest.TestCase):
    def test_truncated_elf_is_reported_as_failure(self):
        with tempfile.TemporaryDirectory(prefix="nexmon-validator-elf-") as tmp:
            patch_dir = Path(tmp)
            (patch_dir / "gen").mkdir()
            (patch_dir / "gen" / "patch.elf").write_bytes(b"\x7fELF")

            validator = FirmwareValidator(patch_dir=str(patch_dir), quiet=True)
            validator.validate_elf()

            self.assertEqual(validator.failed, 1)
            self.assertTrue(
                any("Truncated ELF header" in result["message"] for result in validator.results)
            )

    def test_region_outside_ram_is_reported_as_failure(self):
        with tempfile.TemporaryDirectory(prefix="nexmon-validator-memory-") as tmp:
            patch_dir = Path(tmp)
            (patch_dir / "gen").mkdir()
            (patch_dir / "gen" / "memory.ld").write_text(
                "patch : ORIGIN = 0xffffffff, LENGTH = 0x2\n"
            )

            validator = FirmwareValidator(patch_dir=str(patch_dir), quiet=True)
            validator.definitions = {"RAMSTART": 0x198000, "RAMSIZE": 0xC8000}
            validator.validate_memory_map()

            self.assertGreater(validator.failed, 0)
            self.assertTrue(
                any("Invalid linker region" in result["message"] for result in validator.results)
            )

    def test_bcm43455c0_validation(self):
        patch_dir = os.path.join(NEXMON_ROOT, "patches", "bcm43455c0", "7_45_265-28bca26-CY", "nexmon")
        bin_path = os.path.join(patch_dir, "cyfmac43455-sdio-standard.bin")
        if not os.path.isfile(bin_path):
            self.skipTest("Target firmware binary not built yet")

        validator = FirmwareValidator(patch_dir=patch_dir, quiet=True)
        success = validator.run_all()
        self.assertTrue(success, f"Firmware validation failed with {validator.failed} errors: {validator.results}")
        self.assertGreater(validator.passed, 20)
        self.assertEqual(validator.failed, 0)

    def test_invalid_patch_dir(self):
        validator = FirmwareValidator(patch_dir="/tmp/invalid_nexmon_target", quiet=True)
        success = validator.run_all()
        self.assertFalse(success)
        self.assertGreater(validator.failed, 0)

    @staticmethod
    def _diff_validator(tmp, original: bytes, patched: bytes):
        patch_dir = Path(tmp)
        original_path = patch_dir / "original.bin"
        patched_path = patch_dir / "patched.bin"
        original_path.write_bytes(original)
        patched_path.write_bytes(patched)
        validator = FirmwareValidator(patch_dir=str(patch_dir), quiet=True)
        validator.original_bin = str(original_path)
        validator.patched_bin = str(patched_path)
        return validator

    def test_firmware_growth_is_accepted(self):
        """Some targets place the patch region past the shipped image end."""
        with tempfile.TemporaryDirectory(prefix="nexmon-validator-grow-") as tmp:
            original = b"\x00" * 128
            patched = bytearray(original)
            patched[16:20] = b"\xde\xad\xbe\xef"
            patched.extend(b"\xaa" * 32)
            validator = self._diff_validator(tmp, original, bytes(patched))

            validator.validate_firmware_diff()

            self.assertEqual(validator.failed, 0)
            self.assertTrue(
                any("extended by 32 bytes" in r["message"] for r in validator.results),
                validator.results,
            )

    def test_append_only_firmware_is_rejected(self):
        """Growing without modifying any original byte means no patch ran."""
        with tempfile.TemporaryDirectory(prefix="nexmon-validator-append-") as tmp:
            original = b"\x00" * 128
            validator = self._diff_validator(tmp, original, original + b"\xaa" * 8)

            validator.validate_firmware_diff()

            self.assertGreaterEqual(validator.failed, 1)
            self.assertTrue(
                any("only appends data" in r["message"] for r in validator.results),
                validator.results,
            )

    def test_shrinking_firmware_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="nexmon-validator-shrink-") as tmp:
            validator = self._diff_validator(tmp, b"\x00" * 128, b"\x00" * 64)

            validator.validate_firmware_diff()

            self.assertGreaterEqual(validator.failed, 1)
            self.assertTrue(
                any("smaller than original" in r["message"] for r in validator.results),
                validator.results,
            )

    def test_repo_wrapper_is_clean(self):
        """Repository patches/common/wrapper.c must pass collision and consistency checks."""
        wrapper_path = os.path.join(NEXMON_ROOT, "patches", "common", "wrapper.c")
        fw_version_path = os.path.join(NEXMON_ROOT, "patches", "include", "firmware_version.h")
        self.assertTrue(os.path.isfile(wrapper_path))
        self.assertTrue(os.path.isfile(fw_version_path))

        errors = FirmwareValidator.check_wrapper_integrity(wrapper_path, fw_version_path)
        self.assertEqual(errors, [], f"Wrapper integrity errors found: {errors}")

    def test_wrapper_exact_macro_collision_detected(self):
        """Two distinct functions bound to the exact same (chip, fw, addr) must be caught."""
        with tempfile.TemporaryDirectory(prefix="nexmon-test-wrapper-") as tmp:
            fw_h = Path(tmp) / "firmware_version.h"
            fw_h.write_text(
                "#define CHIP_VER_BCM4361b0 104\n"
                "#define FW_VER_13_38_55_1_sta 410\n"
            )
            wrap_c = Path(tmp) / "wrapper.c"
            wrap_c.write_text(
                "AT(CHIP_VER_BCM4361b0, FW_VER_13_38_55_1_sta, 0x177994)\n"
                "void *pkt_buf_free_skb(void *osh, void *p, int send) { return 0; }\n\n"
                "AT(CHIP_VER_BCM4361b0, FW_VER_13_38_55_1_sta, 0x177994)\n"
                "int wl_sendup(void *wl, void *wlif, void *p) { return 0; }\n"
            )
            errors = FirmwareValidator.check_wrapper_integrity(str(wrap_c), str(fw_h))
            self.assertTrue(any("Wrapper address collision" in e and "0x177994" in e for e in errors), errors)

    def test_wrapper_resolved_macro_collision_detected(self):
        """Different chip macro names with identical numeric values must be caught."""
        with tempfile.TemporaryDirectory(prefix="nexmon-test-wrapper-") as tmp:
            fw_h = Path(tmp) / "firmware_version.h"
            fw_h.write_text(
                "#define CHIP_VER_BCM43438 4\n"
                "#define CHIP_VER_BCM43430a1 4\n"
                "#define FW_VER_ALL 0\n"
            )
            wrap_c = Path(tmp) / "wrapper.c"
            wrap_c.write_text(
                "AT(CHIP_VER_BCM43438, FW_VER_ALL, 0x880B80)\n"
                "void *malloc(unsigned int size) { return 0; }\n\n"
                "AT(CHIP_VER_BCM43430a1, FW_VER_ALL, 0x880B80)\n"
                "void *memcpy(void *dst, const void *src, unsigned int len) { return 0; }\n"
            )
            errors = FirmwareValidator.check_wrapper_integrity(str(wrap_c), str(fw_h))
            self.assertTrue(any("resolved address collision" in e and "0x880B80" in e for e in errors), errors)

    def test_wrapper_bcm43438_bcm43430a1_fallback_inconsistency_detected(self):
        """Missing version override falling back to conflicting FW_VER_ALL must be caught."""
        with tempfile.TemporaryDirectory(prefix="nexmon-test-wrapper-") as tmp:
            fw_h = Path(tmp) / "firmware_version.h"
            fw_h.write_text(
                "#define CHIP_VER_BCM43438 4\n"
                "#define CHIP_VER_BCM43430a1 4\n"
                "#define FW_VER_ALL 0\n"
                "#define FW_VER_7_45_98 43\n"
            )
            wrap_c = Path(tmp) / "wrapper.c"
            wrap_c.write_text(
                "AT(CHIP_VER_BCM43438, FW_VER_ALL, 0x819510)\n"
                "AT(CHIP_VER_BCM43430a1, FW_VER_7_45_98, 0xA5E2)\n"
                "AT(CHIP_VER_BCM43430a1, FW_VER_ALL, 0x819510)\n"
                "void wl_monitor(void) { ; }\n"
            )
            errors = FirmwareValidator.check_wrapper_integrity(str(wrap_c), str(fw_h))
            self.assertTrue(any("fallback inconsistency" in e and "wl_monitor" in e for e in errors), errors)

    def test_wrapper_bcm43438_bcm43430a1_parity_mismatch_detected(self):
        """Functions defined for 7_45_41_26 on one chip name but missing on the other must be caught."""
        with tempfile.TemporaryDirectory(prefix="nexmon-test-wrapper-") as tmp:
            fw_h = Path(tmp) / "firmware_version.h"
            fw_h.write_text(
                "#define CHIP_VER_BCM43438 4\n"
                "#define CHIP_VER_BCM43430a1 4\n"
                "#define FW_VER_7_45_41_26_r640327 40\n"
            )
            wrap_c = Path(tmp) / "wrapper.c"
            wrap_c.write_text(
                "AT(CHIP_VER_BCM43438, FW_VER_7_45_41_26_r640327, 0x2360)\n"
                "void *memcpy(void *d, const void *s, unsigned int n) { return 0; }\n"
            )
            errors = FirmwareValidator.check_wrapper_integrity(str(wrap_c), str(fw_h))
            self.assertTrue(any("parity mismatch" in e and "memcpy" in e for e in errors), errors)

    @staticmethod
    def _make_unbuilt_tree(root: Path) -> tuple[Path, Path]:
        """Create a patch/firmware tree with no build artifacts under root."""
        patch_dir = root / "patches" / "testchip" / "1_0" / "nexmon"
        fw_dir = root / "firmwares" / "testchip" / "1_0"
        patch_dir.mkdir(parents=True)
        fw_dir.mkdir(parents=True)
        (root / "setup_env.sh").write_text("", encoding="utf-8")
        return patch_dir, fw_dir

    def test_validate_firmware_require_behavior(self):
        """--require fails on missing artifacts, but non-require cleanly skips (exit 0)."""
        with tempfile.TemporaryDirectory(prefix="nexmon-validator-") as tmp:
            root = Path(tmp)
            patch_dir, fw_dir = self._make_unbuilt_tree(root)

            validator_skip = FirmwareValidator(
                patch_dir=str(patch_dir),
                fw_dir=str(fw_dir),
                nexmon_root=str(root),
                quiet=True,
                require=False,
            )
            self.assertTrue(validator_skip.run_all())

            validator_fail = FirmwareValidator(
                patch_dir=str(patch_dir),
                fw_dir=str(fw_dir),
                nexmon_root=str(root),
                quiet=True,
                require=True,
            )
            self.assertFalse(validator_fail.run_all())
            self.assertEqual(validator_fail.failed, 1)

    def test_validate_build_forwarding_stub(self):
        """validate_build.py forwarding stub behaves correctly with and without --require."""
        import subprocess

        real_stub = Path(NEXMON_ROOT) / "patches" / "bcm43455c0" / "7_45_265-28bca26-CY" / "nexmon" / "validate_build.py"
        real_validator = Path(NEXMON_ROOT) / "buildtools" / "scripts" / "validate_firmware.py"
        self.assertTrue(real_stub.is_file())
        self.assertTrue(real_validator.is_file())

        with tempfile.TemporaryDirectory(prefix="nexmon-stub-") as tmp:
            root = Path(tmp)
            patch_dir, _fw_dir = self._make_unbuilt_tree(root)
            scripts_dir = root / "buildtools" / "scripts"
            scripts_dir.mkdir(parents=True)
            (scripts_dir / "validate_firmware.py").write_text(
                real_validator.read_text(encoding="utf-8"), encoding="utf-8"
            )
            stub_path = patch_dir / "validate_build.py"
            stub_path.write_text(real_stub.read_text(encoding="utf-8"), encoding="utf-8")

            res_skip = subprocess.run([sys.executable, str(stub_path)], capture_output=True, text=True)
            self.assertEqual(res_skip.returncode, 0, res_skip.stdout + res_skip.stderr)
            self.assertIn("skipping build validation", res_skip.stdout)

            res_req = subprocess.run(
                [sys.executable, str(stub_path), "--require"], capture_output=True, text=True
            )
            self.assertEqual(res_req.returncode, 1, res_req.stdout + res_req.stderr)
            self.assertIn("FAILING build validation", res_req.stdout)

    def test_wrapper_fw_ver_all_conflict_detected(self):
        """Conflicting FW_VER_ALL and specific version on same chip must be caught."""
        with tempfile.TemporaryDirectory(prefix="nexmon-test-wrapper-") as tmp:
            fw_h = Path(tmp) / "firmware_version.h"
            fw_h.write_text(
                "#define CHIP_VER_BCM43455c0 14\n"
                "#define FW_VER_ALL 0\n"
                "#define FW_VER_7_45_154 44\n"
            )
            wrap_c = Path(tmp) / "wrapper.c"
            wrap_c.write_text(
                "AT(CHIP_VER_BCM43455c0, FW_VER_ALL, 0x9BE1C)\n"
                "AT(CHIP_VER_BCM43455c0, FW_VER_7_45_154, 0x19A098)\n"
                "int memcpy(void *d, void *s, int len) { return 0; }\n"
            )
            errors = FirmwareValidator.check_wrapper_integrity(str(wrap_c), str(fw_h))
            self.assertTrue(
                any("Wrapper FW_VER_ALL address conflict" in e and "memcpy" in e for e in errors),
                errors,
            )

    def test_monitormode_free_skb_backported(self):
        """All 21 legacy/monitormode targets must backport pkt_buf_free_skb to prevent leaks."""
        import glob
        pattern = os.path.join(NEXMON_ROOT, "patches", "**", "monitormode.c")
        targets = [
            p for p in glob.glob(pattern, recursive=True)
            if "nonsense" not in p and "bcm4375b1" not in p and "13_38_55_1_sta" not in p
        ]
        self.assertGreaterEqual(len(targets), 20)
        for t in targets:
            content = Path(t).read_text(encoding="utf-8", errors="replace")
            self.assertIn(
                "pkt_buf_free_skb",
                content,
                f"monitormode target {t} is missing pkt_buf_free_skb()",
            )

    def test_firmware_linker_regions_no_overlaps(self):
        """Ensure all generated memory.ld files have zero region overlaps."""
        import glob
        import re
        ld_files = glob.glob(os.path.join(NEXMON_ROOT, "patches", "**", "memory.ld"), recursive=True)
        if not ld_files:
            self.skipTest("No generated memory.ld files found (firmware not built yet)")
        self.assertGreater(len(ld_files), 10)
        for ld in ld_files:
            regions = {}
            with open(ld, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = re.match(r"(\w+)\s*:\s*ORIGIN\s*=\s*(0x[0-9a-fA-F]+),\s*LENGTH\s*=\s*(0x[0-9a-fA-F]+)", line)
                    if m:
                        name, orig, length = m.group(1), int(m.group(2), 16), int(m.group(3), 16)
                        regions[name] = (orig, orig + length)
            if "ucode" in regions:
                u_start, u_end = regions["ucode"]
                for other in ["fpconfig", "patch"]:
                    if other in regions:
                        o_start, o_end = regions[other]
                        if u_start < o_start:
                            self.assertLessEqual(
                                u_end,
                                o_start,
                                f"In {ld}: ucode [0x{u_start:X}, 0x{u_end:X}) overlaps {other} starting at 0x{o_start:X}",
                            )


if __name__ == "__main__":
    unittest.main()
