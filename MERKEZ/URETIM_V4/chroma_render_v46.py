"""Approved planar chroma treatment; does not discover or approve geometry."""
import cv2
import numpy as np

def chroma_region(scene):
    hsv=cv2.cvtColor(scene,cv2.COLOR_BGR2HSV)
    return (hsv[:,:,0]>=130)&(hsv[:,:,0]<=179)&(hsv[:,:,1]>=70)&(hsv[:,:,2]>=38)

def prepare_chroma(scene, mask):
    marked=chroma_region(scene)
    active=mask>0
    # Existing non-chroma templates retain their rendering exactly.
    enabled=np.count_nonzero(marked&active)>max(600,np.count_nonzero(active)*.5)
    if not enabled:return scene, None
    boundary=cv2.dilate(active.astype(np.uint8),np.ones((3,3),np.uint8))>0
    if np.any(marked&boundary&~active):
        raise ValueError('CHROMA_REVIEW_REQUIRED: magenta onaylı baskı maskesi dışında; köşe/maske incelemesi gerekli.')
    neutral=scene.copy()
    luminance=cv2.cvtColor(scene,cv2.COLOR_BGR2GRAY)
    neutral[marked&active]=luminance[marked&active,None]
    return neutral,marked&active
