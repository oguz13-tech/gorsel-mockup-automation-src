import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "SABLON_V2_MIMARI"))

from core.workspace_consistency import (
    load_latest_workspace_report,
    save_workspace_report,
    workspace_consistency_report,
    workspace_report_history,
)


def write_bytes(path: Path, content: bytes = b"test-image-bytes"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def asset_snapshot(root: Path):
    ignored = {
        root / "SABLON_V2_MIMARI" / "reports",
    }
    result = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(parent == path or parent in path.parents for parent in ignored):
            continue
        result[path.relative_to(root).as_posix()] = path.read_bytes()
    return result


class TestWorkspaceConsistencyAudit(unittest.TestCase):
    def _build_runtime(self, root: Path):
        category = "03_Ahsap_Tablo"

        write_bytes(
            root / "2_SABLON_HAVUZU" / category / "AhsapTablo_001.png",
            b"working-1",
        )
        write_bytes(
            root / "2_SABLON_HAVUZU" / category / "AhsapTablo_002.png",
            b"working-2-png",
        )
        write_bytes(
            root / "2_SABLON_HAVUZU" / category / "AhsapTablo_002.jpg",
            b"working-2-jpg",
        )
        write_bytes(
            root / "2_SABLON_HAVUZU" / category / "AhsapTablo_099.png",
            b"working-no-db",
        )

        write_bytes(
            root
            / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
            / category
            / "AhsapTablo_001.png",
            b"backup-1",
        )
        write_bytes(
            root
            / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
            / category
            / "AhsapTablo_003.png",
            b"backup-3",
        )

        write_bytes(
            root
            / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
            / category
            / "AhsapTablo_777.png",
            b"legacy-backup-only",
        )

        write_bytes(
            root
            / "YENI-BOS MOCKUP SABLON HAVUZU"
            / category
            / "AhsapTablo_003.png",
            b"staging-3",
        )
        write_bytes(
            root
            / "SILINEN_SABLONLAR_COP_KUTUSU"
            / "03_Ahsap_Tablo__AhsapTablo_010__20261009_deadbeef.png",
            b"trash",
        )
        write_bytes(
            root
            / "_KURTARMA_PROCESSING"
            / category
            / "orphan.png",
            b"recovery",
        )

        for name in (
            "0_KAGGLE_ONAY_BEKLEYENLER",
            "1_GELEN_KAGGLE_BASKILARI",
            "3_URETILEN_MOCKUPLAR",
            "MOCKUP A HAZIR GÖRSELLER",
            "Mockup_Magaza_Klasorleri",
            "BILINMEYEN_ESKI_KLASOR",
        ):
            write_bytes(root / name / "sample.txt", name.encode("utf-8"))

        settings = {
            "kategoriler": {
                category: {
                    "sablonlar": {
                        "AhsapTablo_001.png": {},
                        "AhsapTablo_002.png": {},
                        "AhsapTablo_003.png": {},
                    }
                }
            }
        }
        return category, settings

    def test_read_only_audit_classifies_active_identity_mismatches_and_special_folders(self):
        with tempfile.TemporaryDirectory() as runtime_tmp, tempfile.TemporaryDirectory() as source_tmp:
            runtime = Path(runtime_tmp)
            source = Path(source_tmp)
            category, settings = self._build_runtime(runtime)

            write_bytes(
                source / "tool.py",
                (
                    'KAGGLE="1_GELEN_KAGGLE_BASKILARI"\n'
                    'OUTPUT="3_URETILEN_MOCKUPLAR"\n'
                    'MANUAL="MOCKUP A HAZIR GÖRSELLER"\n'
                    'MULTI="Mockup_Magaza_Klasorleri"\n'
                    'WORK="2_SABLON_HAVUZU"\n'
                ).encode("utf-8"),
            )

            before = asset_snapshot(runtime)
            progress_rows = []
            report = workspace_consistency_report(
                str(runtime),
                str(source),
                settings,
                progress=lambda current, total, message: progress_rows.append(
                    (current, total, message)
                ),
            )
            after = asset_snapshot(runtime)

            self.assertEqual(before, after)
            self.assertTrue(report["success"])
            self.assertTrue(report["read_only"])
            self.assertFalse(report["assets_mutated"])
            self.assertEqual(report["auto_deleted"], 0)

            summary = report["summary"]
            self.assertEqual(summary["active_db_total"], 3)
            self.assertEqual(summary["fully_matched_active_total"], 1)
            self.assertEqual(summary["active_mismatch_total"], 2)
            self.assertEqual(summary["kaggle_folder_count"], 2)
            self.assertEqual(summary["mockup_folder_count"], 3)
            self.assertEqual(summary["active_integrity_issue_count"], 2)
            self.assertEqual(summary["archive_inventory_count"], 1)
            self.assertEqual(summary["working_hygiene_count"], 1)
            self.assertEqual(summary["duplicate_hygiene_count"], 1)
            self.assertGreaterEqual(
                summary["unclassified_top_level_count"],
                1,
            )

            category_row = report["categories"][category]
            self.assertEqual(category_row["db_count"], 3)
            self.assertEqual(category_row["working_identity_count"], 3)
            self.assertEqual(category_row["backup_identity_count"], 3)
            self.assertEqual(category_row["staging_identity_count"], 1)

            codes = {item["code"] for item in report["issues"]}
            self.assertIn("ACTIVE_BACKUP_MISSING", codes)
            self.assertIn("ACTIVE_WORKING_MISSING", codes)
            self.assertIn("WORKING_WITHOUT_DB", codes)
            self.assertIn("WORKING_DUPLICATE_IDENTITY", codes)
            self.assertIn("ACTIVE_IDENTITY_STILL_IN_STAGING", codes)
            self.assertIn("BACKUP_WITHOUT_DB", codes)

            archive_issue = next(
                item for item in report["issues"]
                if item["code"] == "BACKUP_WITHOUT_DB"
            )
            self.assertEqual(
                archive_issue["scope"],
                "ARCHIVE_INVENTORY",
            )
            self.assertEqual(archive_issue["severity"], "INFO")

            kaggle = {row["folder"]: row for row in report["kaggle_folders"]}
            self.assertEqual(
                kaggle["0_KAGGLE_ONAY_BEKLEYENLER"]["role"],
                "LEGACY_KAGGLE_APPROVAL_INBOX",
            )
            self.assertEqual(
                kaggle["1_GELEN_KAGGLE_BASKILARI"]["role"],
                "MASTER_DESIGN_INPUT",
            )
            self.assertGreater(
                kaggle["1_GELEN_KAGGLE_BASKILARI"][
                    "runtime_code_reference_count"
                ],
                0,
            )

            mockup = {row["folder"]: row for row in report["mockup_folders"]}
            self.assertEqual(
                mockup["3_URETILEN_MOCKUPLAR"]["role"],
                "PRIMARY_RENDER_OUTPUT",
            )
            self.assertEqual(
                mockup["MOCKUP A HAZIR GÖRSELLER"]["role"],
                "MANUAL_RENDER_INPUT",
            )
            self.assertEqual(
                mockup["Mockup_Magaza_Klasorleri"]["role"],
                "MULTI_STORE_OUTPUT",
            )

            unclassified = {
                row["folder"]
                for row in report["unclassified_top_level_folders"]
                if row["exists"]
            }
            self.assertIn("BILINMEYEN_ESKI_KLASOR", unclassified)

            self.assertTrue(progress_rows)
            self.assertEqual(progress_rows[-1][0], 8)
            self.assertEqual(progress_rows[-1][1], 8)

    def test_saved_audit_keeps_history_and_reports_resolved_differences(self):
        with tempfile.TemporaryDirectory() as runtime_tmp, tempfile.TemporaryDirectory() as source_tmp:
            runtime = Path(runtime_tmp)
            source = Path(source_tmp)
            category = "01_Wifi_Kutusu"
            settings = {
                "kategoriler": {
                    category: {
                        "sablonlar": {
                            "Wifi_Kutusu_001.png": {},
                        }
                    }
                }
            }
            write_bytes(
                runtime
                / "2_SABLON_HAVUZU"
                / category
                / "Wifi_Kutusu_001.png",
                b"working",
            )

            first = workspace_consistency_report(
                str(runtime),
                str(source),
                settings,
            )
            saved_first = save_workspace_report(str(runtime), first)
            self.assertFalse(saved_first["diff"]["has_previous"])
            self.assertGreater(saved_first["summary"]["issue_count"], 0)

            write_bytes(
                runtime
                / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
                / category
                / "Wifi_Kutusu_001.png",
                b"backup",
            )

            second = workspace_consistency_report(
                str(runtime),
                str(source),
                settings,
            )
            saved_second = save_workspace_report(str(runtime), second)

            self.assertTrue(saved_second["diff"]["has_previous"])
            self.assertGreaterEqual(
                saved_second["diff"]["resolved_issue_count"],
                1,
            )
            self.assertEqual(
                saved_second["summary"]["active_mismatch_total"],
                0,
            )

            latest = load_latest_workspace_report(str(runtime))
            self.assertEqual(
                latest["saved_at"],
                saved_second["saved_at"],
            )
            history = workspace_report_history(str(runtime), limit=10)
            self.assertEqual(len(history), 2)

            before_assets = asset_snapshot(runtime)
            _ = workspace_report_history(str(runtime), limit=10)
            after_assets = asset_snapshot(runtime)
            self.assertEqual(before_assets, after_assets)

    def test_folder_contract_never_marks_kaggle_or_mockup_for_automatic_delete(self):
        with tempfile.TemporaryDirectory() as runtime_tmp, tempfile.TemporaryDirectory() as source_tmp:
            runtime = Path(runtime_tmp)
            source = Path(source_tmp)
            for name in (
                "Kaggle_A",
                "Kaggle_B",
                "Mockup_A",
                "Mockup_B",
                "Mockup_C",
            ):
                (runtime / name).mkdir(parents=True)

            report = workspace_consistency_report(
                str(runtime),
                str(source),
                {"kategoriler": {}},
            )
            candidates = (
                report["kaggle_folders"]
                + report["mockup_folders"]
            )
            self.assertEqual(len(report["kaggle_folders"]), 2)
            self.assertEqual(len(report["mockup_folders"]), 3)
            self.assertTrue(candidates)
            for row in candidates:
                self.assertFalse(row["automatic_delete_allowed"])
                self.assertTrue(row["read_only_audit"])

    def test_known_runtime_folders_are_classified_and_audit_self_reference_is_ignored(self):
        with tempfile.TemporaryDirectory() as runtime_tmp, tempfile.TemporaryDirectory() as source_tmp:
            runtime = Path(runtime_tmp)
            source = Path(source_tmp)

            expected_roles = {
                ".git": "VERSION_CONTROL_METADATA",
                ".kilo": "DEV_WORKTREE_METADATA",
                "__pycache__": "PYTHON_CACHE",
                "AI_Kalite_Artirici": "QUALITY_ENHANCEMENT_ASSETS",
                "logs": "RUNTIME_LOGS",
                "TEST_ENV": "TEST_SANDBOX",
                "V2_KONTROL_MERKEZI": "LEGACY_CONTROL_CENTER",
                "ÜRÜN ADI YAZDIRMA BOTU": "USER_TOOL_PRODUCT_NAMER",
            }
            for name in expected_roles:
                write_bytes(
                    runtime / name / "sample.txt",
                    name.encode("utf-8"),
                )

            # The audit contract itself mentions canonical folder names.
            # That must never make a legacy folder look actively used.
            audit_source = (
                source
                / "SABLON_V2_MIMARI"
                / "core"
                / "workspace_consistency.py"
            )
            write_bytes(
                audit_source,
                (
                    'LEGACY="0_KAGGLE_ONAY_BEKLEYENLER"\n'
                    'TEST="TEST_ENV"\n'
                    'TOOL="ÜRÜN ADI YAZDIRMA BOTU"\n'
                ).encode("utf-8"),
            )
            write_bytes(
                source / "test_fake_runtime.py",
                b'LEGACY="0_KAGGLE_ONAY_BEKLEYENLER"\n',
            )

            report = workspace_consistency_report(
                str(runtime),
                str(source),
                {"kategoriler": {}},
            )
            rows = {row["folder"]: row for row in report["folders"]}

            for name, role in expected_roles.items():
                self.assertEqual(rows[name]["role"], role)

            self.assertEqual(
                report["summary"]["unclassified_top_level_count"],
                0,
            )
            legacy = rows["0_KAGGLE_ONAY_BEKLEYENLER"]
            self.assertEqual(legacy["runtime_code_reference_count"], 0)
            self.assertEqual(legacy["code_reference_count"], 0)

    def test_frontend_and_backend_expose_persistent_workspace_audit(self):
        js = (
            ROOT
            / "SABLON_V2_MIMARI"
            / "static"
            / "js"
            / "main.js"
        ).read_text(encoding="utf-8")
        html = (
            ROOT
            / "SABLON_V2_MIMARI"
            / "templates"
            / "index.html"
        ).read_text(encoding="utf-8")
        app_source = (
            ROOT
            / "SABLON_V2_MIMARI"
            / "app.py"
        ).read_text(encoding="utf-8")

        self.assertIn("WORKSPACE_CONSISTENCY_SCAN", js)
        self.assertIn("monitorWorkspaceAuditJob", js)
        self.assertIn("resumePersistentJobs", js)
        self.assertIn("D' + (lifecycle.db", js)
        self.assertIn("🧭 Klasör Tutarlılık Taraması", html)
        self.assertIn("📚 Tutarlılık Rapor Geçmişi", html)
        self.assertIn("📚 Sağlık Rapor Geçmişi", html)
        self.assertIn("WORKSPACE_CONSISTENCY_SCAN", app_source)
        self.assertIn("/api/workspace-consistency/last", app_source)
        self.assertIn("/api/workspace-consistency/history", app_source)
        self.assertIn("/api/template-health/history", app_source)


if __name__ == "__main__":
    unittest.main()
