"""Read-only evidence for one store / production selection snapshot.

The file cannot reassign, rekey, approve or modify any store, source or ledger.
Matching for ownership is the full category:uid@source_sha identity. The GUI
uses UID-only selection but the report always exposes the full key and owner.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from .store_profiles_v47 import key_for


def describe_template(item: dict, *, owner: str | None = None) -> dict:
    source = str(item.get('source') or '')
    return {'uid': str(item['uid']), 'category': str(item['category']),
            'source_sha': str(item['source_sha']),
            'filename': Path(source).name if source else str(item['uid']),
            'key': key_for(item), 'owner': owner}


def compare_store_selection(store_names, selected_uids, approved_templates, profile_config):
    """Snapshot, per-store intersection and unassigned selections without writes.

    Does not make a guessed assignment or replace a selected UID. Duplicate
    identifiers are reported and rejected before a real production operation.
    """
    requested = list(store_names)
    chosen_list = [str(uid) for uid in selected_uids]
    selected = set(chosen_list)
    approved = list(approved_templates)
    by_key = {key_for(item): item for item in approved}
    duplicate_key = len(by_key) != len(approved)
    by_uid = {}
    by_identity = {}
    for item in approved:
        by_uid.setdefault(str(item['uid']), []).append(item)
        by_identity.setdefault((str(item['category']), str(item['uid'])), []).append(item)
    duplicates = sorted(uid for uid, items in by_uid.items() if len(items) > 1)
    owner_by_key, owner_by_sha, owner_by_identity = {}, {}, {}
    for store, info in profile_config.get('stores', {}).items():
        for key in info.get('templates', []):
            owner_by_key[key] = store
            owner_by_sha[key.rsplit('@', 1)[-1].lower()] = store
            owner_by_identity[key.rsplit('@', 1)[0]] = store
    # For stores under active selection, a UID is valid only when its complete
    # category+UID+SHA key appears in a corresponding store profile.
    active_keys = {key for store in requested
                   for key in profile_config.get('stores', {}).get(store, {}).get('templates', [])}
    details = []
    all_valid = set()
    all_assigned = set()
    for name in requested:
        info = profile_config.get('stores', {}).get(name)
        if not isinstance(info, dict):
            details.append({'store': name, 'status': 'STORE_NOT_FOUND',
                            'assigned': [], 'matched': [], 'stale': [],
                            'unselected': [], 'stale_reasons': []})
            continue
        assigned = list(info.get('templates', []))
        all_assigned.update(assigned)
        valid = [(key, by_key[key]) for key in assigned if key in by_key]
        stale = [key for key in assigned if key not in by_key]
        reasons = []
        for key in stale:
            identity = key.rsplit('@', 1)[0]
            matching = [describe_template(item) for item in approved
                        if f"{item['category']}:{item['uid']}" == identity]
            reasons.append({'key': key,
                            'reason': 'SOURCE_SHA_CHANGED' if matching else 'APPROVAL_OR_UID_MISSING',
                            'current': matching})
        matched = [(key, t) for key, t in valid if str(t['uid']) in selected]
        unselected = [(key, t) for key, t in valid if str(t['uid']) not in selected]
        all_valid.update(key for key, _ in valid)
        if not assigned:
            status = 'NO_ASSIGNMENT'
        elif stale:
            status = 'STALE_APPROVAL_OR_SHA'
        elif not selected:
            status = 'NO_PRODUCTION_SELECTION'
        elif not matched:
            status = 'NO_COMMON_UID'
        else:
            status = 'READY'
        details.append({'store': name, 'status': status,
                        'assigned': assigned, 'matched': matched, 'stale': stale,
                        'unselected': unselected, 'stale_reasons': reasons})

    selected_details = []
    outside = []
    missing_approved = []
    for uid in sorted(selected):
        items = by_uid.get(uid, [])
        if not items:
            missing_approved.append(uid)
            selected_details.append({'uid': uid, 'category': '(onay bulunamadı)',
                                     'filename': uid, 'source_sha': '', 'key': '',
                                     'owner': None, 'selected_store_member': False})
            outside.append(uid)
            continue
        if not any(key_for(item) in active_keys for item in items):
            outside.append(uid)
        for item in items:
            row = describe_template(item,
                  owner=owner_by_key.get(key_for(item)) or
                        owner_by_sha.get(str(item['source_sha']).lower()) or
                        owner_by_identity.get(f"{item['category']}:{item['uid']}"))
            row['selected_store_member'] = row['key'] in active_keys
            selected_details.append(row)

    ready = (bool(requested) and bool(selected) and not duplicate_key and
             not duplicates and len(set(requested)) == len(requested) and
             not outside and all(d['status'] == 'READY' for d in details))
    union_uids = sorted({str(by_key[k]['uid']) for k in all_valid})
    return {'ready': ready, 'requested': requested,
            'selected_uids': sorted(selected), 'selected_details': selected_details,
            'outside_uids': outside, 'missing_approved_uids': missing_approved,
            'duplicate_keys': duplicate_key, 'duplicate_uids': duplicates,
            'details': details, 'union_uids': union_uids,
            'assigned_count': len(all_assigned), 'approved_count': len(approved)}


def read_profile_identity(manager):
    """A read-only source path + on-disk sha; never cache or change profile."""
    path = manager.path
    if path.is_symlink():
        raise ValueError('STORE_PROFILE_SYMLINK')
    return {'path': str(path.resolve(strict=False)),
            'sha256': sha256(path.read_bytes()).hexdigest() if path.is_file() else '(dosya yok)',
            'exists': path.is_file()}


def format_store_diagnostic(report, *, state_path=None, profile_identity=None,
                            visible_selected_uids=None, internal_selected_uids=None):
    """Safe textual evidence for the actual start() snapshot, copyable in UI."""
    lines = ['MAĞAZA – SERİ ÜRETİM ŞABLON EŞLEŞME TEŞHİSİ',
             'İşlem: SALT OKUNUR; mağaza ataması, maske ve şablon değiştirilmedi.',
             f'Durum: {"UYUMLU" if report["ready"] else "EŞLEŞME / KAYIT KONTROLÜ GEREKİYOR"}',
             'Motor planına gönderilen mağazalar: '+(', '.join(report['requested']) or '(seçilmedi)'),
             'Motor planına gönderilen seçili UID: '+(', '.join(report['selected_uids']) or '(seçilmedi)'),
             f'Onaylı şablon sayısı: {report["approved_count"]}']
    if profile_identity:
        lines.extend(['Profil dosyası: '+profile_identity['path'],
                      'Profil dosyası SHA256: '+profile_identity['sha256']])
    elif state_path:
        lines.append('Profil dosyası: '+str(state_path))
    if visible_selected_uids is not None:
        lines.append('Ekran listesindeki işaretli UID: '+(', '.join(visible_selected_uids) or '(yok)'))
    if internal_selected_uids is not None:
        lines.append('Üretimin hafızasındaki UID: '+(', '.join(internal_selected_uids) or '(yok)'))
    if report['duplicate_keys'] or report['duplicate_uids']:
        lines.append('KİMLİK ÇAKIŞMASI: '+', '.join(report['duplicate_uids']))
    messages = {
        'STORE_NOT_FOUND': 'Mağaza bu profil dosyasında bulunamadı.',
        'NO_ASSIGNMENT': 'Bu mağazaya henüz mockup atanmadı.',
        'STALE_APPROVAL_OR_SHA': 'Atama kaynağı güncel onaylı SHA ile uyuşmuyor.',
        'NO_PRODUCTION_SELECTION': 'Üretim için hiç mockup seçilmedi.',
        'NO_COMMON_UID': 'Atanmış UID ile üretimdeki seçili UID kesişmiyor.',
        'READY': 'Bu mağazada en az bir geçerli UID eşleşiyor.'}
    for d in report['details']:
        lines.extend(['', 'MAĞAZA: '+d['store'], 'NEDEN: '+messages[d['status']],
                      f"Atama={len(d['assigned'])}; ortak={len(d['matched'])}; üretimde işaretlenmeyen={len(d['unselected'])}"])
        for key in d['assigned']:
            lines.append('  ATANMIŞ: '+key)
        for stale in d['stale_reasons']:
            lines.append('  STALE/GEÇERSİZ: '+stale['key']+' / '+stale['reason'])
            for current in stale['current']:
                lines.append('    Güncel onay: '+current['key'])
    lines += ['', 'ÜRETİMDE İŞARETLİ GERÇEK ŞABLONLAR:']
    for row in report['selected_details']:
        lines.append('  '+row['filename']+' | '+row['category']+' | UID '+row['uid']+
                     ' | SHA '+row['source_sha']+' | sahibi '+(row['owner'] or '(boşta)')+
                     (' | mağaza grubunda' if row['selected_store_member'] else ' | SEÇİLİ MAĞAZADA DEĞİL'))
    if report['outside_uids']:
        lines.append('SEÇİLİ MAĞAZALARIN DIŞINDAKİ UID: '+', '.join(report['outside_uids']))
        lines.append('ÇÖZÜM: "Bu Mağazanın Mockuplarını Göster" seçeneğini açın; ' 
                     'isterseniz "Mağazaya Atananları Üretime Seç" ile açıkça seçim yapın.')
    lines.extend(['', 'Atamaları silmek veya yeniden onaylamak teşhis için gerekmez.',
                  'Rapor yalnız bu bilgisayarda hazırlanır, otomatik olarak gönderilmez.'])
    return '\n'.join(lines)
