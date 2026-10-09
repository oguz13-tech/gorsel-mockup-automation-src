import tempfile
import unittest
from pathlib import Path

from PIL import Image

from SABLON_V2_MIMARI.tools_runner import (
    convert_folder_to_png_recursive,
    convert_images,
    rename_images,
)
from SABLON_V2_MIMARI.core.path_registry import (
    PATHS,
    registry_snapshot,
    runtime_path,
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

    def test_rename_blocks_same_stem_with_different_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            existing = root / "Tablo_001.jpg"
            self._image(source, mode="RGBA")
            self._image(existing)

            with self.assertRaises(FileExistsError) as ctx:
                rename_images(
                    [source],
                    "Tablo_",
                    runtime_root=root / "runtime",
                    start_number=1,
                )

            message = str(ctx.exception)
            self.assertIn("AYNI İSİM, FARKLI UZANTI", message)
            self.assertIn("Tablo_001.png", message)
            self.assertIn("Tablo_001.jpg", message)
            self.assertTrue(source.is_file())
            self.assertTrue(existing.is_file())

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

    def test_recursive_png_preserves_subfolders_skips_png_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "incoming"
            nested = source / "A" / "B"
            nested.mkdir(parents=True)

            jpg = source / "one.jpg"
            webp = nested / "two.webp"
            already_png = nested / "keep.png"
            self._image(jpg)
            self._image(webp)
            self._image(already_png, mode="RGBA")
            png_before = already_png.read_bytes()

            output = root / "converted"
            existing_output = output / "A" / "B" / "two.png"
            existing_output.parent.mkdir(parents=True)
            self._image(existing_output, mode="RGBA")
            existing_before = existing_output.read_bytes()

            progress_rows = []
            report = convert_folder_to_png_recursive(
                source,
                output_dir=output,
                runtime_root=root / "runtime",
                progress=lambda current, total, message: progress_rows.append(
                    (current, total, message)
                ),
            )

            self.assertTrue(progress_rows)
            self.assertEqual(progress_rows[0][0], 0)
            self.assertEqual(progress_rows[-1][0], 3)
            self.assertEqual(progress_rows[-1][1], 3)
            self.assertIn("tamamlandı", progress_rows[-1][2].lower())

            self.assertEqual(report["scanned_image_count"], 3)
            self.assertEqual(report["converted_count"], 1)
            self.assertEqual(report["skipped_png_count"], 1)
            self.assertEqual(report["skipped_existing_count"], 1)
            self.assertEqual(report["failed_count"], 0)
            self.assertTrue((output / "one.png").is_file())
            self.assertEqual(
                existing_output.read_bytes(),
                existing_before,
            )
            self.assertEqual(
                already_png.read_bytes(),
                png_before,
            )
            self.assertTrue(jpg.is_file())
            self.assertTrue(webp.is_file())

    def test_recursive_png_is_blocked_inside_live_template_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "runtime"
            source = (
                runtime
                / "2_SABLON_HAVUZU"
                / "01_Wifi_Kutusu"
            )
            source.mkdir(parents=True)
            self._image(source / "sample.jpg")

            with self.assertRaises(ValueError):
                convert_folder_to_png_recursive(
                    source,
                    runtime_root=runtime,
                )

            self.assertTrue((source / "sample.jpg").is_file())

    def test_professional_tools_expose_recursive_png_with_progress_and_independent_launcher(self):
        html = (
            Path(__file__).resolve().parents[1]
            / "SABLON_V2_MIMARI"
            / "templates"
            / "tools.html"
        ).read_text(encoding="utf-8")
        runner = (
            Path(__file__).resolve().parents[1]
            / "SABLON_V2_MIMARI"
            / "tools_runner.py"
        ).read_text(encoding="utf-8")
        bat = (
            Path(__file__).resolve().parents[1]
            / "BAGIMSIZ_ARACLAR"
            / "08_RECURSIVE_PNG_DONUSTURUCU.bat"
        )

        self.assertIn("Recursive PNG Dönüştürücü v2", html)
        self.assertIn("launchTool('png_recursive'", html)
        self.assertIn("ttk.Progressbar", runner)
        self.assertIn("PNG_DONUSUM_RAPORU.json", runner)
        self.assertIn("PNG_DONUSUM_RAPORU.txt", runner)
        self.assertTrue(bat.is_file())

    def test_path_registry_resolves_canonical_runtime_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            self.assertEqual(
                runtime_path("WORKING_POOL", runtime),
                (runtime / "2_SABLON_HAVUZU").resolve(),
            )
            self.assertEqual(
                runtime_path("ORIGINAL_ARCHIVE", runtime),
                (
                    runtime
                    / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
                ).resolve(),
            )
            snapshot = registry_snapshot(runtime)
            self.assertEqual(
                set(snapshot),
                set(PATHS),
            )
            self.assertIn(
                "PRIMARY_RENDER_OUTPUT",
                snapshot,
            )

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
