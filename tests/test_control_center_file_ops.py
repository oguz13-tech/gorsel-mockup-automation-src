import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "V2_KONTROL_MERKEZI" / "app.py"
SPEC = importlib.util.spec_from_file_location("v2_control_center_app", MODULE_PATH)
control = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(control)


class TestSafeTwoPhaseRename(unittest.TestCase):
    def test_success_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "a.txt"
            second = root / "b.txt"
            first.write_bytes(b"alpha")
            second.write_bytes(b"beta")

            results = control.safe_two_phase_rename(
                [str(first), str(second)],
                "renamed_",
            )

            self.assertEqual(len(results), 2)
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())
            self.assertEqual(Path(results[0]).read_bytes(), b"alpha")
            self.assertEqual(Path(results[1]).read_bytes(), b"beta")

    def test_phase_two_failure_restores_all_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "a.txt"
            second = root / "b.txt"
            first.write_bytes(b"alpha")
            second.write_bytes(b"beta")

            real_rename = os.rename
            calls = {"count": 0}

            def flaky_rename(src, dst):
                calls["count"] += 1
                # 2 staging moves, first final move succeeds, second final move
                # fails. Rollback calls after this must be allowed to complete.
                if calls["count"] == 4:
                    raise OSError("synthetic phase-2 failure")
                return real_rename(src, dst)

            with patch.object(control.os, "rename", side_effect=flaky_rename):
                with self.assertRaises(OSError):
                    control.safe_two_phase_rename(
                        [str(first), str(second)],
                        "renamed_",
                    )

            self.assertTrue(first.is_file())
            self.assertTrue(second.is_file())
            self.assertEqual(first.read_bytes(), b"alpha")
            self.assertEqual(second.read_bytes(), b"beta")
            self.assertEqual(
                sorted(path.name for path in root.iterdir()),
                ["a.txt", "b.txt"],
            )


if __name__ == "__main__":
    unittest.main()
