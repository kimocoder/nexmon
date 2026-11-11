#!/usr/bin/env python3
"""Check the ABI and Android API level encoded in ELF files.

Every Android executable and shared library built by ndk-build carries a
.note.android.ident note whose first 4 bytes are the API level it was linked
against, and an ELF header that records the machine type. This script reads both
directly, so it works on a build host without the NDK or binutils.

Exit status is 1 if any file mismatches --abi or needs a higher API than
--max-api, 0 otherwise. Files that are not ELF (assets such as firmware images)
are skipped.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from typing import Iterator, Optional

EM_386 = 3
EM_ARM = 40
EM_X86_64 = 62
EM_AARCH64 = 183

# ELF class => {machine: ABI name}. 32-bit ARM also covers the old `armeabi`
# ABI, which is no longer accepted by current NDKs.
ABI_NAMES = {
    (1, EM_ARM): "armeabi-v7a",
    (2, EM_AARCH64): "arm64-v8a",
    (1, EM_386): "x86",
    (2, EM_X86_64): "x86_64",
}

ELF_MAGIC = b"\x7fELF"


def read_elf_header(data: bytes) -> Optional[tuple[int, int]]:
    """Return (elf class, e_machine), or None when data is not ELF."""
    if len(data) < 20 or data[:4] != ELF_MAGIC:
        return None
    elf_class = data[4]
    endian = "<" if data[5] == 1 else ">"
    (machine,) = struct.unpack_from(endian + "H", data, 18)
    return elf_class, machine


def abi_name(header: tuple[int, int]) -> Optional[str]:
    return ABI_NAMES.get(header)


def _note_from_sections(data: bytes, header: tuple[int, int]) -> Optional[int]:
    """Read .note.android.ident through the section header table."""
    elf_class, _ = header
    endian = "<" if data[5] == 1 else ">"
    if elf_class == 1:
        shoff_at = 0x20
        shentsize = struct.unpack_from(endian + "H", data, 0x2E)[0]
        shnum = struct.unpack_from(endian + "H", data, 0x30)[0]
        shstrndx = struct.unpack_from(endian + "H", data, 0x32)[0]
    else:
        shoff_at = 0x28
        shentsize = struct.unpack_from(endian + "H", data, 0x3A)[0]
        shnum = struct.unpack_from(endian + "H", data, 0x3C)[0]
        shstrndx = struct.unpack_from(endian + "H", data, 0x3E)[0]
    shoff = struct.unpack_from(endian + "Q" if elf_class == 2 else "I", data, shoff_at)[0]
    if not shoff or not shnum or shstrndx >= shnum or shentsize < 40:
        return None
    if shoff + shentsize * shnum > len(data):
        return None

    def section(index: int) -> tuple[int, int, int, int]:
        base = shoff + index * shentsize
        name = struct.unpack_from(endian + "I", data, base)[0]
        if elf_class == 1:
            offset, size = struct.unpack_from(endian + "II", data, base + 16)
        else:
            offset, size = struct.unpack_from(endian + "QQ", data, base + 24)
        return name, offset, size, base

    _, str_off, str_size, _ = section(shstrndx)
    if str_off + str_size > len(data):
        return None
    shstrings = data[str_off:str_off + str_size]

    for index in range(shnum):
        name_off, offset, size, _ = section(index)
        end = shstrings.find(b"\0", name_off)
        if end < 0 or shstrings[name_off:end] != b".note.android.ident":
            continue
        if offset + size > len(data):
            continue
        blob = data[offset:offset + size]
        if len(blob) < 12:
            continue
        namesz, descsz, _ = struct.unpack_from(endian + "III", blob, 0)
        name_end = 12 + namesz
        desc_start = name_end + (-name_end % 4)
        if blob[12:name_end].rstrip(b"\0") != b"Android" or desc_start + descsz > len(blob):
            continue
        if descsz < 4:
            continue
        return struct.unpack_from(endian + "I", blob, desc_start)[0]
    return None


def _note_from_scan(data: bytes) -> Optional[int]:
    """Find the note by scanning for its fixed shape.

    Used when the section header table is absent or does not describe the note
    (for example after objcopy/strip rewrote it).
    """
    needle = b"Android"
    start = 0
    while True:
        pos = data.find(needle, start)
        if pos < 0:
            return None
        start = pos + len(needle)
        if pos < 12:
            continue
        namesz, descsz, note_type = struct.unpack_from("<III", data, pos - 12)
        if namesz != 8 or note_type != 1 or not 4 <= descsz <= 0x1000:
            continue
        desc_start = pos + namesz
        if data[pos + len(needle):desc_start] != b"\0":
            continue
        if desc_start + descsz > len(data):
            continue
        return struct.unpack_from("<I", data, desc_start)[0]


def android_api(data: bytes, header: tuple[int, int]) -> Optional[int]:
    return _note_from_sections(data, header) or _note_from_scan(data)


def iter_files(paths: list[str]) -> Iterator[str]:
    for path in paths:
        if os.path.isdir(path):
            for root, _, names in os.walk(path):
                for name in sorted(names):
                    yield os.path.join(root, name)
        else:
            yield path


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", help="files or directories to inspect")
    parser.add_argument(
        "--max-api",
        type=int,
        default=21,
        help="highest acceptable .note.android.ident API level (default: 21)",
    )
    parser.add_argument(
        "--abi",
        action="append",
        default=None,
        help="acceptable ABI, repeatable (default: armeabi-v7a and arm64-v8a)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="only report failures")
    args = parser.parse_args(argv)
    accepted = set(args.abi or ["armeabi-v7a", "arm64-v8a"])

    failures: list[str] = []
    checked = 0
    for path in iter_files(args.paths):
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            failures.append(f"{path}: cannot read ({exc})")
            continue
        header = read_elf_header(data)
        if header is None:
            continue
        checked += 1
        abi = abi_name(header)
        api = android_api(data, header)
        problems = []
        if abi is None:
            problems.append("unknown machine")
        elif abi not in accepted:
            problems.append(f"ABI {abi} not in {sorted(accepted)}")
        if api is None:
            problems.append("no .note.android.ident (API level unknown)")
        elif api > args.max_api:
            problems.append(f"API {api} > {args.max_api}")
        if problems:
            failures.append(f"{path}: {', '.join(problems)}")
        elif not args.quiet:
            print(f"{path}: {abi} API {api}")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print(f"checked {checked} ELF file(s), {len(failures)} problem(s)", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())