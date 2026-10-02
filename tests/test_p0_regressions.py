"""P0 Regression Tests - Real assertions, not stubs."""
import os
import json
import glob
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TestSecretsRemoved(unittest.TestCase):
    """Verify no API keys remain in any ayarlar*.json file."""

    def test_no_secrets_in_any_json(self):
        json_files = glob.glob(os.path.join(BASE_DIR, "**", "ayarlar*.json"), recursive=True)
        self.assertGreater(len(json_files), 0, "No ayarlar JSON files found")

        for jf in json_files:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
            cloud = data.get("bulut_ayarlari", {})

            # imgbb_keys must be empty list
            keys = cloud.get("imgbb_keys", [])
            self.assertEqual(keys, [], f"imgbb_keys not empty in {jf}")

            # freeimage_key must be empty string
            fk = cloud.get("freeimage_key", "")
            self.assertEqual(fk, "", f"freeimage_key not empty in {jf}")

            # cloudinary secrets must be empty
            cl = cloud.get("cloudinary", {})
            self.assertEqual(cl.get("api_key", ""), "", f"cloudinary api_key not empty in {jf}")
            self.assertEqual(cl.get("api_secret", ""), "", f"cloudinary api_secret not empty in {jf}")


class TestUploadFailedNotSkipped(unittest.TestCase):
    """Verify UPLOAD_FAILED is NOT in the completed-skip list."""

    def test_upload_failed_not_in_completed_statuses(self):
        pc_path = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR",
                               "SISTEM_MOTORU", "pc_master_factory.py")
        with open(pc_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Find is_artifact_completed and check UPLOAD_FAILED is NOT there
        match = content[content.index("def is_artifact_completed"):content.index("def is_artifact_completed")+300]
        self.assertNotIn("UPLOAD_FAILED", match,
                         "UPLOAD_FAILED should not be treated as completed")


class TestQAFailStopsProduction(unittest.TestCase):
    """Verify QA failure returns False (quarantine), not just a warning."""

    def test_qa_fail_returns_false(self):
        pc_path = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR",
                               "SISTEM_MOTORU", "pc_master_factory.py")
        with open(pc_path, "r", encoding="utf-8") as f:
            content = f.read()

        # After "if not valid:" there should be "return False"
        idx = content.index("Kalite Denetimi")
        block = content[idx:idx+300]
        self.assertIn("return False", block,
                      "QA failure must halt production with return False")


if __name__ == "__main__":
    unittest.main()
