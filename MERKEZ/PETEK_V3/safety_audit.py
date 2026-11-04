"""Read-only production receipt auditor for PETEK.

Never deletes, rewrites, or automatically completes an unfinished artifact.
The caller must choose a reviewed recovery action. All paths must live beneath
our dedicated PETEK output tree, and bytes must match the SQLite receipt.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import os
import math
from . import engine


def _is_in(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


def audit_ledger(ledger, output_root):
    """Return a deterministic read-only list of every row and its real state."""
    base = Path(output_root).resolve()
    with ledger.connect() as db:
        records = [dict(r) for r in db.execute('SELECT * FROM artifact ORDER BY key')]
    report=[]
    for rec in records:
        path=Path(rec['output'])
        item={'key': rec['key'], 'sku': rec['sku'], 'status':rec['status'],
              'output':str(path), 'receipt_sha':rec['output_sha'],
              'audit':'REVIEW_REQUIRED', 'detail':''}
        if path.is_symlink() or not _is_in(path.resolve(),base):
            item['detail']='UNSAFE_OUTPUT_PATH'
        elif not path.exists():
            item['detail']='OUTPUT_MISSING'
        elif not path.is_file():
            item['detail']='OUTPUT_NOT_A_FILE'
        else:
            actual=engine.digest(path)
            item['actual_sha']=actual
            if rec['status']=='RENDERED' and actual==rec['output_sha']:
                item['audit']='VERIFIED';item['detail']='OK'
            elif rec['status']=='RENDERED':
                item['detail']='OUTPUT_SHA_MISMATCH'
            elif rec['status']=='PENDING':
                item['detail']='INTERRUPTED_AFTER_FILE_WRITE'
            else:
                item['detail']='UNRESOLVED_ARTIFACT'
        report.append(item)
    return report


def audit_summary(items):
    verified=sum(row['audit']=='VERIFIED' for row in items)
    return {'total':len(items),'verified':verified,
            'review_required':len(items)-verified,
            'issues':[{'key':row['key'],'reason':row['detail']}
                      for row in items if row['audit']!='VERIFIED']}


def receipt_identity(profile, art_sha, *, group, placement, lighting, recipe):
    """One canonical versioned render identity, independent of filename/extension.

    A reviewed change of source, mask, geometry, scale, layout or lighting
    creates a different key. Existing earlier ledger keys are NEVER changed.
    """
    quad=profile.get('quad')
    if not isinstance(quad,list) or len(quad)!=4:
        raise engine.MaskError('Onayli dort kose bilgisi eksik.')
    try:
        geom=[[round(float(p[0]),6),round(float(p[1]),6)] for p in quad]
        physical=round(float(profile['physical_aspect']),8)
        if any(len(p)!=2 or not all(math.isfinite(v) for v in p) for p in geom):
            raise ValueError('nonfinite quad')
        if not math.isfinite(physical) or not 0.1 < physical < 12:
            raise ValueError('nonfinite aspect')
    except (IndexError, ValueError, TypeError, KeyError) as e:
        raise engine.MaskError('Geometri/olcu oranı gecersiz.') from e
    payload={'identity_version':2,'recipe':str(recipe),'group':str(group),
             'template_uid':str(profile['uid']),'source_sha256':str(profile['source_sha']),
             'mask_sha256':str(profile['mask_sha']),'art_sha256':str(art_sha),
             'front_quad':geom,'physical_aspect':physical,
             'placement':str(placement),'lighting':str(lighting)}
    stamp=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
    digest=hashlib.sha256(stamp.encode()).hexdigest()
    return digest,payload
