# brcmfmac Version Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `nexfirmware.py versions` command that reports `brcmfmac` driver and running-firmware versions locally or over ADB.

**Architecture:** Add small local and ADB command runners, then inject the selected runner into a focused detector and pure kernel-log parser. Keep the existing `detect` command unchanged; add concise text and structured JSON rendering for the new report.

**Tech Stack:** Python 3 standard library (`argparse`, `dataclasses`, `subprocess`, `shlex`, `unittest`, `json`), Android ADB.

**Spec:** `docs/superpowers/specs/2026-11-09-brcmfmac-version-detection-design.md`

## Global Constraints

- Local detection is the default; ADB requires `--adb`, with optional `--serial SERIAL` and opt-in `--root`.
- Never use `adb shell -c`; invoke the Android remote shell directly.
- Do not modify local or remote system state, push files, load modules, or change Wi-Fi settings.
- Do not treat `bcmdhd` as `brcmfmac`, infer a driver version from the kernel release, or infer the running firmware version from filenames or arbitrary binary scans.
- A completed detection returns exit status 0 even when the driver is absent; command/transport failures are represented in the report, while CLI setup errors return 1.

## Review Focus

- Built-in driver with no `lsmod` entry: sysfs presence must yield `present`, not `not_found`; test in Task 1.
- Kernel log containing several firmware announcements: select the newest complete entry and preserve parenthesized build metadata; test in Task 1.
- Permission-denied `dmesg`: report firmware status `unavailable` and retain other successful results; test in Task 1.
- Multiple attached Android devices: pass `--serial` to every ADB invocation without interpolating it into shell text; test in Task 2.
- Android `modinfo` emitting large unrelated permission errors: do not copy the full stderr into the report; test concise warnings in Task 1.
- ADB executable missing or device disconnected: emit a clear CLI error and exit 1 rather than a partial success; test in Task 2.

---

### Task 1: Version Parsing and Local Detection

**Files:**
- Modify: `nexfirmware.py` near the existing detection data classes and `DeviceDetector`.
- Test: `tests/test_nexfirmware.py`.

**Interfaces:**
- Produces: `parse_brcmfmac_firmware_log(text: str) -> Dict[str, str]`, returning `version` and optional `fwid` from the newest matching entry, or an empty dictionary.
- Produces: `LocalCommandRunner.run(args: List[str]) -> subprocess.CompletedProcess`, with five-second timeouts and captured text output.
- Produces: `detect_brcmfmac_versions(runner: Any, target: Dict[str, Any]) -> Dict[str, Any]`.
- Report keys: `target`, `driver`, `firmware`, `warnings`; driver keys are `module_name`, `state` (`loaded`, `present`, or `not_found`), `version`, `version_source`, `module_path`, and `dependencies`; firmware keys are `status` (`found`, `not_found`, or `unavailable`), `version`, `fwid`, and `source`.

- [ ] **Step 1: Write failing parser tests**

Add tests using standard lines such as `brcmfmac: brcmf_c_preinit_dcmds: Firmware: BCM4345/6 wl0: ... version 7.45.189 (r724032 CY) FWID 01-140b2f`. Assert exact version/FWID extraction, newest-entry selection, and `{}` for unrelated or incomplete log text.

- [ ] **Step 2: Run parser tests and verify failure**

Run: `python -m pytest tests/test_nexfirmware.py -k firmware_log -v`
Expected: FAIL because `parse_brcmfmac_firmware_log` does not exist.

- [ ] **Step 3: Implement the parser**

Implement `parse_brcmfmac_firmware_log` by scanning matching `brcmfmac`/`Firmware:` lines in reverse and extracting `version` and optional `FWID`; do not reuse the generic binary version regex for log parsing.

- [ ] **Step 4: Run parser tests and verify success**

Run: `python -m pytest tests/test_nexfirmware.py -k firmware_log -v`
Expected: PASS.

- [ ] **Step 5: Write failing detector tests**

Use a fake runner keyed by exact argument lists. Cover: modular driver with `lsmod` and `modinfo`; built-in driver found only through `/sys/module/brcmfmac`; sysfs version taking precedence over `modinfo`; newest firmware log; absent driver; permission-denied `dmesg`; and concise one-line warnings for failed commands.

- [ ] **Step 6: Run detector tests and verify failure**

Run: `python -m pytest tests/test_nexfirmware.py -k brcmfmac_versions -v`
Expected: FAIL because the runner and detector do not exist.

- [ ] **Step 7: Implement local command execution and detection**

Implement `LocalCommandRunner` and `detect_brcmfmac_versions`. Query `lsmod`, `modinfo brcmfmac`, `test -d /sys/module/brcmfmac`, `cat /sys/module/brcmfmac/version`, and `dmesg`; parse only successful stdout, summarize failures without embedding multiline stderr, and continue after individual source failures.

- [ ] **Step 8: Run detector tests and the existing suite**

Run: `python -m pytest tests/test_nexfirmware.py -v`
Expected: all tests PASS.

### Task 2: ADB Transport and CLI Reporting

**Files:**
- Modify: `nexfirmware.py` imports, report renderers, parser, and `main()`.
- Test: `tests/test_nexfirmware.py`.

**Interfaces:**
- Consumes: Task 1 report shape and `detect_brcmfmac_versions`.
- Produces: `AdbCommandRunner(serial: Optional[str] = None, root: bool = False)` with the same `run(args: List[str])` interface as `LocalCommandRunner`.
- Produces: `print_version_report(report: Dict[str, Any], as_json: bool = False) -> None`.
- CLI: `nexfirmware.py versions [--adb] [--serial SERIAL] [--root]`; global `--json` remains supported.

- [ ] **Step 1: Write failing ADB runner tests**

Mock `subprocess.run` and assert the exact host argument vector for default ADB, serial-selected ADB, and root mode. Assert remote arguments are shell-quoted as one command, serial is a separate host argument, and no vector contains `shell -c`.

- [ ] **Step 2: Run ADB tests and verify failure**

Run: `python -m pytest tests/test_nexfirmware.py -k adb_command_runner -v`
Expected: FAIL because `AdbCommandRunner` does not exist.

- [ ] **Step 3: Implement ADB transport**

Build `adb [-s SERIAL] shell <remote-command>` using `shlex.join` for the fixed argument vector. For root mode, wrap the remote command with `su -c` and quote the nested command. Capture text and use a five-second timeout, matching `LocalCommandRunner`.

- [ ] **Step 4: Run ADB tests and verify success**

Run: `python -m pytest tests/test_nexfirmware.py -k adb_command_runner -v`
Expected: PASS.

- [ ] **Step 5: Write failing CLI and rendering tests**

Cover text and JSON reports for found and absent drivers; `--adb --serial ... --root` dispatch; rejection of `--serial`/`--root` without `--adb`; missing `adb` executable; and detector exceptions. Assert JSON is valid and warnings are emitted without multiline command noise.

- [ ] **Step 6: Run CLI tests and verify failure**

Run: `python -m pytest tests/test_nexfirmware.py -k versions_command -v`
Expected: FAIL because the subcommand and renderer do not exist.

- [ ] **Step 7: Implement CLI and output**

Add the `versions` parser and `print_version_report`. In `main()`, select the requested runner, include target type and serial in the report, print human or JSON output, and return 1 with a concise stderr message for setup/detection failures.

- [ ] **Step 8: Run all toolkit tests**

Run: `python -m pytest tests/test_nexfirmware.py -v`
Expected: all tests PASS.

### Task 3: Documentation and End-to-End Verification

**Files:**
- Modify: `README.md` firmware toolkit section.
- Verify: `nexfirmware.py`, `tests/test_nexfirmware.py`.

**Interfaces:**
- Consumes: the completed `versions` CLI from Task 2.

- [ ] **Step 1: Document the command**

Add local, ADB, serial/root, and JSON examples. State that detection is read-only and that permission-limited sources produce warnings rather than fabricated versions.

- [ ] **Step 2: Run static and regression checks**

Run: `python -m py_compile nexfirmware.py && python -m pytest tests/test_nexfirmware.py -v`
Expected: compilation succeeds and all tests PASS.

- [ ] **Step 3: Exercise local and connected-device behavior**

Run:
```sh
./nexfirmware.py versions
./nexfirmware.py --json versions
./nexfirmware.py versions --adb --serial 192.168.1.101:44601
./nexfirmware.py --json versions --adb --serial 192.168.1.101:44601
```
Expected: valid text/JSON in both modes. The Pixel 10 Pro reports `brcmfmac` as `not_found`, firmware as unavailable/not found according to log access, and no claim about `bcmdhd4390` being `brcmfmac`.

- [ ] **Step 4: Check the final workspace**

Run: `git status --short`
Expected: only the intended source, test, README, design, and plan files are changed; remove any generated cache/log artifacts created by the verification commands.
