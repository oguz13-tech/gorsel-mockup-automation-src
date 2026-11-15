"""Regression for actual Windows editor import path causing 8080 HTTP 500."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_flask_import_path_full_render_without_merkez_on_syspath():
    source = r'''
import sys, numpy as np, cv2
from pathlib import Path
root=Path.cwd()
assert str(root/'MERKEZ') not in sys.path, sys.path
from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual
h,w=690,900
scene=np.full((h,w,3),(255,0,255),np.uint8)
scene[:,:65]=(209,217,229)
mask=np.zeros((h,w),np.uint8)
mask[40:650,66:850]=255
for i,x in enumerate(np.linspace(105,810,15).round().astype(int)):
    y0=120+i%3*2; y1=555-i%4*3
    cv2.line(scene,(x,y0),(x,y1),(18,20,22),8,cv2.LINE_AA)
    cv2.line(mask,(x,y0),(x,y1),0,9,cv2.LINE_AA)
quad=np.float32([[66,40],[849,40],[849,649],[66,649]])
art=np.full_like(scene,255)
source=scene.copy(); approved=mask.copy()
result,qa=render_petek_visual(scene,art,quad,mask,1.1163,
    placement='cover',lighting='strong',material_effect=True,
    slot_mode='orta',pink_cleanup=False)
assert qa['slot_qa']['count']==15
assert qa['lighting']=='strong'
assert np.array_equal(result[mask==0],scene[mask==0])
assert np.array_equal(scene,source) and np.array_equal(mask,approved)
assert 'URETIM_V4' not in sys.modules
assert 'PETEK_V3' not in sys.modules
print('FLASK_IMPORT_AND_RENDER_PASS')
'''
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT)
    r = subprocess.run([sys.executable,'-c',source],cwd=str(ROOT),env=env,
                       capture_output=True,text=True,timeout=75)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert 'FLASK_IMPORT_AND_RENDER_PASS' in r.stdout


def test_local_material_file_standalone_has_no_circular_init():
    from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import _load_material_finish
    assert callable(_load_material_finish())
    assert _load_material_finish() is _load_material_finish()
