"""Versioned store->approved-template membership, without moving source files.

Store config is private local application state, outside the synchronized runtime
and original geometry/production SQLite databases. Writes require explicit UI
action, are atomic and retain a recovery backup of the previous config.
"""
from __future__ import annotations
import json
import os
import re
import secrets
import shutil
from pathlib import Path
try:
    from .store_identity_v485 import DEFAULT_STORE_SHORT_CODES, default_store_short_code, normalize_short_code
except ImportError:  # pragma: no cover - direct legacy script execution
    from store_identity_v485 import DEFAULT_STORE_SHORT_CODES, default_store_short_code, normalize_short_code

STORE_ID = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_-]{1,35}$')
SCHEMA = 1


def key_for(template: dict) -> str:
    return str(template['category']) + ':' + str(template['uid']) + '@' + str(template['source_sha'])


def default():
    return {'schema': SCHEMA, 'stores': {}}


def perceptual_fingerprint(item: dict) -> str | None:
    """64-bit dHash with source SHA proof; conservative near-image warning."""
    source=item.get('source')
    if not source:
        return None
    import cv2
    import numpy as np
    from hashlib import sha256
    try:
        path=Path(source)
        if path.is_symlink() or not path.is_file():
            return None
        data=path.read_bytes()
        if sha256(data).hexdigest()!=str(item['source_sha']):
            raise ValueError('DUPLICATE_SOURCE_SHA_CHANGED')
        img=cv2.imdecode(np.frombuffer(data,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        small=cv2.resize(img,(9,8),interpolation=cv2.INTER_AREA)
        bits=(small[:,1:]>small[:,:-1]).reshape(-1)
        value=0
        for bit in bits:
            value=(value<<1)|int(bit)
        return f'{value:016x}'
    except OSError:
        return None


def near_distance(a: str,b: str) -> int:
    return (int(a,16)^int(b,16)).bit_count()


class StoreProfiles:
    def __init__(self, state_root: Path):
        self.root = Path(state_root).resolve()
        self.path = self.root / 'store_profiles_v47.json'

    def load(self) -> dict:
        if not self.path.exists():
            return default()
        if self.path.is_symlink():
            raise ValueError('STORE_PROFILE_SYMLINK')
        raw = json.loads(self.path.read_text(encoding='utf-8'))
        self.validate(raw)
        return raw

    @staticmethod
    def validate(raw):
        if not isinstance(raw,dict) or raw.get('schema')!=SCHEMA or not isinstance(raw.get('stores'),dict):
            raise ValueError('STORE_PROFILE_SCHEMA_INVALID')
        owners={}
        source_owners={}
        short_code_owners={}
        for store, row in raw['stores'].items():
            if not STORE_ID.fullmatch(store) or store == 'LOCAL':
                raise ValueError('STORE_ID_INVALID')
            if not isinstance(row,dict) or not isinstance(row.get('templates'),list):
                raise ValueError('STORE_TEMPLATES_INVALID')
            configured_code = row.get('short_code') or default_store_short_code(str(store))
            if configured_code is not None:
                normalized = normalize_short_code(configured_code)
                if normalized in short_code_owners and short_code_owners[normalized] != store:
                    raise ValueError('MAGAZA_KISA_KODU_CAKISMASI: ' + normalized)
                short_code_owners[normalized] = store
            for template in row['templates']:
                if not isinstance(template,str) or ':' not in template or '@' not in template or len(template)>300:
                    raise ValueError('STORE_TEMPLATE_KEY_INVALID')
                source_sha=template.rsplit('@',1)[-1]
                if not re.fullmatch(r'[0-9a-fA-F]{64}',source_sha):
                    raise ValueError('STORE_TEMPLATE_SHA_INVALID')
                if template in owners:
                    raise ValueError('STORE_TEMPLATE_ASSIGNED_TO_MULTIPLE_STORES: '+template)
                if source_sha in source_owners and source_owners[source_sha] != store:
                    raise ValueError('STORE_SOURCE_IMAGE_REUSED_ACROSS_STORES: '+template)
                owners[template]=store
                source_owners[source_sha]=store

    def save(self, raw: dict):
        self.validate(raw)
        self.root.mkdir(parents=True,exist_ok=True)
        if self.root.is_symlink() or self.path.is_symlink():
            raise ValueError('STORE_PROFILE_UNSAFE_PATH')
        prior = self.path.read_bytes() if self.path.exists() else None
        encoded = json.dumps(raw,ensure_ascii=False,indent=2,sort_keys=True).encode('utf-8')
        import tempfile
        fd, name = tempfile.mkstemp(prefix='.store-v47-',suffix='.tmp',dir=self.root)
        temp=Path(name)
        try:
            with os.fdopen(fd,'wb') as out:
                out.write(encoded);out.flush();os.fsync(out.fileno())
            if prior is not None:
                recovery = self.root / ('store_profiles_v47.backup_'+secrets.token_hex(8)+'.json')
                with recovery.open('xb') as out:
                    out.write(prior);out.flush();os.fsync(out.fileno())
            os.replace(temp,self.path)
        finally:
            temp.unlink(missing_ok=True)
        return self.path

    def preview_rekey(self, substitutions: list[dict]) -> dict:
        """Plan source-SHA changes without writing store config or touching outputs.

        A template UID stays the same: only the source SHA changes. Keep
        membership even for REVIEW_REQUIRED templates; the production
        discoverer excludes them until human reapproval. Never create a
        second mapping for a changed photo.
        """
        raw=self.load()
        planned=json.loads(json.dumps(raw))
        changes={}
        for item in substitutions:
            category=str(item['category'])
            uid=str(item['uid'])
            previous=str(item['old_sha']).lower()
            current=str(item['new_sha']).lower()
            if not re.fullmatch(r'[0-9a-f]{64}',previous) or not re.fullmatch(r'[0-9a-f]{64}',current):
                raise ValueError('STORE_REKEY_SHA_INVALID')
            old=f'{category}:{uid}@{previous}'
            new=f'{category}:{uid}@{current}'
            if old in changes and changes[old]!=new:
                raise ValueError('STORE_REKEY_DUPLICATE_SOURCE_IDENTITY')
            changes[old]=new
        impacted=[]
        for store,row in planned['stores'].items():
            before=list(row['templates'])
            after=[changes.get(key,key) for key in before]
            if len(set(after)) != len(after):
                raise ValueError('STORE_REKEY_DUPLICATE_IN_STORE: '+store)
            if after!=before:
                impacted.append({'store':store,'old':[key for key in before if key in changes],
                                 'new':[changes[key] for key in before if key in changes]})
                row['templates']=after
        self.validate(planned)
        return {'old':raw,'new':planned,'changed':impacted,
                'changed_count':sum(len(row['old']) for row in impacted)}

    def add_store(self, store):
        if not STORE_ID.fullmatch(str(store)) or store == 'LOCAL':
            raise ValueError('Mağaza kimliği 2-36 harf/rakam/_/- olmalı (LOCAL özel).')
        raw=self.load()
        if store in raw['stores']:
            raise ValueError('Mağaza zaten kayıtlı.')
        raw['stores'][store]={'templates':[]}
        default_code = default_store_short_code(str(store))
        if default_code:
            raw['stores'][store]['short_code'] = default_code
        return self.save(raw)

    def short_code(self, store: str) -> str | None:
        """Return the explicit store code, or the requested known default."""
        raw = self.load()
        if store not in raw['stores']:
            raise ValueError('Mağaza bulunamadı: ' + str(store))
        configured = raw['stores'][store].get('short_code')
        if configured:
            return normalize_short_code(configured)
        return default_store_short_code(str(store))

    def set_short_code(self, store: str, short_code: str):
        """Persist a unique store short code with an atomic, backed-up write.

        Existing product identities are intentionally not rewritten.  The UI
        or an operator must review/re-export affected unpublished products.
        """
        code = normalize_short_code(short_code)
        raw = self.load()
        if store not in raw['stores']:
            raise ValueError('Mağaza bulunamadı: ' + str(store))
        for other, row in raw['stores'].items():
            existing = row.get('short_code') or default_store_short_code(str(other))
            if other != store and str(existing or '').upper() == code:
                raise ValueError('MAGAZA_KISA_KODU_CAKISMASI: ' + code)
        raw['stores'][store]['short_code'] = code
        return self.save(raw)

    def assign(self, store, items: list[dict], all_approved: list[dict] | None=None):
        raw=self.load()
        if store not in raw['stores']:
            raise ValueError('Mağaza bulunamadı.')
        template_keys=[key_for(x) for x in items]
        if not template_keys:
            raise ValueError('Atanacak onaylı şablon seçilmedi.')
        owned={key:ident for ident,row in raw['stores'].items() for key in row['templates']}
        for key in template_keys:
            if key in owned and owned[key]!=store:
                raise ValueError('Şablon başka mağazaya atanmış: '+key)
        # User-approved production policy: NO perceptual similarity scans,
        # no output hash comparison for cross-store uniqueness. The identity
        # of the approved template/source SHA is sufficient to block assigning
        # the EXACT SAME template or source file across store profiles. This
        # check is performed by validate(), without decoding any picture.
        if all_approved is not None:
            available={key_for(x) for x in all_approved}
            if any(key not in available for key in template_keys):
                raise ValueError('STORE_ASSIGN_TEMPLATE_NOT_APPROVED')
        raw['stores'][store]['templates']=sorted(set(raw['stores'][store]['templates'])|set(template_keys))
        return self.save(raw)

    def unassign_keys(self, store: str, keys, *, expected_current_keys=None) -> int:
        """Explicit bulk *membership* removal; never delete templates or outputs.

        The optional snapshot fails closed when the store's membership was
        changed after the user opened the confirmation dialog. This uses the
        existing atomic, backup-producing config writer, not production data.
        """
        chosen=list(keys)
        if not chosen or len(chosen)!=len(set(chosen)):
            raise ValueError('Kaldırılacak benzersiz mağaza atamalarını seçin.')
        raw=self.load()
        if store not in raw['stores']:
            raise ValueError('Mağaza bulunamadı. Listeyi yenileyin.')
        before=list(raw['stores'][store]['templates'])
        if expected_current_keys is not None and before!=list(expected_current_keys):
            raise ValueError('Mağaza atamaları onay sırasında değişti. Listeyi yenileyin.')
        if not set(chosen).issubset(set(before)):
            raise ValueError('Seçilen atamalardan biri artık mağazada değil. Listeyi yenileyin.')
        raw['stores'][store]['templates']=[key for key in before if key not in set(chosen)]
        self.save(raw)
        return len(chosen)

    def unassign(self, store, items: list[dict]):
        """Backwards-compatible item-based removal through the safe path."""
        return self.unassign_keys(store,[key_for(item) for item in items])

    def plan(self, selected: list[str], approved: list[dict], *, selected_uids: list[str] | None=None):
        """Snapshot a fail-closed plan. Empty store selection = legacy path.

        The strict API remains intentionally fail-closed for callers that need
        an all-or-nothing preflight.  Production uses :meth:`plan_resilient`
        so one stale membership can be quarantined while unrelated stores keep
        running.
        """
        result = self.plan_resilient(selected, approved, selected_uids=selected_uids)
        if result['stale']:
            raise ValueError('Atanan şablon onayı/SHA değişmiş; kontrol gerekli: '
                             + result['stale'][0]['key'])
        return result['groups']

    def plan_resilient(self, selected: list[str], approved: list[dict], *,
                       selected_uids: list[str] | None = None) -> dict:
        """Build a plan while isolating stale template memberships.

        A stale key is never re-keyed or rendered.  It is returned as an
        explicit review item; only groups with at least one currently approved
        member are returned for production.  If every selected group is stale,
        the caller can still fail closed with a queue-level explanation.
        """
        raw=self.load()
        if not selected or len(selected)!=len(set(selected)):
            raise ValueError('Seçilen mağazalar boş veya tekrarlı.')
        approved_by_key={key_for(item):item for item in approved}
        if len(approved_by_key)!=len(approved):
            raise ValueError('APPROVED_TEMPLATE_KEY_COLLISION')
        filter_uids=set(selected_uids) if selected_uids is not None else None
        groups=[]
        matched_uids=set()
        stale_items=[]
        stale_uids=set()
        for name in selected:
            if name not in raw['stores']:
                raise ValueError('Mağaza profili bulunamadı: '+name)
            stored=raw['stores'][name]['templates']
            if not stored:
                raise ValueError('Mağazaya şablon atanmamış: '+name)
            stale=[k for k in stored if k not in approved_by_key]
            for key in stale:
                uid = key.split(':', 1)[1].split('@', 1)[0]
                # A store may contain many historical assignments, while the
                # operator has selected only a small UID subset for this run.
                # Do not report unrelated stale memberships as failures in
                # the current operation; they remain visible to the store
                # manager on a full assignment audit.
                if filter_uids is None or uid in filter_uids:
                    stale_uids.add(uid)
                    stale_items.append({'store': name, 'key': key,
                                        'reason': 'Atanan şablon onayı/SHA değişmiş; kontrol gerekli'})
            subset=[approved_by_key[k] for k in stored
                    if k in approved_by_key and
                    (filter_uids is None or approved_by_key[k]['uid'] in filter_uids)]
            if not subset and not stale:
                raise ValueError('Seçili şablonlar mağazanın özel grubunda yok: '+name)
            if subset:
                matched_uids.update(str(item['uid']) for item in subset)
                groups.append((name,subset))
        # Legacy plan silently dropped extra selected templates when at least
        # one UID belonged to a selected store. Never present those to users as
        # production selections and then skip them without explanation.
        if filter_uids is not None:
            outside={str(uid) for uid in filter_uids}-matched_uids-stale_uids
            if outside:
                raise ValueError('STORE_SELECTED_UID_NOT_ASSIGNED: '
                                 + ', '.join(sorted(outside)[:20]))
        return {'groups': groups, 'stale': stale_items}
