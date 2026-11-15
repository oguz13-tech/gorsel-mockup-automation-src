import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from SABLON_V2_MIMARI.core.path_registry import (
    read_runtime_pointer,
    rollback_runtime_pointer,
    runtime_pointer_path,
    write_runtime_pointer,
)
from SABLON_V2_MIMARI.core.runtime_migration import (
    build_runtime_migration_plan,
    copy_runtime_workspace,
    switch_runtime_after_verification,
    verify_runtime_workspace,
)


class TestRuntimeMigration(unittest.TestCase):
    def _runtime(self, root: Path, label: str) -> Path:
        runtime = root / label
        db = runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        db.write_bytes(b"sqlite-test-db")
        working = runtime / "2_SABLON_HAVUZU" / "cat"
        working.mkdir(parents=True)
        (working / "one.png").write_bytes(b"PNG-ONE")
        raw = runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / "cat"
        raw.mkdir(parents=True)
        (raw / "one.png").write_bytes(b"RAW-ONE")
        staging = runtime / "YENI-BOS MOCKUP SABLON HAVUZU"
        staging.mkdir(parents=True)
        (staging / "note.txt").write_text("staging", encoding="utf-8")
        git = runtime / ".git"
        git.mkdir(parents=True)
        (git / "secret-index").write_bytes(b"SHOULD_NOT_COPY")
        pycache = runtime / "__pycache__"
        pycache.mkdir(parents=True)
        (pycache / "x.pyc").write_bytes(b"CACHE")
        return runtime

    def test_plan_is_read_only_and_excludes_development_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._runtime(root, "source")
            target = root / "target"
            before = {
                path.relative_to(source).as_posix(): path.read_bytes()
                for path in source.rglob("*")
                if path.is_file()
            }

            plan = build_runtime_migration_plan(source, target)

            after = {
                path.relative_to(source).as_posix(): path.read_bytes()
                for path in source.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)
            self.assertTrue(plan["read_only"])
            self.assertFalse(plan["safety"]["source_delete_allowed"])
            self.assertFalse(
                plan["safety"]["overwrite_conflicting_target_allowed"]
            )
            self.assertGreater(plan["file_count"], 0)
            self.assertNotIn(".git", plan["top_level_file_counts"])
            self.assertNotIn("__pycache__", plan["top_level_file_counts"])

    def test_copy_then_verify_preserves_source_and_never_copies_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._runtime(root, "source")
            target = root / "target"
            source_one = (
                source
                / "2_SABLON_HAVUZU"
                / "cat"
                / "one.png"
            )
            before = source_one.read_bytes()
            progress = []

            result = copy_runtime_workspace(
                source,
                target,
                progress=lambda current, total, message: progress.append(
                    (current, total, message)
                ),
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["state"], "COPIED_AND_VERIFIED")
            self.assertTrue(result["verification"]["verified"])
            self.assertEqual(source_one.read_bytes(), before)
            self.assertEqual(
                (
                    target
                    / "2_SABLON_HAVUZU"
                    / "cat"
                    / "one.png"
                ).read_bytes(),
                before,
            )
            self.assertFalse((target / ".git").exists())
            self.assertFalse((target / "__pycache__").exists())
            self.assertTrue(
                (
                    target
                    / "SABLON_V2_MIMARI"
                    / "reports"
                    / "runtime_migration_manifest.json"
                ).is_file()
            )
            self.assertTrue(progress)

            verified = verify_runtime_workspace(source, target)
            self.assertTrue(verified["verified"])
            self.assertEqual(verified["missing_count"], 0)
            self.assertEqual(verified["mismatch_count"], 0)

    def test_copy_refuses_to_overwrite_conflicting_target_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._runtime(root, "source")
            target = root / "target"
            conflict = (
                target
                / "2_SABLON_HAVUZU"
                / "cat"
                / "one.png"
            )
            conflict.parent.mkdir(parents=True)
            conflict.write_bytes(b"DIFFERENT")
            before = conflict.read_bytes()

            result = copy_runtime_workspace(source, target)

            self.assertFalse(result["success"])
            self.assertEqual(result["state"], "COPY_BLOCKED_BY_CONFLICT")
            self.assertGreater(result["conflict_count"], 0)
            self.assertEqual(conflict.read_bytes(), before)
            self.assertTrue(
                (
                    source
                    / "2_SABLON_HAVUZU"
                    / "cat"
                    / "one.png"
                ).is_file()
            )

    def test_verified_switch_uses_local_pointer_and_rollback_restores_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_app_data = root / "localappdata"
            old_runtime = self._runtime(root, "old_runtime")
            source = self._runtime(root, "source")
            target = root / "target"

            with patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(local_app_data),
                    "MOCKUP_RUNTIME_WORKSPACE": "",
                },
                clear=False,
            ):
                write_runtime_pointer(old_runtime)
                self.assertEqual(read_runtime_pointer(), old_runtime.resolve())

                copied = copy_runtime_workspace(source, target)
                self.assertTrue(copied["success"])

                switched = switch_runtime_after_verification(
                    source,
                    target,
                )
                self.assertTrue(switched["success"])
                self.assertEqual(read_runtime_pointer(), target.resolve())
                self.assertTrue(runtime_pointer_path().is_file())

                restored = rollback_runtime_pointer()
                self.assertEqual(restored, old_runtime.resolve())
                self.assertEqual(
                    read_runtime_pointer(),
                    old_runtime.resolve(),
                )

    def test_launcher_checks_runtime_pointer_before_automatic_discovery(self):
        launcher = (
            Path(__file__).resolve().parents[1]
            / "INCELEME_MERKEZINI_AC.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("runtime_workspace.txt", launcher)
        self.assertIn('runtimeSource = "runtime pointer"', launcher)
        self.assertLess(
            launcher.index("runtime_workspace.txt"),
            launcher.index("$candidates = @("),
        )


if __name__ == "__main__":
    unittest.main()
