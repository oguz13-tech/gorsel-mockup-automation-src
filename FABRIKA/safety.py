"""Local immutable publication, source snapshots, and process-scoped locking."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


class IntegrityError(RuntimeError):
    pass


def safe(path):
    path = Path(path).absolute()
    for p in (path, *path.parents):
        if p.is_symlink() or (p.exists() and getattr(p.lstat(), 'st_reparse_tag', 0) in (0xA0000003, 0xA000000C)):
            raise IntegrityError('Bağlantı/junction yolu engellendi: ' + str(p))
    return path


def sha(path):
    h = hashlib.sha256()
    with safe(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def key(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def separate(a, b):
    a, b = safe(a).resolve(), safe(b).resolve()
    if a == b or a in b.parents or b in a.parents:
        raise IntegrityError('Girdi ve çıktı klasörleri iç içe olamaz: ' + str(a))


def immutable(path, data):
    """Atomic, exclusive publication; identical orphans are recoverable, never overwritten."""
    path = safe(path)
    expected = hashlib.sha256(data).hexdigest()
    if path.exists():
        if sha(path) != expected:
            raise IntegrityError('Aynı isimde farklı içerik; üzerine yazılmadı: ' + str(path))
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.publishing-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        try:
            os.link(name, path)
        except FileExistsError:
            if sha(path) != expected:
                raise IntegrityError('Eşzamanlı çıktı çakışması: ' + str(path))
            return False
        return True
    finally:
        Path(name).unlink(missing_ok=True)


def json_new(path, document):
    return immutable(path, json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2).encode())


def json_atomic(path, document):
    path = safe(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(document, f, ensure_ascii=False, indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read_json(path):
    p = safe(path)
    if p.stat().st_size > 8_000_000:
        raise IntegrityError('JSON boyut sınırı aşıldı.')
    return json.loads(p.read_text(encoding='utf-8-sig'))


class ProcessLock:
    """OS advisory lock released by the kernel after crash; lock file is never deleted."""
    def __init__(self, path):
        self.path = safe(path); self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open('a+b')
        if self.path.stat().st_size == 0:
            self.stream.write(b'0'); self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close(); self.stream = None
            raise IntegrityError('Başka üretim çalışıyor. Bitmesini bekleyin.') from exc
        return self

    def __exit__(self, *args):
        if self.stream:
            self.stream.close(); self.stream = None
