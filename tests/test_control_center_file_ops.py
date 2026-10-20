import importlib.util
import os
import json
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

    def test_prefix_cannot_escape_selected_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "a.txt"
            first.write_bytes(b"alpha")

            for prefix in ("../escaped_", "..\\escaped_", "/absolute_"):
                with self.assertRaises(ValueError):
                    control.safe_two_phase_rename([str(first)], prefix)

            self.assertTrue(first.is_file())
            self.assertEqual(first.read_bytes(), b"alpha")

    def test_phase_two_failure_restores_all_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "a.txt"
            second = root / "b.txt"
            first.write_bytes(b"alpha")
            second.write_bytes(b"beta")

            real_link = os.link
            failures = []
            published = []
            def flaky_link(src, dst, *args, **kwargs):
                if Path(dst).name == "renamed_002.txt":
                    self.assertTrue((root / "renamed_001.txt").is_file())
                    failures.append(str(dst))
                    raise OSError("synthetic phase-2 failure")
                result = real_link(src, dst, *args, **kwargs)
                if Path(dst).name == "renamed_001.txt":
                    published.append(str(dst))
                return result
            with patch.object(control.os, "link", side_effect=flaky_link):
                with self.assertRaises(OSError):
                    control.safe_two_phase_rename([str(first), str(second)], "renamed_")

            self.assertEqual(len(failures), 1)
            self.assertEqual(len(published), 1)
            journals = list((root / "_GORSEL_ISIMLENDIRME_YEDEKLERI").glob("*/manifest.json"))
            self.assertEqual(len(journals), 1)
            journal = json.loads(journals[0].read_text(encoding="utf-8"))
            self.assertEqual(journal["state"], "ROLLED_BACK")
            self.assertEqual([Path(x["snapshot"]).read_bytes() for x in journal["files"]], [b"alpha", b"beta"])
            self.assertFalse((root / "_GORSEL_ISIMLENDIRME_YEDEKLERI" / "RENAME_IN_PROGRESS.lock").exists())
            self.assertTrue(first.is_file())
            self.assertTrue(second.is_file())
            self.assertEqual(first.read_bytes(), b"alpha")
            self.assertEqual(second.read_bytes(), b"beta")
            self.assertEqual(
                sorted(path.name for path in root.iterdir()),
                ["_GORSEL_ISIMLENDIRME_YEDEKLERI", "a.txt", "b.txt"],
            )


if __name__ == "__main__":
    unittest.main()

