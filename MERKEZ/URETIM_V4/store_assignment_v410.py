"""Read-only, explicit store/category mockup inventory for safe manual assignment.

Only mockup source identities are exclusive across stores. A raw artwork/design
is deliberately NOT part of store ownership; it may be rendered in many stores
using distinct approved mockup sources. No pHash/AI similarity checks.
"""
from __future__ import annotations
from .store_profiles_v47 import key_for


def status_inventory(store: str, category: str, approved: list[dict], config: dict) -> list[dict]:
    """Return ordered visible rows with owner/status; never mutate store config."""
    stores = config.get('stores', {})
    if store not in stores:
        raise ValueError('Önce geçerli bir mağaza seçin.')
    owners_by_key, owners_by_sha, owners_by_identity = {}, {}, {}
    for name, info in stores.items():
        for key in info.get('templates', ()):
            owners_by_key[key] = name
            owners_by_sha[key.rsplit('@', 1)[-1].lower()] = name
            owners_by_identity[key.rsplit('@', 1)[0]] = name
    rows = []
    for item in approved:
        if category != 'Tümü' and item['category'] != category:
            continue
        key = key_for(item)
        sha = str(item['source_sha']).lower()
        owner = owners_by_key.get(key) or owners_by_sha.get(sha)
        stale_owner = owners_by_identity.get(key.rsplit('@', 1)[0])
        if owner:
            state = 'assigned_here' if owner == store else 'used_elsewhere'
        elif stale_owner:
            owner = stale_owner
            state = 'stale'
        else:
            state = 'available'
        rows.append({'key': key, 'item': item, 'owner': owner, 'state': state})
    return sorted(rows, key=lambda r: (r['item']['category'], str(r['item']['uid']).casefold()))


def checked_assignment(store: str, category: str, checked: set[str], approved: list[dict], config: dict) -> list[dict]:
    """Fail closed if selection became stale or moved to a different store."""
    if not checked:
        raise ValueError('Önce atanacak mockup görsellerini seçin.')
    view = status_inventory(store, category, approved, config)
    by_key = {row['key']: row for row in view}
    result = []
    for key in sorted(checked):
        row = by_key.get(key)
        if row is None:
            raise ValueError('Şablon listesi değişmiş. Yenileyip tekrar seçin.')
        if row['state'] != 'available':
            raise ValueError(f"Mockup başka mağazada kullanılıyor veya zaten atanmış: {row['item']['uid']} — {row['owner']}")
        result.append(row['item'])
    return result


def assigned_for_store(store: str, approved: list[dict], config: dict) -> list[dict]:
    if store not in config.get('stores', {}):
        raise ValueError('Mağaza bulunamadı.')
    keys = set(config['stores'][store]['templates'])
    approved_by_key = {key_for(item): item for item in approved}
    output = []
    for key in sorted(keys):
        item = approved_by_key.get(key)
        output.append({'key': key, 'item': item, 'stale': item is None})
    return output
