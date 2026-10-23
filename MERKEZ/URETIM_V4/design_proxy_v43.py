"""Bounded high-resolution DESIGN decode, never touches approved photo geometry.

High-resolution JPEG can be DCT-decoded at 1/4 size via OpenCV with no
full 415 MP RGB allocation; original sha stays identity. Arbitrarily huge PNG
is *not* decompressed in RAM: explicit and safe review message instead.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import struct
import numpy as np
import cv2
from PETEK_V3 import engine as petek_engine

MAX_SOURCE_JPEG_BYTES = 250_000_000
MAX_SAFE_PROXY_PIXELS = 35_000_000


def prepare_render_artwork(path: Path, proxy_root: Path) -> tuple[Path, str]:
    """Return (safe render input, SHA of untouched high-resolution original)."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise petek_engine.MaskError("Tasarım dosyası eksik veya güvensiz.")
    size = path.stat().st_size
    ext = path.suffix.lower()
    if not 0 < size <= (MAX_SOURCE_JPEG_BYTES if ext in ('.jpg','.jpeg') else petek_engine.MAX_BYTES):
        raise petek_engine.MaskError(
            f"{path.name}: dosya {size / 1e6:.1f} MB; güvenli kaynak sınırı aşıldı."
        )
    original_sha = petek_engine.digest(path)
    if ext in ('.jpg','.jpeg'):
        # IMREAD_REDUCED_COLOR_4 makes libjpeg decode directly to 1/4
        # dimensions instead of allocating full-scale 415 MP color buffers.
        compressed=np.fromfile(path,dtype=np.uint8)
        reduced=cv2.imdecode(compressed,cv2.IMREAD_REDUCED_COLOR_4)
        if reduced is None:
            raise petek_engine.MaskError("JPEG tasarım okunamadı: " + path.name)
        if min(reduced.shape[:2]) < 32:
            raise petek_engine.MaskError("Tasarım görüntüsü çok küçük: " + path.name)
        # A 415 MP original will decode to ~26 MP, adequate for 1200x1600
        # ecommerce outputs without changing original full-res artwork.
        need_proxy = reduced.shape[0]*reduced.shape[1]*16 > petek_engine.MAX_PIXELS
        if need_proxy:
            if reduced.shape[0]*reduced.shape[1] > MAX_SAFE_PROXY_PIXELS:
                raise petek_engine.MaskError(
                    f"{path.name}: küçültülmüş JPEG bile RAM bütçesini aşar."
                )
            proxy_root.mkdir(parents=True,exist_ok=True)
            proxy=proxy_root / (original_sha[:24] + '_working.jpg')
            if proxy.is_symlink():
                raise petek_engine.MaskError("Çalışma türevi yolu güvensiz")
            if not proxy.exists():
                ok,buf=cv2.imencode('.jpg',reduced,[cv2.IMWRITE_JPEG_QUALITY,95])
                if not ok:
                    raise petek_engine.MaskError("Yüksek çözünürlüklü geçici görüntü hazırlanamadı.")
                try:
                    petek_engine.atomic_new_file(proxy,bytes(buf))
                except FileExistsError:
                    pass
            if proxy.stat().st_size > petek_engine.MAX_BYTES or petek_engine.read_bgr(proxy).size == 0:
                raise petek_engine.MaskError("Çalışma türevi geçersiz")
            return proxy,original_sha
        return path, original_sha
    if ext == '.png':
        # Read IHDR only: no decompression bomb or massive RAM allocation.
        with path.open('rb') as f:
            head=f.read(24)
        if head[:8] == b'\x89PNG\r\n\x1a\n' and head[12:16] == b'IHDR':
            w,h=struct.unpack('>II',head[16:24])
            if w*h > petek_engine.MAX_PIXELS:
                raise petek_engine.MaskError(
                    f"{path.name}: PNG {w}×{h} ({w*h/1e6:.1f} MP); "
                    "kaynağı değiştirmeden JPEG çalışma kopyası kullanın. "
                    "415 MP PNG'nin güvenli akış işlemcisi henüz bulunmuyor."
                )
    return petek_engine.safe_file(path),original_sha