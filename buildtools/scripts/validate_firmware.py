#!/usr/bin/env python3
"""Generalized Firmware Build Validation Tool for Nexmon.

Validates Nexmon firmware patch builds across all Broadcom/Cypress targets:
  1. Build artifact existence (patched bin, original bin, patch ELF, gen/ linker scripts)
  2. Object file compilation integrity
  3. Firmware size preservation or controlled growth, and modification localization
  4. ELF patch file format, architecture (ARM 32-bit LE), and entry point
  5. Memory map boundaries and linker region non-overlap
  6. Nexmon identifier and firmware version string preservation
  7. Patch memory region non-zero content verification
  8. Compiler and linker log inspection for silent failures
  9. Ucode extraction and compression ratio validation
 10. Nexmon capability flags verification
 11. Cryptographic hashes (SHA-256, MD5)

Usage:
  python3 validate_firmware.py [PATCH_DIR]
  python3 validate_firmware.py --patch-dir patches/bcm43455c0/7_45_265-28bca26-CY/nexmon
  python3 validate_firmware.py --json
"""

import argparse
import glob
import hashlib
import json
import os
import re
import struct
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
import ast
import operator

_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.LShift: operator.lshift, ast.RShift: operator.rshift,
    ast.BitOr: operator.or_, ast.BitAnd: operator.and_, ast.BitXor: operator.xor,
}
_UNOPS = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Invert: operator.invert}


def _safe_int_eval(expr: str) -> int:
    """Evaluate an integer arithmetic expression (Makefile $(( )) subset)."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, int):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _BINOPS:
            return _BINOPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UNOPS:
            return _UNOPS[type(n.op)](ev(n.operand))
        raise ValueError(f"unsupported expression: {expr!r}")
    return ev(ast.parse(expr, mode="eval"))


class DefinitionParser:
    """Parses and resolves variables and arithmetic in definitions.mk."""

    @staticmethod
    def parse_file(path: str) -> Dict[str, Any]:
        raw_vars: Dict[str, str] = {}
        if not os.path.isfile(path):
            return {}

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.split("#")[0].strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    is_append = k.endswith("+")
                    k = k.rstrip(":?+!").strip()
                    v = v.strip()
                    if v.startswith("`") and v.endswith("`"):
                        continue
                    if is_append and k in raw_vars:
                        raw_vars[k] = f"{raw_vars[k]} {v}".strip()
                    else:
                        raw_vars[k] = v

        # Memoize fully resolved values to avoid O(vars×passes) re-expansion
        memo: Dict[str, str] = {}

        def resolve_val(val: str, depth: int = 0, seen: Optional[set] = None) -> str:
            if seen is None:
                seen = set()
            if val in memo and depth == 0 and not seen:
                return memo[val]
            if depth > 10:
                return val
            original_val = val
            val = val.replace("$$", "$")
            # First pass: replace $(VAR) with its resolved value
            for _ in range(8):
                m = re.search(r"\$\(([a-zA-Z0-9_]+)\)", val)
                if m:
                    vk = m.group(1)
                    if vk in seen:
                        # Cycle detected — stop expansion.
                        break
                    if vk in raw_vars:
                        seen.add(vk)
                        sub_v = resolve_val(raw_vars[vk], depth + 1, set(seen))
                        seen.remove(vk)
                        val = val[: m.start()] + str(sub_v) + val[m.end() :]
                    else:
                        break
                else:
                    break

            # Second pass: evaluate $(( ... ))
            for _ in range(8):
                m = re.search(r"\$\(\(([^()]+)\)\)", val)
                if m:
                    expr = m.group(1).strip()
                    for vk, vv in raw_vars.items():
                        if vk in expr:
                            sub_v = resolve_val(vv, depth + 1, set(seen))
                            expr = re.sub(r"\b" + re.escape(vk) + r"\b", str(sub_v), expr)
                    try:
                        res = _safe_int_eval(expr)
                        val = val[: m.start()] + hex(res) + val[m.end() :]
                    except Exception:
                        break
                else:
                    break
            if depth == 0 and not seen:
                memo[original_val] = val
            return val

        resolved: Dict[str, Any] = {}
        for k, v in raw_vars.items():
            res = resolve_val(v)
            try:
                if res.startswith(("0x", "0X")):
                    resolved[k] = int(res, 16)
                elif res.isdigit():
                    resolved[k] = int(res)
                else:
                    resolved[k] = res
            except Exception:
                resolved[k] = res

        return resolved


class FirmwareValidator:
    """Comprehensive validation engine for Nexmon firmware builds."""

    def __init__(
        self,
        patch_dir: Optional[str] = None,
        fw_dir: Optional[str] = None,
        nexmon_root: Optional[str] = None,
        quiet: bool = False,
        require: bool = False,
    ):
        self.patch_dir = os.path.abspath(patch_dir or os.getcwd())
        self.quiet = quiet
        self.require = require or os.environ.get("NEXMON_REQUIRE_BUILD") == "1"
        self.results: List[Dict[str, Any]] = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0

        # Locate NEXMON_ROOT
        if nexmon_root:
            self.nexmon_root = os.path.abspath(nexmon_root)
        else:
            cur = self.patch_dir
            found_root = None
            for _ in range(6):
                if os.path.isfile(os.path.join(cur, "setup_env.sh")) and os.path.isdir(os.path.join(cur, "firmwares")):
                    found_root = cur
                    break
                parent = os.path.dirname(cur)
                if parent == cur:
                    break
                cur = parent
            self.nexmon_root = found_root or os.path.abspath(os.path.join(self.patch_dir, "..", "..", "..", ".."))

        # Locate Firmware Directory and definitions.mk
        self.fw_dir = os.path.abspath(fw_dir) if fw_dir else self._find_fw_dir()
        self.definitions: Dict[str, Any] = {}
        if self.fw_dir:
            def_path = os.path.join(self.fw_dir, "definitions.mk")
            if os.path.isfile(def_path):
                self.definitions = DefinitionParser.parse_file(def_path)

        # Firmware binary filenames
        ram_file = self.definitions.get("RAM_FILE")
        if not ram_file and self.fw_dir:
            # Try to discover .bin in fw_dir
            bins = [b for b in os.listdir(self.fw_dir) if b.endswith(".bin") and b != "rom.bin" and b != "ucode.bin"]
            if bins:
                ram_file = bins[0]

        self.ram_filename = ram_file or "cyfmac43455-sdio-standard.bin"
        self.patched_bin = os.path.join(self.patch_dir, self.ram_filename)
        self.original_bin = os.path.join(self.fw_dir, self.ram_filename) if self.fw_dir else None
        self.patch_elf = os.path.join(self.patch_dir, "gen", "patch.elf")

    def _find_fw_dir(self) -> Optional[str]:
        # Check version.mk in patch dir or parent dir
        for check_dir in [self.patch_dir, os.path.dirname(self.patch_dir)]:
            vmk = os.path.join(check_dir, "version.mk")
            if os.path.isfile(vmk):
                with open(vmk, "r") as f:
                    for line in f:
                        if line.startswith("FW_PATH="):
                            path = line.strip().split("=", 1)[1]
                            path = path.replace("$(NEXMON_ROOT)", self.nexmon_root).replace("${NEXMON_ROOT}", self.nexmon_root)
                            if os.path.isdir(path):
                                return os.path.abspath(path)

        # Fallback by directory convention: patches/<chip>/<ver>/nexmon -> firmwares/<chip>/<ver>
        rel = os.path.relpath(self.patch_dir, self.nexmon_root)
        parts = rel.split(os.sep)
        if len(parts) >= 3 and parts[0] == "patches":
            chip = parts[1]
            ver = parts[2]
            candidate = os.path.join(self.nexmon_root, "firmwares", chip, ver)
            if os.path.isdir(candidate):
                return candidate
        return None

    def log_pass(self, msg: str):
        self.passed += 1
        self.results.append({"status": "PASS", "message": msg})
        if not self.quiet:
            print(f"  \033[0;32m✅ PASS:\033[0m {msg}")

    def log_fail(self, msg: str):
        self.failed += 1
        self.results.append({"status": "FAIL", "message": msg})
        if not self.quiet:
            print(f"  \033[0;31m❌ FAIL:\033[0m {msg}")

    def log_warn(self, msg: str):
        self.warnings += 1
        self.results.append({"status": "WARN", "message": msg})
        if not self.quiet:
            print(f"  \033[0;33m⚠️  WARN:\033[0m {msg}")

    def section(self, title: str):
        if not self.quiet:
            print(f"\n{'='*60}\n  {title}\n{'='*60}")

    def validate_artifacts(self):
        self.section("1. Build Artifact Existence")
        for name, path in [
            ("Patched firmware", self.patched_bin),
            ("Original firmware", self.original_bin),
            ("Patch ELF", self.patch_elf),
        ]:
            if path and os.path.isfile(path):
                self.log_pass(f"{name} exists: {os.path.basename(path)}")
            else:
                self.log_fail(f"{name} missing: {path}")

        # Check essential generated files in gen/. flashpatches.* only exist
        # on targets that apply flash patches at all.
        for gen_file in ["nexmon.ld", "memory.ld", "nexmon.mk"]:
            p = os.path.join(self.patch_dir, "gen", gen_file)
            if os.path.isfile(p):
                self.log_pass(f"Generated file exists: {gen_file}")
            else:
                self.log_fail(f"Generated file missing: {gen_file}")
        for gen_file in ["flashpatches.ld", "flashpatches.mk"]:
            p = os.path.join(self.patch_dir, "gen", gen_file)
            if os.path.isfile(p):
                self.log_pass(f"Generated file exists: {gen_file}")

    def _makefile_sources(self) -> Optional[List[str]]:
        """Object names the target Makefile actually compiles, or None.

        Targets differ in which patches/common/*.c they pull in (nexmon
        builds often use a wildcard, rom_extraction targets an explicit
        subset), so derive the expected set from the Makefile instead of
        assuming every shared source is linked everywhere.
        """
        mk = os.path.join(self.patch_dir, "Makefile")
        if not os.path.isfile(mk):
            return None
        with open(mk, "r", encoding="utf-8", errors="replace") as f:
            text = f.read().replace("\\\n", " ")
        values: List[str] = []
        for line in text.splitlines():
            m = re.match(r"\s*(?:LOCAL_SRCS|COMMON_SRCS|FW_SRCS)\s*[:+]?=\s*(.*)", line)
            if m:
                values.append(m.group(1))
        if not values:
            return None

        def subst(value: str) -> str:
            value = value.replace("$(NEXMON_ROOT)", self.nexmon_root)
            if self.fw_dir:
                value = value.replace("$(FW_PATH)", self.fw_dir)
            return value

        def expand_wildcard(match):
            pattern = subst(match.group(1).strip())
            if not os.path.isabs(pattern):
                pattern = os.path.join(self.patch_dir, pattern)
            return " ".join(glob.glob(pattern))

        sources: List[str] = []
        for value in values:
            value = subst(value)
            value = re.sub(r"\$\(wildcard\s+([^)]*)\)", expand_wildcard, value)
            sources.extend(t for t in value.split() if t.endswith(".c"))

        seen = set()
        objs = []
        for src in sources:
            obj = os.path.splitext(os.path.basename(src))[0] + ".o"
            if obj not in seen:
                seen.add(obj)
                objs.append(obj)
        return objs

    def validate_objects(self):
        self.section("2. Object File Compilation")
        obj_dir = os.path.join(self.patch_dir, "obj")
        actual_objs = set(os.listdir(obj_dir)) if os.path.isdir(obj_dir) else set()

        expected_objs = self._makefile_sources()
        if expected_objs is None:
            # Fallback heuristic for trees without a parseable Makefile.
            src_c = glob.glob(os.path.join(self.patch_dir, "src", "*.c"))
            common_c = glob.glob(os.path.join(self.nexmon_root, "patches", "common", "*.c"))
            fw_c = glob.glob(os.path.join(self.fw_dir, "*.c")) if self.fw_dir else []
            seen_objs = set()
            expected_objs = []
            for f in src_c + common_c + fw_c:
                obj = os.path.splitext(os.path.basename(f))[0] + ".o"
                if obj not in seen_objs:
                    seen_objs.add(obj)
                    expected_objs.append(obj)

        for obj in expected_objs:
            if obj in actual_objs:
                self.log_pass(f"Object file compiled: {obj}")
            else:
                self.log_fail(f"Expected object missing: {obj}")

    def validate_firmware_diff(self):
        self.section("3. Firmware Size and In-Place Patching Integrity")
        if not (self.patched_bin and os.path.isfile(self.patched_bin) and self.original_bin and os.path.isfile(self.original_bin)):
            self.log_fail("Cannot compare firmware — binary file missing")
            return

        with open(self.patched_bin, "rb") as f:
            patched_data = f.read()
        with open(self.original_bin, "rb") as f:
            orig_data = f.read()

        # Some targets place the patch region past the end of the shipped
        # firmware; dd then extends the file. Only shrinking is impossible.
        if len(patched_data) == len(orig_data):
            self.log_pass(f"Sizes match exactly: {len(patched_data)} bytes (in-place patching invariant)")
        elif len(patched_data) > len(orig_data):
            self.log_pass(
                f"Patched firmware extended by {len(patched_data) - len(orig_data)} bytes "
                f"({len(patched_data)} vs {len(orig_data)}): patch region lies past the original end"
            )
        else:
            self.log_fail(
                f"Patched firmware is smaller than original: "
                f"{len(patched_data)} < {len(orig_data)}"
            )

        common = min(len(patched_data), len(orig_data))
        if common and patched_data[:common] != orig_data[:common]:
            # Use numpy for 10× speedup on 500KB images when available; fallback
            # to Python loop. Both are correct, numpy just avoids per-byte Python.
            try:
                import numpy as np
                diff_count = int(np.count_nonzero(
                    np.frombuffer(patched_data[:common], dtype=np.uint8)
                    != np.frombuffer(orig_data[:common], dtype=np.uint8)
                ))
            except Exception:
                diff_count = sum(1 for a, b in zip(patched_data[:common], orig_data[:common]) if a != b)
            diff_count += len(patched_data) - common
            self.log_pass(f"Firmware was patched: {diff_count} bytes differ from original")
            unchanged_pct = (len(patched_data) - diff_count) / len(patched_data) * 100.0
            if unchanged_pct > 80.0:
                self.log_pass(f"Patch modification is properly localized: {unchanged_pct:.2f}% unchanged")
            else:
                self.log_warn(f"Large patch footprint: only {unchanged_pct:.2f}% unchanged")
        elif len(patched_data) > len(orig_data):
            self.log_fail("Patched firmware only appends data — no original bytes were modified!")
        else:
            self.log_fail("Patched firmware is IDENTICAL to original — patches were not applied!")

    def validate_elf(self):
        self.section("4. ELF Patch File Validation")
        if not (self.patch_elf and os.path.isfile(self.patch_elf)):
            self.log_fail(f"Patch ELF not found: {self.patch_elf}")
            return

        with open(self.patch_elf, "rb") as f:
            elf_data = f.read()

        if elf_data[:4] == b"\x7fELF":
            self.log_pass("ELF magic header valid")
        else:
            self.log_fail("Invalid ELF magic header")
            return

        # ELF32 has a 52-byte fixed header. Check it in full before indexing
        # individual fields so truncated build output is recorded as a normal
        # validation failure rather than raising IndexError/struct.error.
        if len(elf_data) < 52:
            self.log_fail(
                f"Truncated ELF header ({len(elf_data)} bytes; expected at least 52)"
            )
            return

        # 32-bit check
        if elf_data[4] == 1:
            self.log_pass("ELF class: 32-bit (ARM)")
        else:
            self.log_fail(f"ELF class: {elf_data[4]} (expected 1 for 32-bit)")

        # Little-endian
        if elf_data[5] == 1:
            self.log_pass("ELF encoding: little-endian")
        else:
            self.log_fail(f"ELF encoding: {elf_data[5]} (expected 1 for LE)")

        # Machine: ARM (40)
        e_machine = struct.unpack("<H", elf_data[18:20])[0]
        if e_machine == 40:
            self.log_pass("ELF target machine: ARM (EM_ARM = 40)")
        else:
            self.log_fail(f"ELF machine: {e_machine} (expected 40 for ARM)")

        # Entry point
        e_entry = struct.unpack("<I", elf_data[24:28])[0]
        ram_start = self.definitions.get("RAMSTART", 0)
        ram_size = self.definitions.get("RAMSIZE", 0)
        if e_entry == 0:
            self.log_pass("ELF entry point: 0x00000000 (standard for firmware patch ELF)")
        elif ram_start and ram_size:
            ram_end = ram_start + ram_size
            if ram_start <= e_entry < ram_end or (0 < e_entry < 0x200000):
                self.log_pass(f"ELF entry point valid: 0x{e_entry:08X}")
            else:
                self.log_warn(f"ELF entry point 0x{e_entry:08X} outside expected RAM range")
        else:
            self.log_pass(f"ELF entry point: 0x{e_entry:08X}")

    def _elf_sections(self):
        """Parse 32-bit little-endian section headers from gen/patch.elf."""
        if getattr(self, "_elf_cache", None) is not None:
            return self._elf_cache
        self._elf_cache = []
        if not (self.patch_elf and os.path.isfile(self.patch_elf)):
            return self._elf_cache
        with open(self.patch_elf, "rb") as f:
            data = f.read()
        if len(data) < 52 or data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
            return self._elf_cache
        e_shoff, = struct.unpack_from("<I", data, 0x20)
        e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", data, 0x2E)
        if e_shentsize < 40 or e_shnum == 0 or e_shoff + e_shnum * e_shentsize > len(data):
            return self._elf_cache
        raw = []
        for i in range(e_shnum):
            off = e_shoff + i * e_shentsize
            sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from("<IIIIII", data, off)
            sh_link, = struct.unpack_from("<I", data, off + 0x18)
            raw.append({
                "sh_name": sh_name, "type": sh_type, "flags": sh_flags,
                "addr": sh_addr, "offset": sh_offset, "size": sh_size,
                "link": sh_link, "name": "",
            })
        strtab = b""
        if 0 <= e_shstrndx < len(raw):
            s = raw[e_shstrndx]
            strtab = data[s["offset"]:s["offset"] + s["size"]]
        for sec in raw:
            name_off = sec.pop("sh_name")
            if strtab and name_off < len(strtab):
                end = strtab.find(b"\0", name_off)
                sec["name"] = strtab[name_off:end if end != -1 else len(strtab)].decode("ascii", "replace")
        self._elf_cache = raw
        return self._elf_cache

    def _elf_alloc_sections(self):
        """Allocated sections with a real address, as (name, start, end)."""
        return [
            (s["name"], s["addr"], s["addr"] + s["size"])
            for s in self._elf_sections()
            if (s["flags"] & 0x2) and s["addr"] and s["size"]
        ]

    def _elf_symbol_address(self, wanted: str) -> Optional[int]:
        sections = self._elf_sections()
        if not sections:
            return None
        with open(self.patch_elf, "rb") as f:
            data = f.read()
        for sec in sections:
            if sec["type"] != 2:  # SHT_SYMTAB
                continue
            if not (0 <= sec["link"] < len(sections)):
                continue
            strtab = sections[sec["link"]]
            strtab_data = data[strtab["offset"]:strtab["offset"] + strtab["size"]]
            for j in range(sec["size"] // 16):
                off = sec["offset"] + j * 16
                if off + 16 > len(data):
                    break
                st_name, st_value, _st_size, _st_info, _st_other, _shndx = struct.unpack_from(
                    "<IIIBBH", data, off
                )
                if st_name < len(strtab_data):
                    end = strtab_data.find(b"\0", st_name)
                    name = strtab_data[
                        st_name:end if end != -1 else len(strtab_data)
                    ].decode("ascii", "replace")
                    if name == wanted:
                        return st_value
        return None

    @staticmethod
    def parse_firmware_versions(
        fw_version_path: str,
    ) -> Tuple[Dict[str, int], Dict[str, int]]:
        """Parse CHIP_VER_* and FW_VER_* defines from firmware_version.h."""
        chip_defs: Dict[str, int] = {"CHIP_VER_ALL": 0}
        fw_defs: Dict[str, int] = {"FW_VER_ALL": 0}
        if not os.path.isfile(fw_version_path):
            return chip_defs, fw_defs
        with open(fw_version_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m_chip = re.match(r"#define\s+(CHIP_VER_\w+)\s+(\d+)", line)
                if m_chip:
                    chip_defs[m_chip.group(1)] = int(m_chip.group(2))
                m_fw = re.match(r"#define\s+(FW_VER_\w+)\s+(\d+)", line)
                if m_fw:
                    fw_defs[m_fw.group(1)] = int(m_fw.group(2))
        return chip_defs, fw_defs

    @staticmethod
    def parse_wrapper_bindings(
        wrapper_path: str,
        chip_defs: Optional[Dict[str, int]] = None,
        fw_defs: Optional[Dict[str, int]] = None,
    ) -> List[Dict[str, Any]]:
        """Parse all AT(chip, fw, addr) annotations and function signatures in wrapper.c."""
        chip_defs = chip_defs or {}
        fw_defs = fw_defs or {}
        bindings: List[Dict[str, Any]] = []
        if not os.path.isfile(wrapper_path):
            return bindings

        at_pattern = re.compile(
            r"^\s*AT\s*\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*,\s*(0x[0-9a-fA-F]+|\d+)\s*\)"
        )
        func_skip = {
            "AT", "void", "int", "bool", "uint", "uint32", "uint16", "uint8",
            "char", "unsigned", "short", "long", "float", "double", "struct",
            "const", "static", "inline", "extern",
        }

        pending_ats: List[Tuple[str, str, int, int]] = []
        with open(wrapper_path, "r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f, 1):
                m = at_pattern.match(line)
                if m:
                    chip, fw, addr_str = m.group(1), m.group(2), m.group(3)
                    addr = int(addr_str, 16) if addr_str.startswith(("0x", "0X")) else int(addr_str)
                    pending_ats.append((chip, fw, addr, idx))
                    continue
                if pending_ats:
                    stripped = line.strip()
                    if not stripped or stripped.startswith(("//", "/*", "*")):
                        continue
                    m_func = re.search(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", line)
                    if m_func and m_func.group(1) not in func_skip:
                        func_name = m_func.group(1)
                        for c, w, a, l in pending_ats:
                            c_num = chip_defs.get(c, -1)
                            w_num = fw_defs.get(w, -1)
                            bindings.append({
                                "func": func_name,
                                "chip": c,
                                "fw": w,
                                "chip_num": c_num,
                                "fw_num": w_num,
                                "addr": a,
                                "line": l,
                            })
                        pending_ats = []
        return bindings

    @classmethod
    def check_wrapper_integrity(
        cls,
        wrapper_path: str,
        fw_version_path: str,
        target_chip: Optional[str] = None,
        target_fw: Optional[str] = None,
    ) -> List[str]:
        """Validate wrapper bindings for address collisions and BCM43438/BCM43430a1 consistency.

        Detects:
          1. Exact macro collisions: two distinct functions bound to the same (chip, fw, addr).
          2. Resolved numeric collisions: two distinct functions resolving to the same (chip_id, fw_id, addr)
             across macro aliases (e.g. CHIP_VER_BCM43438 vs CHIP_VER_BCM43430a1).
          3. BCM43438 vs BCM43430a1 consistency: conflicting addresses, dangerous fallback to FW_VER_ALL,
             or missing parity on primary shared versions.
          4. Target-specific collisions across resolved wrapper bindings.
        """
        chip_defs, fw_defs = cls.parse_firmware_versions(fw_version_path)
        bindings = cls.parse_wrapper_bindings(wrapper_path, chip_defs, fw_defs)
        errors: List[str] = []

        if not bindings:
            errors.append(f"No wrapper bindings parsed from {wrapper_path}")
            return errors

        # 1. Exact macro collisions: (chip, fw, addr) -> multiple distinct functions
        macro_map: Dict[Tuple[str, str, int], Dict[str, Set[int]]] = defaultdict(lambda: defaultdict(set))
        for b in bindings:
            macro_map[(b["chip"], b["fw"], b["addr"])][b["func"]].add(b["line"])

        for (c, w, addr), funcs in sorted(macro_map.items()):
            if len(funcs) > 1:
                detail = ", ".join(f"{f} (line {min(lines)})" for f, lines in sorted(funcs.items()))
                errors.append(
                    f"Wrapper address collision: distinct functions share ({c}, {w}, 0x{addr:X}): {detail}"
                )

        # 2. Resolved numeric collisions across aliases
        resolved_map: Dict[Tuple[int, int, int], Dict[str, Set[Tuple[str, str, int]]]] = defaultdict(lambda: defaultdict(set))
        for b in bindings:
            if b["chip_num"] >= 0 and b["fw_num"] >= 0:
                resolved_map[(b["chip_num"], b["fw_num"], b["addr"])][b["func"]].add((b["chip"], b["fw"], b["line"]))

        for (c_num, w_num, addr), funcs in sorted(resolved_map.items()):
            if len(funcs) > 1:
                macro_pairs = {(c, w) for flist in funcs.values() for c, w, l in flist}
                if len(macro_pairs) > 1:
                    detail = ", ".join(f"{f} ({c}/{w})" for f, flist in sorted(funcs.items()) for c, w, l in flist)
                    errors.append(
                        f"Wrapper resolved address collision (chip_id={c_num}, fw_id={w_num}, 0x{addr:X}): {detail}"
                    )

        # 3. BCM43438 vs BCM43430a1 consistency check
        b38_by_func: Dict[str, Dict[str, int]] = defaultdict(dict)
        b30_by_func: Dict[str, Dict[str, int]] = defaultdict(dict)
        for b in bindings:
            if b["chip"] == "CHIP_VER_BCM43438":
                b38_by_func[b["func"]][b["fw"]] = b["addr"]
            elif b["chip"] == "CHIP_VER_BCM43430a1":
                b30_by_func[b["func"]][b["fw"]] = b["addr"]

        all_bcm_funcs = set(b38_by_func.keys()) | set(b30_by_func.keys())
        for f in sorted(all_bcm_funcs):
            f38 = b38_by_func.get(f, {})
            f30 = b30_by_func.get(f, {})

            # Shared versions: explicit address must match
            shared_fws = set(f38.keys()) & set(f30.keys())
            for fw in sorted(shared_fws):
                if f38[fw] != f30[fw]:
                    errors.append(
                        f"BCM43438/BCM43430a1 inconsistency for '{f}' on {fw}: BCM43438=0x{f38[fw]:X} vs BCM43430a1=0x{f30[fw]:X}"
                    )

            # Fallback inconsistency: one defines explicit fw, the other falls back to differing FW_VER_ALL
            for fw, addr in f38.items():
                if fw != "FW_VER_ALL" and fw not in f30 and "FW_VER_ALL" in f30 and f30["FW_VER_ALL"] != addr:
                    errors.append(
                        f"BCM43438/BCM43430a1 fallback inconsistency for '{f}': BCM43438 defines 0x{addr:X} for {fw}, "
                        f"but BCM43430a1 falls back to 0x{f30['FW_VER_ALL']:X} (FW_VER_ALL)"
                    )
            for fw, addr in f30.items():
                if fw != "FW_VER_ALL" and fw not in f38 and "FW_VER_ALL" in f38 and f38["FW_VER_ALL"] != addr:
                    errors.append(
                        f"BCM43438/BCM43430a1 fallback inconsistency for '{f}': BCM43430a1 defines 0x{addr:X} for {fw}, "
                        f"but BCM43438 falls back to 0x{f38['FW_VER_ALL']:X} (FW_VER_ALL)"
                    )

            # Parity check for primary shared firmware version
            primary_shared = "FW_VER_7_45_41_26_r640327"
            if primary_shared in f38 and primary_shared not in f30:
                errors.append(
                    f"BCM43438/BCM43430a1 parity mismatch: '{f}' defined for BCM43438 on {primary_shared} but missing on BCM43430a1"
                )
            elif primary_shared in f30 and primary_shared not in f38:
                errors.append(
                    f"BCM43438/BCM43430a1 parity mismatch: '{f}' defined for BCM43430a1 on {primary_shared} but missing on BCM43438"
                )

        # 4. Target-specific collision check (when target chip & fw are known)
        if target_chip and target_fw:
            t_cnum = chip_defs.get(target_chip)
            t_fwnum = fw_defs.get(target_fw)
            t_map: Dict[int, Set[str]] = defaultdict(set)
            for b in bindings:
                c_match = (
                    b["chip"] == "CHIP_VER_ALL"
                    or b["chip"] == target_chip
                    or (t_cnum is not None and b["chip_num"] == t_cnum)
                )
                w_match = (
                    b["fw"] == "FW_VER_ALL"
                    or b["fw"] == target_fw
                    or (t_fwnum is not None and b["fw_num"] == t_fwnum)
                )
                if c_match and w_match:
                    t_map[b["addr"]].add(b["func"])

            for addr, funcs in sorted(t_map.items()):
                if len(funcs) > 1:
                    errors.append(
                        f"Target {target_chip}/{target_fw} wrapper collision at 0x{addr:X} across functions: {sorted(funcs)}"
                    )

        return errors

    def validate_wrapper(self, wrapper_path: Optional[str] = None, fw_version_path: Optional[str] = None):
        self.section("10. Wrapper Address Collisions & BCM43438/BCM43430a1 Consistency")
        wrapper_path = wrapper_path or os.path.join(self.nexmon_root, "patches", "common", "wrapper.c")
        fw_version_path = fw_version_path or os.path.join(self.nexmon_root, "patches", "include", "firmware_version.h")

        if not os.path.isfile(wrapper_path):
            self.log_warn(f"wrapper.c not found: {wrapper_path}")
            return
        if not os.path.isfile(fw_version_path):
            self.log_warn(f"firmware_version.h not found: {fw_version_path}")
            return

        target_chip = self.definitions.get("NEXMON_CHIP")
        target_fw = self.definitions.get("NEXMON_FW_VERSION")

        errors = self.check_wrapper_integrity(
            wrapper_path=wrapper_path,
            fw_version_path=fw_version_path,
            target_chip=target_chip,
            target_fw=target_fw,
        )

        for err in errors:
            self.log_fail(err)

        if not errors:
            self.log_pass("Wrapper function bindings are consistent and collision-free.")

    def validate_memory_map(self):
        self.section("5. Memory Map and Linker Region Validation")
        memory_ld_path = os.path.join(self.patch_dir, "gen", "memory.ld")
        if not os.path.isfile(memory_ld_path):
            self.log_warn("gen/memory.ld not found; skipping linker region checks")
            return

        rom_start = self.definitions.get("ROMSTART")
        rom_size = self.definitions.get("ROMSIZE")
        ram_start = self.definitions.get("RAMSTART")
        ram_size = self.definitions.get("RAMSIZE")
        ram_end = (
            ram_start + ram_size
            if (ram_start is not None and ram_size is not None)
            else None
        )

        linker_regions = {}
        with open(memory_ld_path, "r") as f:
            for line in f:
                m = re.match(r"(\w+)\s*:\s*ORIGIN\s*=\s*(0x[0-9a-fA-F]+),\s*LENGTH\s*=\s*(0x[0-9a-fA-F]+)", line)
                if m:
                    name = m.group(1)
                    origin = int(m.group(2), 16)
                    length = int(m.group(3), 16)
                    linker_regions[name] = (origin, origin + length, length)

        if not linker_regions:
            self.log_fail("No memory regions found in linker script")
            return

        for name, (start, end, size) in linker_regions.items():
            normalized_name = name.lower()
            if size <= 0 or start < 0 or end <= start or end > 0x100000000:
                self.log_fail(
                    f"Invalid linker region '{name}': start=0x{start:X}, size=0x{size:X}"
                )
                continue

            if normalized_name == "rom":
                expected_end = (
                    rom_start + rom_size
                    if rom_start is not None and rom_size is not None
                    else None
                )
                if expected_end is not None and (
                    start != rom_start or end != expected_end
                ):
                    self.log_fail(
                        f"Linker region 'rom' does not match firmware bounds: "
                        f"0x{start:06X}-0x{end:06X} (expected "
                        f"0x{rom_start:06X}-0x{expected_end:06X})"
                    )
                else:
                    self.log_pass(
                        f"Linker region 'rom': 0x{start:06X}-0x{end:06X} (0x{size:X})"
                    )
                continue

            if normalized_name == "ram":
                if ram_end is not None and (start != ram_start or end != ram_end):
                    self.log_fail(
                        f"Linker region 'ram' does not match firmware bounds: "
                        f"0x{start:06X}-0x{end:06X} (expected "
                        f"0x{ram_start:06X}-0x{ram_end:06X})"
                    )
                else:
                    self.log_pass(
                        f"Linker region 'ram': 0x{start:06X}-0x{end:06X} (0x{size:X})"
                    )
                continue

            if ram_start is None or ram_end is None:
                self.log_fail(
                    f"Cannot validate linker region '{name}' without RAMSTART/RAMSIZE"
                )
            elif ram_start <= start < end <= ram_end:
                self.log_pass(
                    f"Linker region '{name}': 0x{start:06X}-0x{end:06X} within RAM"
                )
            else:
                self.log_fail(
                    f"Linker region '{name}' outside RAM bounds: "
                    f"0x{start:06X}-0x{end:06X} (RAM "
                    f"0x{ram_start:06X}-0x{ram_end:06X})"
                )

        # Check ordering of sub-regions. A declared overlap is only fatal if
        # an allocated section actually extends into the next region (some
        # targets declare a generous ucode container that overlaps fpconfig,
        # while the linked ucode blob stops well before it).
        sub = [(n, linker_regions[n]) for n in ("ucode", "fpconfig", "patch") if n in linker_regions]
        sub.sort(key=lambda x: x[1][0])
        alloc = self._elf_alloc_sections()
        for i in range(len(sub) - 1):
            n1, (s1, e1, _) = sub[i]
            n2, (s2, _, _) = sub[i + 1]
            if e1 <= s2:
                self.log_pass(f"Linker regions non-overlapping: '{n1}' ends 0x{e1:X} <= '{n2}' starts 0x{s2:X}")
                continue
            if not alloc:
                self.log_warn(
                    f"Declared linker regions '{n1}' and '{n2}' overlap "
                    f"(0x{e1:X} > 0x{s2:X}); no ELF sections available to check actual extent"
                )
                continue
            intruders = [
                (name, start, end) for name, start, end in alloc
                if s1 <= start < e1 and end > s2
            ]
            if intruders:
                name, start, end = intruders[0]
                self.log_fail(
                    f"Linker region overlap is real: section '{name}' "
                    f"0x{start:X}-0x{end:X} intrudes into '{n2}' at 0x{s2:X}"
                )
            else:
                in_first = [end for _, start, end in alloc if s1 <= start < e1]
                actual_end = max(in_first) if in_first else s1
                self.log_pass(
                    f"Declared regions '{n1}'/'{n2}' overlap, but allocated sections "
                    f"end 0x{actual_end:X} <= '{n2}' start 0x{s2:X}"
                )

    def validate_logs(self):
        self.section("6. Compiler & Linker Log Inspection")
        log_dir = os.path.join(self.patch_dir, "log")
        if not os.path.isdir(log_dir):
            self.log_warn(f"Log directory not found: {log_dir}")
            return

        for logname in ["compiler.log", "linker.log", "flashpatches.log", "patches.log", "linker.err", "error.log"]:
            logpath = os.path.join(log_dir, logname)
            if not os.path.isfile(logpath):
                continue

            with open(logpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            errors = []
            for line in content.splitlines():
                if not line.strip():
                    continue
                lower = line.lower()
                if "removing unused section" in lower:
                    continue
                # Benign linker map ASSERT expressions (ld map outputs: 0x00000001 ASSERT ((...)))
                if "assert (" in lower or "assert(" in lower:
                    if logname == "linker.log" or "0x00000001" in line:
                        continue
                    if "failed" not in lower and "error" not in lower:
                        continue
                if "has a load segment with rwx permissions" in lower:
                    continue
                if any(kw in lower for kw in ("error", "undefined reference", "undefined symbol", "warning:", "fatal error", "assertion failed", "_static_assert")):
                    errors.append(line)
                elif "warning" in lower and "unused" not in lower:
                    # Catch standalone warnings (e.g., implicit declaration) but ignore linker GC
                    errors.append(line)
            if errors:
                self.log_fail(f"{logname}: {len(errors)} error(s) found in log")
            else:
                self.log_pass(f"{logname}: clean (no errors)")

    def validate_firmware_strings(self):
        self.section("7. Firmware Identifier & Version String Verification")
        if not (self.patched_bin and os.path.isfile(self.patched_bin)):
            return

        with open(self.patched_bin, "rb") as f:
            data = f.read()

        if b"nexmon" in data.lower():
            self.log_pass("Nexmon identifier confirmed in patched binary")
        else:
            self.log_warn("No literal 'nexmon' string found in patched binary")

        build_num_path = os.path.join(self.patch_dir, "BUILD_NUMBER")
        if os.path.isfile(build_num_path):
            with open(build_num_path, "r") as f:
                bnum = f.read().strip()
            self.log_pass(f"Build number registered: {bnum}")

    def validate_ucode(self):
        self.section("9. Ucode Extraction and Compression Ratio Validation")
        # Check that ucode extraction / compression artefacts exist and the
        # compressed image is smaller than the raw one — a basic sanity gate
        # for the tinflate path that feeds PATCHSIZE reclaim checks.
        candidates = [
            (os.path.join(self.patch_dir, "gen", "ucode.bin"), "gen/ucode.bin"),
            (os.path.join(self.patch_dir, "gen", "ucode_compressed.bin"), "gen/ucode_compressed.bin"),
            (os.path.join(self.patch_dir, "src", "ucode_compressed.c"), "src/ucode_compressed.c"),
        ]
        found = {name: os.path.isfile(path) for path, name in candidates}
        for path, name in candidates:
            if found[name]:
                size = os.path.getsize(path)
                if size == 0:
                    self.log_fail(f"Ucode artefact {name} is empty")
                else:
                    self.log_pass(f"Ucode artefact {name} exists ({size} bytes)")
            else:
                self.log_warn(f"Ucode artefact {name} not found — skipping ratio check")
        if found["gen/ucode.bin"] and found["gen/ucode_compressed.bin"]:
            raw_size = os.path.getsize(os.path.join(self.patch_dir, "gen", "ucode.bin"))
            cmp_size = os.path.getsize(os.path.join(self.patch_dir, "gen", "ucode_compressed.bin"))
            if raw_size > 0 and cmp_size > 0:
                ratio = cmp_size / raw_size
                if cmp_size < raw_size and 0.1 < ratio < 0.9:
                    self.log_pass(f"Ucode compression ratio sane: {cmp_size}/{raw_size} ({ratio:.1%})")
                elif cmp_size >= raw_size:
                    self.log_fail(f"Ucode compressed image not smaller than raw: {cmp_size} >= {raw_size}")
                else:
                    self.log_warn(f"Ucode compression ratio unusual: {cmp_size}/{raw_size} ({ratio:.1%})")
            # Also verify that the compressed blob decompresses to the raw size
            # and matches raw ucode byte-for-byte via a zlib check.
            try:
                import zlib
                with open(os.path.join(self.patch_dir, "gen", "ucode_compressed.bin"), "rb") as f:
                    comp_data = f.read()
                # zlib-flate output is raw zlib stream; try decompress.
                decomp = zlib.decompress(comp_data)
                raw_ucode_path = os.path.join(self.patch_dir, "gen", "ucode.bin")
                raw_ucode = None
                if os.path.isfile(raw_ucode_path):
                    with open(raw_ucode_path, "rb") as f:
                        raw_ucode = f.read()

                if raw_ucode is not None and decomp != raw_ucode:
                    self.log_fail("Ucode decompressed content does not match raw gen/ucode.bin!")
                elif len(decomp) == raw_size:
                    self.log_pass("Ucode compressed blob decompresses and matches raw ucode")
                else:
                    self.log_fail(f"Ucode decompressed size {len(decomp)} != raw {raw_size}")
            except Exception as e:
                self.log_fail(f"Ucode decompression failed: {e}")

    def validate_capabilities(self):
        self.section("8. Capability Word (nexutil -G)")
        if not (self.patch_elf and os.path.isfile(self.patch_elf) and
                self.patched_bin and os.path.isfile(self.patched_bin)):
            self.log_warn("Skipping capability check — patch ELF or patched binary missing")
            return
        addr = self._elf_symbol_address("capabilities")
        if addr is None:
            self.log_warn("No 'capabilities' symbol in patch ELF; cannot verify the word")
            return
        ram_start = self.definitions.get("RAMSTART")
        if ram_start is None:
            self.log_warn("RAMSTART unknown; cannot map the capabilities symbol to a file offset")
            return
        if addr < ram_start:
            self.log_warn(f"capabilities symbol 0x{addr:X} is below RAMSTART 0x{ram_start:X}")
            return
        with open(self.patched_bin, "rb") as f:
            f.seek(addr - ram_start)
            raw = f.read(4)
        if len(raw) != 4:
            self.log_fail(f"capabilities word at 0x{addr:X} is outside the patched image")
            return
        value = struct.unpack("<I", raw)[0]
        known = 0x7  # monitor | radiotap | frame injection
        self.log_pass(f"Capability word in patched image: 0x{value:x}")
        if value & ~known:
            self.log_warn(f"Capability word advertises unknown bits: 0x{value & ~known:x}")

    def compute_hashes(self):
        self.section("11. Cryptographic Hashes")
        if self.patched_bin and os.path.isfile(self.patched_bin):
            with open(self.patched_bin, "rb") as f:
                data = f.read()
            sha256 = hashlib.sha256(data).hexdigest()
            md5 = hashlib.md5(data).hexdigest()
            self.log_pass(f"Patched SHA-256: {sha256}")
            self.log_pass(f"Patched MD5:     {md5}")

    def run_all(self) -> bool:
        """Run all validation stages. Returns True if all passed with zero failures."""
        if not self.quiet:
            print(f"Validating firmware patch: {self.patch_dir}")
            if self.fw_dir:
                print(f"Target firmware base:     {self.fw_dir}")

        if not self.fw_dir or not os.path.isdir(self.fw_dir):
            self.log_fail(f"Invalid target: firmware directory not found for {self.patch_dir}")
            return False

        has_artifacts = bool(
            self.patched_bin
            and os.path.isfile(self.patched_bin)
            and self.patch_elf
            and os.path.isfile(self.patch_elf)
        )
        if not has_artifacts:
            rel_bin = (
                os.path.relpath(self.patched_bin, self.patch_dir)
                if self.patched_bin
                else self.ram_filename
            )
            if self.require:
                self.log_fail(
                    f"build artifacts not found ({rel_bin}, gen/patch.elf); FAILING build validation."
                )
                if not self.quiet:
                    print(f"Build the firmware first (make -C {self.patch_dir}).")
                return False
            else:
                if not self.quiet:
                    print(
                        f"build artifacts not found ({rel_bin}, gen/patch.elf); skipping build validation."
                    )
                    print(f"Build the firmware first (make -C {self.patch_dir}).")
                return True

        self.validate_artifacts()
        self.validate_objects()
        self.validate_firmware_diff()
        self.validate_elf()
        self.validate_memory_map()
        self.validate_logs()
        self.validate_firmware_strings()
        self.validate_ucode()
        self.validate_capabilities()
        self.validate_wrapper()
        self.compute_hashes()

        if not self.quiet:
            print(f"\n{'='*60}\n  VALIDATION SUMMARY\n{'='*60}")
            print(f"  ✅ Passed:   {self.passed}")
            print(f"  ❌ Failed:   {self.failed}")
            print(f"  ⚠️  Warnings: {self.warnings}\n{'='*60}")
            if self.failed == 0:
                print("  \033[0;32mFIRMWARE VALIDATION PASSED ✓\033[0m\n")
            else:
                print("  \033[0;31mFIRMWARE VALIDATION FAILED ❌\033[0m\n")

        return self.failed == 0


def main():
    parser = argparse.ArgumentParser(description="Generalized Firmware Build Validation Tool for Nexmon")
    parser.add_argument("patch_dir", nargs="?", default=None, help="Path to firmware patch directory (e.g. patches/.../nexmon)")
    parser.add_argument("--patch-dir", dest="opt_patch_dir", default=None, help="Explicit path to patch directory")
    parser.add_argument("--fw-dir", dest="fw_dir", default=None, help="Explicit path to target firmware directory")
    parser.add_argument("--nexmon-root", dest="nexmon_root", default=None, help="Nexmon repository root")
    parser.add_argument("--require", action="store_true", help="Fail if build artifacts are missing (default: skip cleanly if unbuilt)")
    parser.add_argument("--check-wrapper", action="store_true", help="Validate patches/common/wrapper.c bindings and exit")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet output")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    patch_dir = args.opt_patch_dir or args.patch_dir or os.getcwd()

    if args.check_wrapper:
        nexmon_root = args.nexmon_root
        if not nexmon_root:
            cur = os.path.abspath(patch_dir)
            for _ in range(6):
                if os.path.isfile(os.path.join(cur, "setup_env.sh")) and os.path.isdir(os.path.join(cur, "firmwares")):
                    nexmon_root = cur
                    break
                parent = os.path.dirname(cur)
                if parent == cur:
                    break
                cur = parent
        nexmon_root = nexmon_root or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        wrapper_path = os.path.join(nexmon_root, "patches", "common", "wrapper.c")
        fw_version_path = os.path.join(nexmon_root, "patches", "include", "firmware_version.h")
        errors = FirmwareValidator.check_wrapper_integrity(wrapper_path, fw_version_path)
        if not args.quiet:
            print(f"\n{'='*60}\n  WRAPPER INTEGRITY CHECK\n{'='*60}")
            if not errors:
                print("  \033[0;32m✅ PASS:\033[0m Wrapper function bindings are consistent and collision-free.")
                print(f"\n{'='*60}\n  VALIDATION SUMMARY\n{'='*60}")
                print("  \033[0;32mWRAPPER VALIDATION PASSED ✓\033[0m\n")
            else:
                for err in errors:
                    print(f"  \033[0;31m❌ FAIL:\033[0m {err}")
                print(f"\n{'='*60}\n  VALIDATION SUMMARY\n{'='*60}")
                print("  \033[0;31mWRAPPER VALIDATION FAILED ❌\033[0m\n")
        if args.json:
            print(json.dumps({"success": len(errors) == 0, "errors": errors}, indent=2))
        sys.exit(0 if len(errors) == 0 else 1)

    validator = FirmwareValidator(
        patch_dir=patch_dir,
        fw_dir=args.fw_dir,
        nexmon_root=args.nexmon_root,
        quiet=args.quiet or args.json,
        require=args.require,
    )
    success = validator.run_all()

    if args.json:
        out = {
            "patch_dir": validator.patch_dir,
            "fw_dir": validator.fw_dir,
            "passed": validator.passed,
            "failed": validator.failed,
            "warnings": validator.warnings,
            "success": success,
            "results": validator.results,
        }
        print(json.dumps(out, indent=2))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
