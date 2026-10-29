"""HAM BASKI TASARIMLARI — 7-category, persistent, extension-neutral numbered intake.

Every file gets a globally unique, never recycled 'Ham<number>' ID across the
ENTIRE directory tree. Existing names are adopted exactly once, thereafter new
files are numbered only when complete/stable. No image transcoding occurs.
Private SQLite + portable monotonic high-water receipt protect deleted IDs.
Output visual hashes/pHash are NOT calculated; intake exact-byte SHA detects
accidentally imported duplicate source files and verifies atomic copy.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import threading
import time
from typing import Callable

from PIL import Image, UnidentifiedImageError

FOLDER = 'HAM BASKI TASARIMLARI'
RECEIPT = '_HAM_NUMARA_GECMISI.json'
EXTENSIONS = frozenset({'.png','.jpg','.jpeg','.webp'})
SUSPECT = frozenset({'.bmp','.gif','.tif','.tiff','.avif','.heic','.jpe'})
_NUMBER = re.compile(r'^ham([1-9][0-9]*)$',re.IGNORECASE)
MAX_FILE_BYTES = 250_000_000
MAX_ID = 999_999_999


def _sha(file: Path) -> str:
    h = hashlib.sha256()
    with file.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):
            h.update(part)
    return h.hexdigest()


def _number(file: Path) -> int | None:
    m=_NUMBER.fullmatch(file.stem)
    return int(m.group(1)) if m else None


def _safe_path(path: Path, root: Path) -> bool:
    try:rel=path.relative_to(root)
    except ValueError:return False
    if not rel.parts:return False
    return (not path.is_symlink() and
            not any(p.is_symlink() for p in (root, *list(path.parents)[:-1]) if p.exists()))


def _atomic_receipt(file: Path, count: int) -> None:
    if file.is_symlink():raise ValueError('HAM_HISTORY_SYMLINK')
    payload=json.dumps({'schema':1,'never_reuse_up_to':count,
                        'note':'Bu numaralar silinse dahi yeniden verilmez.'},
                       ensure_ascii=False,indent=2).encode('utf-8')
    fd,tmp=tempfile.mkstemp(prefix='.ham-history-',suffix='.tmp',dir=file.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(payload);f.flush();os.fsync(f.fileno())
        os.replace(tmp,file)
    finally:
        Path(tmp).unlink(missing_ok=True)


def _receipt_high(file: Path) -> int:
    if file.is_symlink():raise ValueError('HAM_HISTORY_SYMLINK')
    if not file.exists():return 0
    obj=json.loads(file.read_text('utf-8'))
    if obj.get('schema')!=1 or not isinstance(obj.get('never_reuse_up_to'),int):
        raise ValueError('HAM_HISTORY_CORRUPT_DO_NOT_RESET')
    n=obj['never_reuse_up_to']
    if not 0<=n<=MAX_ID:raise ValueError('HAM_HISTORY_OUT_OF_RANGE')
    return n


class HamDesignVault:
    def __init__(self, workspace: Path, *, local_state: Path | None=None):
        self.workspace=Path(workspace).resolve(strict=True)
        if not self.workspace.is_dir() or self.workspace.is_symlink():
            raise ValueError('HAM_WORKSPACE_INVALID')
        self.folder=self.workspace/FOLDER
        if self.folder.is_symlink() or (self.folder.exists() and not self.folder.is_dir()):
            raise ValueError('HAM_FOLDER_UNSAFE')
        self.folder.mkdir(exist_ok=True)
        self.receipt=self.folder/RECEIPT
        base=Path(local_state or
                  (Path(os.environ.get('LOCALAPPDATA') or (Path.home()/'.local/share'))/
                   'GorselMockup'/'HamBaski'))
        if base.is_symlink():raise ValueError('HAM_LOCAL_STATE_SYMLINK')
        base.mkdir(parents=True,exist_ok=True)
        workspace_key=hashlib.sha256(os.path.normcase(str(self.workspace)).encode('utf-8')).hexdigest()[:24]
        self.db=base/('ham_registry_'+workspace_key+'.sqlite3')
        if self.db.is_symlink():raise ValueError('HAM_DB_SYMLINK')
        self.last_seen:dict[str,tuple]= {}
        self.lock=threading.RLock()
        self._init_db()

    def _connection(self):
        conn=sqlite3.connect(self.db,timeout=20)
        conn.row_factory=sqlite3.Row
        conn.execute('PRAGMA busy_timeout=20000')
        conn.execute('PRAGMA synchronous=FULL')
        return conn

    def _files(self):
        # Path.rglob silently follows some junctions; avoid via os.walk and
        # reject BOTH file links and directory links.
        for directory,dirs,files in os.walk(self.folder,followlinks=False):
            folder=Path(directory)
            dirs[:]=sorted(x for x in dirs if not (folder/x).is_symlink())
            for name in sorted(files):
                path=folder/name
                if path.is_symlink():continue
                if path.suffix.lower() in EXTENSIONS and path.is_file():
                    yield path

    def _init_db(self):
        with self._connection() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS meta(
                  id INTEGER PRIMARY KEY CHECK(id=1),
                  high INTEGER NOT NULL CHECK(high>=0), initialized INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS history(
                  number INTEGER PRIMARY KEY,
                  path TEXT NOT NULL, source_name TEXT NOT NULL,
                  sha TEXT NOT NULL, size INTEGER NOT NULL,
                  mtime_ns INTEGER NOT NULL, status TEXT NOT NULL,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
              CREATE INDEX IF NOT EXISTS ham_sha_idx ON history(sha);
            """)
            row=db.execute('SELECT high,initialized FROM meta WHERE id=1').fetchone()
            mirror=_receipt_high(self.receipt)
            if row is None:
                # First-run adoption of existing numbered files. Never rename
                # those files or recycle their observed sequence.
                seen:dict[int,str]={}
                existing=[]
                for path in self._files():
                    num=_number(path)
                    if num is None:continue
                    if num>MAX_ID:raise ValueError('HAM_NUMARA_ARALIK_DISI')
                    if num in seen:
                        raise ValueError('HAM_AYNI_NUMARA_FARKLI_DOSYA: '+
                                         seen[num]+' / '+str(path))
                    seen[num]=str(path)
                    existing.append((num,path))
                high=max([mirror,*seen.keys()],default=0)
                db.execute('INSERT INTO meta(id,high,initialized) VALUES(1,?,1)',(high,))
                for num,path in existing:
                    stat=path.stat()
                    if stat.st_size>MAX_FILE_BYTES:raise ValueError('HAM_IMAGE_TOO_LARGE')
                    db.execute("""INSERT INTO history
                         (number,path,source_name,sha,size,mtime_ns,status)
                         VALUES(?,?,?,?,?,?,'ACTIVE')""",
                         (num,str(path.relative_to(self.folder)),path.name,_sha(path),
                          stat.st_size,stat.st_mtime_ns))
            else:
                high=max(row['high'],mirror)
                if high!=row['high']:
                    db.execute('UPDATE meta SET high=? WHERE id=1',(high,))
            if high>mirror:_atomic_receipt(self.receipt,high)

    def _check_existing(self, files: list[Path], db)->list[dict]:
        alerts=[]
        seen:dict[int,Path]={}
        for path in files:
            n=_number(path)
            if n is None:continue
            if n in seen:
                alerts.append({'type':'HAM_NUMBER_EXTENSION_COLLISION',
                               'file':str(path),'other':str(seen[n])})
            else:seen[n]=path
        active=list(db.execute("SELECT number,path,sha,size,mtime_ns FROM history WHERE status='ACTIVE'"))
        for row in active:
            original=self.folder/row['path']
            if not original.is_file() or original.is_symlink():
                alerts.append({'type':'HAM_REGISTERED_FILE_MISSING',
                               'file':str(original),'number':row['number']})
            elif original.stat().st_size!=row['size'] or original.stat().st_mtime_ns!=row['mtime_ns']:
                if _sha(original)!=row['sha']:
                    alerts.append({'type':'HAM_REGISTERED_BYTES_CHANGED',
                                   'file':str(original),'number':row['number']})
                else:
                    # Last-write timestamp may change without changing pixels;
                    # keep authoritative SHA and refresh stat to avoid rehashing.
                    st=original.stat()
                    db.execute('UPDATE history SET size=?,mtime_ns=? WHERE number=?',
                               (st.st_size,st.st_mtime_ns,row['number']))
        return alerts

    def _next_number(self, db, occupied: set[int]) -> int:
        high=db.execute('SELECT high FROM meta WHERE id=1').fetchone()[0]
        # Never reuse a number even if file vanished or the transaction failed.
        candidate=max(high,*occupied,0)+1
        if candidate>MAX_ID:raise ValueError('HAM_NUMBER_LIMIT_REACHED')
        return candidate

    def _reserve(self, db,number:int,source:Path,dest:Path,sha:str,stat):
        # Commit reservation BEFORE filesystem update; an interrupted name is
        # a tombstone. On resume RESERVED is reconciled, not recycled.
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT high FROM meta WHERE id=1').fetchone()[0]
        if number<=old:raise ValueError('HAM_NUMBER_REUSED_BLOCKED')
        db.execute('UPDATE meta SET high=? WHERE id=1',(number,))
        db.execute("""INSERT INTO history(number,path,source_name,sha,size,mtime_ns,status)
                      VALUES(?,?,?,?,?,?,'RESERVED')""",
                   (number,str(dest.relative_to(self.folder)),str(source.relative_to(self.folder)),
                    sha,stat.st_size,stat.st_mtime_ns))
        db.commit()
        _atomic_receipt(self.receipt,number)

    def _publish(self,source:Path,dest:Path,expected_sha:str):
        if dest.exists() or dest.is_symlink():raise FileExistsError('HAM_TARGET_EXISTS')
        try:
            os.link(source,dest)  # exclusive, same underlying bytes/inode
        except OSError:
            # Cloud-folder filesystems may disallow hardlinks: create-only
            # copy is safe; never overwrite an already registered name.
            with source.open('rb') as inp,dest.open('xb') as out:
                for piece in iter(lambda:inp.read(1024*1024),b''):
                    out.write(piece)
                out.flush();os.fsync(out.fileno())
        if _sha(source)!=expected_sha or _sha(dest)!=expected_sha:
            dest.unlink(missing_ok=True)
            raise RuntimeError('HAM_COPY_SHA_CHANGED')
        source.unlink()

    def _recover(self,db):
        notices=[]
        for row in db.execute("SELECT * FROM history WHERE status='RESERVED'"):
            dest=self.folder/row['path']
            source=self.folder/row['source_name']
            if dest.is_file() and not dest.is_symlink() and _sha(dest)==row['sha']:
                stat=dest.stat()
                db.execute("""UPDATE history SET status='ACTIVE',size=?,mtime_ns=?
                              WHERE number=?""",(stat.st_size,stat.st_mtime_ns,row['number']))
                if source.is_file() and source!=dest:
                    notices.append({'type':'HAM_INTERRUPTED_DUPLICATE_REVIEW',
                                    'file':str(source),'number':row['number']})
            elif not source.exists():
                notices.append({'type':'HAM_INTERRUPTED_MISSING_SOURCE',
                                'file':str(dest),'number':row['number']})
        db.commit()
        return notices

    def sweep(self,*,stable_seconds:float=2.0):
        with self.lock:
            result={'renamed':[],'warnings':[],'pending':0,'high':0}
            with self._connection() as db:
                result['warnings']+=self._recover(db)
                all_files=list(self._files())
                for current,dirs,files in os.walk(self.folder,followlinks=False):
                    here=Path(current)
                    for name in dirs+files:
                        candidate=here/name
                        if candidate.is_symlink():
                            result['warnings'].append(
                                {'type':'HAM_SYMLINK_BLOCKED','file':str(candidate)})
                    for name in files:
                        candidate=here/name
                        if candidate.suffix.lower() in SUSPECT:
                            result['warnings'].append(
                                {'type':'HAM_UNSUPPORTED_IMAGE_FORMAT',
                                 'file':str(candidate)})
                result['warnings']+=self._check_existing(all_files,db)
                # Deleted source is a permanent tombstone, not a global pause:
                # keep the number reserved and warn while other imports proceed.
                blocking={'HAM_NUMBER_EXTENSION_COLLISION',
                          'HAM_REGISTERED_BYTES_CHANGED',
                          'HAM_INTERRUPTED_DUPLICATE_REVIEW',
                          'HAM_INTERRUPTED_MISSING_SOURCE'}
                if any(w['type'] in blocking for w in result['warnings']):
                    result['high']=db.execute('SELECT high FROM meta WHERE id=1').fetchone()[0]
                    return result # Existing identity ambiguity needs human review.
                tracked={x['path'] for x in db.execute("SELECT path FROM history WHERE status='ACTIVE'")}
                occupied={n for f in all_files if (n:=_number(f)) is not None}
                old_sha={x['sha'] for x in db.execute("SELECT sha FROM history WHERE status='ACTIVE'")}
                # Same apparent raw name with different codec must not silently
                # become two independent HAM IDs, even across nested folders.
                import unicodedata
                fresh=[f for f in all_files
                       if str(f.relative_to(self.folder)) not in tracked]
                by_stem={}
                for f in fresh:
                    key=unicodedata.normalize('NFC',f.stem).casefold()
                    by_stem.setdefault(key,[]).append(f)
                ambiguous={f for group in by_stem.values()
                           if len({q.suffix.lower() for q in group})>1
                           for f in group}
                for duplicate in sorted(ambiguous):
                    result['warnings'].append({
                      'type':'HAM_SAME_NAME_DIFFERENT_EXTENSION',
                      'file':str(duplicate),
                      'others':[str(q) for q in by_stem[
                          unicodedata.normalize('NFC',duplicate.stem).casefold()]
                          if q!=duplicate]})
                for file in all_files:
                    rel=str(file.relative_to(self.folder))
                    if rel in tracked:continue
                    if file in ambiguous:continue
                    if not _safe_path(file,self.folder):
                        result['warnings'].append({'type':'HAM_UNSAFE_INPUT','file':str(file)})
                        continue
                    stat=file.stat()
                    if stat.st_size==0 or stat.st_size>MAX_FILE_BYTES:
                        result['warnings'].append({'type':'HAM_EMPTY_OR_TOO_LARGE','file':str(file)})
                        continue
                    fingerprint=(stat.st_size,stat.st_mtime_ns)
                    if self.last_seen.get(rel)!=fingerprint or time.time()-stat.st_mtime<stable_seconds:
                        self.last_seen[rel]=fingerprint;result['pending']+=1;continue
                    try:
                        with Image.open(file) as im:im.verify()
                        digest=_sha(file)
                        if digest in old_sha:
                            result['warnings'].append({'type':'HAM_EXACT_DUPLICATE_BYTES',
                                                       'file':str(file)})
                            continue
                        number=self._next_number(db,occupied)
                        dest=file.with_name(f'Ham{number}{file.suffix.lower()}')
                        self._reserve(db,number,file,dest,digest,stat)
                        self._publish(file,dest,digest)
                        out=dest.stat()
                        db.execute("""UPDATE history SET status='ACTIVE',size=?,mtime_ns=?
                                      WHERE number=?""",(out.st_size,out.st_mtime_ns,number))
                        db.commit()
                        old_sha.add(digest);occupied.add(number)
                        self.last_seen.pop(rel,None)
                        result['renamed'].append({'old':rel,
                                                   'new':str(dest.relative_to(self.folder)),
                                                   'number':number})
                    except (OSError,ValueError,RuntimeError,UnidentifiedImageError,
                            Image.DecompressionBombError) as exc:
                        result['warnings'].append({'type':'HAM_INPUT_REVIEW','file':str(file),
                                                   'reason':str(exc)[:180]})
                result['high']=db.execute('SELECT high FROM meta WHERE id=1').fetchone()[0]
            return result

    def audit(self):
        with self.lock,self._connection() as db:
            files=list(self._files())
            issues=self._recover(db)+self._check_existing(files,db)
            used=[x['number'] for x in db.execute('SELECT number FROM history')]
            tracked={x['path'] for x in db.execute("SELECT path FROM history WHERE status='ACTIVE'")}
            unregistered=[str(f.relative_to(self.folder)) for f in files
                          if str(f.relative_to(self.folder)) not in tracked]
            return {'path':str(self.folder),'high':db.execute('SELECT high FROM meta WHERE id=1').fetchone()[0],
                    'registered':len(used),'issues':issues,
                    'unregistered':unregistered}

    def validate_for_production(self):
        report=self.audit()
        if report['issues'] or report['unregistered']:
            raise ValueError('HAM_BASKI_TASARIMLARI_ONCE_KONTROL: '+
                json.dumps({'issues':report['issues'][:4],
                            'unregistered':report['unregistered'][:4]},ensure_ascii=False))
        # Validate active bytes before a production snapshot; no expensive
        # visual hash/pHash scan and no output image comparison.
        with self._connection() as db:
            for row in db.execute("SELECT path,sha FROM history WHERE status='ACTIVE'"):
                file=self.folder/row['path']
                if _sha(file)!=row['sha']:
                    raise ValueError('HAM_DESIGN_SHA_MISMATCH: '+row['path'])
        return report


class HamDesignWatcher:
    def __init__(self,workspace:Path,notify:Callable[[str],None]|None=None,interval=3.0):
        self.vault=HamDesignVault(workspace)
        self.notify=notify or (lambda message:None)
        self.interval=max(1.0,float(interval))
        self.stop_event=threading.Event()
        self.thread=None

    def _send(self,message):
        try:self.notify(message)
        except Exception:pass

    def sweep(self):
        info=self.vault.sweep()
        for item in info['renamed']:
            self._send('HAM TASARIM: '+item['old']+' → '+item['new'])
        for item in info['warnings'][:12]:
            self._send('⚠️ HAM TASARIM KONTROL: '+json.dumps(item,ensure_ascii=False))
        return info

    def start(self):
        if self.thread and self.thread.is_alive():return
        self.stop_event.clear()
        def worker():
            while not self.stop_event.is_set():
                try:self.sweep()
                except Exception as exc:self._send('HAM TASARIM IZLEME DURDU: '+str(exc))
                self.stop_event.wait(self.interval)
        self.thread=threading.Thread(target=worker,name='HamBaskiAutoV487',daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():self.thread.join(timeout=5)
