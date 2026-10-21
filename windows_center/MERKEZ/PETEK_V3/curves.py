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


def interpolate(points):
    """Shape-preserving piecewise Hermite, no overshoot at data intervals.

    Restrict each pixel to values between its two adjacent user-entered Y
    coordinates. Unlike global splines this cannot oscillate into cut-outs.
    """
    pts = normalized(points)
    x, y = pts[:,0],pts[:,1]
    h = np.diff(x)
    d = np.diff(y)/h
    m = np.zeros_like(y)
    m[0] = d[0]
    m[-1] = d[-1]
    for i in range(1,len(x)-1):
        if d[i-1]*d[i] > 0:
            w1 = 2*h[i]+h[i-1]
            w2 = h[i]+2*h[i-1]
            m[i] = (w1+w2)/(w1/d[i-1]+w2/d[i])
        else:
            m[i] = 0.
    # PCHIP endpoint slope limit keeps short steep sections well-behaved.
    for at, i, neighbour in [(0,0,1),(-1,-1,-2)]:
        k = 0 if at==0 else -1
        if len(x)>2:
            end = ((2*h[k]+h[neighbour if at==0 else -2])*d[k]
                   -h[k]*d[neighbour if at==0 else -2])/(h[k]+h[neighbour if at==0 else -2])
            if np.sign(end)!=np.sign(d[k]):end=0.
            elif np.sign(d[k])!=np.sign(d[neighbour if at==0 else -2]) and abs(end)>abs(3*d[k]):end=3*d[k]
            m[i]=end
    xs = np.arange(int(x[0]),int(x[-1])+1)
    idx=np.searchsorted(x,xs,side='right')-1
    idx=np.clip(idx,0,len(h)-1)
    t=(xs-x[idx])/h[idx]
    ys=(2*t**3-3*t**2+1)*y[idx]+(t**3-2*t**2+t)*h[idx]*m[idx] \
       +(-2*t**3+3*t**2)*y[idx+1]+(t**3-t**2)*h[idx]*m[idx+1]
    ys=np.maximum(np.minimum(y[idx],y[idx+1]),np.minimum(np.maximum(y[idx],y[idx+1]),ys))
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
        if require_ends and coverage(points,q)<.92:
            raise engine.MaskError(('Üst' if kind=='top' else 'Alt')+
                ' kavis uçları panelin iki yanına yeterince yaklaşmıyor. '
                'İlk ve son kontrol noktalarını kenarlara doğru sürükle (en az %92 genişlik).')
        xs,ys=interpolate(points)
        valid=(xs>=0)&(xs<out.shape[1]);xs=xs[valid];ys=ys[valid]
        for x,y in zip(xs,ys):
            row=int(np.clip(round(y),0,out.shape[0]-1))
            if kind=='top':out[:row,int(x)]=0
            else:out[row:,int(x)]=0
    return out
