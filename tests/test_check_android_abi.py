#!/usr/bin/env python3
"""Tests for buildtools/scripts/check_android_abi.py"""

import importlib.util
import struct
import unittest

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "buildtools/scripts/check_android_abi.py"


def load_module():
    spec = importlib.util.spec_from_file_location("check_android_abi", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def elf32_with_note(api: int, machine: int = 40) -> bytes:
    """Build a minimal little-endian ELF32 with a .note.android.ident section."""
    shstrtab = b"\0.note.android.ident\0.shstrtab\0"
    note = struct.pack("<III", 8, 84, 1) + b"Android\0" + struct.pack("<I", api).ljust(84, b"\0")

    shstr_off = 0x200
    note_off = 0x100
    sh_off = 0x300
    sh_entsize = 40

    blob = bytearray(sh_off + 3 * sh_entsize)
    header = struct.pack(
        "<16sHHIIIIIHHHHHH",
        b"\x7fELF\x01\x01\x01" + b"\0" * 9,
        3, machine, 1, 0, 0, sh_off, 0x5000000,
        52, 0, 0, sh_entsize, 3, 2,
    )
    blob[: len(header)] = header
    blob[note_off:note_off + len(note)] = note
    blob[shstr_off:shstr_off + len(shstrtab)] = shstrtab

    def section(name, offset, size):
        return struct.pack("<IIIIIIIIII", name, 7, 0, 0, offset, size, 0, 0, 4, 0)

    sections = b"".join([
        b"\0" * sh_entsize,
        section(1, note_off, len(note)),
        section(21, shstr_off, len(shstrtab)),
    ])
    blob[sh_off:sh_off + len(sections)] = sections
    return bytes(blob)


class TestElfHeader(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_non_elf_is_none(self):
        self.assertIsNone(self.mod.read_elf_header(b"not an elf file"))

    def test_armv7_and_arm64(self):
        self.assertEqual(self.mod.abi_name(self.mod.read_elf_header(elf32_with_note(21))), "armeabi-v7a")
        self.assertEqual(self.mod.abi_name(self.mod.read_elf_header(elf32_with_note(21, 183))), None)
        self.assertEqual(self.mod.ABI_NAMES[(2, 183)], "arm64-v8a")


class TestNoteParsing(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_reads_api_from_section_table(self):
        data = elf32_with_note(21)
        self.assertEqual(self.mod.android_api(data, self.mod.read_elf_header(data)), 21)

    def test_reads_api_from_raw_scan(self):
        self.assertEqual(self.mod._note_from_scan(elf32_with_note(26)), 26)

    def test_absent_note_is_none(self):
        self.assertIsNone(self.mod._note_from_scan(b"no notes here"))


class TestCommandLine(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        self.tmp = __import__("tempfile").NamedTemporaryFile(suffix=".so", delete=False)
        self.tmp.write(elf32_with_note(21))
        self.tmp.close()

    def tearDown(self):
        __import__("os").unlink(self.tmp.name)

    def test_accepts_api_21_armv7(self):
        self.assertEqual(self.mod.main([self.tmp.name, "--max-api", "21", "--abi", "armeabi-v7a"]), 0)

    def test_rejects_api_23(self):
        with __import__("tempfile").NamedTemporaryFile(suffix=".so", delete=False) as handle:
            handle.write(elf32_with_note(23))
        try:
            self.assertEqual(self.mod.main([handle.name, "--max-api", "21"]), 1)
        finally:
            __import__("os").unlink(handle.name)

    def test_rejects_wrong_abi(self):
        self.assertEqual(self.mod.main([self.tmp.name, "--abi", "arm64-v8a"]), 1)

    def test_skips_relocatable_objects(self):
        # ndk-build leaves ET_REL .o files under objs/; the linker, not the
        # compiler, adds .note.android.ident to the shipped artifacts.
        data = bytearray(elf32_with_note(21))
        struct.pack_into("<H", data, 16, 1)
        data[0x100:0x100 + 104] = b"\0" * 104
        with __import__("tempfile").NamedTemporaryFile(suffix=".o", delete=False) as handle:
            handle.write(data)
        try:
            self.assertEqual(self.mod.main([handle.name, "--max-api", "21"]), 0)
        finally:
            __import__("os").unlink(handle.name)


if __name__ == "__main__":
    unittest.main()