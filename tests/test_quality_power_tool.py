import importlib.util
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "99_SISTEM_MOTORLARI_VE_KODLAR"
    / "SISTEM_MOTORU"
    / "kalite_artirici_otomasyon.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "quality_power_tool_under_test",
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestQualityPowerTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = _load_module()

    def test_basic_output_validation_rejects_downscale(self):
        source = np.zeros((800, 600, 3), dtype=np.uint8)
        candidate = np.zeros((400, 300, 3), dtype=np.uint8)
        valid, message = self.tool._basic_output_valid(
            source,
            candidate,
        )
        self.assertFalse(valid)
        self.assertIn("küçülmüş", message)

    def test_basic_output_validation_rejects_aspect_change(self):
        source = np.zeros((800, 600, 3), dtype=np.uint8)
        source[100:700, 100:500] = 120
        candidate = np.zeros((1600, 1600, 3), dtype=np.uint8)
        candidate[100:1500, 100:1500] = 120
        valid, message = self.tool._basic_output_valid(
            source,
            candidate,
        )
        self.assertFalse(valid)
        self.assertIn("en-boy oranı", message)

    def test_collect_files_preserves_nested_sources_and_excludes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "input"
            output_root = source_root / "4K_POWER_TOOL_OUTPUT"
            nested = source_root / "02_Cam_Tablo"
            nested.mkdir(parents=True)
            output_root.mkdir(parents=True)

            valid_img = np.full((20, 30, 3), 100, dtype=np.uint8)
            ok, encoded = cv2.imencode(".jpg", valid_img)
            self.assertTrue(ok)
            encoded.tofile(str(nested / "a.jpg"))
            encoded.tofile(str(output_root / "already.jpg"))

            files = self.tool._collect_files(source_root, output_root)
            self.assertEqual(files, [nested / "a.jpg"])


if __name__ == "__main__":
    unittest.main()
