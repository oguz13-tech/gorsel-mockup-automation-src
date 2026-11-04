"""V3.8 source-photometric PETEK print treatment.

This is deliberately NOT a scene editor. No fake floor shadows or synthetic
sunrays are invented; only the approved printable pixels may change.  The
illumination estimator samples the original unprinted wood in a robust,
low-resolution pyramid, while artwork remains native-resolution/sharp.
"""
from __future__ import annotations
import cv2
import numpy as np

MODES = ('natural', 'strong', 'off')


def light_map(scene: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Smooth original wood illumination; reject slots/transparent protected areas."""
    h, w = mask.shape
    scale = min(1., 512. / max(h, w))
    size = (max(32, int(round(w*scale))), max(32, int(round(h*scale))))
    small = cv2.resize(scene, size, interpolation=cv2.INTER_AREA).astype(np.float32)/255.
    region = cv2.resize(mask, size, interpolation=cv2.INTER_AREA)
    # Erode to prevent the original pitch-black slot from contaminating lit wood.
    valid = np.uint8(region >= 220)
    valid = cv2.erode(valid, cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3)))
    # No data is never interpreted as black light. Prefer neutral default.
    if valid.sum() < 30:
        return np.full((h,w,3), .90, dtype=np.float32)
    sigma=max(3., max(size)*.045)
    weight=valid.astype(np.float32)
    denominator=cv2.GaussianBlur(weight,(0,0),sigma)
    numerator=cv2.GaussianBlur(small*weight[:,:,None],(0,0),sigma)
    field=numerator/np.maximum(denominator[:,:,None],.02)
    # Sparse support must not create black halos around deep arches.
    med=np.median(small[valid>0],axis=0).astype(np.float32)
    field=np.where(denominator[:,:,None] >= .10,field,med[None,None,:])
    return cv2.resize(field,(w,h),interpolation=cv2.INTER_LINEAR)


def apply(scene: np.ndarray, art: np.ndarray, mask: np.ndarray, mode: str='natural') -> np.ndarray:
    """Moderate material/photo tonality; avoids old +47% brightness and fake glare."""
    if mode not in MODES:
        raise ValueError('Işık ve kontrast modu tanınmadı')
    if scene.shape!=art.shape or scene.shape[:2]!=mask.shape or scene.dtype!=np.uint8 or art.dtype!=np.uint8:
        raise ValueError('Mockup, tasarım, maske çözünürlükleri eşleşmeli')
    if mode=='off':
        return art.copy()
    valid = mask>=220
    if np.count_nonzero(valid)<200:
        return art.copy()
    field=light_map(scene,mask)
    # BGR sRGB luminance proxy; broad estimated white wood is not a neutral
    # 255 screen. Normalize illumination to its median, NOT to display white.
    lum=field[:,:,0]*.114+field[:,:,1]*.587+field[:,:,2]*.299
    typical=float(np.median(lum[valid]))
    photo_ratio=lum/max(typical,.25)
    # Constrain print exposure. Let darkness show but do not invent white glow.
    s=.66 if mode=='natural' else .85
    gain=np.clip(1.+s*(photo_ratio-1.), .78 if mode=='natural' else .70,
                 1.045 if mode=='natural' else 1.075)
    # A gentle print contrast, with filmic toe / shoulder. Bright colors do not
    # go neon, and midtones retain separation without a global blur pass.
    x=art.astype(np.float32)/255.
    contrast=1.065 if mode=='natural' else 1.115
    x=np.clip((x-.46)*contrast+.46,0,1)
    # Soft tone shoulder above 0.83 reduces white clipping after illumination.
    toe=.83
    x=np.where(x>toe, toe+(1.-toe)*(1.-np.exp(-np.maximum(0.,x-toe)/(1.-toe)))/(1.-np.exp(-1.)), x)
    x=np.clip(x*gain[:,:,None],0,1)
    # Tiny scene-derived warm/cool cast, no fabricated golden spotlights.
    average=np.median(field[valid],axis=0)
    channel=field/np.maximum(average[None,None,:],.18)
    channel/=np.maximum(np.mean(channel,axis=2,keepdims=True),.2)
    colour_power=.16 if mode=='natural' else .24
    tint=np.power(np.clip(channel,.90,1.10),colour_power)
    x=np.clip(x*tint,0,1)
    # Diffuse inner contact at printed wood edge only. Never affects a slot.
    # Stronger here would look like a dark sticker border.
    distance=cv2.distanceTransform(np.uint8(mask>127),cv2.DIST_L2,3)
    ao=(.033 if mode=='natural' else .045)*np.exp(-np.maximum(distance-.7,0)/2.1)
    x*=(1.-ao[:,:,None])
    return np.uint8(np.clip(x*255.+.5,0,255))
