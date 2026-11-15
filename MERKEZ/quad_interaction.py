"""Pure reusable source-pixel geometry dragging; no database writes."""
from dataclasses import dataclass
import numpy as np


def target(quad,x,y,scale=1):
    q=np.asarray(quad,float)
    if q.shape!=(4,2):return None
    p=np.array([x,y],float)
    ds=np.linalg.norm(q-p,axis=1)
    rad=22/max(.01,scale)
    if ds.min()<rad:return ('corner',int(ds.argmin()))
    def segment(a,b):
        v=b-a;f=np.clip(np.dot(p-a,v)/max(1e-8,np.dot(v,v)),0,1)
        return np.linalg.norm(p-(a+f*v))
    edge=[segment(q[i],q[(i+1)%4]) for i in range(4)]
    if min(edge)<rad*.55:return ('edge',int(np.argmin(edge)))
    v=np.roll(q,-1,axis=0)-q
    crosses=[v[i,0]*(p-q[i])[1]-v[i,1]*(p-q[i])[0] for i in range(4)]
    if min(crosses)>=0 or max(crosses)<=0:return ('inside',-1)
    return None

@dataclass
class Drag:
    start:np.ndarray
    anchor:tuple
    handle:tuple
    image_size:tuple

    def at(self,x,y):
        q=self.start.copy()
        shift=np.array([x-self.anchor[0],y-self.anchor[1]],float)
        limits=np.array(self.image_size,float)-1
        kind,index=self.handle
        if kind=='inside':
            shift=np.clip(shift,-q.min(axis=0),limits-q.max(axis=0))
            q+=shift
        else:
            for i in ([index] if kind=='corner' else [index,(index+1)%4]):
                q[i]=np.clip(q[i]+shift,[0,0],limits)
        return q

def begin(quad,x,y,image_size,scale=1):
    t=target(quad,x,y,scale)
    return Drag(np.asarray(quad,float).copy(),(x,y),t,image_size) if t else None
