"""PETEK physical folders mapped to one logical production category.

The user's existing Petek_Dolabi directory is supported without renaming it.
06_Petek_Kapama is the INTERNAL category ID. Never create a competing active
alias or move/erase photos to 'fix' names. Separate PETEK mask registry lives
outside the synchronized workspace under LOCALAPPDATA/GorselMockup/PetekV3.
"""
from __future__ import annotations
from pathlib import Path

CATEGORY = '06_Petek_Kapama'
FRIENDLY = 'Petek_Dolabi'
NAMES = (FRIENDLY, CATEGORY)
SECTIONS = (
    'YENI-BOS MOCKUP SABLON HAVUZU',
    '2_SABLON_HAVUZU',
    '2_SABLON_HAVUZU_ORIJINAL_YEDEK',
)
IMAGE_SUFFIXES = {'.png','.jpg','.jpeg','.webp'}


def petek_directory(workspace: Path, section: str) -> Path:
    """Read-only resolve an existing PETEK folder; don't make duplicates."""
    if section not in SECTIONS:
        raise ValueError('UNKNOWN_PETEK_SECTION')
    base = Path(workspace) / section
    if base.is_symlink():
        raise ValueError('SYMLINK_PETEK_PARENT')
    aliases = [base / name for name in NAMES]
    for path in aliases:
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError('UNSAFE_PETEK_PATH: ' + str(path))
    existing = [path for path in aliases if path.is_dir()]
    active = [
        path for path in existing
        if any(p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES for p in path.iterdir())
    ]
    if len(active) > 1:
        raise ValueError('PETEK_ALIAS_CONFLICT: Her iki klasörde görseller var; otomatik birleştirme yok.')
    if active:
        return active[0]
    if existing:
        return existing[0]  # User-facing Petek_Dolabi wins when empty.
    return aliases[0]


def prepare_petek_folders(workspace: Path) -> dict:
    """Explicit create-only bootstrap, no modification of legacy images or DB."""
    root = Path(workspace)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('WORKSPACE_MISSING_OR_SYMLINK')
    db = root / 'SABLON_V2_MIMARI' / 'ayarlar.db'
    if db.is_symlink() or not db.is_file():
        raise ValueError('WORKSPACE_DB_REQUIRED')
    # Preflight ALL paths before the first mkdir. Both aliases with live images
    # must be manually reconciled, not silently merged or arbitrarily selected.
    resolved = {section: petek_directory(root,section) for section in SECTIONS}
    created = []
    for path in resolved.values():
        if not path.exists():
            if path.parent.is_symlink():
                raise ValueError('SYMLINK_PETEK_PARENT')
            path.mkdir(parents=True, exist_ok=False)
            created.append(str(path))
    return {'logical_category': CATEGORY, 'user_visible_name': FRIENDLY,
            'paths': {section:str(path) for section,path in resolved.items()},
            'created': created,
            'note': 'PETEK_V3 maske/onay kayıtları yerel AppData dizininde; fotoğraf silinmedi veya taşınmadı.'}
