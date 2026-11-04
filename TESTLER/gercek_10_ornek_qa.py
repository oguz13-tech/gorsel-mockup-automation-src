"""Offline read-only QA of ten user-supplied PETEK photographs. DRAFT ONLY."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from PETEK_V3 import engine


def main():
    photos=ROOT/'ORNEK_PETEK_MOCKUPLARI'
    suggestions=json.loads((ROOT/'MERKEZ'/'PETEK_V3'/'reference_quads.json').read_text('utf-8'))
    records=[]
    art=np.full((420,700,3),(50,110,180),dtype=np.uint8)
    for photo in sorted(photos.glob('*.jpeg')):
        item={'file':photo.name,'sha256':engine.digest(photo),'approved':False}
        try:
            q=suggestions[item['sha256']]['quad']
            image=engine.read_bgr(photo)
            mask,info=engine.auto_mask_candidate(image,q)
            result,qa=engine.render(image,art,q,mask,marketplace=True)
            item.update({'status':'DRAFT_REVIEW_REQUIRED',
                         'print_fraction':engine.mask_check(mask,image,q)['printable_fraction'],
                         'original_mask_zero_pixels_preserved':qa['source_pixels_unchanged'],
                         'marketplace_shape':list(result.shape)})
        except (engine.MaskError,OSError,ValueError,KeyError) as exc:
            item.update({'status':'ERROR','message':str(exc)})
        records.append(item)
    print(json.dumps(records,ensure_ascii=False,indent=2))
    print('SONUC:',sum(r['status']=='DRAFT_REVIEW_REQUIRED' for r in records),
          '/',len(records),'resim taslak QA, INSAN ONAYI YAPILMADI')
    return 0 if len(records)==10 and all(r['status']=='DRAFT_REVIEW_REQUIRED' for r in records) else 2

if __name__=='__main__':raise SystemExit(main())
