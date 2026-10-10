"""Regression tests for fail-closed, no-clobber mockup source replacement.

All images and recovery operations use disposable temporary directories.
The user's real working pool, original archive and database are never opened.
"""
import errno
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from SABLON_V2_MIMARI.core import lifecycle_reconciliation as lifecycle


CATEGORY = "03_Ahsap_Tablo"
TEMPLATE = "AhsapTablo_015.png"


def image_bytes(value: int) -> bytes:
    pixels = np.full((18, 27, 3), value, dtype=np.uint8)
    success, encoded = cv2.imencode(".png", pixels)
    if not success:
        raise AssertionError("Sentetik PNG oluşturulamadı")
    return encoded.tobytes()


class TestNoOverwriteSourceReplacement(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.backup = (
            self.root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / CATEGORY / TEMPLATE
        )
        self.working = self.root / "2_SABLON_HAVUZU" / CATEGORY / TEMPLATE
        self.backup.parent.mkdir(parents=True, exist_ok=True)
        self.working.parent.mkdir(parents=True, exist_ok=True)

    def create_old_files(self):
        old_backup, old_working = image_bytes(18), image_bytes(45)
        self.backup.write_bytes(old_backup)
        self.working.write_bytes(old_working)
        return old_backup, old_working

    def manifest(self):
        manifests = list((
            self.root / "SABLON_V2_MIMARI" / "recovery" / "lifecycle"
        ).glob("*/manifest.json"))
        self.assertEqual(len(manifests), 1)
        return json.loads(manifests[0].read_text(encoding="utf-8")), manifests[0].parent

    def test_01_atomic_create_never_overwrites_existing_file(self):
        target = self.root / "evidence.png"
        target.write_bytes(b"ORIGINAL")
        with self.assertRaises(lifecycle.LifecycleSafetyError):
            lifecycle._atomic_create_bytes(target, b"NEW")
        self.assertEqual(target.read_bytes(), b"ORIGINAL")
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_02_atomic_create_publishes_complete_bytes(self):
        target = self.root / "evidence.png"
        lifecycle._atomic_create_bytes(target, b"COMPLETE")
        self.assertEqual(target.read_bytes(), b"COMPLETE")
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_03_race_during_backup_publish_never_deletes_other_writers_file(self):
        old_backup, old_working = self.create_old_files()
        real_link = os.link

        def inject_race(src, dst):
            # New backup target was moved to recovery; another writer wins
            # the name just before we publish this operation's bytes.
            if Path(dst) == self.backup:
                Path(dst).write_bytes(b"OTHER-WRITER")
                raise FileExistsError(errno.EEXIST, "target exists", str(dst))
            return real_link(src, dst)

        with patch.object(lifecycle.os, "link", side_effect=inject_race):
            with self.assertRaises(lifecycle.LifecycleSafetyError):
                lifecycle.replace_original_and_working(
                    self.root, category=CATEGORY, template=TEMPLATE,
                    upload_filename=TEMPLATE, upload_bytes=image_bytes(160),
                )

        self.assertEqual(self.backup.read_bytes(), b"OTHER-WRITER")
        self.assertEqual(self.working.read_bytes(), old_working)
        m, operation_dir = self.manifest()
        self.assertEqual(m["state"], "RECOVERY_REQUIRED")
        self.assertIn("Kaynak yolunda başka dosya", " ".join(m["rollback_conflicts"]))
        self.assertEqual(
            (operation_dir / "original_before" / TEMPLATE).read_bytes(),
            old_backup,
        )

    def test_04_race_during_working_publish_preserves_concurrent_file(self):
        old_backup, old_working = self.create_old_files()
        real_link = os.link

        def inject_race(src, dst):
            if Path(dst) == self.working:
                Path(dst).write_bytes(b"WORKER-OWNED")
                raise FileExistsError(errno.EEXIST, "target exists", str(dst))
            return real_link(src, dst)

        with patch.object(lifecycle.os, "link", side_effect=inject_race):
            with self.assertRaises(lifecycle.LifecycleSafetyError):
                lifecycle.replace_original_and_working(
                    self.root, category=CATEGORY, template=TEMPLATE,
                    upload_filename=TEMPLATE, upload_bytes=image_bytes(160),
                )

        self.assertEqual(self.backup.read_bytes(), old_backup)
        self.assertEqual(self.working.read_bytes(), b"WORKER-OWNED")
        m, operation_dir = self.manifest()
        self.assertEqual(m["state"], "RECOVERY_REQUIRED")
        self.assertEqual(
            (operation_dir / "working_before" / TEMPLATE).read_bytes(),
            old_working,
        )

    def test_05_unsupported_hardlink_fails_closed_and_restores_originals(self):
        old_backup, old_working = self.create_old_files()
        with patch.object(
            lifecycle.os, "link",
            side_effect=OSError(errno.EOPNOTSUPP, "hardlinks unsupported"),
        ):
            with self.assertRaises(lifecycle.LifecycleSafetyError):
                lifecycle.replace_original_and_working(
                    self.root, category=CATEGORY, template=TEMPLATE,
                    upload_filename=TEMPLATE, upload_bytes=image_bytes(160),
                )

        self.assertEqual(self.backup.read_bytes(), old_backup)
        self.assertEqual(self.working.read_bytes(), old_working)
        m, _ = self.manifest()
        self.assertEqual(m["state"], "ROLLED_BACK")
        self.assertEqual(m["rollback_conflicts"], [])

    def test_06_successful_source_replace_archives_every_old_byte(self):
        old_backup, old_working = self.create_old_files()
        incoming = image_bytes(180)
        result = lifecycle.replace_original_and_working(
            self.root, category=CATEGORY, template=TEMPLATE,
            upload_filename=TEMPLATE, upload_bytes=incoming,
        )
        self.assertEqual(result["state"], "COMMITTED")
        self.assertEqual(self.backup.read_bytes(), incoming)
        self.assertEqual(
            result["new_backup_sha256"],
            lifecycle.sha256_file(self.backup),
        )
        self.assertEqual(
            result["new_working_sha256"],
            lifecycle.sha256_file(self.working),
        )
        m, operation_dir = self.manifest()
        self.assertEqual(m["state"], "COMMITTED")
        self.assertEqual(
            (operation_dir / "original_before" / TEMPLATE).read_bytes(),
            old_backup,
        )
        self.assertEqual(
            (operation_dir / "working_before" / TEMPLATE).read_bytes(),
            old_working,
        )


if __name__ == "__main__":
    unittest.main()
