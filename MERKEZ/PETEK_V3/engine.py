"""PETEK V3 original-detail-preserving raster engine, no procedural vents.

All coordinates/masks live in the original photograph's pixel space.
The source photo is never written, moved, renamed, or enhanced in place.
"""
from __future__ import annotations
import hashlib
import io
import os
from pathlib import Path
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageOps, ImageFile

Image.MAX_IMAGE_PIXELS = 40_000_000
ImageFile.LOAD_TRUNCATED_IMAGES = False
MAX_BYTES = 80_000_000
MAX_PIXELS = 40_000_000
RECIPE = 'petek-v3-v38-natural-contrast-print-finish-cover'
# The reviewed wood mask and source geometry remain compatible with V3.1.
LEGACY_APPROVAL_RECIPES = frozenset({'petek-v3-original-pixel-mask-shadows-v2','petek-v3-original-pixel-mask-shadows-v3-cover', 'petek-v3-scene-light-interactive-v35-cover', 'petek-v3-scene-light-v36-zoom-shading-cover','petek-v3-v37-manual-curves-quad-locked-cover', RECIPE})
PLACEMENT_MODES = ('cover', 'contain')


class MaskError(RuntimeError):
    pass


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_file(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise MaskError('Gorsel bulunamadi veya guvensiz baglanti.')
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise MaskError('Gorsel boyutu izin verilen sinirda degil.')
    return path.resolve(strict=True)


def read_bgr(path: Path) -> np.ndarray:
    """Correct EXIF orientation and decompression cap before opening source."""
    path = safe_file(path)
    try:
        with Image.open(path) as im:
            if im.width * im.height > MAX_PIXELS or min(im.size) < 128:
                raise MaskError('Gorsel boyutlari desteklenmiyor.')
            if getattr(im, 'n_frames', 1) != 1:
                raise MaskError('Cok kareli gorsel desteklenmiyor.')
            converted = ImageOps.exif_transpose(im).convert('RGB')
            array = np.asarray(converted, dtype=np.uint8).copy()
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise MaskError('Gorsel okunamadi: ' + path.name) from exc
    return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)


def validated_quad(points, shape):
    h, w = shape[:2]
    try:
        q = np.asarray(points, np.float64)
    except (ValueError, TypeError) as exc:
        raise MaskError('Dort kose sayisal olmali.') from exc
    if q.shape != (4, 2) or not np.isfinite(q).all():
        raise MaskError('Dort nokta gerekli: sol ust, sag ust, sag alt, sol alt.')
    if q[:,0].min() < 0 or q[:,1].min() < 0 or q[:,0].max() > w-1 or q[:,1].max() > h-1:
        raise MaskError('Dort kose gorselin disina tasiyor.')
    edges = np.roll(q, -1, axis=0) - q
    """2-D scalar cross product without deprecated NumPy vector behavior."""
    nxt = np.roll(edges, -1, axis=0)
    turn = edges[:,0]*nxt[:,1] - edges[:,1]*nxt[:,0]
    if not np.all(turn > 1e-3) or min(np.linalg.norm(edges, axis=1)) < 15:
        raise MaskError('Dort kose saat yonunde sol ustten baslayan disbukey bir alan olmali.')
    if cv2.contourArea(q.astype(np.float32)) < w*h*.018:
        raise MaskError('On panel beklenenden kucuk.')
    return q.astype(np.float32)


def polygon_mask(shape, quad):
    mask = np.zeros(shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, np.round(quad).astype(np.int32), 255)
    return mask


def auto_mask_candidate(scene, quad):
    """Conservative draft only, never treated as an approved mask.

    Use per-quad LAB brightness distribution and 2-D morphological region
    analysis. Deliberately avoid painting black vents, curved voids and floor.
    All final edges require an explicit visual approval in the GUI.
    """
    quad = validated_quad(quad, scene.shape)
    polygon = polygon_mask(scene.shape, quad)
    # Magenta reference scenes need a different PETEK print-mask detector.
    # The LAB white-wood algorithm below would reject vivid #FF00FF and give
    # an empty mask. Preserve black vent slots and curved black openings by
    # NEVER filling their gaps with a large morphology kernel.
    hsv = cv2.cvtColor(scene, cv2.COLOR_BGR2HSV)
    magenta = cv2.inRange(hsv, (130, 55, 82), (177, 255, 255))
    magenta[polygon == 0] = 0
    area = max(1,int(np.count_nonzero(polygon)))
    ratio = float(np.count_nonzero(magenta)) / area
    if ratio >= .16:
        proposed = cv2.morphologyEx(magenta, cv2.MORPH_OPEN,
               cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3)))
        proposed = cv2.morphologyEx(proposed, cv2.MORPH_CLOSE,
               cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3)))
        proposed[polygon==0] = 0
        if float(np.count_nonzero(proposed))/area < .12:
            raise MaskError('PETEK_MAGENTA_BASKI_YUZEYI_YETERSIZ')
        return proposed, {'status':'TASLAK','mode':'MAGENTA_BASKI_YUZEYI',
            'area_ratio':round(float(np.count_nonzero(proposed))/area,4),
            'warning':'Magenta renkli ahsap secildi; siyah izgara, kavis ve golgeler otomatik boyanmaz. INSAN ONAYI GEREKLI.'}
    lab = cv2.cvtColor(scene, cv2.COLOR_BGR2LAB)
    lum = lab[:,:,0].astype(np.float32)
    l = lum[polygon>0]
    if len(l) < 100:
        raise MaskError('Panel bolgesi bulunamadi.')
    # First derive a generous wood candidate to avoid cutting a diagonal seam
    # through naturally shaded white wood. Protect DARK slots independently
    # using a horizontal morphological black-hat: neighboring white wood is
    # much lighter than a narrow recessed vertical vent.
    q25,q65,q90 = np.percentile(l, [25,65,90])
    cutoff = float(max(95., min(125., q25 * .70)))
    a = lab[:,:,1].astype(np.float32)-128
    b = lab[:,:,2].astype(np.float32)-128
    chroma = np.hypot(a,b)
    candidate = (lum >= cutoff) & (chroma < 38.) & (polygon>0)
    closed = cv2.morphologyEx(lab[:,:,0], cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_RECT,(49,3)))
    contrast = closed.astype(np.int16)-lab[:,:,0].astype(np.int16)
    slot_shadow = (contrast >= 27) & (lum < 215)
    slot_shadow = cv2.dilate(slot_shadow.astype(np.uint8),
                             cv2.getStructuringElement(cv2.MORPH_RECT,(5,5))) > 0
    proposed = np.where(candidate & ~slot_shadow,255,0).astype(np.uint8)
    proposed = cv2.morphologyEx(proposed,cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3)))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(proposed,connectivity=8)
    for component in range(1,n):
        if int(stats[component,cv2.CC_STAT_AREA]) < max(20,int(np.count_nonzero(polygon)*.000025)):
            proposed[labels==component]=0
    # Do not overrun quadrilateral even at anti-aliased border.
    proposed[polygon==0]=0
    proposed,repair=repair_wood_pinholes(scene,proposed,quad)
    return proposed, {'status':'TASLAK', 'l_threshold':round(float(cutoff),2),
                  'repaired_wood_pinhole_pixels':repair['fixed_pixels'],
                  'area_ratio':float(round(np.count_nonzero(proposed)/max(1,np.count_nonzero(polygon)),4)),
                  'warning':'TASLAK: ust-alt kavisleri cizgi araci ile ayir; delikler, golgeler, zemin ve kenarlari incele.'}




def repair_wood_pinholes(scene, mask, quad):
    """Conservative, non-destructive repair of WOOD-TEXTURE false negatives.

    An old auto-mask treats the short dark strokes of wood grain as though
    they were ventilation slots. This repairs only isolated, SMALL islands
    inside the already printable region. It never creates a new large area,
    alters source pixels, touches the quadrilateral perimeter, or crosses a
    long connected opening such as a vent or a curved top/bottom recess.
    The caller owns approval, undo and persistence; we return a *copy*.
    """
    if not isinstance(scene, np.ndarray) or scene.dtype != np.uint8 or scene.ndim != 3:
        raise MaskError('Geçerli bir kaynak mockup fotoğrafı gerekli.')
    if not isinstance(mask,np.ndarray) or mask.dtype!=np.uint8 or mask.ndim!=2 or mask.shape!=scene.shape[:2]:
        raise MaskError('Maske kaynak fotoğraf boyutunda olmalı.')
    q=validated_quad(quad,scene.shape)
    panel=polygon_mask(scene.shape,q)
    h,w=scene.shape[:2]
    # A protective boundary around the quadrilateral prevents accidental
    # bridging into black top/bottom openings and the room/floor.
    perimeter=cv2.erode(panel,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))
    valid=(perimeter>0)
    outside=(mask==0)&(panel>0)
    n,labels,stats,_=cv2.connectedComponentsWithStats(outside.astype(np.uint8),connectivity=8)
    ys=q[:,1];xs=q[:,0]
    panel_h=float(max(1,max(ys)-min(ys)))
    panel_w=float(max(1,max(xs)-min(xs)))
    # Do not fill long thin openings or other large/nonlocal components.
    max_area=min(900,max(125,int(panel_h*panel_w*0.0010)))
    max_width=max(5,int(panel_w*.026))
    max_height=max(8,int(panel_h*.13))
    lab=cv2.cvtColor(scene,cv2.COLOR_BGR2LAB)
    light=lab[:,:,0]
    result=mask.copy()
    fixed_components=0; fixed_pixels=0
    rejected_dark=0; rejected_boundary=0
    ring_kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9))
    for idx in range(1,n):
        x,y,cw,ch,area=map(int,stats[idx])
        if area<2 or area>max_area or cw>max_width or ch>max_height:
            continue
        # Verify this is inside reviewed mask and well away from the polygon
        # edge; preserve even tiny real openings touching border/other voids.
        region=labels[y:y+ch,x:x+cw]==idx
        if np.any(~valid[y:y+ch,x:x+cw][region]):
            rejected_boundary+=1;continue
        x0=max(0,x-5);y0=max(0,y-5);x1=min(w,x+cw+5);y1=min(h,y+ch+5)
        zone=labels[y0:y1,x0:x1]==idx
        border=cv2.dilate(zone.astype(np.uint8),ring_kernel)>0
        neighbors=border & (~zone) & (mask[y0:y1,x0:x1]>127)
        # If not mostly surrounded by a reviewed printable region, this may
        # be an extension of a real recess/slot: fail closed.
        if np.count_nonzero(neighbors)<max(12, int(area*.65)):
            continue
        wood_l=light[y0:y1,x0:x1][neighbors].astype(np.float32)
        hole_l=light[y0:y1,x0:x1][zone].astype(np.float32)
        if not len(wood_l) or not len(hole_l):continue
        # Strongly dark elements are possible real holes, not wood texture.
        if float(np.median(hole_l)) < float(np.median(wood_l))-40.:
            rejected_dark+=1;continue
        wood_ab=lab[y0:y1,x0:x1][neighbors][:,1:3].astype(np.float32)
        hole_ab=lab[y0:y1,x0:x1][zone][:,1:3].astype(np.float32)
        if np.linalg.norm(np.median(hole_ab,axis=0)-np.median(wood_ab,axis=0))>24.:
            continue
        # All actual mask writes happen only to those isolated components.
        selected=result[y:y+ch,x:x+cw]
        selected[region]=255
        fixed_components+=1;fixed_pixels+=area
    if np.any(result[panel==0]!=mask[panel==0]):
        raise MaskError('Dörtgen dışındaki alan değiştirilemez.')
    return result,{'fixed_components':fixed_components,'fixed_pixels':fixed_pixels,
                   'rejected_dark':rejected_dark,'rejected_boundary':rejected_boundary,
                   'status':'TASLAK — insan kontrolü gereklidir'}


def clip_mask_to_panel(mask, scene, quad):
    """Return a NEW mask confined to reviewed quad, plus exact removed count.

    This is a geometric edit aid only; it never changes original assets, disk
    profiles or approved masks. Clipped pixels do not imply a correct semantic
    wood/hole mask. Caller must re-review after changing four corners.
    """
    if not isinstance(mask, np.ndarray) or mask.dtype != np.uint8 or mask.ndim != 2 \
            or mask.shape != scene.shape[:2]:
        raise MaskError('Maske, orijinal fotoğrafa ait 8-bit gri maske olmalı.')
    q = validated_quad(quad, scene.shape)
    polygon = polygon_mask(scene.shape, q)
    outside = (mask > 1) & (polygon == 0)
    count = int(np.count_nonzero(outside))
    clipped = mask.copy()
    clipped[polygon == 0] = 0
    return clipped, count


def count_outside_panel(mask, scene, quad):
    """Report unreviewed out-of-quad pixels, without silently fixing them."""
    _, count = clip_mask_to_panel(mask, scene, quad)
    return count


def mask_check(mask, scene, quad):
    if mask.dtype != np.uint8 or mask.ndim != 2 or mask.shape != scene.shape[:2]:
        raise MaskError('Maske orijinal fotografin piksel boyutuyla ayni olmali.')
    q = validated_quad(quad,scene.shape)
    polygon = polygon_mask(scene.shape,q)
    leak = int(np.count_nonzero((mask>1)&(polygon==0)))
    if leak:
        raise MaskError(f'Maske panel disina tasiyor: {leak} piksel.')
    fraction = float(np.count_nonzero(mask>127)/max(1,np.count_nonzero(polygon)))
    if fraction < 0.14 or fraction > 0.995:
        raise MaskError(f'Baski alani supheli ({fraction:.1%}). Insan duzeltmesi gerekli.')
    return {'printable_fraction':round(fraction,5),'preserved_pixels':int(np.count_nonzero(mask==0))}


def png_bytes(mask: np.ndarray) -> bytes:
    if mask.ndim != 2 or mask.dtype != np.uint8: raise MaskError('8-bit maske gerekli.')
    success, data = cv2.imencode('.png',mask,[cv2.IMWRITE_PNG_COMPRESSION,3])
    if not success: raise MaskError('Maskenin PNG kodlamasi basarisiz.')
    return data.tobytes()


def decode_mask(path: Path) -> np.ndarray:
    data = np.fromfile(str(safe_file(path)), dtype=np.uint8)
    img = cv2.imdecode(data,cv2.IMREAD_UNCHANGED)
    if img is None or img.ndim != 2 or img.dtype != np.uint8:
        raise MaskError('Maske PNG siyah-beyaz 8-bit olmali.')
    return img


def mask_hash(mask: np.ndarray) -> str:
    return hashlib.sha256(mask.tobytes()).hexdigest()


def warp_artwork(art: np.ndarray, quad: np.ndarray, scene_shape,
                 physical_aspect: float, *, placement: str = 'cover', overscan: float = 0.):
    """One sharp projection. Default: fill the entire face, no white padding.

    cover:  aspect-preserving center crop in source artwork coordinates, then
            a single perspective transformation. Printed surface is fully
            covered, with no synthetic white stripes.
    contain: preserve all content; unused virtual face is neutral white, by
             explicit choice only (e.g. important full-page typography).

    The destination quad covers the entire front face; the approved mask alone
    determines which original pixels (vents/arches/floor) remain untouched.
    """
    if not np.isfinite(physical_aspect) or not .12 <= physical_aspect <= 12:
        raise MaskError('Baski yuzeyi fiziksel en/boy orani 0.12-12 olmali.')
    if not np.isfinite(overscan) or not 0 <= overscan <= .035:
        raise MaskError('Baski tasma payi 0 - %3.5 arasinda olmali.')
    if placement not in PLACEMENT_MODES:
        raise MaskError('Bilinmeyen baski yerlestirme modu: ' + str(placement))
    if not isinstance(art, np.ndarray) or art.ndim != 3 or art.shape[2] != 3 or art.dtype != np.uint8:
        raise MaskError('Tasarim 3 kanalli RGB/BGR olmali.')
    h, w = scene_shape[:2]
    if h <= 0 or w <= 0:
        raise MaskError('Sahne boyutlari gecersiz.')
    # At or near source resolution to avoid unnecessary up/down resampling.
    estimated = max(500, int(max(np.linalg.norm(quad[1]-quad[0]),
                                 np.linalg.norm(quad[2]-quad[1]))*1.5))
    ah, aw = art.shape[:2]
    longest = min(4000, max(estimated, ah, aw))
    if physical_aspect >= 1:
        sw, sh = longest, max(2, int(round(longest/physical_aspect)))
    else:
        sh, sw = longest, max(2, int(round(longest*physical_aspect)))
    if sw*sh > 16_000_000:
        raise MaskError('Perspektif calisma alani cok buyuk.')
    target_aspect = sw / sh
    source_aspect = aw / ah

    if placement == 'cover':
        # Crop virtual source bounds rather than introduce a resized letterbox.
        # cv2.warpPerspective samples directly from native artwork: no extra
        # interpolation of a resized or cropped intermediate RGB bitmap.
        if source_aspect >= target_aspect:
            used_w = ah * target_aspect
            xmin, xmax = (aw - used_w)/2.0, (aw + used_w)/2.0
            ymin, ymax = 0.0, float(ah)
        else:
            used_h = aw / target_aspect
            xmin, xmax = 0.0, float(aw)
            ymin, ymax = (ah - used_h)/2.0, (ah + used_h)/2.0
        # Optional crop-in *within artwork*, not a modification to the approved
        # print mask; cannot repair missing printable pixels. Preview/A-B only.
        if overscan:
            trimx=(xmax-xmin)*overscan; trimy=(ymax-ymin)*overscan
            xmin+=trimx; xmax-=trimx; ymin+=trimy; ymax-=trimy
        # Half-pixel-centred transform edges; a fraction of overscan prevents
        # out-of-bounds bright rims at the 4 perimeter corners.
        source = np.float32([
            [xmin + .5, ymin + .5], [xmax - .5, ymin + .5],
            [xmax - .5, ymax - .5], [xmin + .5, ymax - .5],
        ])
        page = art
    else:
        # Opt-in content preservation for prints where any crop is unacceptable.
        scale = min(sw/aw, sh/ah)
        rw, rh = max(1, int(round(aw*scale))), max(1,int(round(ah*scale)))
        scaled=cv2.resize(art,(rw,rh), interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_CUBIC)
        page=np.full((sh,sw,3),255,np.uint8)
        x,y=(sw-rw)//2,(sh-rh)//2
        page[y:y+rh,x:x+rw]=scaled
        source=np.float32([[0,0],[sw-1,0],[sw-1,sh-1],[0,sh-1]])

    projection=cv2.getPerspectiveTransform(source,quad.astype(np.float32))
    if not np.isfinite(projection).all() or abs(np.linalg.det(projection))<1e-12:
        raise MaskError('Perspektif matrisi guvensiz.')
    return cv2.warpPerspective(page, projection, (w,h),
                               flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE if placement == 'cover'
                               else cv2.BORDER_CONSTANT,
                               borderValue=(255,255,255))


def composite(scene, projected, mask, quad, preserve_shading=True,
              lighting='natural', edge_feather_px=1.4):
    """Render only into approved wood, optionally soften INNER print edge.

    This changes no pixel outside mask, creates no fake floor shadow, and does
    not silently 'fix' semantic mask mistakes.
    """
    from .realism import apply
    report=mask_check(mask,scene,quad)
    if scene.dtype!=np.uint8 or projected.shape!=scene.shape:
        raise MaskError('Baski/kaynak boyutu uyusmuyor')
    if not 0 <= float(edge_feather_px) <= 4:
        raise MaskError('Kenar gecisi 0-4 kaynak piksel olmali')
    lit=apply(scene,projected,mask,lighting if preserve_shading else 'off')
    out=scene.copy()
    active=(mask>0)
    if not np.any(active):
        raise MaskError('Baski maskesi bos')
    alpha=(mask.astype(np.float32)/255.)
    if edge_feather_px:
        # 0-4px transition is entirely INSIDE the original allowed mask.
        distance=cv2.distanceTransform(np.uint8(active),cv2.DIST_L2,3)
        alpha*=np.clip(distance / float(edge_feather_px),0,1)
    a=alpha[active][:,None]
    out[active]=np.uint8(np.clip(lit[active].astype(np.float32)*a+
                               scene[active].astype(np.float32)*(1.-a)+.5,0,255))
    if not np.array_equal(out[mask==0],scene[mask==0]):
        raise MaskError('Orijinal koruma ihlali')
    report.update({'source_pixels_unchanged':True,'lighting':lighting,
                   'edge_feather_source_px':float(edge_feather_px),'recipe':RECIPE})
    return out,report


def canvas_3x4(scene,width=1200,height=1600):
    """Preserve scene aspect; no center crop, stretch or fake blurred edges."""
    if width!=1200 or height!=1600:raise MaskError('Ticari cikti 1200x1600 olmali.')
    h,w=scene.shape[:2]
    ratio=min(width/w,height/h)
    ow,oh=max(1,round(w*ratio)),max(1,round(h*ratio))
    native=cv2.resize(scene,(ow,oh),interpolation=cv2.INTER_AREA if ratio<1 else cv2.INTER_LANCZOS4)
    target=np.full((height,width,3),(245,245,245),np.uint8)
    dx,dy=(width-ow)//2,(height-oh)//2
    target[dy:dy+oh,dx:dx+ow]=native
    return target


def render(source, art, quad, mask, physical_aspect:float=1.1163, *,shading=True,marketplace=True, placement='cover', lighting='natural', frame_mm=0, overscan=0., edge_feather_px=1.4, panel_width_cm=None):
    scene=read_bgr(source) if not isinstance(source,np.ndarray) else source
    design=read_bgr(art) if not isinstance(art,np.ndarray) else art
    q=validated_quad(quad,scene.shape)
    from .finish import white_border
    projection=warp_artwork(design,q,scene.shape,physical_aspect,placement=placement,overscan=overscan)
    projection=white_border(projection,q,mask,frame_mm=frame_mm,
                            panel_width_cm=panel_width_cm,physical_aspect=physical_aspect)
    composed,report=composite(scene,projection,mask,q,preserve_shading=shading,
                              lighting=lighting,edge_feather_px=edge_feather_px)
    report.update({'artwork_placement':placement,'frame_mm':frame_mm,
                   'frame_width_nominal':panel_width_cm is None,
                   'art_overscan':float(overscan),
                   'cut_and_paste_verified':True,
                   'zero_blur_padding':placement == 'cover'})
    return (canvas_3x4(composed) if marketplace else composed),report


def atomic_new_file(path: Path, data:bytes):
    """Atomic create-only: current output never overwritten on crash/rerun."""
    path=Path(path)
    if path.is_symlink() or path.exists():
        raise MaskError('Ayni isimli dosya var: ASLA UZERINE YAZILMAZ.')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.parent.is_symlink():raise MaskError('Cikti klasoru guvensiz baglanti.')
    fd,temp=tempfile.mkstemp(prefix='.petek-v3-',suffix='.temp',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.link(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def encode_png(img):
    ok,buf=cv2.imencode('.png',img,[cv2.IMWRITE_PNG_COMPRESSION,4])
    if not ok:raise MaskError('Cikti PNG kodlanamadi.')
    return buf.tobytes()
