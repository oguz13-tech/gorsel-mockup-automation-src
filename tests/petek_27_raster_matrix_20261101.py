"""Execute from project root with explicit PYTHONPATH for exact baseline-vs-candidate raster hash comparison."""
import hashlib,json
import numpy as np
from tests.test_vnext_petek_protected_409_original_source_20261101 import sample as sample_one
from tests.test_vnext_petek_two_wall_shadows import photo
from tests.test_vnext_petek_preview_parity_and_recovery_20261101 import sample as sample_grille
from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual

def digest(x):return hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
fixtures=[]
s,m,q,_=sample_one();fixtures.append(('fringe',s,m,q,1.1163,'off'))
s,m,q=photo();fixtures.append(('wall',s,m,q,1.4,'off'))
s,m,q,_=sample_grille(15,bad_mask=False);fixtures.append(('vents',s,m,q,1.1163,'orta'))
results={}
for label,scene,mask,quad,aspect,slot_mode in fixtures:
    for color,bgr in [('white',(255,255,255)),('grey',(215,219,225)),('pink',(230,15,230))]:
        art=np.full((350,500,3),bgr,dtype=np.uint8)
        for light in ['off','natural','strong']:
            key=f'{label}/{color}/{light}'
            try:
                pic,qa=render_petek_visual(scene,art,quad,mask,aspect,
                            placement='cover',lighting=light,
                            material_effect=light!='off',slot_mode=slot_mode,
                            pink_cleanup=True)
                results[key]={'status':'OK','hash':digest(pic),'pixels':int(pic.size),'pink':qa['pink_qa'].get('remaining_pixels')}
            except Exception as exc:
                results[key]={'status':'ERROR','error':str(exc)}
print(json.dumps(results,sort_keys=True,ensure_ascii=False))
