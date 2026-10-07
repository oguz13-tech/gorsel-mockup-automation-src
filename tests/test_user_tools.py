import tempfile
import unittest
from pathlib import Path

from PIL import Image

from SABLON_V2_MIMARI.tools_runner import (
    convert_images,
    rename_images,
)


class TestIndependentUserTools(unittest.TestCase):
    def _image(self, path: Path, size=(32, 24), mode="RGB"):
        Image.new(mode, size, 128).save(path)

    def test_rename_is_two_phase_and_preserves_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "z.jpg"
            b = root / "a.png"
            self._image(a)
            self._image(b, mode="RGBA")

            outputs = rename_images(
                [a, b],
                "Tablo_",
                runtime_root=root / "runtime",
            )

            self.assertEqual(
                [p.name for p in outputs],
                ["Tablo_001.png", "Tablo_002.jpg"],
            )
            self.assertTrue(all(p.is_file() for p in outputs))
            self.assertFalse(a.exists())
            self.assertFalse(b.exists())

    def test_rename_never_overwrites_unselected_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jpg"
            collision = root / "Tablo_001.jpg"
            self._image(source)
            self._image(collision)

            with self.assertRaises(FileExistsError):
                rename_images(
                    [source],
                    "Tablo_",
                    runtime_root=root / "runtime",
                )

            self.assertTrue(source.is_file())
            self.assertTrue(collision.is_file())

    def test_rename_is_blocked_inside_live_template_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            protected = runtime / "2_SABLON_HAVUZU" / "cat"
            protected.mkdir(parents=True)
            source = protected / "mockup.png"
            self._image(source, mode="RGBA")

            with self.assertRaises(ValueError):
                rename_images(
                    [source],
                    "Mockup_",
                    runtime_root=runtime,
                )

            self.assertTrue(source.is_file())

    def test_format_converter_keeps_originals_and_writes_separate_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sample.png"
            self._image(source, mode="RGBA")
            before = source.read_bytes()

            output_dir, outputs = convert_images([source], "JPG")

            self.assertTrue(source.is_file())
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(output_dir.name, "FORMAT_JPG_CIKTILARI")
            self.assertEqual(len(outputs), 1)
            self.assertEqual(outputs[0].suffix.lower(), ".jpg")
            self.assertTrue(outputs[0].is_file())


if __name__ == "__main__":
    unittest.main()
