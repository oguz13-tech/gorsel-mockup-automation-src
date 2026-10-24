"""Bounded high-resolution DESIGN decode, never touches approved photo geometry.

High-resolution JPEG can be DCT-decoded at 1/4 size via OpenCV with no
full 415 MP RGB allocation; original sha stays identity. Arbitrarily huge PNG
is *not* decompressed in RAM: explicit and safe review message instead.
"""
from __future__ import annotations
import hashlib
import os
import subprocess
from pathlib import Path
import struct
import numpy as np
import cv2
from PETEK_V3 import engine as petek_engine

MAX_SOURCE_JPEG_BYTES = 250_000_000
MAX_SAFE_PROXY_PIXELS = 35_000_000


def _large_png_or_webp_proxy(path: Path, sha: str, proxy_root: Path) -> Path:
    """Opt-in disk-bounded ImageMagick source proxy for very large PNG/WebP.

    No 'resize' fallback without configured verified engine. Geometry/quads are
    unaffected; the untouched original SHA always remains the receipt identity.
    """
    engine = os.environ.get("MAGICK_EXE", "").strip()
    if not engine:
        raise petek_engine.MaskError(
            f"{path.name}: büyük PNG/WebP çalışma kopyası için MAGICK_EXE ayarlayın; "
            "orijinal dosya korunur, işlem otomatik başlatılmadı."
        )
    exe = Path(engine)
    if not exe.is_file() or exe.is_symlink():
        raise petek_engine.MaskError("MAGICK_EXE yok veya sembolik bağlantı; işlem reddedildi.")
    if proxy_root.is_symlink():
        raise petek_engine.MaskError("Çalışma kopyası klasörü güvensiz.")
    proxy_root.mkdir(parents=True, exist_ok=True)
    proxy = proxy_root / f"{sha[:24]}_v45_large_render.png"
    if proxy.is_symlink():
        raise petek_engine.MaskError("Çalışma kopyası sembolik bağlantı.")
    if proxy.exists():
        petek_engine.safe_file(proxy)
        petek_engine.read_bgr(proxy)
        return proxy
    import tempfile
    with tempfile.TemporaryDirectory(prefix="large_art_", dir=str(proxy_root)) as td:
        stage = Path(td) / "downsampled.png"
        # Limit CPU/elapsed time, memory and disk cache when decoding huge source.
        # First frame only; no arbitrary command interpolation or shell.
        cmd = [str(exe), "-limit", "memory", "256MiB",
               "-limit", "map", "512MiB", "-limit", "disk", "2048MiB",
               str(path) + "[0]", "-auto-orient", "-resize", "6000x6000>",
               "-strip", str(stage)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  errors="replace", timeout=180, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise petek_engine.MaskError("Büyük tasarım çalışma kopyası zaman/bellek sınırında başarısız.") from exc
        if proc.returncode != 0 or not stage.is_file():
            raise petek_engine.MaskError("Büyük PNG/WebP güvenli işlenemedi (ImageMagick hata kodu "
                                          + str(proc.returncode) + ").")
        petek_engine.safe_file(stage)  # both compressed and decoded pixel limits
        rendered = petek_engine.read_bgr(stage)
        if rendered.ndim != 3 or min(rendered.shape[:2]) < 32:
            raise petek_engine.MaskError("Büyük tasarım çalışma kopyası hatalı.")
        if petek_engine.digest(path) != sha:
            raise petek_engine.MaskError("Kaynak tasarım dönüştürme sırasında değişti.")
        try:
            petek_engine.atomic_new_file(proxy, stage.read_bytes())
        except FileExistsError:
            petek_engine.safe_file(proxy)
        return proxy


def prepare_render_artwork(path: Path, proxy_root: Path) -> tuple[Path, str]:
    """Return (safe render input, SHA of untouched high-resolution original)."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise petek_engine.MaskError("Tasarım dosyası eksik veya güvensiz.")
    size = path.stat().st_size
    ext = path.suffix.lower()
    allowed_bytes = MAX_SOURCE_JPEG_BYTES if ext in ('.jpg', '.jpeg', '.png', '.webp') else petek_engine.MAX_BYTES
    if not 0 < size <= allowed_bytes:
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
            if w*h > 600_000_000 or min(w, h) < 32:
                raise petek_engine.MaskError(f"{path.name}: PNG kaynak başlığı anormal büyük/uygunsuz.")
            if w*h > petek_engine.MAX_PIXELS or size > petek_engine.MAX_BYTES:
                if not os.environ.get('MAGICK_EXE', '').strip():
                    raise petek_engine.MaskError(
                        f"{path.name}: PNG {w}×{h} ({w*h/1e6:.1f} MP) — "
                        "MAGICK_EXE kurulu değil; kaynak korunarak güvenli çalışma kopyası oluşturulamadı."
                    )
                return _large_png_or_webp_proxy(path, original_sha, proxy_root), original_sha
    if ext == '.webp' and (size > petek_engine.MAX_BYTES):
        return _large_png_or_webp_proxy(path, original_sha, proxy_root), original_sha
    try:
        return petek_engine.safe_file(path), original_sha
    except petek_engine.MaskError:
        if ext == '.webp':
            return _large_png_or_webp_proxy(path, original_sha, proxy_root), original_sha
        raise
