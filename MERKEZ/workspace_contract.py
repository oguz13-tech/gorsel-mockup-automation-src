"""Canonical code/runtime workspace contract.

The application deliberately has two roots with different roles:

* ``CODEX_ACTIVE`` contains the signed source tree and immutable application
  assets.
* its parent (or an explicitly selected runtime) contains the live database,
  settings and template pools.

This module is the only place where those roots are resolved.  Resolution in
non-strict mode is useful to import read-only utilities and synthetic tests;
all launchers and serving paths must call :func:`resolve_contract` with
``validate=True`` and fail closed on an invalid contract.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Mapping


class WorkspaceContractError(RuntimeError):
    """The source/runtime pair is missing, ambiguous or unsafe."""


CODE_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ENV_KEYS = ("GORSEL_RUNTIME_ROOT", "MOCKUP_RUNTIME_WORKSPACE")
RUNTIME_POINTER_CANDIDATES = (
    ("GorselMockup", "UnifiedCenter", "workspace.json"),
    ("JarvisMockup", "runtime_workspace.txt"),
)


def _absolute(value: str | os.PathLike) -> Path:
    return Path(value).expanduser().absolute()


def _is_reparse_or_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        # FILE_ATTRIBUTE_REPARSE_POINT.  It catches junctions on Windows;
        # ordinary POSIX files simply do not expose this attribute.
        return bool(int(getattr(path.stat(), "st_file_attributes", 0)) & 0x400)
    except OSError:
        return False


def _read_pointer(path: Path) -> str | None:
    if not path.is_file() or _is_reparse_or_symlink(path):
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if path.suffix.casefold() == ".json":
            raw = str(json.loads(raw).get("path") or "").strip()
        return raw or None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _pointer_path_candidates(env: Mapping[str, str]) -> list[Path]:
    base_text = str(env.get("LOCALAPPDATA") or "").strip()
    if base_text:
        base = _absolute(base_text)
        return [
            base / "GorselMockup" / "UnifiedCenter" / "workspace.json",
            base / "JarvisMockup" / "runtime_workspace.txt",
        ]
    return [
        Path.home() / ".gorsel_mockup" / "GorselMockup" / "UnifiedCenter" / "workspace.json",
        Path.home() / "AppData" / "Local" / "JarvisMockup" / "runtime_workspace.txt",
        Path.home() / ".jarvis_mockup" / "JarvisMockup" / "runtime_workspace.txt",
    ]


def resolve_code_root(code_root: str | os.PathLike | None = None) -> Path:
    """Return the source tree containing this module, never the live root."""
    selected = _absolute(code_root) if code_root is not None else CODE_ROOT
    return selected


def resolve_runtime_root(
    *,
    code_root: str | os.PathLike | None = None,
    runtime_root: str | os.PathLike | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve one runtime candidate using one deterministic precedence order.

    Explicit values and stale pointers are not silently replaced.  This is
    important when an old OneDrive checkout still exists beside the portable
    installation.
    """
    environment = os.environ if env is None else env
    if runtime_root is not None:
        return _absolute(runtime_root)

    for key in RUNTIME_ENV_KEYS:
        raw = str(environment.get(key) or "").strip()
        if raw:
            return _absolute(raw)

    for pointer in _pointer_path_candidates(environment):
        if not pointer.exists():
            continue
        raw = _read_pointer(pointer)
        if not raw:
            raise WorkspaceContractError(f"Runtime pointer okunamadı: {pointer}")
        return _absolute(raw)

    source = resolve_code_root(code_root)
    # The canonical portable installation is C:\GorselUretimMerkezi\CODEX_ACTIVE
    # beside C:\GorselUretimMerkezi.  No historical OneDrive yedek is used.
    return source.parent


@dataclass(frozen=True)
class WorkspaceContract:
    code_root: Path
    runtime_root: Path
    database: Path
    ayarlar_json: Path
    source_identity: str = "CODEX_ACTIVE"
    runtime_identity: str = "LIVE_RUNTIME"

    def as_dict(self) -> dict[str, str]:
        return {
            "code_root": str(self.code_root),
            "runtime_root": str(self.runtime_root),
            "database": str(self.database),
            "ayarlar_json": str(self.ayarlar_json),
            "source_identity": self.source_identity,
            "runtime_identity": self.runtime_identity,
        }

    def validate(self) -> list[str]:
        problems: list[str] = validate_code_root(self.code_root)
        code = self.code_root
        runtime = self.runtime_root

        if _is_reparse_or_symlink(runtime) or not runtime.is_dir():
            problems.append(f"Runtime kökü yok veya güvenli değil: {runtime}")
        if code == runtime:
            problems.append("Kaynak ve runtime kökleri aynı olamaz.")

        required_runtime = (
            (self.ayarlar_json, "ayarlar.json"),
            (runtime / "SABLON_V2_MIMARI", "SABLON_V2_MIMARI"),
            (self.database, "SABLON_V2_MIMARI/ayarlar.db"),
            (runtime / "2_SABLON_HAVUZU", "2_SABLON_HAVUZU"),
            (runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK", "2_SABLON_HAVUZU_ORIJINAL_YEDEK"),
        )
        for item, label in required_runtime:
            if not item.exists() or _is_reparse_or_symlink(item):
                problems.append(f"Runtime öğesi yok veya güvenli değil ({label}): {item}")
        return problems

    def require_valid(self) -> "WorkspaceContract":
        problems = self.validate()
        if problems:
            raise WorkspaceContractError("Çalışma alanı sözleşmesi geçersiz:\n" + "\n".join(problems))
        return self


def validate_code_root(code_root: str | os.PathLike) -> list[str]:
    """Validate only the immutable source side of the contract."""
    code = _absolute(code_root)
    problems: list[str] = []
    if _is_reparse_or_symlink(code) or not code.is_dir():
        problems.append(f"Kaynak kod kökü yok veya güvenli değil: {code}")
    for relative in ("MERKEZ", "SABLON_V2_MIMARI/app.py", "SABLON_V2_MIMARI/core/db.py"):
        item = code / relative
        if not item.is_file() and relative != "MERKEZ":
            problems.append(f"Kaynak ağacında zorunlu öğe yok: {item}")
        elif relative == "MERKEZ" and not item.is_dir():
            problems.append(f"Kaynak ağacında zorunlu öğe yok: {item}")
        elif _is_reparse_or_symlink(item):
            problems.append(f"Kaynak ağacında bağlantı/reparse öğesi reddedildi: {item}")
    source_db = code / "SABLON_V2_MIMARI" / "ayarlar.db"
    if source_db.exists():
        problems.append(f"Kaynak kod kökünde canlı DB bulundu: {source_db}")
    return problems


def resolve_contract(
    *,
    code_root: str | os.PathLike | None = None,
    runtime_root: str | os.PathLike | None = None,
    env: Mapping[str, str] | None = None,
    validate: bool = False,
) -> WorkspaceContract:
    code = resolve_code_root(code_root)
    runtime = resolve_runtime_root(code_root=code, runtime_root=runtime_root, env=env)
    contract = WorkspaceContract(
        code_root=code,
        runtime_root=runtime,
        database=runtime / "SABLON_V2_MIMARI" / "ayarlar.db",
        ayarlar_json=runtime / "ayarlar.json",
    )
    if validate:
        contract.require_valid()
    return contract


def contract_report(**kwargs) -> dict[str, object]:
    """Read-only diagnostic suitable for the center and support reports."""
    contract = resolve_contract(**kwargs)
    problems = contract.validate()
    return {**contract.as_dict(), "ready": not problems, "problems": problems}

