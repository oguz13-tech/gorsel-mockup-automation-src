"""V3.8 source-photometric PETEK print treatment.

Only approved printable pixels may change. Original chroma-key magenta never
serves as a white light source and may never bleed through the print. The
illumination estimator uses verified neutral furniture, and a soft deterministic
window/leaf shadow layer brings room light onto the matte print without
brightening physical vents or editing approved mask/quad/original source.
"""
from __future__ import annotations
import cv2
import numpy as np

MODES = ('natural', 'strong', 'off')


def _magenta_pixels(scene: np.ndarray) -> np.ndarray:
    hsv=cv2.cvtColor(scene,cv2.COLOR_BGR2HSV)
    b,g,r=(scene[:,:,i].astype(np.int16) for i in range(3))
    return ((hsv[:,:,0]>=125)&(hsv[:,:,0]<=178)&(hsv[:,:,1]>=55)
            &(hsv[:,:,2]>=65)&(r>g+25)&(b>g+16))


def _neutral_white(scene: np.ndarray, mask: np.ndarray):
    """Nearby REAL painted-white furniture; never chroma-key magenta."""
    hsv=cv2.cvtColor(scene,cv2.COLOR_BGR2HSV)
    neutral=(mask==0)&(hsv[:,:,1]<=48)&(hsv[:,:,2]>=130)&(hsv[:,:,2]<=252)&~_magenta_pixels(scene)
    yy,xx=np.where(mask>127)
    if yy.size:
        x0,x1=int(xx.min()),int(xx.max());y0,y1=int(yy.min()),int(yy.max())
        dx=max(12,round((x1-x0+1)*.21));dy=max(12,round((y1-y0+1)*.12))
        Y,X=np.ogrid[:mask.shape[0],:mask.shape[1]]
        sides=(((X>=max(x0-dx,0))&(X<x0))|((X>x1)&(X<=min(x1+dx,mask.shape[1]-1))))
        side_rows=(Y>=max(0,y0-dy))&(Y<=min(mask.shape[0]-1,y1+dy))
        near=neutral&sides&side_rows
        if np.count_nonzero(near)>25:neutral=near
    if np.count_nonzero(neutral)>25:
        ref=np.median(scene[neutral].astype(np.float32),axis=0)/255.
        return np.clip(ref,.62,.94).astype(np.float32),True
    # No reliable painted-white in the source: fail to a neutral matte tone.
    return np.array([.842,.854,.865],np.float32),False


def light_map(scene: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Original photographic illuminance without any magenta RGB sampling."""
    h,w=mask.shape
    ref,_=_neutral_white(scene,mask)
    rgb=np.asarray(scene)
    hsv=cv2.cvtColor(rgb,cv2.COLOR_BGR2HSV)
    valid=(mask>=220)&~_magenta_pixels(scene)&(hsv[:,:,1]<=62)&(hsv[:,:,2]>=90)
    # A magenta original has no physical printable-wood photometry: do NOT
    # invent pink illumination from its chroma marker.
    if np.count_nonzero(valid)<max(100,int(mask.size*.025)):
        return np.broadcast_to(ref,(h,w,3)).copy()
    scale=min(1.,512./max(h,w));size=(max(32,round(w*scale)),max(32,round(h*scale)))
    small=cv2.resize(rgb,size,interpolation=cv2.INTER_AREA).astype(np.float32)/255.
    weight=cv2.resize(valid.astype(np.uint8),size,interpolation=cv2.INTER_NEAREST).astype(np.float32)
    sigma=max(3.,max(size)*.05)
    den=cv2.GaussianBlur(weight,(0,0),sigma)
    num=cv2.GaussianBlur(small*weight[:,:,None],(0,0),sigma)
    field=num/np.maximum(den[:,:,None],.025)
    field=np.where(den[:,:,None]>.08,field,ref.reshape(1,1,3))
    return cv2.resize(np.clip(field,.35,.98),(w,h),interpolation=cv2.INTER_LINEAR)


def _window_shadow_field(shape, mask, *, shadow_style="classic", corner_side="right"):
    """EXACTLY TWO soft, continuous, near-horizontal sun-shade bands.

    One scene-space field is reused for ink and a separately qualified wall
    region; their center-lines therefore coincide at the wall/front seam.
    No freehand spot/blotch shadows and no artificial specular highlight.
    """
    h,w=shape[:2]
    yy,xx=np.where(mask>127)
    if xx.size<200:
        return np.zeros((h,w),np.float32)
    x0,x1=int(xx.min()),int(xx.max())
    y0,y1=int(yy.min()),int(yy.max())
    H,W=192,256
    gy,gx=np.mgrid[0:H,0:W].astype(np.float32)
    # Coordinates of the whole PHOTO, NOT separately normalized wall/print.
    px=gx/(W-1)*max(1,w-1)
    py=gy/(H-1)*max(1,h-1)
    nx=(px-x0)/max(1,x1-x0)
    ny=(py-y0)/max(1,y1-y0)
    shadow=np.zeros((H,W),np.float32)
    if shadow_style == 'corner':
        if corner_side not in ('left','right'):
            raise ValueError('PETEK_CORNER_SIDE_INVALID')
        # Two almost-horizontal real-scene shadows. Their surface projection is
        # mostly ABOVE the printable panel: only the nearer strip grazes one
        # upper corner, rather than painting two complete front-face bars.
        # Shadow continues to the photo wall (and disappears behind the cabinet).
        toward=(nx if corner_side=='right' else 1.-nx)
        seam=(-.205+.205*toward)
        for lift,width,weight in ((0.,.038,.75),(-.12,.042,.84)):
            d=ny-(seam+lift)
            shadow+=weight*np.exp(-.5*(d/width)**2)
    elif shadow_style == 'classic':
        bands=((.27,.067,.94),(.625,.071,.87))
        for center,width,weight in bands:
            d=ny-(center+.025*(nx-.5))
            shadow+=weight*np.exp(-.5*(d/width)**2)
    else:
        raise ValueError('PETEK_SHADOW_STYLE_INVALID')
    shadow=cv2.GaussianBlur(np.clip(shadow,0,1),(0,0),1.15)
    return cv2.resize(shadow,(w,h),interpolation=cv2.INTER_LINEAR)


def _diffuse_window_shadows(shape, mask, intensity, *, shadow_style="classic", corner_side="right"):
    """Printable-panel part of the two-band wall-to-PETEK scene shadow."""
    field=_window_shadow_field(shape,mask,shadow_style=shadow_style,corner_side=corner_side)
    return np.clip(field*float(intensity)*(mask>0),0,
                   .36 if intensity>=.5 else .18 if intensity<.2 else .36)


def apply(scene: np.ndarray, art: np.ndarray, mask: np.ndarray, mode: str='natural', *, shadow_style='classic', corner_side='right') -> np.ndarray:
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

    # Bright neutral artwork regions (especially white backgrounds) must not
    # jump to display-white and reveal a pasted sticker. Derive a scene-native
    # "paper white" from the photographed panel illumination and softly pull
    # very bright low-chroma print areas toward it.
    scene_white,_has_photographed_white=_neutral_white(scene,mask)
    luma=np.mean(x,axis=2)
    chroma=np.max(x,axis=2)-np.min(x,axis=2)
    white_like=np.clip((luma-.76)/.20,0,1)*np.clip((.18-chroma)/.18,0,1)
    if np.any(white_like>0):
        t=(white_like**1.4)[:,:,None]
        # Soft cap: keep detail while preventing paper white from blowing past
        # the photographed furniture white.
        # Only near-white, low-chroma parts of the design may change tone;
        # preserve saturated color artwork and fine printed lines.
        capped=np.minimum(x,scene_white[None,None,:])
        x=x*(1.-t)+capped*t

    # Edge transition harmonization: a very shallow, entirely INSIDE-mask mix
    # prevents harsh seams where the new print meets the original painted body.
    distance=cv2.distanceTransform(np.uint8(mask>127),cv2.DIST_L2,3)
    edge_mix=np.clip(1.-distance/6.5,0,1)
    if np.any(edge_mix>0):
        scene_norm=np.clip(scene.astype(np.float32)/255.,0,1)
        hsv_source=cv2.cvtColor(scene,cv2.COLOR_BGR2HSV)
        safe_source=(~_magenta_pixels(scene))&(hsv_source[:,:,1]<=48)&(hsv_source[:,:,2]>=100)
        mix=((edge_mix**1.8)*.16*safe_source)[:,:,None]
        x=x*(1.-mix)+scene_norm*mix

    # LEFT-TO-CENTRE WARM-WHITE RETURN, not a full-face gray gradient.
    # At the left print seam, match the photographed painted side panel.
    # Across the centre, gradually recover bright matte paper white. The
    # physically neutral side reference is NEVER the magenta key panel.
    # Affect low-chroma bright artwork ONLY: preserve black calligraphy,
    # saturated design colours and physical vent/curve protected pixels.
    ys,xs=np.where(valid)
    if ys.size:
        left,right=float(xs.min()),float(max(xs.max(),xs.min()+1))
        nx_full=np.clip((np.arange(mask.shape[1],dtype=np.float32)-left)/(right-left),0,1)
        # Smooth ramp finished near 62% panel width; avoid a visible seam.
        t=np.clip((nx_full-.035)/.585,0,1)
        t=t*t*(3.-2.*t)
        # Slightly lift the true daylight white at the centre. The left edge
        # still starts from the photographed cabinet, not pure #FFFFFF.
        # This replaces the overly gray former +.115 target, preserving
        # colour artwork and a gradual seam-free left-to-centre transition.
        true_white=np.minimum(scene_white+.145,.982)
        target_white=(scene_white[None,:]*(1.-t[:,None])+
                      true_white[None,:]*t[:,None])
        # Existing tonal correction retained for color artwork; the newly
        # requested smooth ramp is applied only to near-neutral whites.
        white_weight=np.clip(white_like**1.5,0,1)[:,:,None]
        ramp=target_white[None,:,:]
        x=x*(1.-white_weight)+ramp*white_weight

    # White-only lift uses the pre-shadow surface colour, never source magenta.
    white_luma=np.mean(x,axis=2)
    white_chroma=np.max(x,axis=2)-np.min(x,axis=2)
    white_gate=(np.clip((white_luma-.64)/.20,0,1)*
                np.clip((.14-white_chroma)/.14,0,1))
    # Matte, non-specular daylight: shadows darken ink, never make white blow out.
    window_shadow=_diffuse_window_shadows(scene.shape,mask,.12 if mode=='natural' else .33,
                                          shadow_style=shadow_style,corner_side=corner_side)
    x*=1.-window_shadow[:,:,None]
    # Neutral-white photographic recovery (not a global gamma/brightness
    # increase): lift white printed backgrounds by a few RGB code values,
    # including shaded whites, without washing out two long shadow bands.
    # The gate is sampled from the pre-shadow neutral artwork so deliberate
    # shaded whites still receive the same subtle paper-white recovery.
    lift=(.012 if mode=='natural' else .028)*white_gate
    # Retain physical shadow contrast; weaker lift inside the two bands.
    lift*=1.-.28*window_shadow
    lighter=np.minimum(x+lift[:,:,None],.987)
    x=np.where((white_gate>0)[:,:,None],lighter,x)
    # Very fine deterministic matte MDF ink texture (not wood-grain stripes).
    # About 1 RGB code value of diffuse microtexture, never on cutouts.
    if mode=='strong':
        rng=np.random.default_rng(41631)
        grain=rng.normal(0.,.0034,size=mask.shape).astype(np.float32)
        x=np.clip(x*(1.+grain[:,:,None]),0,1)
        # The tiny random matte grain must not turn recovered white into
        # isolated clipped #FFFFFF glints. Colour artwork is untouched.
        x=np.where((white_gate>0)[:,:,None],np.minimum(x,.988),x)
    # Diffuse inner contact at printed wood edge only. Never affects a slot.
    # Stronger here would look like a dark sticker border.
    ao=(.030 if mode=='natural' else .040)*np.exp(-np.maximum(distance-.7,0)/2.3)
    x*=(1.-ao[:,:,None])
    return np.uint8(np.clip(x*255.+.5,0,255))
