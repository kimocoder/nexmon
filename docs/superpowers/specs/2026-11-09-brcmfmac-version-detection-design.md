# brcmfmac driver and firmware version detection

## Intent

Add a focused, read-only way to identify the `brcmfmac` driver and running firmware version on either the local Linux host or an Android device connected through ADB.

## Goals

- Add `nexfirmware.py versions`; local detection remains the default.
- Support `--adb`, optional `--serial SERIAL`, and opt-in `--root` for Android devices where `su` is available.
- Report driver presence/loading, module version and path when available, firmware version, FWID when available, and the source of each result.
- Preserve the existing global human-readable and `--json` output modes.
- Distinguish absence from inaccessible or unavailable information through warnings and structured status fields.
- Reuse the existing Broadcom/Cypress firmware-version parsing and add unit tests using mocked command output.

## Non-goals

- Do not detect or query the Broadcom `bcmdhd` driver as though it were `brcmfmac`.
- Do not load modules, change Wi-Fi state, push files, or modify device settings.
- Do not infer a driver version from the kernel release or infer firmware compatibility from filenames alone.

## Constraints and device findings

- The connected Pixel 10 Pro exposes `bcmdhd4390`, not `brcmfmac`, and has no `su`; the expected result there is an explicit `brcmfmac` absence, not a fabricated version.
- Android `adb shell` does not accept the host-style `-c` option; invoke the remote shell directly.
- Kernel logs and module files may be permission-denied. These failures must be reported without discarding results from other sources.

## Approaches

- **Extend `nexfirmware.py` (selected):** a `versions` subcommand fits the existing detection toolkit and reuses its parsers, JSON support, and tests.
- **Standalone script:** narrower initial diff, but duplicates transport, parsing, and CLI behavior and creates overlapping tools.

## Implementation outline

- Add a small command runner abstraction for local commands and ADB remote-shell commands, including optional device serial and `su -c` wrapping only when requested.
- Collect `lsmod`, `modinfo brcmfmac`, `/sys/module/brcmfmac/version`, and kernel-log output. Treat sysfs module presence as evidence that a built-in driver is present even when `lsmod` has no entry.
- Parse `brcmfmac` firmware announcements from newest kernel-log entry first. Do not scan arbitrary firmware binaries as a substitute for the running firmware in this focused command.
- Return a result containing target, driver, firmware, and warnings. Text output prints concise labeled values; JSON exposes the same information and source/status details.
- Add tests for modular and built-in drivers, standard firmware announcements, missing drivers, inaccessible logs, ADB command construction, JSON/text output, and CLI dispatch.

## Verification

Run the focused unit tests and the full existing `tests/test_nexfirmware.py` suite. Exercise local and ADB text/JSON commands. Confirm that the connected Pixel returns a clear `brcmfmac`-not-found result without changing the device.
