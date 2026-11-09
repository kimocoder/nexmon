#!/usr/bin/env python3
"""Unit tests for the nexfirmware toolkit (detection, reverse engineering, lifecycle).

Exercises detection routines, binary analysis, definitions derivation, disassembly,
pull, put, and edit functions without requiring active radio transmissions.
"""

import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

# Add root directory to path
ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

import nexfirmware


class TestDeviceDetection(unittest.TestCase):
    def test_detect_host(self):
        host = nexfirmware.DeviceDetector.detect_host()
        self.assertIsNotNone(host.model)
        self.assertIsNotNone(host.arch)
        self.assertIsNotNone(host.kernel)
        self.assertIsInstance(host.is_raspberry_pi, bool)

    def test_detect_hardware(self):
        devs = nexfirmware.DeviceDetector.detect_hardware()
        self.assertIsInstance(devs, list)
        if devs:
            d = devs[0]
            self.assertIn(d.bus_type, ("sdio", "pci", "usb", "unknown"))
            self.assertTrue(d.vendor_id.startswith("0x") or d.vendor_id == "unknown")

    def test_detect_driver(self):
        drv = nexfirmware.DeviceDetector.detect_driver()
        self.assertEqual(drv.module_name, "brcmfmac")
        self.assertIsInstance(drv.loaded, bool)
        self.assertIsInstance(drv.is_nexmon, bool)

    def test_full_detection(self):
        rep = nexfirmware.DeviceDetector.full_detection()
        self.assertIsNotNone(rep.chip_name)
        self.assertIsNotNone(rep.host)
        self.assertIsNotNone(rep.driver)


class TestBrcmfmacFirmwareLog(unittest.TestCase):
    def test_firmware_log_extracts_version_and_fwid(self):
        line = (
            "[  124.000100] brcmfmac: brcmf_c_preinit_dcmds: Firmware: "
            "BCM4345/6 wl0: Mar 23 2020 02:40:48 version "
            "7.45.189 (r724032 CY) FWID 01-140b2f"
        )

        result = nexfirmware.parse_brcmfmac_firmware_log(line)

        self.assertEqual(
            result, {"version": "7.45.189 (r724032 CY)", "fwid": "01-140b2f"}
        )

    def test_firmware_log_uses_newest_complete_announcement(self):
        text = "\n".join(
            [
                "brcmfmac: Firmware: BCM4339 version 6.37.34.43 FWID 01-old",
                "brcmfmac: Firmware: BCM4345/6 version 7.45.265 (28bca26 CY) FWID 01-c0ffee",
                "brcmfmac: Firmware: incomplete final announcement",
            ]
        )

        result = nexfirmware.parse_brcmfmac_firmware_log(text)

        self.assertEqual(
            result, {"version": "7.45.265 (28bca26 CY)", "fwid": "01-c0ffee"}
        )

    def test_firmware_log_rejects_unrelated_and_incomplete_lines(self):
        text = "\n".join(
            [
                "bcmdhd: Firmware: BCM4390 version 27.10.1121.57",
                "brcmfmac: Firmware: no version announced",
            ]
        )

        self.assertEqual(nexfirmware.parse_brcmfmac_firmware_log(text), {})


class FakeCommandRunner:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def run(self, args):
        self.calls.append(args)
        return self.responses.get(
            tuple(args),
            subprocess.CompletedProcess(args, 1, stdout="", stderr="not found"),
        )


class TestBrcmfmacVersionDetection(unittest.TestCase):
    def test_brcmfmac_versions_local_runner_captures_command_output(self):
        completed = subprocess.CompletedProcess(["lsmod"], 0, stdout="", stderr="")
        with mock.patch.object(
            nexfirmware.subprocess, "run", return_value=completed
        ) as run:
            result = nexfirmware.LocalCommandRunner().run(["lsmod"])

        self.assertIs(result, completed)
        run.assert_called_once_with(
            ["lsmod"], capture_output=True, text=True, timeout=5
        )

    def test_brcmfmac_versions_modular_driver_and_firmware(self):
        runner = FakeCommandRunner(
            {
                ("lsmod",): subprocess.CompletedProcess(
                    ["lsmod"],
                    0,
                    stdout="brcmfmac 409600 0 brcmutil,cfg80211\n",
                    stderr="",
                ),
                ("modinfo", "brcmfmac"): subprocess.CompletedProcess(
                    ["modinfo", "brcmfmac"],
                    0,
                    stdout=(
                        "version: 6.12.1-modinfo\n"
                        "filename: /lib/modules/brcmfmac.ko\n"
                    ),
                    stderr="",
                ),
                ("test", "-d", "/sys/module/brcmfmac"): subprocess.CompletedProcess(
                    ["test"], 0
                ),
                ("cat", "/sys/module/brcmfmac/version"): subprocess.CompletedProcess(
                    ["cat"], 0, stdout="6.12.1-sysfs\n", stderr=""
                ),
                ("dmesg",): subprocess.CompletedProcess(
                    ["dmesg"],
                    0,
                    stdout=(
                        "brcmfmac: Firmware: BCM4345/6 version "
                        "7.45.265 (28bca26 CY) FWID 01-c0ffee\n"
                    ),
                    stderr="",
                ),
            }
        )

        report = nexfirmware.detect_brcmfmac_versions(runner, {"type": "local"})

        self.assertEqual(report["driver"]["state"], "loaded")
        self.assertEqual(report["driver"]["version"], "6.12.1-sysfs")
        self.assertEqual(report["driver"]["version_source"], "sysfs")
        self.assertEqual(report["driver"]["module_path"], "/lib/modules/brcmfmac.ko")
        self.assertEqual(report["driver"]["dependencies"], ["brcmutil", "cfg80211"])
        self.assertEqual(
            report["firmware"],
            {
                "status": "found",
                "version": "7.45.265 (28bca26 CY)",
                "fwid": "01-c0ffee",
                "source": "kernel_log",
            },
        )

    def test_brcmfmac_versions_detects_built_in_driver_without_module_version(self):
        runner = FakeCommandRunner(
            {
                ("lsmod",): subprocess.CompletedProcess(["lsmod"], 0),
                ("test", "-d", "/sys/module/brcmfmac"): subprocess.CompletedProcess(
                    ["test"], 0
                ),
                ("dmesg",): subprocess.CompletedProcess(["dmesg"], 0),
            }
        )

        report = nexfirmware.detect_brcmfmac_versions(runner, {"type": "local"})

        self.assertEqual(report["driver"]["state"], "present")
        self.assertIsNone(report["driver"]["version"])
        self.assertEqual(report["firmware"]["status"], "not_found")

    def test_brcmfmac_versions_distinguishes_absent_driver_and_denied_logs(self):
        runner = FakeCommandRunner(
            {
                ("dmesg",): subprocess.CompletedProcess(
                    ["dmesg"], 1, stdout="", stderr="dmesg: Permission denied"
                ),
                ("modinfo", "brcmfmac"): subprocess.CompletedProcess(
                    ["modinfo", "brcmfmac"],
                    1,
                    stdout="",
                    stderr="unrelated permission error\nmodinfo: brcmfmac: not found",
                ),
            }
        )

        report = nexfirmware.detect_brcmfmac_versions(runner, {"type": "local"})

        self.assertEqual(report["driver"]["state"], "not_found")
        self.assertEqual(report["firmware"]["status"], "unavailable")
        self.assertTrue(any("Permission denied" in item for item in report["warnings"]))
        self.assertTrue(all("\n" not in item for item in report["warnings"]))
        self.assertFalse(any("unrelated permission error" in item for item in report["warnings"]))


class TestAdbCommandRunner(unittest.TestCase):
    def test_adb_command_runner_uses_direct_remote_shell(self):
        completed = subprocess.CompletedProcess(["adb"], 0)
        with mock.patch.object(
            nexfirmware.subprocess, "run", return_value=completed
        ) as run:
            result = nexfirmware.AdbCommandRunner().run(["dmesg"])

        self.assertIs(result, completed)
        run.assert_called_once_with(
            ["adb", "shell", "dmesg"],
            capture_output=True,
            text=True,
            timeout=5,
        )

    def test_adb_command_runner_keeps_serial_outside_remote_command(self):
        with mock.patch.object(nexfirmware.subprocess, "run") as run:
            nexfirmware.AdbCommandRunner(serial="192.168.1.20:5555").run(["lsmod"])

        run.assert_called_once_with(
            ["adb", "-s", "192.168.1.20:5555", "shell", "lsmod"],
            capture_output=True,
            text=True,
            timeout=5,
        )

    def test_adb_command_runner_quotes_root_remote_command(self):
        with mock.patch.object(nexfirmware.subprocess, "run") as run:
            nexfirmware.AdbCommandRunner(root=True).run(
                ["cat", "/sys/module/brcmfmac/version"]
            )

        run.assert_called_once_with(
            [
                "adb",
                "shell",
                "su",
                "-c",
                "'cat /sys/module/brcmfmac/version'",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )


class TestFirmwareReverseEngineering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock_fw = ROOT / "firmwares/bcm43455c0/7_45_265-28bca26-CY/cyfmac43455-sdio-standard.bin"
        if not cls.stock_fw.is_file():
            raise unittest.SkipTest("Stock firmware binary not present")

    def test_analyze_stock_firmware(self):
        rep = nexfirmware.FirmwareReverseEngineer.analyze_firmware(str(self.stock_fw))
        self.assertEqual(rep.file_size, 609309)
        self.assertEqual(rep.version_string, "7.45.265 (28bca26 CY)")
        self.assertEqual(rep.ucode_start, 0x21F24C)
        self.assertEqual(rep.reclaim_0_end, 0x22CAD4)
        self.assertEqual(rep.ucode_write_bl_hook, 0x20EF78)
        self.assertEqual(rep.templateram_start, 0x22C1F4)
        self.assertEqual(rep.templateram_size, 0x8E0)
        self.assertGreater(len(rep.flash_patches), 200)
        self.assertIn("NEXMON_CHIP=CHIP_VER_BCM43455c0", rep.definitions_mk)
        self.assertFalse(rep.is_nexmon_patched)

    def test_disassemble_range(self):
        lines = nexfirmware.FirmwareReverseEngineer.disassemble_range(
            str(self.stock_fw), 0x20EF78, count_bytes=16
        )
        self.assertGreater(len(lines), 0)
        # BL hook to wlc_ucode_write
        full_text = " ".join(lines)
        self.assertIn("bl", full_text)

    def test_extract_ucode(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-ucode-") as tmp:
            out_file = Path(tmp) / "ucode.bin"
            ok, msg = nexfirmware.FirmwareReverseEngineer.extract_ucode(str(self.stock_fw), str(out_file))
            self.assertTrue(ok, msg)
            self.assertTrue(out_file.is_file())
            # Microcode magic at start
            ucode_bytes = out_file.read_bytes()
            self.assertEqual(ucode_bytes[:8], nexfirmware.FirmwareReverseEngineer.UCODE_MAGIC)

    def test_strings_tool_uses_offsets_and_minimum_length(self):
        completed = subprocess.CompletedProcess(
            ["strings"], 0, stdout="10 firmware-version\n", stderr=""
        )
        with (
            mock.patch.object(
                nexfirmware.shutil, "which", return_value="/usr/bin/strings"
            ),
            mock.patch.object(
                nexfirmware.subprocess, "run", return_value=completed
            ) as run,
        ):
            result = nexfirmware.FirmwareReverseEngineer.extract_strings(
                str(self.stock_fw), min_length=8
            )

        command = run.call_args.args[0]
        self.assertEqual(command[:6], ["/usr/bin/strings", "-a", "-t", "x", "-n", "8"])
        self.assertEqual(result["output"], "10 firmware-version\n")

    def test_binwalk_report_can_be_saved(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-binwalk-") as tmp:
            output = Path(tmp) / "reports" / "binwalk.txt"
            completed = subprocess.CompletedProcess(
                ["binwalk"], 0, stdout="DECIMAL HEX DESCRIPTION\n", stderr=""
            )
            with (
                mock.patch.object(
                    nexfirmware.shutil, "which", return_value="/usr/bin/binwalk"
                ),
                mock.patch.object(
                    nexfirmware.subprocess, "run", return_value=completed
                ),
            ):
                result = nexfirmware.FirmwareReverseEngineer.scan_binwalk(
                    str(self.stock_fw), output_file=str(output)
                )

            self.assertEqual(output.read_text(), "DECIMAL HEX DESCRIPTION\n")
            self.assertEqual(result["output_path"], str(output))
            self.assertIsNone(result["output"])

    def test_requested_missing_analysis_tool_is_an_error(self):
        with mock.patch.object(nexfirmware.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "binwalk is not installed"):
                nexfirmware.FirmwareReverseEngineer.scan_binwalk(str(self.stock_fw))


class TestFirmwareLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock_fw = ROOT / "firmwares/bcm43455c0/7_45_265-28bca26-CY/cyfmac43455-sdio-standard.bin"
        if not cls.stock_fw.is_file():
            raise unittest.SkipTest("Stock firmware binary not present")

    def test_edit_firmware(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-edit-") as tmp:
            tmp_dir = Path(tmp)
            orig_copy = tmp_dir / "firmware.bin"
            shutil.copy2(self.stock_fw, orig_copy)

            out_copy = tmp_dir / "firmware_edited.bin"
            # Apply a test patch at 0x198000
            res = nexfirmware.FirmwareManager.edit(
                str(orig_copy),
                out_file=str(out_copy),
                patches=[(0x198000, b"\x12\x34\x56\x78")]
            )
            self.assertTrue(out_copy.is_file())
            self.assertNotEqual(res["original_sha256"], res["modified_sha256"])
            modified_bytes = out_copy.read_bytes()
            self.assertEqual(modified_bytes[:4], b"\x12\x34\x56\x78")

    def test_edit_rejects_negative_patch_offset(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-edit-negative-") as tmp:
            source = Path(tmp) / "firmware.bin"
            source.write_bytes(b"abcdefgh")

            with self.assertRaisesRegex(ValueError, "non-negative"):
                nexfirmware.FirmwareManager.edit(
                    str(source), patches=[(-1, b"ZZ")]
                )

            self.assertEqual(source.read_bytes(), b"abcdefgh")

    def test_edit_rejects_patch_past_end_without_writing_output(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-edit-bounds-") as tmp:
            source = Path(tmp) / "firmware.bin"
            output = Path(tmp) / "edited.bin"
            source.write_bytes(b"abcdefgh")

            with self.assertRaisesRegex(ValueError, "exceeds file size"):
                nexfirmware.FirmwareManager.edit(
                    str(source), out_file=str(output), patches=[(7, b"ZZ")]
                )

            self.assertEqual(source.read_bytes(), b"abcdefgh")
            self.assertFalse(output.exists())

    def test_put_rejects_non_basename_destination(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-put-name-") as tmp:
            source = Path(tmp) / "firmware.bin"
            source.write_bytes(b"firmware")

            for invalid_name in (
                "",
                "../escaped.bin",
                "/tmp/escaped.bin",
                "sub/fw.bin",
                "..",
            ):
                with self.subTest(name=invalid_name):
                    with self.assertRaisesRegex(ValueError, "must be a basename"):
                        nexfirmware.FirmwareManager.put(
                            str(source),
                            dest_name=invalid_name,
                            update_alternatives=False,
                        )

    def test_put_atomically_replaces_existing_firmware(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-put-atomic-") as tmp:
            root = Path(tmp)
            install_dir = root / "install"
            install_dir.mkdir()
            source = root / "firmware.bin"
            source.write_bytes(b"N" * 100001)
            target = install_dir / "installed.bin"
            target.write_bytes(b"old firmware")
            detection = SimpleNamespace(active_firmware=None)

            with (
                mock.patch.object(nexfirmware.os, "geteuid", return_value=0),
                mock.patch.object(
                    nexfirmware.FirmwareManager, "INSTALL_DIR", install_dir
                ),
                mock.patch.object(
                    nexfirmware.DeviceDetector,
                    "full_detection",
                    return_value=detection,
                ),
            ):
                result = nexfirmware.FirmwareManager.put(
                    str(source),
                    dest_name="installed.bin",
                    update_alternatives=False,
                    backup_current=False,
                )

            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(result["installed_path"], str(target))
            self.assertEqual(list(install_dir.glob(".*.tmp")), [])

    def test_put_keeps_existing_target_when_atomic_publish_fails(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-put-failure-") as tmp:
            root = Path(tmp)
            install_dir = root / "install"
            install_dir.mkdir()
            source = root / "firmware.bin"
            source.write_bytes(b"N" * 100001)
            target = install_dir / "installed.bin"
            target.write_bytes(b"old firmware")
            detection = SimpleNamespace(active_firmware=None)

            with (
                mock.patch.object(nexfirmware.os, "geteuid", return_value=0),
                mock.patch.object(
                    nexfirmware.FirmwareManager, "INSTALL_DIR", install_dir
                ),
                mock.patch.object(
                    nexfirmware.DeviceDetector,
                    "full_detection",
                    return_value=detection,
                ),
                mock.patch.object(
                    nexfirmware.os, "replace", side_effect=OSError("publish failed")
                ),
            ):
                with self.assertRaisesRegex(OSError, "publish failed"):
                    nexfirmware.FirmwareManager.put(
                        str(source),
                        dest_name="installed.bin",
                        update_alternatives=False,
                        backup_current=False,
                    )

            self.assertEqual(target.read_bytes(), b"old firmware")
            self.assertEqual(list(install_dir.glob(".*.tmp")), [])

    def test_put_propagates_activation_failure(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-put-activate-") as tmp:
            root = Path(tmp)
            install_dir = root / "install"
            source = root / "firmware.bin"
            source.write_bytes(b"N" * 100001)
            detection = SimpleNamespace(active_firmware=None)

            with (
                mock.patch.object(nexfirmware.os, "geteuid", return_value=0),
                mock.patch.object(
                    nexfirmware.FirmwareManager, "INSTALL_DIR", install_dir
                ),
                mock.patch.object(
                    nexfirmware.DeviceDetector,
                    "full_detection",
                    return_value=detection,
                ),
                mock.patch.object(
                    nexfirmware.shutil,
                    "which",
                    return_value="/usr/bin/update-alternatives",
                ),
                mock.patch.object(
                    nexfirmware.subprocess,
                    "run",
                    side_effect=subprocess.CalledProcessError(
                        1, ["update-alternatives"], stderr="activation failed"
                    ),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "activation failed"):
                    nexfirmware.FirmwareManager.put(
                        str(source),
                        update_alternatives=True,
                        backup_current=False,
                    )

    def test_put_propagates_driver_reload_failure(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-put-reload-") as tmp:
            root = Path(tmp)
            install_dir = root / "install"
            source = root / "firmware.bin"
            source.write_bytes(b"N" * 100001)
            detection = SimpleNamespace(active_firmware=None)

            with (
                mock.patch.object(nexfirmware.os, "geteuid", return_value=0),
                mock.patch.object(
                    nexfirmware.FirmwareManager, "INSTALL_DIR", install_dir
                ),
                mock.patch.object(
                    nexfirmware.DeviceDetector,
                    "full_detection",
                    return_value=detection,
                ),
                mock.patch.object(
                    nexfirmware.shutil, "which", return_value="/usr/sbin/modprobe"
                ),
                mock.patch.object(
                    nexfirmware.subprocess,
                    "run",
                    side_effect=subprocess.CalledProcessError(
                        1, ["modprobe"], stderr="reload failed"
                    ),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "reload failed"):
                    nexfirmware.FirmwareManager.put(
                        str(source),
                        update_alternatives=False,
                        reload_driver=True,
                        backup_current=False,
                    )

    @staticmethod
    def _restore_detection(active_path: Path):
        active_data = active_path.read_bytes()
        return SimpleNamespace(
            chip_name="BCM43455c0",
            chip_num=0x4345,
            chip_rev=6,
            active_firmware=SimpleNamespace(
                active_path=str(active_path),
                symlink_path="/etc/alternatives/cyfmac43455-sdio.bin",
                file_size=len(active_data),
                version_string=nexfirmware.extract_firmware_version(active_data),
                is_nexmon=b"nexmon" in active_data.lower(),
            ),
        )

    def test_find_original_prefers_registered_stock_and_rejects_nexmon(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-find-original-") as tmp:
            root = Path(tmp)
            active = root / "active-nexmon.bin"
            active.write_bytes(b"7.45.265 (28bca26 CY) nexmon.org" + b"\0" * 100000)
            stock = root / "cyfmac43455-sdio-standard.bin"
            stock.write_bytes(b"7.45.265 (28bca26 CY) stock" + b"\0" * 100000)
            patched_candidate = root / "cyfmac43455-sdio-minimal.bin"
            patched_candidate.write_bytes(b"NEXMON" + b"\0" * 100000)
            detection = self._restore_detection(active)

            with (
                mock.patch.object(
                    nexfirmware.FirmwareManager,
                    "_list_alternatives",
                    return_value=[patched_candidate, stock],
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager, "SYSTEM_FIRMWARE_DIRS", ()
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager,
                    "REPO_FIRMWARE_DIR",
                    root / "repository",
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager, "INSTALL_DIR", root / "installed"
                ),
            ):
                found = nexfirmware.FirmwareManager.find_original_firmware(detection)

            self.assertEqual(found["selected"]["path"], str(stock.resolve()))
            self.assertEqual(found["selected"]["origin"], "alternatives")
            self.assertNotIn(
                str(patched_candidate.resolve()),
                [candidate["path"] for candidate in found["candidates"]],
            )

    def test_restore_dry_run_finds_original_without_root_or_writes(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-restore-plan-") as tmp:
            root = Path(tmp)
            active = root / "active.bin"
            active_bytes = b"7.45.265 (28bca26 CY) nexmon.org" + b"\0" * 100000
            active.write_bytes(active_bytes)
            stock = root / "cyfmac43455-sdio-standard.bin"
            stock.write_bytes(b"7.45.265 (28bca26 CY) stock" + b"\0" * 100000)
            detection = self._restore_detection(active)

            with (
                mock.patch.object(
                    nexfirmware.DeviceDetector,
                    "full_detection",
                    return_value=detection,
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager,
                    "_list_alternatives",
                    return_value=[stock],
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager, "SYSTEM_FIRMWARE_DIRS", ()
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager,
                    "REPO_FIRMWARE_DIR",
                    root / "repository",
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager, "INSTALL_DIR", root / "installed"
                ),
                mock.patch.object(nexfirmware.os, "geteuid", return_value=1000),
                mock.patch.object(
                    nexfirmware.shutil,
                    "which",
                    return_value="/usr/bin/update-alternatives",
                ),
            ):
                result = nexfirmware.FirmwareManager.restore(dry_run=True)

            self.assertTrue(result["dry_run"])
            self.assertEqual(result["activation"], "update-alternatives")
            self.assertEqual(active.read_bytes(), active_bytes)
            self.assertFalse((root / "installed").exists())

    def test_restore_activates_registered_original_and_backs_up_current(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-restore-alt-") as tmp:
            root = Path(tmp)
            install_dir = root / "installed"
            active = root / "active.bin"
            active_bytes = b"7.45.265 (28bca26 CY) nexmon.org" + b"\0" * 100000
            active.write_bytes(active_bytes)
            stock = root / "cyfmac43455-sdio-standard.bin"
            stock.write_bytes(b"7.45.265 (28bca26 CY) stock" + b"\0" * 100000)
            detection = self._restore_detection(active)

            with (
                mock.patch.object(
                    nexfirmware.DeviceDetector,
                    "full_detection",
                    return_value=detection,
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager,
                    "_list_alternatives",
                    return_value=[stock],
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager, "SYSTEM_FIRMWARE_DIRS", ()
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager,
                    "REPO_FIRMWARE_DIR",
                    root / "repository",
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager, "INSTALL_DIR", install_dir
                ),
                mock.patch.object(nexfirmware.os, "geteuid", return_value=0),
                mock.patch.object(
                    nexfirmware.shutil,
                    "which",
                    return_value="/usr/bin/update-alternatives",
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager, "_run_required"
                ) as run_required,
            ):
                result = nexfirmware.FirmwareManager.restore()

            self.assertEqual(result["activation"], "update-alternatives")
            backup = Path(result["backup_created"])
            self.assertEqual(backup.read_bytes(), active_bytes)
            run_required.assert_called_once_with(
                [
                    "/usr/bin/update-alternatives",
                    "--set",
                    "cyfmac43455-sdio.bin",
                    str(stock),
                ],
                "original firmware activation",
            )

    def test_restore_falls_back_to_atomic_replacement(self):
        with tempfile.TemporaryDirectory(prefix="nex-test-restore-copy-") as tmp:
            root = Path(tmp)
            active = root / "active.bin"
            active.write_bytes(b"7.45.265 (28bca26 CY) nexmon.org" + b"\0" * 100000)
            stock = root / "cyfmac43455-sdio-standard.bin"
            stock_data = b"7.45.265 (28bca26 CY) stock" + b"\0" * 100000
            stock.write_bytes(stock_data)
            detection = self._restore_detection(active)

            with (
                mock.patch.object(
                    nexfirmware.DeviceDetector,
                    "full_detection",
                    return_value=detection,
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager,
                    "_list_alternatives",
                    return_value=[],
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager,
                    "SYSTEM_FIRMWARE_DIRS",
                    (root,),
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager,
                    "REPO_FIRMWARE_DIR",
                    root / "repository",
                ),
                mock.patch.object(
                    nexfirmware.FirmwareManager, "INSTALL_DIR", root / "installed"
                ),
                mock.patch.object(nexfirmware.os, "geteuid", return_value=0),
                mock.patch.object(nexfirmware.shutil, "which", return_value=None),
            ):
                result = nexfirmware.FirmwareManager.restore(backup_current=False)

            self.assertEqual(result["activation"], "atomic-replacement")
            self.assertEqual(active.read_bytes(), stock_data)


class TestFirmwareCli(unittest.TestCase):
    def test_reverse_tool_options(self):
        args = nexfirmware.build_parser().parse_args(
            ["reverse", "firmware.bin", "--strings", "--binwalk", "scan.txt"]
        )
        self.assertEqual(args.strings, "-")
        self.assertEqual(args.binwalk, "scan.txt")

    def test_restore_options(self):
        args = nexfirmware.build_parser().parse_args(
            ["restore", "--source", "stock.bin", "--reload", "--dry-run"]
        )
        self.assertEqual(args.source, "stock.bin")
        self.assertTrue(args.reload)
        self.assertTrue(args.dry_run)


class TestVersionsCommand(unittest.TestCase):
    @staticmethod
    def _report(state="loaded"):
        return {
            "target": {"type": "local", "serial": None},
            "driver": {
                "module_name": "brcmfmac",
                "state": state,
                "version": "6.12.1" if state == "loaded" else None,
                "version_source": "sysfs" if state == "loaded" else None,
                "module_path": "/lib/modules/brcmfmac.ko" if state == "loaded" else None,
                "dependencies": ["cfg80211"] if state == "loaded" else [],
            },
            "firmware": {
                "status": "found" if state == "loaded" else "unavailable",
                "version": "7.45.265 (28bca26 CY)" if state == "loaded" else None,
                "fwid": "01-c0ffee" if state == "loaded" else None,
                "source": "kernel_log" if state == "loaded" else None,
            },
            "warnings": [],
        }

    def test_versions_command_json_renderer_preserves_report(self):
        report = self._report()
        stdout = io.StringIO()
        with mock.patch.object(nexfirmware.sys, "stdout", stdout):
            nexfirmware.print_version_report(report, as_json=True)

        self.assertEqual(nexfirmware.json.loads(stdout.getvalue()), report)

    def test_versions_command_text_renderer_shows_absence_and_warnings(self):
        report = self._report(state="not_found")
        report["warnings"] = ["dmesg: Permission denied"]
        stdout = io.StringIO()
        with mock.patch.object(nexfirmware.sys, "stdout", stdout):
            nexfirmware.print_version_report(report)

        output = stdout.getvalue()
        self.assertIn("Driver: brcmfmac (not found)", output)
        self.assertIn("Firmware version: unavailable", output)
        self.assertIn("dmesg: Permission denied", output)

    def test_versions_command_adb_dispatch_checks_connection(self):
        report = self._report()
        runner = mock.Mock()
        with (
            mock.patch.object(
                nexfirmware.sys,
                "argv",
                [
                    "nexfirmware",
                    "versions",
                    "--adb",
                    "--serial",
                    "192.168.1.20:5555",
                    "--root",
                ],
            ),
            mock.patch.object(nexfirmware.shutil, "which", return_value="/usr/bin/adb"),
            mock.patch.object(nexfirmware, "AdbCommandRunner", return_value=runner) as cls,
            mock.patch.object(
                nexfirmware, "detect_brcmfmac_versions", return_value=report
            ) as detect,
            mock.patch.object(nexfirmware, "print_version_report") as print_report,
        ):
            status = nexfirmware.main()

        self.assertEqual(status, 0)
        cls.assert_called_once_with(serial="192.168.1.20:5555", root=True)
        runner.check_connection.assert_called_once_with()
        detect.assert_called_once_with(
            runner, {"type": "adb", "serial": "192.168.1.20:5555"}
        )
        print_report.assert_called_once_with(report, as_json=False)

    def test_versions_command_rejects_adb_options_in_local_mode(self):
        for option in (["--serial", "device"], ["--root"]):
            with self.subTest(option=option):
                stderr = io.StringIO()
                with (
                    mock.patch.object(
                        nexfirmware.sys, "argv", ["nexfirmware", "versions"] + option
                    ),
                    mock.patch.object(nexfirmware.sys, "stderr", stderr),
                ):
                    status = nexfirmware.main()

                self.assertEqual(status, 1)
                self.assertIn("require --adb", stderr.getvalue())

    def test_versions_command_missing_adb_is_an_error(self):
        stderr = io.StringIO()
        with (
            mock.patch.object(
                nexfirmware.sys, "argv", ["nexfirmware", "versions", "--adb"]
            ),
            mock.patch.object(nexfirmware.shutil, "which", return_value=None),
            mock.patch.object(nexfirmware.sys, "stderr", stderr),
        ):
            status = nexfirmware.main()

        self.assertEqual(status, 1)
        self.assertIn("adb executable not found", stderr.getvalue())

    def test_versions_command_disconnected_adb_is_an_error(self):
        runner = mock.Mock()
        runner.check_connection.side_effect = RuntimeError("device offline")
        stderr = io.StringIO()
        with (
            mock.patch.object(
                nexfirmware.sys, "argv", ["nexfirmware", "versions", "--adb"]
            ),
            mock.patch.object(nexfirmware.shutil, "which", return_value="/usr/bin/adb"),
            mock.patch.object(nexfirmware, "AdbCommandRunner", return_value=runner),
            mock.patch.object(nexfirmware.sys, "stderr", stderr),
        ):
            status = nexfirmware.main()

        self.assertEqual(status, 1)
        self.assertIn("device offline", stderr.getvalue())

    def test_versions_command_detector_exception_is_an_error(self):
        stderr = io.StringIO()
        with (
            mock.patch.object(nexfirmware.sys, "argv", ["nexfirmware", "versions"]),
            mock.patch.object(
                nexfirmware,
                "detect_brcmfmac_versions",
                side_effect=RuntimeError("detection failed"),
            ),
            mock.patch.object(nexfirmware.sys, "stderr", stderr),
        ):
            status = nexfirmware.main()

        self.assertEqual(status, 1)
        self.assertIn("detection failed", stderr.getvalue())

    def test_scaffold_patch_dry_run(self):
        """Test scaffolding in dry-run mode without touching disk."""
        res = nexfirmware.FirmwarePatchScaffolder.scaffold_patch(
            chip="bcm43455c0",
            version="7_45_189",
            dry_run=True,
        )
        self.assertEqual(res.chip, "bcm43455c0")
        self.assertEqual(res.version, "7_45_189")
        self.assertEqual(res.variant, "nexmon")
        self.assertEqual(len(res.created_files), 3)
        self.assertIn("NEXMON_CHIP", res.definitions)
        self.assertEqual(res.definitions["NEXMON_CHIP"], "CHIP_VER_BCM43455c0")

    def test_scaffold_patch_write_and_overwrite_guards(self):
        """Test full disk generation of version.mk, Makefile, and patch.c."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p_root = Path(tmpdir) / "patches"
            f_root = Path(tmpdir) / "firmwares"

            # Create mock definitions.mk
            mock_fw_dir = f_root / "bcm43999" / "1_2_3"
            mock_fw_dir.mkdir(parents=True)
            defs_file = mock_fw_dir / "definitions.mk"
            defs_file.write_text("NEXMON_CHIP=CHIP_VER_BCM43999\nNEXMON_FW_VERSION=FW_VER_1_2_3\n")

            res = nexfirmware.FirmwarePatchScaffolder.scaffold_patch(
                chip="bcm43999",
                version="1_2_3",
                patches_root=p_root,
                firmwares_root=f_root,
            )
            self.assertEqual(len(res.created_files), 3)

            version_mk = p_root / "bcm43999" / "1_2_3" / "version.mk"
            makefile = p_root / "bcm43999" / "1_2_3" / "nexmon" / "Makefile"
            patch_c = p_root / "bcm43999" / "1_2_3" / "nexmon" / "src" / "patch.c"

            self.assertTrue(version_mk.is_file())
            self.assertTrue(makefile.is_file())
            self.assertTrue(patch_c.is_file())

            # Check contents
            self.assertIn("FW_PATH=$(NEXMON_ROOT)/firmwares/bcm43999/1_2_3", version_mk.read_text())
            self.assertIn("firmware_patch.mk", makefile.read_text())
            self.assertIn("CHIP_VER_BCM43999", patch_c.read_text())
            self.assertIn("FW_VER_1_2_3", patch_c.read_text())

            # Attempt overwrite without force must raise FileExistsError
            with self.assertRaises(FileExistsError):
                nexfirmware.FirmwarePatchScaffolder.scaffold_patch(
                    chip="bcm43999",
                    version="1_2_3",
                    patches_root=p_root,
                    firmwares_root=f_root,
                    force=False,
                )

            # Overwrite with force=True must succeed
            res_force = nexfirmware.FirmwarePatchScaffolder.scaffold_patch(
                chip="bcm43999",
                version="1_2_3",
                patches_root=p_root,
                firmwares_root=f_root,
                force=True,
            )
            self.assertEqual(len(res_force.created_files), 3)

    def test_init_patch_cli_dispatch(self):
        """Test nexfirmware init-patch CLI command dispatch."""
        stdout = io.StringIO()
        with (
            mock.patch.object(
                nexfirmware.sys,
                "argv",
                ["nexfirmware", "init-patch", "bcm43455c0", "7_45_189", "--dry-run"],
            ),
            mock.patch.object(nexfirmware.sys, "stdout", stdout),
        ):
            status = nexfirmware.main()

        self.assertEqual(status, 0)
        self.assertIn("Scaffolded firmware patch target (dry-run)", stdout.getvalue())
        self.assertIn("bcm43455c0", stdout.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
