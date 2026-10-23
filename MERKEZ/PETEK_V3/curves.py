"""Human-drawn independent PETEK boundary curves.

Never detects or invents a boundary. Interpolation only joins the exact user
control points. Equal integer X positions use the most recent user point.
The curve never extrapolates outside its explicitly selected endpoint span.
"""
from __future__ import annotations
import numpy as np
from . import engine


def normalized(points, *, min_unique=3):
    if len(points) > 256:
        raise engine.MaskError('Bir kaviste en fazla 256 kontrol noktası kullanılabilir.')
    selected = {}
    for xy in points:
        try:
            if len(xy) != 2: raise ValueError('bad point')
            x, y = float(xy[0]), float(xy[1])
        except (TypeError, ValueError) as ex:
            raise engine.MaskError('Kavis koordinatları geçersiz.') from ex
        if not np.isfinite(x) or not np.isfinite(y):
            raise engine.MaskError('Kavis koordinatları sayısal ve sonlu olmalı.')
        selected[int(round(x))] = float(y)  # last manually placed point wins
    ordered = sorted(selected.items())
    if len(ordered) < min_unique:
        raise engine.MaskError(f'Kavis için {min_unique} farklı yatay konum gerekli. Aynı yere tıklanan noktayı sürükleyebilirsin.')
    return np.asarray(ordered, np.float64)


def _quad_side_x(top, bottom, y):
    """X of an actual (possibly slanted) quad side at the user's endpoint Y."""
    dy=float(bottom[1]-top[1])
    ratio=0. if abs(dy)<1e-6 else np.clip((y-top[1])/dy,0.,1.)
    return float(top[0]+ratio*(bottom[0]-top[0]))


def joined_endpoints(points, quad, *, require_ends=True):
    """Join ONLY the ends of a user-drawn curve to the quad side edges.

    This does not guess the curve, invent control points in its middle, or
    mirror the opposite curve. The join is horizontal at the explicitly
    chosen endpoint Y. Limit horizontal gaps to 8% of panel width, to avoid
    silently masking the wrong material after an incomplete annotation.
    """
    pts=normalized(points)
    q=np.asarray(quad,np.float64)
    if q.shape!=(4,2) or not np.isfinite(q).all():
        raise engine.MaskError('Kavis uçları için dört köşe gerekli.')
    width=max(1.,float(np.max(q[:,0])-np.min(q[:,0])))
    gap_limit=max(5.,width*.08)
    left=_quad_side_x(q[0],q[3],pts[0,1])
    right=_quad_side_x(q[1],q[2],pts[-1,1])
    left_gap=float(pts[0,0]-left)
    right_gap=float(right-pts[-1,0])
    if require_ends and (left_gap>gap_limit or right_gap>gap_limit):
        raise engine.MaskError(
            'Kavis uçları yan kenarlara yeterince yakın değil. İlk noktayı SOL, son noktayı '
            'SAĞ kenara yakın işaretle; program son dar boşluğu kenara bağlar. '
            'Köşenin üzerine tam tıklamak zorunda değilsin.')
    # Do not build nonsensical lines from distant out-of-quad points. A fresh
    # drawing with clearly incomplete ends must await user verification.
    if left_gap>gap_limit or right_gap>gap_limit:
        return pts
    # When a side is tilted, the source-X crossing is not the min/max quad X.
    # Joining at the user's selected Y respects the physical perspective.
    if left < pts[0,0]-.001:
        pts=np.vstack(([left,pts[0,1]],pts))
    elif left > pts[0,0]+.001:
        pts[0,0]=left
    if right > pts[-1,0]+.001:
        pts=np.vstack((pts,[right,pts[-1,1]]))
    elif right < pts[-1,0]-.001:
        pts[-1,0]=right
    if np.any(np.diff(pts[:,0])<=0):
        raise engine.MaskError('Kavis noktaları yatay olarak birbirine çok yakın; uç noktayı düzelt.')
    return pts


def interpolate(points, quad=None, *, require_ends=False):
    """High-control linear join of the ACTUAL clicked control points.

    V3.7 used a shape-preserving cubic; closely spaced/uneven annotations
    still looked 'rubbery' near narrow sides. Linear interpolation is the
    previous manual, no-tangent, no-overshoot behaviour requested by user.
    Endpoints can be joined to actual quad edges without mirroring curves.
    """
    pts=joined_endpoints(points,quad,require_ends=require_ends) if quad is not None else normalized(points)
    x,y=pts[:,0],pts[:,1]
    if x[-1] <= x[0]:
        raise engine.MaskError('Kavis genişliği sıfır; uç noktaları ayır.')
    xs=np.arange(int(np.ceil(x[0])),int(np.floor(x[-1]))+1)
    if not len(xs):
        # Very narrow side with fractional source coordinates.
        xs=np.asarray([int(round((x[0]+x[-1])*.5))])
    ys=np.interp(xs,x,y)
    return xs,ys


def coverage(points, quad):
    """Fraction of panel horizontal extent explicitly covered by click range."""
    arr=normalized(points)
    panel=np.asarray(quad,dtype=float)
    left=float(np.min(panel[:,0]));right=float(np.max(panel[:,0]))
    return max(0.,min(1.,(min(right,arr[-1,0])-max(left,arr[0,0]))/max(1.,right-left)))


def apply(base, quad, top=(), bottom=(), *, require_ends=True):
    """Compose two independent curves from the uncut wood mask.

    For each X, protect pixels above the user TOP curve and below the user
    BOTTOM curve. The two control point sets are never connected or guessed.
    """
    if base.dtype!=np.uint8 or base.ndim!=2:
        raise engine.MaskError('Kavis için 8 bit maske gerekli.')
    q=engine.validated_quad(quad,base.shape)
    polygon=engine.polygon_mask(base.shape,q)
    out=base.copy()
    out[polygon==0]=0
    for kind,points in (('top',top),('bottom',bottom)):
        if not points:continue
        # Drawing may be provisional with 1-2 points; do not destroy mask.
        if not require_ends and len(normalized(points,min_unique=1))<3:continue
        xs,ys=interpolate(points,q,require_ends=require_ends)
        valid=(xs>=0)&(xs<out.shape[1]);xs=xs[valid];ys=ys[valid]
        for x,y in zip(xs,ys):
            row=int(np.clip(round(y),0,out.shape[0]-1))
            if kind=='top':out[:row,int(x)]=0
            else:out[row:,int(x)]=0
    return out
