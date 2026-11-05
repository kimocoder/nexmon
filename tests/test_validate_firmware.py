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


if __name__ == "__main__":
    unittest.main()
