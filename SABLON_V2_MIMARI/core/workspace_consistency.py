from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".avif"}

ROLE_SPECS = [
    {
        "role": "LEGACY_KAGGLE_APPROVAL_INBOX",
        "folder": "0_KAGGLE_ONAY_BEKLEYENLER",
        "label": "Eski Kaggle insan-onay kuyruğu",
        "expected": (
            "Eski V2 akışında Kaggle çıktıları burada onay bekler, onaylananlar "
            "1_GELEN_KAGGLE_BASKILARI'na aktarılırdı. Legacy ama amaçlıdır; "
            "otomatik silinmez veya taşınmaz."
        ),
        "active_equality_member": False,
    },
    {
        "role": "MASTER_DESIGN_INPUT",
        "folder": "1_GELEN_KAGGLE_BASKILARI",
        "label": "Aktif üretim master tasarım girişi",
        "expected": (
            "pc_master_factory FACTORY_DIR olarak doğrudan kullanır. H/V master "
            "tasarımlar ve manifest burada bulunur; silinmez/yeniden adlandırılmaz."
        ),
        "active_equality_member": False,
    },
    {
        "role": "WORKING_POOL",
        "folder": "2_SABLON_HAVUZU",
        "label": "Aktif çalışma şablonları",
        "expected": "Aktif DB kimlikleriyle 1:1 kimlik eşleşmesi gerekir.",
        "active_equality_member": True,
    },
    {
        "role": "ORIGINAL_ARCHIVE",
        "folder": "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
        "label": "Ham / orijinal arşiv",
        "expected": (
            "Her aktif DB kimliğinin ham karşılığı burada bulunmalıdır. "
            "DB dışı eski/legacy ham dosyalar aktif bütünlük hatası değil, "
            "arşiv envanteri olarak raporlanır."
        ),
        "active_equality_member": True,
    },
    {
        "role": "PRIMARY_RENDER_OUTPUT",
        "folder": "3_URETILEN_MOCKUPLAR",
        "label": "Aktif ana mockup/render çıktıları",
        "expected": (
            "pc_master_factory ana render çıktısını buraya yazar. Aktif şablon "
            "havuzuyla sayı eşitliği beklenmez."
        ),
        "active_equality_member": False,
    },
    {
        "role": "EXCEL_EXPORT_OUTPUT",
        "folder": "4_EXCEL_YUKLEME_LISTELERI",
        "label": "Pazaryeri Excel çıktı alanı",
        "expected": (
            "Üretim sonrası yükleme listeleri burada tutulur; aktif şablon "
            "havuzuyla eşit olmak zorunda değildir."
        ),
        "active_equality_member": False,
    },
    {
        "role": "MANUAL_RENDER_INPUT",
        "folder": "MOCKUP A HAZIR GÖRSELLER",
        "label": "Manuel mockup motoru tasarım girişi",
        "expected": (
            "manuel_mockup_motoru bu klasördeki görselleri şablonlara giydirir. "
            "Amaçlı aktif araç girişidir; otomatik silinmez."
        ),
        "active_equality_member": False,
    },
    {
        "role": "MULTI_STORE_OUTPUT",
        "folder": "Mockup_Magaza_Klasorleri",
        "label": "Çoklu mağaza mockup çıktı alanı",
        "expected": (
            "pc_master_factory OUTPUT_COKLU_DIR olarak kullanır. Boş olması "
            "gereksiz olduğu anlamına gelmez."
        ),
        "active_equality_member": False,
    },
    {
        "role": "INBOX_STAGING",
        "folder": "YENI-BOS MOCKUP SABLON HAVUZU",
        "label": "Yeni şablon gelen kutusu / staging",
        "expected": (
            "Aktif havuzla eşit olmak zorunda değildir; işlenmemiş/bekleyen "
            "dosyaları içerir."
        ),
        "active_equality_member": False,
    },
    {
        "role": "RECOVERABLE_TRASH",
        "folder": "SILINEN_SABLONLAR_COP_KUTUSU",
        "label": "Geri alınabilir silinen şablonlar",
        "expected": "Aktif havuzla eşit değildir; silinen geçmişi içerir.",
        "active_equality_member": False,
    },
    {
        "role": "LEGACY_TRASH_CANDIDATE",
        "folder": "_COP_KUTUSU",
        "label": "Eski/yardımcı çöp alanı",
        "expected": "Silinmez; audit ile kullanım/referans durumu belirlenir.",
        "active_equality_member": False,
    },
    {
        "role": "PROCESSING_RECOVERY",
        "folder": "_KURTARMA_PROCESSING",
        "label": "Yarım kalan staging işlemleri kurtarma alanı",
        "expected": "Aktif havuzla eşit değildir; yalnız kurtarma kayıtları içerir.",
        "active_equality_member": False,
    },
    {
        "role": "SYSTEM_INTERNAL",
        "folder": "99_SISTEM_MOTORLARI_VE_KODLAR",
        "label": "Sistem motorları, loglar ve iç veriler",
        "expected": "Sistem iç klasörüdür; kullanıcı şablon eşitliğine dahil değildir.",
        "active_equality_member": False,
    },
    {
        "role": "REVIEW_SYSTEM_DATA",
        "folder": "SABLON_V2_MIMARI",
        "label": "İnceleme Merkezi DB/rapor/runtime verileri",
        "expected": "Sistem iç klasörüdür; kullanıcı şablon eşitliğine dahil değildir.",
        "active_equality_member": False,
    },
]


def _safe_progress(
    progress: Optional[Callable[[int, int, str], None]],
    current: int,
    total: int,
    message: str,
) -> None:
    if progress:
        progress(current, total, message)


def _should_stop(callback: Optional[Callable[[], bool]]) -> bool:
    return bool(callback and callback())


def _identity(filename: str) -> str:
    return Path(str(filename)).stem.casefold()


def _iter_image_files(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.casefold() in IMAGE_EXTS:
            yield path


def _scan_category_tree(root: Path) -> Dict[str, Dict[str, List[str]]]:
    result: Dict[str, Dict[str, List[str]]] = {}
    if not root.is_dir():
        return result

    for category_dir in sorted(
        (p for p in root.iterdir() if p.is_dir()),
        key=lambda p: p.name.casefold(),
    ):
        identities: Dict[str, List[str]] = {}
        for path in sorted(_iter_image_files(category_dir) or []):
            rel = path.relative_to(category_dir).as_posix()
            identities.setdefault(_identity(path.name), []).append(rel)
        result[category_dir.name] = identities
    return result


def _scan_top_level_folder(root: Path) -> dict:
    if not root.exists():
        return {
            "exists": False,
            "file_count": 0,
            "image_count": 0,
            "dir_count": 0,
            "size_bytes": 0,
        }

    file_count = 0
    image_count = 0
    dir_count = 0
    size_bytes = 0
    try:
        for path in root.rglob("*"):
            try:
                if path.is_dir():
                    dir_count += 1
                elif path.is_file():
                    file_count += 1
                    if path.suffix.casefold() in IMAGE_EXTS:
                        image_count += 1
                    size_bytes += int(path.stat().st_size)
            except OSError:
                continue
    except OSError:
        pass

    return {
        "exists": root.is_dir(),
        "file_count": file_count,
        "image_count": image_count,
        "dir_count": dir_count,
        "size_bytes": size_bytes,
    }


def _source_reference_inventory(source_root: Path, names: List[str]) -> Dict[str, dict]:
    lowered = {name: name.casefold() for name in names}
    refs = {
        name: {
            "reference_count": 0,
            "files": [],
            "runtime_reference_count": 0,
            "runtime_reference_files": [],
        }
        for name in names
    }
    if not source_root.is_dir() or not names:
        return refs

    text_exts = {
        ".py", ".ps1", ".bat", ".cmd", ".json", ".md", ".txt",
        ".html", ".js", ".yml", ".yaml", ".toml",
    }
    runtime_exts = {".py", ".ps1", ".bat", ".cmd", ".html", ".js"}
    ignored_parts = {
        ".git", "__pycache__", ".venv", "venv", "node_modules",
    }

    for path in source_root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in text_exts:
            continue
        if any(part in ignored_parts for part in path.parts):
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            text_value = path.read_text(
                encoding="utf-8",
                errors="ignore",
            ).casefold()
        except OSError:
            continue

        rel = path.relative_to(source_root).as_posix()
        rel_parts = set(Path(rel).parts)
        is_runtime_reference = bool(
            path.suffix.casefold() in runtime_exts
            and ".kilo" not in rel_parts
            and "tests" not in rel_parts
            and path.name not in {"create_analysis_doc.py"}
        )

        for name, needle in lowered.items():
            count = text_value.count(needle)
            if not count:
                continue
            refs[name]["reference_count"] += int(count)
            if len(refs[name]["files"]) < 12:
                refs[name]["files"].append(rel)

            if is_runtime_reference:
                refs[name]["runtime_reference_count"] += int(count)
                if len(refs[name]["runtime_reference_files"]) < 12:
                    refs[name]["runtime_reference_files"].append(rel)
    return refs


def _discover_all_top_level_folders(runtime_root: Path) -> List[Path]:
    if not runtime_root.is_dir():
        return []
    try:
        return sorted(
            [path for path in runtime_root.iterdir() if path.is_dir()],
            key=lambda p: p.name.casefold(),
        )
    except OSError:
        return []


def _folder_role_contract(runtime_root: Path, source_root: Path) -> List[dict]:
    known_by_folder = {item["folder"]: item for item in ROLE_SPECS}
    top_level = _discover_all_top_level_folders(runtime_root)
    known_names = list(known_by_folder)
    top_names = [path.name for path in top_level]
    refs = _source_reference_inventory(
        source_root,
        sorted(set(known_names + top_names)),
    )

    all_paths: Dict[str, Path] = {
        item["folder"]: runtime_root / item["folder"]
        for item in ROLE_SPECS
    }
    for path in top_level:
        all_paths.setdefault(path.name, path)

    rows = []
    for name, path in sorted(
        all_paths.items(),
        key=lambda item: item[0].casefold(),
    ):
        spec = known_by_folder.get(name)
        lower = name.casefold()
        if spec:
            role = spec["role"]
            label = spec["label"]
            expected = spec["expected"]
            equality = bool(spec["active_equality_member"])
            discovery = "CANONICAL_ROLE"
        elif "kaggle" in lower:
            role = "KAGGLE_FOLDER_CANDIDATE"
            label = "Kaggle ile ilişkili sınıflandırılmamış klasör"
            expected = (
                "Görevi audit ile belirlenir. Otomatik silinmez, taşınmaz, "
                "birleştirilmez veya yeniden adlandırılmaz."
            )
            equality = False
            discovery = "NAME_DISCOVERY"
        elif "mockup" in lower:
            role = "MOCKUP_FOLDER_CANDIDATE"
            label = "Mockup ile ilişkili sınıflandırılmamış klasör"
            expected = (
                "Görevi audit ile belirlenir. Otomatik silinmez, taşınmaz, "
                "birleştirilmez veya yeniden adlandırılmaz."
            )
            equality = False
            discovery = "NAME_DISCOVERY"
        else:
            role = "UNCLASSIFIED_TOP_LEVEL"
            label = "Henüz görev sözleşmesine alınmamış üst seviye klasör"
            expected = (
                "Otomatik silinmez veya taşınmaz. Önce kullanım amacı ve kod "
                "bağlantıları belirlenir."
            )
            equality = False
            discovery = "TOP_LEVEL_DISCOVERY"

        inventory = _scan_top_level_folder(path)
        reference = refs.get(name, {})
        rows.append({
            "folder": name,
            "absolute_path": str(path.resolve()),
            "role": role,
            "label": label,
            "expected_contract": expected,
            "active_equality_member": equality,
            "discovery": discovery,
            "exists": bool(inventory["exists"]),
            "inventory": inventory,
            "code_reference_count": int(
                reference.get("reference_count", 0)
            ),
            "code_reference_files": list(
                reference.get("files", [])
            ),
            "runtime_code_reference_count": int(
                reference.get("runtime_reference_count", 0)
            ),
            "runtime_code_reference_files": list(
                reference.get("runtime_reference_files", [])
            ),
            "read_only_audit": True,
            "automatic_delete_allowed": False,
        })
    return rows

def _db_inventory(settings: dict) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}
    categories = (settings or {}).get("kategoriler", {})
    if not isinstance(categories, dict):
        return result

    for category, category_data in categories.items():
        templates = (
            category_data.get("sablonlar", {})
            if isinstance(category_data, dict)
            else {}
        )
        if not isinstance(templates, dict):
            templates = {}
        result[str(category)] = {
            _identity(name): str(name)
            for name in templates.keys()
        }
    return result


def _issue(
    code: str,
    severity: str,
    category: str,
    identity: str,
    label: str,
    details: str,
) -> dict:
    scope = "ACTIVE_INTEGRITY"
    if code == "BACKUP_WITHOUT_DB":
        scope = "ARCHIVE_INVENTORY"
    elif code == "WORKING_WITHOUT_DB":
        scope = "WORKING_HYGIENE"
    elif "DUPLICATE_IDENTITY" in code:
        scope = "DUPLICATE_HYGIENE"
    elif code == "ACTIVE_IDENTITY_STILL_IN_STAGING":
        scope = "STAGING_INFO"

    return {
        "fingerprint": "|".join([
            str(code),
            str(category).casefold(),
            str(identity).casefold(),
        ]),
        "code": code,
        "severity": severity,
        "scope": scope,
        "category": category,
        "identity": identity,
        "label": label,
        "details": details,
    }


def _compare_active_sets(
    db: Dict[str, Dict[str, str]],
    working: Dict[str, Dict[str, List[str]]],
    backup: Dict[str, Dict[str, List[str]]],
    staging: Dict[str, Dict[str, List[str]]],
) -> Tuple[Dict[str, dict], Dict[str, Dict[str, dict]], List[dict]]:
    categories = sorted(
        set(db) | set(working) | set(backup) | set(staging),
        key=str.casefold,
    )
    category_rows: Dict[str, dict] = {}
    templates: Dict[str, Dict[str, dict]] = {}
    issues: List[dict] = []

    for category in categories:
        db_map = db.get(category, {})
        work_map = working.get(category, {})
        backup_map = backup.get(category, {})
        staging_map = staging.get(category, {})
        all_ids = sorted(
            set(db_map) | set(work_map) | set(backup_map) | set(staging_map)
        )
        cat_templates = {}
        matched = 0

        for identity in all_ids:
            in_db = identity in db_map
            work_files = list(work_map.get(identity, []))
            backup_files = list(backup_map.get(identity, []))
            staging_files = list(staging_map.get(identity, []))
            work_exists = bool(work_files)
            backup_exists = bool(backup_files)
            fully_matched = bool(in_db and work_exists and backup_exists)
            if fully_matched:
                matched += 1

            state_issues = []
            if in_db and not work_exists and not backup_exists:
                item = _issue(
                    "ACTIVE_RECORD_BOTH_FILES_MISSING",
                    "CRITICAL",
                    category,
                    identity,
                    "DB kaydı var; çalışma ve ham dosya yok",
                    "Aktif DB kimliği iki ana dosya alanında da bulunamadı.",
                )
                issues.append(item)
                state_issues.append(item["code"])
            elif in_db and not work_exists:
                item = _issue(
                    "ACTIVE_WORKING_MISSING",
                    "WARNING",
                    category,
                    identity,
                    "Aktif çalışma dosyası eksik",
                    "DB ve ham yedek var olabilir; çalışma kopyası bulunamadı.",
                )
                issues.append(item)
                state_issues.append(item["code"])
            elif in_db and not backup_exists:
                item = _issue(
                    "ACTIVE_BACKUP_MISSING",
                    "WARNING",
                    category,
                    identity,
                    "Ham/orijinal yedek eksik",
                    "DB ve çalışma kaydı var olabilir; korunmuş ham yedek bulunamadı.",
                )
                issues.append(item)
                state_issues.append(item["code"])

            if work_exists and not in_db:
                item = _issue(
                    "WORKING_WITHOUT_DB",
                    "WARNING",
                    category,
                    identity,
                    "Çalışma dosyası var; aktif DB kaydı yok",
                    "Dosya otomatik silinmeyecek; insan incelemesi gerekir.",
                )
                issues.append(item)
                state_issues.append(item["code"])

            if backup_exists and not in_db:
                item = _issue(
                    "BACKUP_WITHOUT_DB",
                    "INFO",
                    category,
                    identity,
                    "Ham yedek var; aktif DB kaydı yok",
                    "Yedek otomatik silinmeyecek; geçmiş/çöp/recovery ilişkisi incelenmeli.",
                )
                issues.append(item)
                state_issues.append(item["code"])

            if len(work_files) > 1:
                item = _issue(
                    "WORKING_DUPLICATE_IDENTITY",
                    "WARNING",
                    category,
                    identity,
                    "Çalışma havuzunda aynı kimliğe birden fazla dosya",
                    ", ".join(work_files),
                )
                issues.append(item)
                state_issues.append(item["code"])

            if len(backup_files) > 1:
                item = _issue(
                    "BACKUP_DUPLICATE_IDENTITY",
                    "WARNING",
                    category,
                    identity,
                    "Ham arşivde aynı kimliğe birden fazla dosya",
                    ", ".join(backup_files),
                )
                issues.append(item)
                state_issues.append(item["code"])

            if in_db and staging_files:
                item = _issue(
                    "ACTIVE_IDENTITY_STILL_IN_STAGING",
                    "INFO",
                    category,
                    identity,
                    "Aktif kimliğin staging kopyası da var",
                    "İşlenmiş dosyanın staging'de kalıp kalmadığı kontrol edilmeli.",
                )
                issues.append(item)
                state_issues.append(item["code"])

            display_name = (
                db_map.get(identity)
                or (work_files[0] if work_files else None)
                or (backup_files[0] if backup_files else None)
                or (staging_files[0] if staging_files else identity)
            )
            cat_templates[str(display_name)] = {
                "identity": identity,
                "db": bool(in_db),
                "working": bool(work_exists),
                "backup": bool(backup_exists),
                "staging": bool(staging_files),
                "working_files": work_files,
                "backup_files": backup_files,
                "staging_files": staging_files,
                "fully_matched_active": fully_matched,
                "issue_codes": state_issues,
            }

        category_issues = [
            item for item in issues if item["category"] == category
        ]
        category_rows[category] = {
            "db_count": len(db_map),
            "working_identity_count": len(work_map),
            "backup_identity_count": len(backup_map),
            "staging_identity_count": len(staging_map),
            "fully_matched_active_count": matched,
            "issue_count": len(category_issues),
            "active_integrity_issue_count": sum(
                1 for item in category_issues
                if item.get("scope") == "ACTIVE_INTEGRITY"
            ),
            "archive_inventory_count": sum(
                1 for item in category_issues
                if item.get("scope") == "ARCHIVE_INVENTORY"
            ),
            "working_hygiene_count": sum(
                1 for item in category_issues
                if item.get("scope") == "WORKING_HYGIENE"
            ),
            "duplicate_hygiene_count": sum(
                1 for item in category_issues
                if item.get("scope") == "DUPLICATE_HYGIENE"
            ),
            "critical_count": sum(
                1 for item in category_issues
                if item["severity"] == "CRITICAL"
            ),
            "warning_count": sum(
                1 for item in category_issues
                if item["severity"] == "WARNING"
            ),
            "info_count": sum(
                1 for item in category_issues
                if item["severity"] == "INFO"
            ),
        }
        templates[category] = cat_templates

    return category_rows, templates, issues


def _scan_trash_identity_counts(root: Path) -> dict:
    result = {
        "exists": root.is_dir(),
        "file_count": 0,
        "meta_count": 0,
        "categories": {},
    }
    if not root.is_dir():
        return result

    for path in root.iterdir():
        if not path.is_file():
            continue
        result["file_count"] += 1
        if path.name.endswith("_meta.json"):
            result["meta_count"] += 1
        parts = path.name.split("__")
        if len(parts) >= 2:
            category = parts[0]
            result["categories"][category] = (
                int(result["categories"].get(category, 0)) + 1
            )
    return result


def _report_diff(previous: Optional[dict], current: dict) -> dict:
    if not previous:
        return {
            "has_previous": False,
            "previous_saved_at": None,
            "new_issue_count": 0,
            "resolved_issue_count": 0,
            "unchanged_issue_count": 0,
            "new_issues": [],
            "resolved_issues": [],
        }

    old = {
        item.get("fingerprint"): item
        for item in previous.get("issues", [])
        if item.get("fingerprint")
    }
    new = {
        item.get("fingerprint"): item
        for item in current.get("issues", [])
        if item.get("fingerprint")
    }
    new_keys = sorted(set(new) - set(old))
    resolved_keys = sorted(set(old) - set(new))
    unchanged = set(new) & set(old)
    return {
        "has_previous": True,
        "previous_saved_at": previous.get("saved_at"),
        "new_issue_count": len(new_keys),
        "resolved_issue_count": len(resolved_keys),
        "unchanged_issue_count": len(unchanged),
        "new_issues": [new[key] for key in new_keys],
        "resolved_issues": [old[key] for key in resolved_keys],
    }


def workspace_consistency_report(
    runtime_root: str,
    source_root: str,
    settings: dict,
    *,
    progress: Optional[Callable[[int, int, str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> dict:
    runtime = Path(runtime_root).expanduser().resolve()
    source = Path(source_root).expanduser().resolve()
    total_steps = 8

    _safe_progress(progress, 0, total_steps, "Aktif DB kimlikleri okunuyor...")
    db = _db_inventory(settings)
    if _should_stop(should_stop):
        return {"success": False, "cancelled": True, "read_only": True}

    _safe_progress(progress, 1, total_steps, "Çalışma havuzu envanteri çıkarılıyor...")
    working = _scan_category_tree(runtime / "2_SABLON_HAVUZU")
    if _should_stop(should_stop):
        return {"success": False, "cancelled": True, "read_only": True}

    _safe_progress(progress, 2, total_steps, "Ham/orijinal arşiv envanteri çıkarılıyor...")
    backup = _scan_category_tree(
        runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
    )
    if _should_stop(should_stop):
        return {"success": False, "cancelled": True, "read_only": True}

    _safe_progress(progress, 3, total_steps, "Staging/gelen kutusu taranıyor...")
    staging = _scan_category_tree(
        runtime / "YENI-BOS MOCKUP SABLON HAVUZU"
    )

    _safe_progress(progress, 4, total_steps, "DB ↔ çalışma ↔ ham kimlikleri karşılaştırılıyor...")
    categories, templates, issues = _compare_active_sets(
        db,
        working,
        backup,
        staging,
    )
    if _should_stop(should_stop):
        return {"success": False, "cancelled": True, "read_only": True}

    _safe_progress(progress, 5, total_steps, "Çöp ve recovery alanları sayılıyor...")
    trash = _scan_trash_identity_counts(
        runtime / "SILINEN_SABLONLAR_COP_KUTUSU"
    )
    legacy_trash = _scan_top_level_folder(runtime / "_COP_KUTUSU")
    recovery = _scan_top_level_folder(runtime / "_KURTARMA_PROCESSING")

    _safe_progress(progress, 6, total_steps, "Kaggle ve Mockup klasörleri keşfediliyor...")
    folders = _folder_role_contract(runtime, source)
    kaggle_roles = {
        "LEGACY_KAGGLE_APPROVAL_INBOX",
        "MASTER_DESIGN_INPUT",
        "KAGGLE_FOLDER_CANDIDATE",
    }
    mockup_roles = {
        "PRIMARY_RENDER_OUTPUT",
        "MANUAL_RENDER_INPUT",
        "MULTI_STORE_OUTPUT",
        "MOCKUP_FOLDER_CANDIDATE",
    }
    kaggle_folders = [
        row for row in folders
        if row["role"] in kaggle_roles
    ]
    mockup_folders = [
        row for row in folders
        if row["role"] in mockup_roles
    ]
    unclassified_folders = [
        row for row in folders
        if row["role"] == "UNCLASSIFIED_TOP_LEVEL"
    ]

    _safe_progress(progress, 7, total_steps, "Özet hazırlanıyor...")
    active_total = sum(row["db_count"] for row in categories.values())
    fully_matched = sum(
        row["fully_matched_active_count"]
        for row in categories.values()
    )
    summary = {
        "active_db_total": active_total,
        "fully_matched_active_total": fully_matched,
        "active_mismatch_total": max(0, active_total - fully_matched),
        "issue_count": len(issues),
        "active_integrity_issue_count": sum(
            1 for item in issues
            if item.get("scope") == "ACTIVE_INTEGRITY"
        ),
        "archive_inventory_count": sum(
            1 for item in issues
            if item.get("scope") == "ARCHIVE_INVENTORY"
        ),
        "working_hygiene_count": sum(
            1 for item in issues
            if item.get("scope") == "WORKING_HYGIENE"
        ),
        "duplicate_hygiene_count": sum(
            1 for item in issues
            if item.get("scope") == "DUPLICATE_HYGIENE"
        ),
        "critical_count": sum(
            1 for item in issues if item["severity"] == "CRITICAL"
        ),
        "warning_count": sum(
            1 for item in issues if item["severity"] == "WARNING"
        ),
        "info_count": sum(
            1 for item in issues if item["severity"] == "INFO"
        ),
        "category_count": len(categories),
        "kaggle_folder_count": len(kaggle_folders),
        "mockup_folder_count": len(mockup_folders),
        "top_level_folder_count": len(
            [row for row in folders if row.get("exists")]
        ),
        "unclassified_top_level_count": len(
            [row for row in unclassified_folders if row.get("exists")]
        ),
        "trash_file_count": int(trash["file_count"]),
        "recovery_file_count": int(recovery["file_count"]),
    }

    _safe_progress(progress, total_steps, total_steps, "Read-only tutarlılık raporu hazır.")
    return {
        "success": True,
        "read_only": True,
        "assets_mutated": False,
        "auto_deleted": 0,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "runtime_root": str(runtime),
        "source_root": str(source),
        "contract": {
            "active_identity_rule": (
                "Aktif DB kimliği ↔ çalışma kopyası ↔ ham/orijinal yedek "
                "kimlik olarak 1:1 bulunmalıdır."
            ),
            "staging_rule": (
                "Staging/gelen kutusu aktif havuzla eşit değildir; yalnız "
                "bekleyen veya başarısız girişleri barındırabilir."
            ),
            "trash_recovery_rule": (
                "Çöp ve recovery aktif eşitlik kümesine dahil değildir."
            ),
            "destructive_actions": "DISABLED",
        },
        "summary": summary,
        "categories": categories,
        "templates": templates,
        "issues": issues,
        "folders": folders,
        "kaggle_folders": kaggle_folders,
        "mockup_folders": mockup_folders,
        "unclassified_top_level_folders": unclassified_folders,
        "trash": trash,
        "legacy_trash": legacy_trash,
        "recovery": recovery,
    }


def _report_root(runtime_root: str) -> Path:
    return (
        Path(runtime_root).expanduser().resolve()
        / "SABLON_V2_MIMARI"
        / "reports"
        / "workspace_consistency"
    )


def load_latest_workspace_report(runtime_root: str) -> Optional[dict]:
    path = _report_root(runtime_root) / "latest.json"
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not data.get("success"):
        return None
    return data


def save_workspace_report(runtime_root: str, report: dict) -> dict:
    if not isinstance(report, dict) or not report.get("success"):
        raise ValueError("Geçersiz workspace tutarlılık raporu.")

    root = _report_root(runtime_root)
    history = root / "history"
    history.mkdir(parents=True, exist_ok=True)
    previous = load_latest_workspace_report(runtime_root)

    saved = dict(report)
    saved["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    saved["saved_report"] = True
    saved["diff"] = _report_diff(previous, saved)

    token = uuid.uuid4().hex[:8]
    stamp = time.strftime("%Y%m%d_%H%M%S")
    history_path = history / f"{stamp}_{token}.json"
    latest_path = root / "latest.json"

    serialized = json.dumps(
        saved,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    for target in (history_path, latest_path):
        tmp = target.with_name(target.name + f".{uuid.uuid4().hex}.tmp")
        try:
            with tmp.open("wb") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, target)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
    return saved


def workspace_report_history(runtime_root: str, limit: int = 20) -> List[dict]:
    root = _report_root(runtime_root) / "history"
    if not root.is_dir():
        return []

    rows = []
    for path in sorted(
        root.glob("*.json"),
        key=lambda p: p.name,
        reverse=True,
    )[: max(1, min(100, int(limit)))]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            summary = data.get("summary", {})
            rows.append({
                "file": path.name,
                "saved_at": data.get("saved_at"),
                "generated_at": data.get("generated_at"),
                "active_db_total": int(summary.get("active_db_total", 0)),
                "fully_matched_active_total": int(
                    summary.get("fully_matched_active_total", 0)
                ),
                "issue_count": int(summary.get("issue_count", 0)),
                "active_integrity_issue_count": int(
                    summary.get("active_integrity_issue_count", 0)
                ),
                "archive_inventory_count": int(
                    summary.get("archive_inventory_count", 0)
                ),
                "working_hygiene_count": int(
                    summary.get("working_hygiene_count", 0)
                ),
                "duplicate_hygiene_count": int(
                    summary.get("duplicate_hygiene_count", 0)
                ),
                "critical_count": int(summary.get("critical_count", 0)),
                "warning_count": int(summary.get("warning_count", 0)),
                "kaggle_folder_count": int(summary.get("kaggle_folder_count", 0)),
                "mockup_folder_count": int(summary.get("mockup_folder_count", 0)),
                "unclassified_top_level_count": int(
                    summary.get("unclassified_top_level_count", 0)
                ),
            })
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return rows
