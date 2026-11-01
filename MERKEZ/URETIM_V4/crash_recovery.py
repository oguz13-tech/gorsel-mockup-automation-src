"""V4.0 User-Approved Crash, Lock, and Interrupted Batch Recovery Engine.

Never silently deletes user files or auto-completes unverified renders.
1. `inspect_interrupted_state`: Read-only diagnostic of stale lock files
   (checks whether the recorded PID is still alive) and interrupted `PENDING` /
   `REVIEW_REQUIRED` ledger rows across both Unified V4 and PETEK V3 ledgers.
2. `recover_interrupted_state`: Requires explicit human confirmation
   (`confirm='I_APPROVE_SAFE_CRASH_RECOVERY'`) and operator name. Moves any
   partial/unverified output file from an interrupted `PENDING` row into an
   immutable quarantine folder (`KARANTINA_KESINTI/<timestamp>/`), removes
   dead-PID lock files, resets interrupted `PENDING` rows so the next batch run
   resumes cleanly from checkpoint without re-rendering verified `RENDERED`
   outputs, and writes an atomic SHA-verified recovery audit receipt.
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from PETEK_V3 import engine as petek_engine


def _is_pid_alive(pid: int) -> bool:
    """Return True if an OS process with `pid` is currently alive."""
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _inspect_lock_file(lock_path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "lock_path": str(lock_path),
        "exists": False,
        "pid": None,
        "pid_alive": False,
        "stale_lock": False,
    }
    if not lock_path.exists() and not lock_path.is_symlink():
        return info
    info["exists"] = True
    if lock_path.is_symlink():
        info["stale_lock"] = True
        info["reason"] = "SYMLINK_LOCK"
        return info
    try:
        raw = lock_path.read_text(encoding="utf-8", errors="replace").strip()
        pid = int(raw.splitlines()[0].strip())
        info["pid"] = pid
        info["pid_alive"] = _is_pid_alive(pid)
        info["stale_lock"] = not info["pid_alive"]
    except (ValueError, IndexError, OSError):
        info["stale_lock"] = True
    return info


def inspect_interrupted_state(
    ledger_db_path: Path,
    lock_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Read-only inspection of lock state and interrupted/unfinished ledger rows."""
    ledger_db_path = Path(ledger_db_path)
    lock_path = Path(lock_path)
    output_root = Path(output_root)

    lock_info = _inspect_lock_file(lock_path)
    pending_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    rendered_verified = 0
    rendered_corrupt: list[dict[str, Any]] = []

    if ledger_db_path.is_file() and not ledger_db_path.is_symlink():
        with sqlite3.connect(ledger_db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10) as con:
            con.row_factory = sqlite3.Row
            for row in con.execute("SELECT * FROM artifact ORDER BY key"):
                rec = dict(row)
                out_path = Path(rec["output"])
                exists = out_path.exists() and not out_path.is_symlink()
                if rec["status"] == "PENDING":
                    pending_rows.append(
                        {
                            "key": rec["key"],
                            "sku": rec["sku"],
                            "uid": rec["uid"],
                            "art_name": rec["art_name"],
                            "output": str(out_path),
                            "partial_file_exists": exists,
                        }
                    )
                elif rec["status"] == "REVIEW_REQUIRED":
                    review_rows.append(
                        {
                            "key": rec["key"],
                            "sku": rec["sku"],
                            "uid": rec["uid"],
                            "art_name": rec["art_name"],
                            "output": str(out_path),
                            "message": rec.get("message", ""),
                            "file_exists": exists,
                        }
                    )
                elif rec["status"] == "RENDERED":
                    if exists and out_path.is_file() and petek_engine.digest(out_path) == rec["output_sha"]:
                        rendered_verified += 1
                    else:
                        rendered_corrupt.append(
                            {
                                "key": rec["key"],
                                "sku": rec["sku"],
                                "output": str(out_path),
                                "expected_sha": rec["output_sha"],
                            }
                        )

    recovery_needed = bool(lock_info["stale_lock"] or pending_rows or review_rows)
    return {
        "ledger_db": str(ledger_db_path),
        "output_root": str(output_root),
        "lock": lock_info,
        "rendered_verified_count": rendered_verified,
        "rendered_corrupt_count": len(rendered_corrupt),
        "rendered_corrupt": rendered_corrupt,
        "interrupted_pending_count": len(pending_rows),
        "interrupted_pending": pending_rows,
        "review_required_count": len(review_rows),
        "review_required": review_rows,
        "recovery_needed": recovery_needed,
        "can_recover_safely": not lock_info["pid_alive"],
    }


def recover_interrupted_state(
    ledger_db_path: Path,
    lock_path: Path,
    output_root: Path,
    reports_root: Path,
    *,
    reviewer: str,
    confirm: str,
    requeue_review_required: bool = False,
) -> dict[str, Any]:
    """Perform explicit user-approved recovery of stale lock and interrupted PENDING jobs.

    - Refuses to run if `confirm != 'I_APPROVE_SAFE_CRASH_RECOVERY'` or `reviewer` is blank.
    - Refuses to remove a lock if the owning PID is still alive.
    - Quarantines any partial file on disk into `KARANTINA_KESINTI/<stamp>/` (no deletion).
    - Removes `PENDING` rows (and optionally `REVIEW_REQUIRED` rows if requested) so
      re-running the batch cleanly re-renders them while reusing all `RENDERED` rows.
    """
    if confirm != "I_APPROVE_SAFE_CRASH_RECOVERY":
        raise petek_engine.MaskError(
            "Kesinti kurtarma için açık kullanıcı onayı (I_APPROVE_SAFE_CRASH_RECOVERY) gerekli."
        )
    if not str(reviewer or "").strip():
        raise petek_engine.MaskError("Kurtarmayı onaylayan operatör adı boş olamaz.")

    state = inspect_interrupted_state(ledger_db_path, lock_path, output_root)
    if state["lock"]["pid_alive"]:
        raise petek_engine.MaskError(
            f"Üretim işlemi hâlen aktif (PID {state['lock']['pid']}). Aktif kilit silinemez."
        )

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    reports_root = Path(reports_root).resolve()
    reports_root.mkdir(parents=True, exist_ok=True)
    quarantine_dir = reports_root.parent / "KARANTINA_KESINTI" / stamp

    quarantined_files: list[dict[str, str]] = []
    cleared_keys: list[str] = []

    target_rows = list(state["interrupted_pending"])
    if requeue_review_required:
        target_rows.extend(state["review_required"])

    output_root_resolved = Path(output_root).resolve()
    for item in target_rows:
        out_path = Path(item["output"])
        if out_path.exists() and not out_path.is_symlink():
            resolved = out_path.resolve()
            if output_root_resolved in resolved.parents or resolved == output_root_resolved:
                quarantine_dir.mkdir(parents=True, exist_ok=True)
                dest = quarantine_dir / f"{item['key']}_{out_path.name}"
                shutil.move(str(out_path), str(dest))
                quarantined_files.append(
                    {
                        "key": item["key"],
                        "original_path": str(out_path),
                        "quarantined_to": str(dest),
                        "sha256": petek_engine.digest(dest),
                    }
                )

    if Path(ledger_db_path).is_file() and not Path(ledger_db_path).is_symlink():
        with sqlite3.connect(str(ledger_db_path), timeout=30) as con:
            for item in target_rows:
                key = item["key"]
                if requeue_review_required:
                    cur = con.execute(
                        "DELETE FROM artifact WHERE key=? AND status IN ('PENDING','REVIEW_REQUIRED')",
                        (key,),
                    )
                else:
                    cur = con.execute(
                        "DELETE FROM artifact WHERE key=? AND status='PENDING'",
                        (key,),
                    )
                if cur.rowcount:
                    cleared_keys.append(key)

    lock_removed = False
    if state["lock"]["exists"] and state["lock"]["stale_lock"]:
        Path(lock_path).unlink(missing_ok=True)
        lock_removed = True

    receipt = {
        "timestamp": stamp,
        "reviewer": str(reviewer).strip(),
        "confirm": confirm,
        "lock_removed": lock_removed,
        "cleared_interrupted_keys": cleared_keys,
        "quarantined_partial_files": quarantined_files,
        "preserved_rendered_verified_count": state["rendered_verified_count"],
    }
    report_path = reports_root / f"KESINTI_KURTARMA_RAPORU_{stamp}.json"
    petek_engine.atomic_new_file(
        report_path,
        json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8"),
    )
    receipt["report_path"] = str(report_path)
    return receipt
