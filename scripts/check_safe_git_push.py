"""Block GitHub publication of personal mockup photos, DBs and generated assets.

Only evaluates the checked-out ref and its commit ancestry; never modifies files.
"""
from __future__ import annotations
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "feat/v4-1-windows-safe-guided"
BLOCKED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".db", ".sqlite", ".sqlite3", ".xlsx", ".xls", ".csv", ".pem", ".key", ".env"}
BLOCKED_DIRS = {"ORNEK_PETEK_MOCKUPLARI", "GUNLUK_KULLANICI_VERILERI", "USER_WORKSPACE", "PRIVATE", ".venv", "venv"}

def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.STDOUT)

def forbidden(name: str) -> bool:
    path = Path(name)
    return bool(set(path.parts) & BLOCKED_DIRS) or path.suffix.lower() in BLOCKED_SUFFIXES

def main() -> int:
    branch = git("branch", "--show-current").decode().strip()
    if branch != BRANCH:
        print(f"DURDURULDU: izin verilen Git dalı {BRANCH}; mevcut {branch!r}")
        return 2
    tracked = [p.decode("utf-8", errors="replace") for p in git("ls-files", "-z").split(b"\0") if p]
    # Every object reachable from this branch is examined, not just the latest tree.
    ancestors = git("rev-list", "--objects", "HEAD").decode("utf-8", errors="replace").splitlines()
    history_paths = [line.split(" ", 1)[1] for line in ancestors if " " in line]
    blocked = sorted(set(x for x in tracked + history_paths if forbidden(x)))
    if blocked:
        print("DURDURULDU: Git geçmişinde veya izlenen dosyalarda kişisel/veri dosyaları bulunuyor:")
        for name in blocked[:30]: print(" -", name)
        return 3
    # Any source changes must be committed so exactly-reviewed files are published.
    if git("status", "--porcelain").strip():
        print("DURDURULDU: Git çalışma ağacı temiz değil. Önce değişiklikleri denetleyip commit yapın.")
        return 4
    print("GÜVENLİ: branch geçmişinde özel görseller/veritabanları yok; değişiklikler kayıtlı.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.CalledProcessError) as exc:
        print("DURDURULDU: Git güvenlik kontrolü çalışmadı:", exc)
        sys.exit(5)
