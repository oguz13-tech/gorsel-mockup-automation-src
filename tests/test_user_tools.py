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

    def test_rename_can_start_from_135_without_appending_001(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = []
            for name in ("c.png", "a.png", "b.png"):
                path = root / name
                self._image(path, mode="RGBA")
                files.append(path)

            outputs = rename_images(
                files,
                "Wifi_Kutusu_",
                runtime_root=root / "runtime",
                start_number=135,
            )

            self.assertEqual(
                [p.name for p in outputs],
                [
                    "Wifi_Kutusu_135.png",
                    "Wifi_Kutusu_136.png",
                    "Wifi_Kutusu_137.png",
                ],
            )

    def test_template_number_used_in_trash_is_forced_to_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / "runtime"
            trash = runtime / "SILINEN_SABLONLAR_COP_KUTUSU"
            trash.mkdir(parents=True)
            (runtime / "SABLON_V2_MIMARI").mkdir(parents=True)
            import sqlite3
            sqlite3.connect(
                runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
            ).close()

            (trash / "old_meta.json").write_text(
                '{"kategori":"01_Wifi_Kutusu",'
                '"sablon":"Wifi_Kutusu_135.png"}',
                encoding="utf-8",
            )

            source = root / "new.png"
            self._image(source, mode="RGBA")

            from SABLON_V2_MIMARI.core.template_identity import (
                TemplateNumberConflictError,
            )

            with self.assertRaises(TemplateNumberConflictError) as ctx:
                rename_images(
                    [source],
                    "Wifi_Kutusu_",
                    runtime_root=runtime,
                    start_number=135,
                )

            self.assertEqual(ctx.exception.conflicts, (135,))
            self.assertGreaterEqual(
                int(ctx.exception.suggested_start),
                136,
            )
            self.assertTrue(source.is_file())

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
