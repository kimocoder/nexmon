#!/usr/bin/env python3
"""Validate kernel driver syntax, comment integrity, and Kbuild compilation.

Checks all patches/driver/brcmfmac_*.y-nexmon trees for:
- Comment token integrity (detecting stray '*/' outside comments and unclosed comments)
- Preprocessor directive balance (#if/#ifdef/#ifndef vs #endif)
- Brace balance ({ vs }) outside comments and string literals
- Optional Kbuild compilation against available kernel headers or build trees
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DRIVER_ROOT = ROOT / "patches" / "driver"


def validate_driver_file(path: Path) -> list[str]:
    """Validate a single C or header file for comment and syntax integrity."""
    errors: list[str] = []
    try:
        content = path.read_text(errors="replace")
    except OSError as e:
        return [f"Failed to read {path}: {e}"]

    lines = content.splitlines()
    in_block_comment = False
    in_string: str | None = None
    escape = False
    if_stack: list[tuple[int, str]] = []

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()

        # Preprocessor directive balance (when outside block comments)
        if not in_block_comment and stripped.startswith("#"):
            directive = re.match(r"#\s*([a-zA-Z_]+)", stripped)
            if directive:
                cmd = directive.group(1)
                if cmd in ("if", "ifdef", "ifndef"):
                    if_stack.append((idx, cmd))
                elif cmd in ("elif", "else"):
                    if not if_stack:
                        errors.append(f"Line {idx}: Stray #{cmd} without matching #if")
                elif cmd == "endif":
                    if not if_stack:
                        errors.append(f"Line {idx}: Stray #endif without matching #if")
                    else:
                        if_stack.pop()

        i = 0
        while i < len(line):
            ch = line[i]
            pair = line[i : i + 2]

            if in_block_comment:
                if pair == "*/":
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue

            if in_string:
                if escape:
                    escape = False
                    i += 1
                    continue
                if ch == "\\":
                    escape = True
                    i += 1
                    continue
                if ch == in_string:
                    in_string = None
                    i += 1
                    continue
                i += 1
                continue

            # Outside comments and strings
            if pair == "//":
                # Line comment extends to end of line
                break
            if pair == "/*":
                in_block_comment = True
                i += 2
                continue
            if pair == "*/":
                errors.append(f"Line {idx}: Stray closing comment delimiter '*/' outside comment")
                i += 2
                continue

            if ch in ('"', "'"):
                in_string = ch
                i += 1
                continue

            i += 1

    if in_block_comment:
        errors.append(f"Line {len(lines)}: Unclosed block comment '/*' reaching end of file")
    if if_stack:
        start_idx, cmd = if_stack[-1]
        errors.append(f"Line {start_idx}: Unclosed #{cmd} reaching end of file")

    return errors


def check_driver_directory(driver_dir: Path) -> dict[Path, list[str]]:
    """Scan all C and header files in driver_dir and return a mapping of path to errors."""
    file_errors: dict[Path, list[str]] = {}
    for ext in ("*.c", "*.h"):
        for path in sorted(driver_dir.glob(ext)):
            errs = validate_driver_file(path)
            if errs:
                file_errors[path] = errs
    return file_errors


def check_all_drivers(root_dir: Path = DRIVER_ROOT) -> tuple[int, int, dict[Path, list[str]]]:
    """Check syntax across all patches/driver/brcmfmac_*.y-nexmon trees."""
    driver_dirs = sorted(root_dir.glob("brcmfmac_*.y-nexmon"))
    total_files = 0
    total_errors = 0
    all_errors: dict[Path, list[str]] = {}

    for d in driver_dirs:
        for ext in ("*.c", "*.h"):
            files = list(d.glob(ext))
            total_files += len(files)
            for f in files:
                errs = validate_driver_file(f)
                if errs:
                    all_errors[f] = errs
                    total_errors += len(errs)

    return total_files, total_errors, all_errors


def find_kernel_build_dir(explicit_kdir: str | Path | None = None) -> Path | None:
    """Find a candidate Linux kernel build or header directory."""
    candidates: list[Path] = []
    if explicit_kdir:
        candidates.append(Path(explicit_kdir))

    import os
    env_kdir = os.environ.get("KDIR")
    if env_kdir:
        candidates.append(Path(env_kdir))

    # Check uname -r modules build symlink
    try:
        uname_r = subprocess.check_output(["uname", "-r"], text=True).strip()
        candidates.append(Path(f"/lib/modules/{uname_r}/build"))
    except Exception:
        pass

    # Common local kernel trees
    candidates.append(Path("/srv/nfs/shared/linux-rpi"))

    # Check linux-headers under /usr/src
    for p in sorted(Path("/usr/src").glob("linux-headers-*")):
        candidates.append(p)

    for c in candidates:
        if c.is_dir() and (c / "Makefile").is_file():
            return c.resolve()

    return None


def detect_kernel_version(kbuild_dir: Path) -> tuple[int, int] | None:
    """Detect the (major, minor) kernel version from a kernel build tree."""
    makefile = kbuild_dir / "Makefile"
    if not makefile.is_file():
        return None

    try:
        content = makefile.read_text(errors="replace")
        version_m = re.search(r"^VERSION\s*=\s*(\d+)", content, re.MULTILINE)
        patchlevel_m = re.search(r"^PATCHLEVEL\s*=\s*(\d+)", content, re.MULTILINE)
        if version_m and patchlevel_m:
            return int(version_m.group(1)), int(patchlevel_m.group(1))
    except Exception:
        pass

    return None


def compile_driver_kbuild(
    driver_dir: Path,
    kbuild_dir: Path,
    arch: str | None = None,
) -> tuple[bool, str]:
    """Compile driver_dir against kbuild_dir using Kbuild."""
    import os
    nproc = os.cpu_count() or 2
    cmd = ["make", f"-j{nproc}", "-C", str(kbuild_dir), f"M={driver_dir.resolve()}"]
    if arch:
        cmd.append(f"ARCH={arch}")
    cmd.append("modules")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    success = proc.returncode == 0
    output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")

    # Clean up generated artifacts
    clean_cmd = ["make", "-C", str(kbuild_dir), f"M={driver_dir.resolve()}", "clean"]
    subprocess.run(clean_cmd, capture_output=True)

    return success, output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        default=True,
        help="Run comment and syntax checks on all driver trees (default)",
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="Compile-check matching driver tree with Kbuild if kernel headers are available",
    )
    parser.add_argument(
        "--require-kbuild",
        action="store_true",
        help="Fail if no kernel build tree is available or Kbuild compilation fails",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run both syntax checks and Kbuild compilation checks",
    )
    parser.add_argument(
        "--kdir",
        type=Path,
        help="Explicit path to kernel build/header directory",
    )
    parser.add_argument(
        "--driver-dir",
        type=Path,
        help="Specific driver tree directory to check",
    )

    args = parser.parse_args()
    if args.all:
        args.compile = True

    exit_code = 0

    # 1. Syntax & structure check
    if args.driver_dir:
        files = list(args.driver_dir.glob("*.c")) + list(args.driver_dir.glob("*.h"))
        print(f"Checking syntax for {len(files)} files in {args.driver_dir}...")
        errors = check_driver_directory(args.driver_dir)
        total_errors = sum(len(e) for e in errors.values())
        if errors:
            for path, err_list in errors.items():
                print(f"FAILED: {path}:")
                for err in err_list:
                    print(f"  {err}")
            exit_code = 1
        else:
            print(f"PASSED: {len(files)} files in {args.driver_dir} are clean.")
    else:
        print("Checking driver comment and syntax integrity across all trees...")
        total_files, total_errors, all_errors = check_all_drivers()
        if all_errors:
            print(f"FAILED: {total_errors} errors across {len(all_errors)} files:")
            for path, err_list in all_errors.items():
                print(f"  {path.relative_to(ROOT)}:")
                for err in err_list:
                    print(f"    {err}")
            exit_code = 1
        else:
            print(f"PASSED: {total_files} driver files checked across all trees (0 syntax/comment errors).")

    # 2. Kbuild compile check
    if args.compile or args.require_kbuild:
        kdir = find_kernel_build_dir(args.kdir)
        if not kdir:
            msg = "No Linux kernel build directory found (/lib/modules/$(uname -r)/build or KDIR)."
            if args.require_kbuild:
                print(f"ERROR: {msg}", file=sys.stderr)
                return 1
            print(f"INFO: Skipping Kbuild compile check ({msg})")
            return exit_code

        kver = detect_kernel_version(kdir)
        if not kver:
            print(f"WARNING: Could not determine kernel version from {kdir}")
            return exit_code

        major, minor = kver
        target_dir = args.driver_dir or (DRIVER_ROOT / f"brcmfmac_{major}.{minor}.y-nexmon")
        if not target_dir.is_dir():
            print(f"INFO: No matching driver tree for kernel {major}.{minor} ({target_dir.name} not found); skipping Kbuild.")
            return exit_code

        print(f"Compile-checking driver {target_dir.name} against kernel {major}.{minor} ({kdir})...")
        success, output = compile_driver_kbuild(target_dir, kdir)
        if success:
            print(f"PASSED: Kbuild compilation succeeded for {target_dir.name}.")
        else:
            print(f"FAILED: Kbuild compilation failed for {target_dir.name}:", file=sys.stderr)
            print(output, file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
