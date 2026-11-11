#!/usr/bin/env python3
"""Regression tests for libnexio build-mode selection.

A native build and an Android NDK build both write utilities/libnexio/libnexio.a.
Without a build-mode stamp, make can consider the archive newer than libnexio.c
and silently reuse an archive produced by the other toolchain, which then fails
to link (bionic __errno/__sF symbols against a GNU linker).
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBNEXIO_MAKEFILE = ROOT / "utilities" / "libnexio" / "Makefile"


class LibnexioBuildModeTests(unittest.TestCase):
    def setUp(self):
        for tool in ("make", "ar", "cc"):
            if shutil.which(tool) is None:
                self.skipTest(f"{tool} not available")

        self.tmp = tempfile.TemporaryDirectory(prefix="nexmon-libnexio-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.libdir = self.root / "libnexio"
        self.libdir.mkdir()

        shutil.copy2(LIBNEXIO_MAKEFILE, self.libdir / "Makefile")
        (self.libdir / "libnexio.c").write_text("int nex_dummy(void) { return 0; }\n")
        (self.libdir / "libnexio.h").write_text("int nex_dummy(void);\n")
        (self.libdir / "Android.mk").write_text("")
        (self.libdir / "Application.mk").write_text("")
        (self.root / "patches" / "include").mkdir(parents=True)
        (self.root / "nexutil").mkdir()

        self.fake_cc = self.root / "fake-cc"
        self.fake_cc.write_text(
            "#!/bin/sh\n"
            "out=\"\"\n"
            "prev=\"\"\n"
            "for arg in \"$@\"; do\n"
            "    [ \"$prev\" = \"-o\" ] && out=\"$arg\"\n"
            "    prev=\"$arg\"\n"
            "done\n"
            "if [ -n \"$out\" ]; then\n"
            "    mkdir -p \"$(dirname \"$out\")\"\n"
            "    printf 'native\\n' > \"$out\"\n"
            "fi\n"
            "exit 0\n"
        )
        self.fake_cc.chmod(0o755)

        self.ndk = self.root / "ndk"
        self.ndk.mkdir()
        self.ndk_build = self.ndk / "ndk-build"
        self.ndk_build.write_text(
            "#!/bin/sh\n"
            "abi=arm64-v8a\n"
            "for arg in \"$@\"; do\n"
            "    case \"$arg\" in APP_ABI=*) abi=\"${arg#APP_ABI=}\" ;; esac\n"
            "done\n"
            "mkdir -p \"local/$abi\"\n"
            "printf 'android\\n' > \"local/$abi/android.o\"\n"
            "ar rcs \"local/$abi/libnexio.a\" \"local/$abi/android.o\"\n"
        )
        self.ndk_build.chmod(0o755)

    def _make(self, *args):
        return subprocess.run(
            ["make", "-C", str(self.libdir), "GIT_VERSION=test", *args],
            capture_output=True,
            text=True,
            timeout=60,
        )

    def _archive_members(self):
        return subprocess.check_output(
            ["ar", "t", str(self.libdir / "libnexio.a")], text=True
        ).split()

    def test_switching_build_mode_rebuilds_archive(self):
        res = self._make("NATIVE_BUILD=1", f"CC={self.fake_cc}")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(self._archive_members(), ["libnexio.o"])

        res = self._make(f"NDK_ROOT={self.ndk}")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(self._archive_members(), ["android.o"])

        res = self._make("NATIVE_BUILD=1", f"CC={self.fake_cc}")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(
            self._archive_members(),
            ["libnexio.o"],
            "native build reused the Android archive left by the previous build",
        )


if __name__ == "__main__":
    unittest.main()