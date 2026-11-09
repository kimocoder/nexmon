"""Host regression coverage for native callback JNI ownership."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("gcc"), "gcc is required for JNI mock tests")
class JNICallbackTests(unittest.TestCase):
    def test_callback_lifecycle(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run([str(root / "tests/jni/run.sh")], cwd=root, check=True)


if __name__ == "__main__":
    unittest.main()
