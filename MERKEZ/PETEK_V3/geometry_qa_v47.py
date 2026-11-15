"""PETEK geometric acceptance report for immutable human-approved front mask.

No semantic assertion of slot count is possible from a 2D mask alone. Optional
human-labelled protection regions (vents, top/bottom arch, floor, side face)
let operators prove byte-exact preservation in synthetic and real renders.
"""
from __future__ import annotations
import numpy as np
import cv2
from . import engine

LABELS=('vents','top_curve','bottom_curve','side_face','floor','background')

def region_mask(shape, polygons):
    out=np.zeros(shape[:2],dtype=np.uint8)
    for polygon in polygons or []:
        pts=np.asarray(polygon,np.float32)
        if pts.ndim!=2 or pts.shape[0]<3 or pts.shape[1]!=2 or not np.isfinite(pts).all():
            raise engine.MaskError('PETEK_HUMAN_REGION_INVALID')
        cv2.fillPoly(out,[np.rint(pts).astype(np.int32)],255)
    return out

def inspect_print_safety(original, output, printable, quad, *, protected=None):
    if (original.shape!=output.shape or original.dtype!=np.uint8 or output.dtype!=np.uint8
            or printable.shape!=original.shape[:2]):
        raise engine.MaskError('PETEK_QA_SHAPE_MISMATCH')
    engine.mask_check(printable,original,quad)
    result={'status':'PASS','printed_pixels':int(np.count_nonzero(printable)),
            'protected_pixels':int(np.count_nonzero(printable==0)),
            'regions':{},'requires_human_region_review':not bool(protected)}
    changed=np.any(original!=output,axis=2)
    violations=int(np.count_nonzero(changed & (printable==0)))
    result['changed_outside_print_mask']=violations
    if violations:result['status']='FAIL'
    for name,polygons in (protected or {}).items():
        if name not in LABELS:
            raise engine.MaskError('PETEK_UNKNOWN_PROTECTED_REGION: '+str(name))
        roi=region_mask(original.shape,polygons)>0
        leak=int(np.count_nonzero(roi & (printable>0)))
        damaged=int(np.count_nonzero(roi & changed))
        result['regions'][name]={'area':int(np.count_nonzero(roi)),
                                  'print_mask_leak_pixels':leak,
                                  'changed_pixels':damaged}
        if leak or damaged:result['status']='FAIL'
    return result
