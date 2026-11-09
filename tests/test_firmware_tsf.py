"""Regression coverage for BCM4375b1 radiotap TSF64 preservation."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FirmwareTsfTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("gcc"), "gcc required")
    def test_recovered_tsf_survives_low_word_rollover(self):
        """Execute each target's recovery/writeback block with a nonzero high word."""
        sources = sorted((ROOT / "patches/bcm4375b1").glob("*/nexmon/src/monitormode.c"))
        self.assertEqual(len(sources), 2)
        for source in sources:
            with self.subTest(target=source.parts[-4]), tempfile.TemporaryDirectory() as tmp:
                text = source.read_text()
                start = text.index("wlc_recover_tsf64(wlc, wrxh,")
                end = text.index("myrtap->dbm_antsignal", start)
                block = text[start:end]
                harness = r"""
#include <assert.h>
#include <stdint.h>
static uint64_t recovered;
static void wlc_recover_tsf64(void *wlc, void *wrxh, unsigned int *hi, unsigned int *lo)
{
    (void)wlc; (void)wrxh;
    *hi = (unsigned int)(recovered >> 32);
    *lo = (unsigned int)recovered;
}
static uint64_t capture(void)
{
    struct { struct { unsigned int tsf_l, tsf_h; } tsf; } header = {0}, *myrtap = &header;
    void *wlc = 0, *wrxh = 0;
RECOVERY_BLOCK
    return ((uint64_t)myrtap->tsf.tsf_h << 32) | myrtap->tsf.tsf_l;
}
int main(void)
{
    recovered = UINT64_C(0x12345678ffffffff);
    uint64_t before = capture();
    assert(before == recovered);
    recovered++;
    uint64_t after = capture();
    assert(after == recovered);
    assert(after == before + 1);
    return 0;
}
""".replace("RECOVERY_BLOCK", block)
                c_file = Path(tmp) / "tsf.c"
                executable = Path(tmp) / "tsf"
                c_file.write_text(harness)
                subprocess.run(["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                                str(c_file), "-o", str(executable)], check=True)
                subprocess.run([str(executable)], check=True)
