import sqlite3
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "SABLON_V2_MIMARI"))

from core import db


class TestTemplateProfileLegacyUniqueMigration(unittest.TestCase):
    def _legacy_connection(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """CREATE TABLE template_profiles (
                   template_uid TEXT UNIQUE,
                   category TEXT,
                   source_relative_path TEXT,
                   source_asset_sha256 TEXT,
                   profile_version TEXT,
                   analyzer_version TEXT,
                   product_class TEXT,
                   orientation TEXT,
                   geometry_type TEXT,
                   print_policy TEXT,
                   surface_quad TEXT,
                   outer_quad TEXT,
                   surface_mask_path TEXT,
                   material TEXT,
                   has_frame INTEGER,
                   has_mat INTEGER,
                   has_reflection INTEGER,
                   has_occlusion INTEGER,
                   confidence_total REAL,
                   component_confidences TEXT,
                   review_status TEXT,
                   manually_verified INTEGER,
                   updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        conn.execute(
            """INSERT INTO template_profiles (
                   template_uid, category, source_relative_path,
                   source_asset_sha256, surface_quad,
                   review_status, manually_verified
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "05_Ocak_Arkasi_OcakArkasi_001.png",
                "05_Ocak_Arkasi",
                "05_Ocak_Arkasi/OcakArkasi_001.png",
                "old-source-hash",
                "[[1,2],[3,4],[5,6],[7,8]]",
                "APPROVED",
                1,
            ),
        )
        conn.commit()
        return conn

    def test_migration_removes_legacy_uid_unique_without_data_loss(self):
        conn = self._legacy_connection()
        try:
            db.migrate_schema(conn)
            conn.commit()

            row = conn.execute(
                """SELECT template_uid, category, source_relative_path,
                          source_asset_sha256, surface_quad,
                          review_status, manually_verified, is_active
                   FROM template_profiles"""
            ).fetchone()
            self.assertEqual(
                row,
                (
                    "05_Ocak_Arkasi_OcakArkasi_001.png",
                    "05_Ocak_Arkasi",
                    "05_Ocak_Arkasi/OcakArkasi_001.png",
                    "old-source-hash",
                    "[[1,2],[3,4],[5,6],[7,8]]",
                    "APPROVED",
                    1,
                    1,
                ),
            )

            unique_uid_indexes = []
            for index_row in conn.execute(
                "PRAGMA index_list(template_profiles)"
            ).fetchall():
                if not int(index_row[2] or 0):
                    continue
                index_name = str(index_row[1])
                quoted = index_name.replace('"', '""')
                columns = [
                    info[2]
                    for info in conn.execute(
                        f'PRAGMA index_info("{quoted}")'
                    ).fetchall()
                ]
                if columns == ["template_uid"]:
                    unique_uid_indexes.append(index_name)

            self.assertEqual(unique_uid_indexes, [])

            # EPIC-3 must allow stale + current source-version rows for one UID.
            conn.execute(
                """INSERT INTO template_profiles (
                       template_uid, category, source_relative_path,
                       source_asset_sha256, review_status,
                       manually_verified, is_active
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    "05_Ocak_Arkasi_OcakArkasi_001.png",
                    "05_Ocak_Arkasi",
                    "05_Ocak_Arkasi/OcakArkasi_001.png",
                    "new-source-hash",
                    "REVIEW_REQUIRED",
                    0,
                    1,
                ),
            )
            conn.commit()

            count = conn.execute(
                """SELECT COUNT(*) FROM template_profiles
                   WHERE template_uid=?""",
                ("05_Ocak_Arkasi_OcakArkasi_001.png",),
            ).fetchone()[0]
            self.assertEqual(count, 2)

            # Re-running startup migration must be a no-op.
            db.migrate_schema(conn)
            conn.commit()
            count_after = conn.execute(
                """SELECT COUNT(*) FROM template_profiles
                   WHERE template_uid=?""",
                ("05_Ocak_Arkasi_OcakArkasi_001.png",),
            ).fetchone()[0]
            self.assertEqual(count_after, 2)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
