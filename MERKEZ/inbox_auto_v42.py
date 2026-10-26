"""Automatic create-only intake for new mockup photos (all seven categories).

Never deletes/overwrites a working or original-archive file. Inbox files are
moved to human-readable archive/review folders only after a complete SHA-256
verified copy. Incomplete writes are ignored until stable across polls.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
import os
import sqlite3
from pathlib import Path
import shutil
import threading
import time
import uuid
import unicodedata
from typing import Callable

CATEGORIES=("01_Wifi_Kutusu","02_Cam_Tablo_Dikey","02_Cam_Tablo_Yatay",
            "03_Ahsap_Tablo","04_Cam_Dograma","05_Ocak_Arkasi","06_Petek_Kapama")
IMG={'.jpg','.jpeg','.png','.webp'}
DONE='Bunlar Zaten Taşındı Bu Klasörü Sil'
CONFLICT='ISIM_CAKISMASI_KONTROL_ET'
REVIEW='EKLENENLER_INCELEME_BEKLIYOR'

def file_sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def _ensure_folder(p:Path):
    if p.is_symlink():raise ValueError('SYMLINK_FOLDER_REJECTED '+str(p))
    p.mkdir(parents=True,exist_ok=True)
    if p.is_symlink():raise ValueError('SYMLINK_FOLDER_REJECTED '+str(p))

def _collision_variants(directory:Path,name:str)->list[Path]:
    if not directory.is_dir():return []
    stem=unicodedata.normalize('NFC', Path(name).stem).casefold()
    return [p for p in directory.iterdir() if p.is_file() and not p.is_symlink()
            and p.suffix.lower() in IMG
            and unicodedata.normalize('NFC', p.stem).casefold()==stem]

def copy_create_only(source:Path,dest:Path,expected_sha:str)->Path:
    """Exclusive publish via same-directory temp and hardlink; no replace path."""
    _ensure_folder(dest.parent)
    if source.is_symlink() or dest.is_symlink():raise ValueError('SYMLINK_FILE_REJECTED')
    temp=dest.parent/('.'+uuid.uuid4().hex+'.pending')
    try:
        with source.open('rb') as i,temp.open('xb') as o:
            for chunk in iter(lambda:i.read(1024*1024),b''):o.write(chunk)
            o.flush();os.fsync(o.fileno())
        if file_sha(temp)!=expected_sha:raise RuntimeError('SOURCE_CHANGED_WHILE_COPYING')
        # os.link is create-only on Windows and POSIX. Any unsupported filesystem
        # fails closed, rather than using os.replace() on a live asset.
        os.link(temp,dest)
        if file_sha(dest)!=expected_sha:raise RuntimeError('PUBLISHED_SHA_MISMATCH')
        return dest
    finally:
        try:temp.unlink(missing_ok=True)
        except OSError:pass

def safe_stage_move(source:Path,directory:Path,sha:str):
    _ensure_folder(directory)
    destination=directory/source.name
    if destination.exists():
        if destination.is_file() and not destination.is_symlink() and file_sha(destination)==sha:
            # Already staged here: keep BOTH rather than silently deleting.
            destination=directory/(source.stem+'__'+uuid.uuid4().hex[:10]+source.suffix)
        else:
            destination=directory/(source.stem+'__'+sha[:12]+'_'+uuid.uuid4().hex[:6]+source.suffix)
    copy_create_only(source,destination,sha)
    if file_sha(source)!=sha or file_sha(destination)!=sha:raise RuntimeError('STAGING_SHA_CHANGED')
    source.unlink()  # Only user-submitted INBOX copy, never working/archive.
    return destination

def register_pending_legacy(root:Path,category:str,filename:str):
    """Add *new* source to editor as REVIEW_REQUIRED, never auto-approve.

    Existing profiles and approved template JSON are strictly immutable.
    SQLite online backup outside OneDrive is required before insertion.
    """
    if category=='06_Petek_Kapama':return 'PETEK_MASK_REVIEW'
    db=root/'SABLON_V2_MIMARI'/'ayarlar.db'
    if not db.is_file() or db.is_symlink():raise FileNotFoundError('LIVE_DB_MISSING')
    with sqlite3.connect(db) as conn:
        tables={x[0] for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'categories','templates','template_profiles'}.issubset(tables):
            raise RuntimeError('UNKNOWN_LIVE_SCHEMA_NO_AUTO_INSERT')
        row=conn.execute('SELECT 1 FROM templates WHERE category_id=? AND filename=?',(category,filename)).fetchone()
        if row:return 'ALREADY_REGISTERED'
        label_row=conn.execute('SELECT 1 FROM categories WHERE id=?',(category,)).fetchone()
        if not label_row:raise RuntimeError('CATEGORY_NOT_IN_DB_NO_AUTO_INSERT')
        local=os.getenv('LOCALAPPDATA')
        backup_dir=(Path(local) if local else Path.home()/'.gorsel_mockup')/'GorselMockup'/'AutoIntakeBackups'
        _ensure_folder(backup_dir)
        target=backup_dir/('before_inbox_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:10]+'.sqlite3')
        # Database backup is create-only, cannot overwrite an existing snapshot.
        with sqlite3.connect(target) as output:
            conn.backup(output)
        if file_sha(target)=='':raise RuntimeError('DB_BACKUP_EMPTY')
        data={'tip':'perspektif','koseler':[],'review_status':'REVIEW_REQUIRED',
              'kaynak':'Otomatik yeni şablon girişi; dört köşe insan onayı bekliyor'}
        conn.execute('INSERT OR IGNORE INTO templates (category_id,filename,data) VALUES (?,?,?)',
                     (category,filename,json.dumps(data,ensure_ascii=False)))
        conn.commit()
        return 'REGISTERED_REVIEW_REQUIRED'


def historical_db_identity_reserved(root: Path, category: str, filename: str) -> bool:
    """Read-only historical identity guard; no deleted/approved ID resurrection.

    A missing working/backup file does not mean its identifier is free.  Past
    identities in templates, template_profiles, and number registry remain
    reserved until an operator resolves them in the recovery UI.
    """
    db = root / 'SABLON_V2_MIMARI' / 'ayarlar.db'
    if not db.is_file() or db.is_symlink():
        raise RuntimeError('LIVE_DB_MISSING_OR_SYMLINK')
    identity = unicodedata.normalize('NFC', Path(filename).stem).casefold()
    con = sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        con.execute('PRAGMA query_only=ON')
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'templates', 'template_profiles'}.issubset(tables):
            raise RuntimeError('UNRECOGNIZED_SCHEMA_IDENTITY_CHECK_BLOCKED')
        for (existing,) in con.execute('SELECT filename FROM templates WHERE category_id=?', (category,)):
            if unicodedata.normalize('NFC', Path(str(existing)).stem).casefold() == identity:
                return True
        cols = {r[1] for r in con.execute('PRAGMA table_info(template_profiles)')}
        if not {'category', 'template_uid'}.issubset(cols):
            raise RuntimeError('PROFILE_SCHEMA_IDENTITY_CHECK_BLOCKED')
        extra = 'source_relative_path' if 'source_relative_path' in cols else "''"
        for uid, source_path in con.execute(
            f'SELECT template_uid, {extra} FROM template_profiles WHERE category=?', (category,)
        ):
            if source_path and unicodedata.normalize('NFC', Path(str(source_path).replace('\\', '/')).stem).casefold() == identity:
                return True
            uid_stem = unicodedata.normalize('NFC', Path(str(uid or '')).stem).casefold()
            if uid_stem in {identity, f'{category}_{identity}'.casefold()}:
                return True
        if 'template_number_registry' in tables:
            # Registry contains IDs for removed files; prefer a false positive
            # (manual review) over silently reusing a historic number.
            regcols = {r[1] for r in con.execute('PRAGMA table_info(template_number_registry)')}
            if {'category', 'canonical_name'}.issubset(regcols):
                for (name,) in con.execute(
                    'SELECT canonical_name FROM template_number_registry WHERE category=?', (category,)
                ):
                    if name and unicodedata.normalize('NFC', Path(str(name)).stem).casefold() == identity:
                        return True
        return False
    finally:
        con.close()


def ingest_one(root:Path,category:str,source:Path)->dict:
    root=Path(root)
    if category not in CATEGORIES:raise ValueError('INVALID_CATEGORY')
    if category == '06_Petek_Kapama':
        from petek_folders_v46 import petek_directory
        inbox = petek_directory(root, 'YENI-BOS MOCKUP SABLON HAVUZU')
        work = petek_directory(root, '2_SABLON_HAVUZU')
        backup = petek_directory(root, '2_SABLON_HAVUZU_ORIJINAL_YEDEK')
    else:
        inbox=root/'YENI-BOS MOCKUP SABLON HAVUZU'/category
        work=root/'2_SABLON_HAVUZU'/category
        backup=root/'2_SABLON_HAVUZU_ORIJINAL_YEDEK'/category
    if not source.is_file() or source.is_symlink() or source.suffix.lower() not in IMG:
        raise ValueError('INVALID_INBOX_SOURCE')
    if source.parent.resolve()!=inbox.resolve():raise ValueError('ONLY_DIRECT_INBOX_FILES')
    # Never touch unrelated working roots. Real user DB is mandatory.
    if not (root/'SABLON_V2_MIMARI'/'ayarlar.db').is_file():
        raise FileNotFoundError('WORKSPACE_DB_REQUIRED_FAIL_CLOSED')
    for folder in (inbox,work,backup):
        if folder.is_symlink():raise ValueError('SYMLINK_DIRECTORY_REJECTED')
    sha=file_sha(source)
    # A malicious/unfinished file renamed to .png/.jpg is never registered as a
    # valid mockup. Use header-level image verification only, not AI analysis.
    try:
        from PIL import Image
        with Image.open(source) as opened:
            opened.verify()
    except (OSError, ValueError, SyntaxError) as exc:
        dest=safe_stage_move(source,inbox/CONFLICT,sha)
        return {'status':'INVALID_IMAGE_REVIEW','category':category,'name':source.name,
                'reason':'Dosya okunabilir bir görsel değil','at':str(dest)}
    candidates=_collision_variants(work,source.name)
    historical=_collision_variants(backup,source.name)
    # Identity is extension-free and case insensitive, content SHA decides.
    matches=[p for p in (candidates+historical) if file_sha(p)==sha]
    conflicts=[p for p in (candidates+historical) if file_sha(p)!=sha]
    if conflicts:
        dest=safe_stage_move(source,inbox/CONFLICT,sha)
        return {'status':'CONFLICT_REVIEW','category':category,'name':source.name,'at':str(dest)}
    if candidates:
        # If the same source was staged earlier but database insertion failed,
        # repair the missing registration without altering any approved row.
        register_pending_legacy(root,category,candidates[0].name)
        dest=safe_stage_move(source,inbox/DONE,sha)
        return {'status':'ALREADY_WORKING','category':category,'name':source.name,'at':str(dest)}
    if historical and not matches:
        dest=safe_stage_move(source,inbox/CONFLICT,sha)
        return {'status':'CONFLICT_REVIEW','category':category,'name':source.name,'at':str(dest)}
    if not candidates and historical and any(
        p.name.casefold()!=source.name.casefold() for p in historical
    ):
        # An old archived .png plus new .jpeg of the same logical template
        # could silently register two format variants. Human review is required
        # even when the compressed bytes happen to be identical.
        dest=safe_stage_move(source,inbox/CONFLICT,sha)
        return {'status':'CONFLICT_REVIEW','category':category,'name':source.name,
                'reason':'Aynı numaralı şablon yedekte farklı uzantı/ad ile var',
                'at':str(dest)}
    # Files may have been moved/deleted while their historical APPROVED,
    # recycled identity, or template row remains in SQLite.  Do NOT turn
    # an untrusted inbox picture into an already-reserved logical template.
    # PETEK has its own immutable, SHA-bound mask registry, not a seven-category
    # row in the six-category legacy SQLite table.
    if category != '06_Petek_Kapama' and historical_db_identity_reserved(root, category, source.name):
        dest = safe_stage_move(source, inbox / CONFLICT, sha)
        return {'status': 'CONFLICT_REVIEW', 'category': category,
                'name': source.name, 'reason': 'DB_HISTORICAL_IDENTITY_RESERVED',
                'at': str(dest)}

    # A new name OR a missing working copy of a source present in backup.
    # First provide an immutable backup, then a create-only working photo.
    if not historical:
        copy_create_only(source,backup/source.name,sha)
    copy_create_only(source,work/source.name,sha)
    # Without database registration, the file would be invisible to the
    # four-corner editor. Insert an unapproved record, never touch APPROVED.
    register_state=register_pending_legacy(root,category,source.name)
    dest=safe_stage_move(source,inbox/REVIEW,sha)
    return {'status':'IMPORTED_NEEDS_CORNERS','category':category,'name':source.name,
            'registration':register_state,'at':str(dest)}

class AutoInboxWatcher:
    def __init__(self,root:Path,notify:Callable[[str],None]|None=None,interval=3.):
        self.root=Path(root)
        self.notify=notify or (lambda msg:None)
        self.interval=max(1.,float(interval))
        self.stop_event=threading.Event()
        self.thread=None
        self.last_seen={}
        self.lock=threading.Lock()
        self.stats=Counter()

    def _send(self,message):
        try:self.notify(message)
        except Exception:pass

    def sweep(self):
        if not (self.root/'SABLON_V2_MIMARI'/'ayarlar.db').is_file():return []
        outcome=[]
        for category in CATEGORIES:
            if category == '06_Petek_Kapama':
                from petek_folders_v46 import petek_directory
                try:
                    inbox=petek_directory(self.root, 'YENI-BOS MOCKUP SABLON HAVUZU')
                except (OSError, ValueError) as exc:
                    self._send('PETEK Yeni Boş klasör uyuşmazlığı: '+str(exc))
                    continue
            else:
                inbox=self.root/'YENI-BOS MOCKUP SABLON HAVUZU'/category
            if inbox.is_symlink() or not inbox.is_dir():continue
            for file in sorted(inbox.iterdir()):
                if file.is_symlink() or not file.is_file() or file.suffix.lower() not in IMG:continue
                try:
                    stat=file.stat()
                    fingerprint=(stat.st_size,stat.st_mtime_ns)
                    key=str(file)
                    # Wait for 2 unchanged sweeps and at least 2 seconds since modification.
                    if self.last_seen.get(key)!=fingerprint or time.time()-stat.st_mtime<2.:
                        self.last_seen[key]=fingerprint;continue
                    result=ingest_one(self.root,category,file)
                    outcome.append(result)
                    self.stats[result['status']]+=1
                    self.last_seen.pop(key,None)
                    self._send(f"Yeni şablon: {result['category']} / {result['name']} → {result['status']}")
                except FileExistsError as exc:
                    self._send(f'İsim çakışması: {file.name}: {exc}')
                except (OSError,ValueError,RuntimeError) as exc:
                    self._send(f'Yeni şablon beklemede: {file.name}: {exc}')
        return outcome

    def start(self):
        with self.lock:
            if self.thread is not None and self.thread.is_alive():return
            self.stop_event.clear()
            def work():
                while not self.stop_event.is_set():
                    try:self.sweep()
                    except Exception as exc:self._send(f'Klasör izleme hatası: {exc}')
                    self.stop_event.wait(self.interval)
            self.thread=threading.Thread(target=work,name='MockupAutoInboxV42',daemon=True)
            self.thread.start()

    def stop(self):
        self.stop_event.set()
