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
        for store, row in raw['stores'].items():
            if not STORE_ID.fullmatch(store) or store == 'LOCAL':
                raise ValueError('STORE_ID_INVALID')
            if not isinstance(row,dict) or not isinstance(row.get('templates'),list):
                raise ValueError('STORE_TEMPLATES_INVALID')
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

    def add_store(self, store):
        if not STORE_ID.fullmatch(str(store)) or store == 'LOCAL':
            raise ValueError('Mağaza kimliği 2-36 harf/rakam/_/- olmalı (LOCAL özel).')
        raw=self.load()
        if store in raw['stores']:
            raise ValueError('Mağaza zaten kayıtlı.')
        raw['stores'][store]={'templates':[]}
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
        # Old SHA-only profiles remain supported. For new UI assignment,
        # compare every approved source via conservative perceptual similarity.
        if all_approved is not None:
            available={key_for(x):x for x in all_approved}
            fingerprints={key:perceptual_fingerprint(item) for key,item in available.items()}
            for key in template_keys:
                fp=fingerprints.get(key)
                if not fp:
                    raise ValueError('BENZERLIK_KAYNAK_OKUNAMADI: '+key)
                for other,owner in owned.items():
                    if owner==store or other==key:continue
                    other_fp=fingerprints.get(other)
                    if other_fp is None:
                        raise ValueError('BENZERLIK_ESKI_ATAMA_DOGRULANAMIYOR: '+other)
                    if near_distance(fp,other_fp)<=4:
                        raise ValueError('MAGAZALAR_ARASI_BENZER_MOCKUP: '+key+' / '+other)
        raw['stores'][store]['templates']=sorted(set(raw['stores'][store]['templates'])|set(template_keys))
        return self.save(raw)

    def unassign(self, store, items: list[dict]):
        raw=self.load()
        if store not in raw['stores']:
            raise ValueError('Mağaza bulunamadı.')
        removed={key_for(x) for x in items}
        raw['stores'][store]['templates']=[x for x in raw['stores'][store]['templates'] if x not in removed]
        return self.save(raw)

    def plan(self, selected: list[str], approved: list[dict], *, selected_uids: list[str] | None=None):
        """Snapshot a fail-closed plan. Empty store selection = legacy path."""
        raw=self.load()
        if not selected or len(selected)!=len(set(selected)):
            raise ValueError('Seçilen mağazalar boş veya tekrarlı.')
        approved_by_key={key_for(item):item for item in approved}
        if len(approved_by_key)!=len(approved):
            raise ValueError('APPROVED_TEMPLATE_KEY_COLLISION')
        filter_uids=set(selected_uids) if selected_uids is not None else None
        groups=[]
        for name in selected:
            if name not in raw['stores']:
                raise ValueError('Mağaza profili bulunamadı: '+name)
            stored=raw['stores'][name]['templates']
            if not stored:
                raise ValueError('Mağazaya şablon atanmamış: '+name)
            stale=[k for k in stored if k not in approved_by_key]
            if stale:
                raise ValueError('Atanan şablon onayı/SHA değişmiş; kontrol gerekli: '+stale[0])
            subset=[approved_by_key[k] for k in stored if
                    (filter_uids is None or approved_by_key[k]['uid'] in filter_uids)]
            if not subset:
                raise ValueError('Seçili şablonlar mağazanın özel grubunda yok: '+name)
            groups.append((name,subset))
        return groups
