"""V4.9 independent orientation sorter: 3 non-destructive output categories.

The geometry is based on the full image canvas after EXIF orientation, not
semantic content. No resize, crop, decode/re-encode or approval/DB mutation.
"""
from __future__ import annotations

import csv
import hashlib
import os
import shutil
import uuid
from pathlib import Path
from dataclasses import dataclass
from PIL import Image, ImageOps

SUPPORTED = frozenset({'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff'})
CLASSES = ('YATAY', 'DİKEY', 'KARE')

@dataclass
class SortResult:
    source_count: int
    copied: int
    moved: int
    counts: dict[str, int]
    errors: list[str]
    report_path: Path


def orientation(source: Path, square_tolerance: float = 0.01) -> tuple[str, tuple[int,int]]:
    if not 0 <= square_tolerance < 1:
        raise ValueError('Kare toleransı 0 ile 1 arasında olmalıdır.')
    with Image.open(source) as opened:
        if opened.format is None:
            raise ValueError('Görsel biçimi okunamadı.')
        img = ImageOps.exif_transpose(opened)
        width, height = img.size
        if width <= 0 or height <= 0:
            raise ValueError('Boş görsel boyutu.')
        img.load()  # Catch truncated/corrupt images before copying.
    ratio = abs(width - height) / max(width, height)
    return ('KARE' if ratio <= square_tolerance else
            'YATAY' if width > height else 'DİKEY'), (width,height)


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def _unique_file(directory: Path, filename: str, writer) -> Path:
    stem, suffix = Path(filename).stem, Path(filename).suffix
    for n in range(1,100000):
        target = directory / (filename if n == 1 else f'{stem}__{n:03d}{suffix}')
        try:
            writer(target)
            return target
        except FileExistsError:
            continue
    raise RuntimeError('Benzersiz dosya adı üretilemedi: '+filename)


def _create_only_copy(source: Path, destination: Path) -> None:
    """Publish verified bytes without overwriting or deleting preexisting assets.

    Hardlink publication is atomic and no-clobber. On filesystems which reject
    hardlinks, exclusive-create publication is used. Cleanup only touches a
    destination actually created by this attempt, never one found on disk.
    """
    tmp = destination.parent / ('.yonlendirme_' + uuid.uuid4().hex + '.part')
    created_target = False
    try:
        with source.open('rb') as src, tmp.open('xb') as dst:
            shutil.copyfileobj(src, dst, 1024 * 1024)
            dst.flush()
            os.fsync(dst.fileno())
        if _sha256(source) != _sha256(tmp):
            raise OSError('Kopyalama SHA256 doğrulaması başarısız')
        try:
            os.link(tmp, destination)  # Fails if destination exists.
            created_target = True
        except FileExistsError:
            raise
        except OSError:
            # NEVER delete an existing destination on exclusive-open failure.
            with destination.open('xb') as dst:
                created_target = True
                with tmp.open('rb') as src:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
        if _sha256(destination) != _sha256(tmp):
            raise OSError('Hedef SHA256 doğrulaması başarısız')
    except BaseException:
        if created_target:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    finally:
        tmp.unlink(missing_ok=True)


def sort_folder(source: Path, output: Path, *, recursive: bool=True,
                square_tolerance: float=.01, move: bool=False,
                protected_roots: tuple[Path,...]=(), progress=None) -> SortResult:
    source, output = Path(source).absolute(), Path(output).absolute()
    if source.is_symlink() or output.is_symlink():
        raise ValueError('Yönlendirme / sembolik bağ klasörü desteklenmez.')
    if not source.is_dir():
        raise ValueError('Kaynak klasör bulunamadı.')
    if is_under(output,source) or is_under(source,output):
        raise ValueError('Çıktı klasörü kaynak klasörün içinde veya üstünde olamaz.')
    for protected in protected_roots:
        if is_under(output,protected) or is_under(protected,output):
            raise ValueError('Korunan çalışma/şablon/yedek alanına çıktı yazılamaz.')
        if move and (is_under(source,protected) or is_under(protected,source)):
            raise ValueError('Canlı şablon/yedek alanından TAŞIMA yasaktır.')
    if not 0 <= square_tolerance < 1:
        raise ValueError('Kare toleransı 0 ile 1 arasında olmalıdır.')

    if recursive:
        files=[]
        for current, dirs, names in os.walk(source,followlinks=False):
            dirs[:] = sorted(d for d in dirs if not (Path(current)/d).is_symlink())
            files.extend(Path(current)/n for n in sorted(names) if Path(n).suffix.lower() in SUPPORTED)
    else:
        files=sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED)
    output.mkdir(parents=True,exist_ok=True)
    for name in CLASSES:
        child=output/name
        if child.is_symlink():
            raise ValueError('Çıktı alt klasörü sembolik bağ olamaz: '+str(child))
        child.mkdir(exist_ok=True)
    counts=dict.fromkeys(CLASSES,0)
    errors=[]
    logs=[]
    copied=moved=0
    for i,file in enumerate(files,1):
        if file.is_symlink():
            errors.append(f'SYMLINK_ATLANDI: {file}')
            continue
        try:
            if progress:
                progress(i,len(files),file.name)
            category,(width,height)=orientation(file,square_tolerance)
            target = _unique_file(output/category,file.name,lambda dst: _create_only_copy(file,dst))
            if move:
                # SHA was already confirmed during copy; verify again before deletion.
                if _sha256(file)!=_sha256(target):
                    raise ValueError('Taşıma öncesi SHA256 değişti; kaynak korunuyor.')
                file.unlink()
                moved+=1
            else:
                copied+=1
            counts[category]+=1
            logs.append([str(file),str(target),category,width,height,'MOVED' if move else 'COPIED',''])
        except Exception as exc:
            # Pillow decompression-bomb, truncated image, missing file,
            # permissions and a per-image callback failure must not kill a batch.
            errors.append(f'{file}: {type(exc).__name__}: {exc}')
            logs.append([str(file),'','',0,0,'ERROR',f'{type(exc).__name__}: {exc}'])
    def write_report(path:Path):
        with path.open('x',newline='',encoding='utf-8-sig') as stream:
            writer=csv.writer(stream,delimiter=';')
            writer.writerow(['KAYNAK','HEDEF','YON','EN','BOY','DURUM','HATA'])
            writer.writerows(logs)
    report=_unique_file(output,'YON_AYIRMA_RAPORU.csv',write_report)
    return SortResult(len(files),copied,moved,counts,errors,report)
