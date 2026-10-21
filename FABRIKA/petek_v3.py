"""Source-detail-preserving PETEK: human quad, reviewed source-bound print mask.

White/neutral wood analysis is a proposal, never automatic human approval.
All protected pixels are copied from the formatted source, including real slots.
Artwork uses proportional center crop and one perspective resampling. No blur fill.
"""
from dataclasses import dataclass
import io
from pathlib import Path
import warnings

import cv2
import numpy as np
from PIL import Image, ImageOps

from .safety import IntegrityError, immutable, json_new, key, read_json, safe, sha

RECIPE = 'petek-original-details-v3.1'
ANALYZER = 'neutral-wood-local-contrast-v1'
CATEGORY = '06_Petek_Dolabi'
SIZE = (1200, 1600)


def image(path):
    path = safe(path)
    if path.stat().st_size > 100_000_000:
        raise ValueError('Görsel 100 MB sınırını aşıyor.')
    raw = path.read_bytes()
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(raw)) as src:
            if src.width * src.height > 28_000_000 or min(src.size) < 64 or getattr(src, 'n_frames', 1) != 1:
                raise ValueError('Görsel boyutu veya kare sayısı desteklenmiyor.')
            normalized = ImageOps.exif_transpose(src).convert('RGBA')
            if normalized.getchannel('A').getextrema() != (255, 255):
                raise ValueError('Saydam görsel yerine opak JPG/PNG seçin.')
            return cv2.cvtColor(np.array(normalized.convert('RGB')), cv2.COLOR_RGB2BGR)


def png(array):
    ok, encoded = cv2.imencode('.png', array)
    if not ok:
        raise ValueError('PNG oluşturulamadı.')
    return encoded.tobytes()


def quad_mask(shape, quad):
    q = np.array(quad, np.float32)
    h, w = shape[:2]
    if q.shape != (4, 2) or not np.isfinite(q).all():
        raise ValueError('Dört köşe gerekli.')
    if np.any(q < 0) or np.any(q[:, 0] >= w) or np.any(q[:, 1] >= h):
        raise ValueError('Köşeler görselin dışında.')
    if not cv2.isContourConvex(q) or cv2.contourArea(q, oriented=True) < max(100, h*w*.005):
        raise ValueError('Sıra: 1 sol üst, 2 sağ üst, 3 sağ alt, 4 sol alt. Köşeler kesişmemeli.')
    if q[:2, 1].mean() >= q[2:, 1].mean() or q[[0, 3], 0].mean() >= q[[1, 2], 0].mean():
        raise ValueError('Köşeleri sol üst → sağ üst → sağ alt → sol alt sırasıyla seçin.')
    if np.min(np.linalg.norm(np.roll(q, -1, axis=0)-q, axis=1)) < 20:
        raise ValueError('Ön panel kenarı çok küçük.')
    mask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(mask, np.rint(q).astype(np.int32), 255)
    return mask


@dataclass
class Analysis:
    mask: np.ndarray
    metrics: dict


def analyze(scene, quad, sensitivity=0):
    """Propose wood pixels; dark/colored holes and their edges remain source pixels.

    No fixed aperture count or hand-built curve. Local contrast catches narrow
    recesses whose absolute brightness overlaps shaded wood. Manual mask review
    is required because a light background can be indistinguishable from wood.
    """
    roi = quad_mask(scene.shape, quad)
    lab = cv2.cvtColor(scene, cv2.COLOR_BGR2LAB).astype(np.float32)
    luma = lab[:, :, 0]
    sample = lab[roi > 0]
    bright = sample[sample[:, 0] >= np.percentile(sample[:, 0], 65)]
    neutral = np.median(bright[:, 1:], axis=0)
    threshold = max(60., float(np.percentile(bright[:, 0], 50)) * .58) + float(sensitivity)
    chroma = np.linalg.norm(lab[:, :, 1:] - neutral, axis=2)
    q = np.array(quad)
    width = (np.linalg.norm(q[1]-q[0])+np.linalg.norm(q[2]-q[3]))/2
    diameter = max(5, min(81, int(width * .04) | 1))
    local = cv2.morphologyEx(luma, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (diameter, diameter)))
    wood = (luma >= threshold) & (chroma < 28) & ((local-luma) < 23) & (roi > 0)
    # Isolated light highlights inside apertures aren't printable wood.
    n, labels, stats, _ = cv2.connectedComponentsWithStats(wood.astype(np.uint8), 8)
    minimum = max(12, int(np.count_nonzero(roi)*.0002))
    keep = np.zeros(n, bool)
    if n > 1:
        keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= minimum
    wood = keep[labels]
    # One-pixel edge guard retains real bevels and prevents print spill.
    mask = cv2.erode(wood.astype(np.uint8)*255, np.ones((3, 3), np.uint8))
    area = int(np.count_nonzero(roi)); printed = int(np.count_nonzero(mask))
    fraction = printed / area
    metrics = {'analyzer': ANALYZER, 'coverage': fraction, 'threshold': threshold,
               'protected_pixels_in_quad': area-printed, 'requires_human_review': True,
               'warnings': []}
    if fraction < .35 or fraction > .96:
        metrics['warnings'].append('Baskı alanı olağandışı; maske önizlemesini ve boşlukları kontrol edin.')
    if np.percentile(bright[:, 0], 50) < 145:
        metrics['warnings'].append('Koyu ahşap/belirsiz ışık: otomatik beyaz yüzey analizi uygun olmayabilir.')
    return Analysis(mask, metrics)


def overlay(scene, mask):
    out = scene.copy()
    active = mask > 0
    color = np.array([70, 220, 40], np.float32)
    out[active] = np.rint(scene[active]*.60 + color*.40).astype(np.uint8)
    return out


def save_profile(root, template, quad, mask, metrics, reviewed=False, aspect=None):
    """Store immutable mask/profile under full content identity, no live approvals."""
    if reviewed is not True:
        raise ValueError('Yeşil baskı alanını kontrol edip açıkça onaylayın.')
    template = safe(template); root = safe(root)
    scene = image(template); digest = sha(template)
    roi = quad_mask(scene.shape, quad)
    if mask.shape != roi.shape or mask.dtype != np.uint8 or not np.isin(mask, [0, 255]).all():
        raise ValueError('Maske boyutu/türü geçersiz.')
    if np.any(mask[roi == 0]) or np.count_nonzero(mask) < 100:
        raise ValueError('Maske dört köşe dışına taşıyor veya boş.')
    if aspect is not None and (not np.isfinite(aspect) or not .15 <= aspect <= 6):
        raise ValueError('Fiziksel en/boy oranı 0.15–6 arasında olmalı.')
    mask_bytes = png(mask)
    import hashlib
    document = {'version': 3, 'category': CATEGORY, 'source': str(template),
                'source_sha256': digest, 'quad': quad, 'mask_sha256': hashlib.sha256(mask_bytes).hexdigest(),
                'reviewed': True, 'analyzer': ANALYZER, 'metrics': metrics,
                'aspect': aspect, 'source_dimensions': [scene.shape[1], scene.shape[0]]}
    document['profile_key'] = key({k:v for k,v in document.items() if k not in ('source','metrics')})
    directory = root/document['profile_key']
    directory.mkdir(parents=True, exist_ok=True)
    immutable(directory/'PRINT_MASK.png', mask_bytes)
    # Path may change, but existing immutable approval keeps its original source provenance.
    path = directory/'PROFILE.json'
    if path.exists():
        existing = read_json(path)
        if existing['profile_key'] != document['profile_key']:
            raise IntegrityError('Profil kimliği çakışması.')
    else:
        json_new(path, document)
    return path


def load_profile(path):
    path = safe(path); p = read_json(path)
    if p.get('version') != 3 or p.get('category') != CATEGORY or p.get('reviewed') is not True:
        raise ValueError('PETEK V3 insan onaylı maske gerekli. Eski planı dört köşe ile yeniden inceleyin.')
    identity = {k:v for k,v in p.items() if k not in ('source','metrics','profile_key')}
    if key(identity) != p['profile_key'] or sha(p['source']) != p['source_sha256']:
        raise IntegrityError('Şablon veya onaylı profil değişmiş; yeniden inceleme gerekli.')
    mask_path = path.parent/'PRINT_MASK.png'
    if sha(mask_path) != p['mask_sha256']:
        raise IntegrityError('Onaylı maske değiştirilmiş.')
    source = image(p['source'])
    mask = cv2.imdecode(np.frombuffer(mask_path.read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE)
    roi = quad_mask(source.shape, p['quad'])
    if mask is None or mask.shape != roi.shape or not np.isin(mask, [0,255]).all() or np.any(mask[roi==0]):
        raise IntegrityError('Onaylı maske ile kaynak boyutları uyumsuz.')
    return p, source, mask


def render(art, source, mask, quad, aspect=None, interpolation=cv2.INTER_CUBIC):
    """Return exact protected scene pixels at output resolution and a quality report."""
    roi = quad_mask(source.shape, quad)
    if mask.shape != roi.shape or np.any(mask[roi == 0]):
        raise IntegrityError('Baskı maskesi panel dışına taşıyor.')
    sw, sh = source.shape[1], source.shape[0]
    ow, oh = SIZE
    scale = min(ow/sw, oh/sh)
    rw, rh = max(1, round(sw*scale)), max(1, round(sh*scale))
    dx, dy = (ow-rw)//2, (oh-rh)//2
    background = np.full((oh, ow, 3), 245, np.uint8)
    # Scene is formatted once; detail preservation is measured against this same baseline.
    background[dy:dy+rh, dx:dx+rw] = cv2.resize(source, (rw,rh), interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_CUBIC)
    m = np.zeros((oh, ow), np.uint8)
    m[dy:dy+rh, dx:dx+rw] = cv2.resize(mask,(rw,rh),interpolation=cv2.INTER_NEAREST)
    q = np.asarray(quad,np.float32)*[rw/sw,rh/sh]+[dx,dy]
    edges = np.linalg.norm(np.roll(q,-1,axis=0)-q,axis=1)
    target_ratio = float(aspect or ((edges[0]+edges[2])/(edges[1]+edges[3])))
    ah, aw = art.shape[:2]
    if aw/ah > target_ratio:
        cw, ch = ah*target_ratio, float(ah)
    else:
        cw, ch = float(aw), aw/target_ratio
    left, top = (aw-cw)/2, (ah-ch)/2
    src = np.array([[left,top],[left+cw-1,top],[left+cw-1,top+ch-1],[left,top+ch-1]],np.float32)
    matrix = cv2.getPerspectiveTransform(src,q.astype(np.float32))
    # Strong minification requires a low-pass resize; do it only when >2x.
    # This avoids moiré without an unconditional resize/blur/upscale chain.
    reduction = min(cw/max(edges[0],edges[2]),ch/max(edges[1],edges[3]))
    prefiltered = False
    if reduction > 2:
        factor = 1/reduction
        nw, nh = max(2,round(aw*factor)),max(2,round(ah*factor))
        art = cv2.resize(art,(nw,nh),interpolation=cv2.INTER_AREA)
        src *= np.array([nw/aw,nh/ah],np.float32)
        matrix = cv2.getPerspectiveTransform(src,q.astype(np.float32))
        prefiltered = True
    projected = cv2.warpPerspective(art,matrix,SIZE,flags=interpolation,borderMode=cv2.BORDER_REPLICATE)
    # Soft illumination only: source holes never participate in print composition.
    lum = cv2.cvtColor(background,cv2.COLOR_BGR2LAB)[:,:,0].astype(np.float32)
    reference = max(1,float(np.percentile(lum[m>0],80)))
    shade = np.clip(lum/reference,.72,1.08)
    printed = np.clip(projected.astype(np.float32)*shade[:,:,None],0,255)
    # One-pixel inward antialias, no spread outside the approved mask.
    alpha = np.minimum(cv2.distanceTransform(m,cv2.DIST_L2,3),1.0)
    result = background.copy(); active = m>0
    result[active] = np.rint(printed[active]*alpha[active,None]+background[active]*(1-alpha[active,None])).astype(np.uint8)
    preserved = int(np.max(np.abs(result[~active].astype(np.int16)-background[~active].astype(np.int16)))) if (~active).any() else 0
    quality = {'recipe':RECIPE,'protected_pixel_max_difference':preserved,
               'crop_fraction':1-(cw*ch)/(aw*ah),'interpolation':int(interpolation),
               'minification_prefilter':prefiltered,'print_blur_fill':False,
               'estimated_aspect':aspect is None,'dimensions':[ow,oh],
               'scene_padding': [dx,dy], 'human_output_review_required':True}
    return result, quality
