"""PETEK seventh-category Flask endpoints; reuse existing V3 mask registry.

Only the working Petek_Dolabi folder is exposed; private files, historic
originals and approved profiles are never overwritten. CSRF is handled by
the parent app's existing global guard.
"""
import base64
import re
from pathlib import Path
import cv2
import numpy as np
from flask import Blueprint,current_app,jsonify,request,send_file
from MERKEZ.PETEK_V3 import engine,curves
from MERKEZ.PETEK_V3.registry import Registry
from MERKEZ.petek_folders_v46 import petek_directory

petek_web=Blueprint('petek_web_v477',__name__)
MAX_MASK=16*1024*1024
SUFFIXES={'.jpg','.jpeg','.png','.webp'}

def _working():
    root=Path(current_app.config['PETEK_WORKSPACE_V477']).resolve(strict=True)
    directory=petek_directory(root,'2_SABLON_HAVUZU')
    if directory.is_symlink():raise ValueError('PETEK_WORKING_SYMLINK')
    return directory

def _photo(name):
    if not isinstance(name,str) or not name or name in ('.','..') or len(name)>180:
        raise ValueError('PETEK_BAD_FILENAME')
    if '/' in name or '\\' in name or Path(name).name!=name:
        raise ValueError('PETEK_BAD_FILENAME')
    folder=_working()
    file=folder/name
    if (file.is_symlink() or not file.is_file() or
            file.suffix.lower() not in SUFFIXES or file.resolve().parent!=folder.resolve()):
        raise ValueError('PETEK_SOURCE_NOT_IN_WORKING_POOL')
    return file

def _identity(registry,file):
    sha=engine.digest(file)
    matches=[row for row in registry.list() if row['source_sha']==sha]
    if len(matches)>1:raise ValueError('PETEK_MULTIPLE_PROFILES_MATCH_ONE_SHA')
    if matches:return matches[0]['uid'],sha
    uid=re.sub('[^A-Za-z0-9_-]','_',file.stem)[:80] or 'petek'
    if (registry.profiles/(uid+'.json')).is_file():
        uid=uid[:61]+'_'+sha[:16]
        if (registry.profiles/(uid+'.json')).exists():
            raise ValueError('PETEK_UID_SOURCE_CONFLICT')
    return uid,sha

def _png_data(mask):
    return 'data:image/png;base64,'+base64.b64encode(engine.png_bytes(mask)).decode('ascii')

def _decode(data,shape):
    if not isinstance(data,str) or not data.startswith('data:image/png;base64,'):
        raise ValueError('PETEK_MASK_PNG_REQUIRED')
    encoded=data.partition(',')[2]
    if len(encoded)>MAX_MASK*4//3+16:raise ValueError('PETEK_MASK_TOO_LARGE')
    try:raw=base64.b64decode(encoded,validate=True)
    except (ValueError,TypeError) as exc:raise ValueError('PETEK_BAD_MASK_ENCODING') from exc
    if len(raw)>MAX_MASK:raise ValueError('PETEK_MASK_TOO_LARGE')
    mask=cv2.imdecode(np.frombuffer(raw,dtype=np.uint8),cv2.IMREAD_UNCHANGED)
    if mask is None or mask.dtype!=np.uint8 or mask.shape[:2]!=shape[:2]:
        raise ValueError('PETEK_MASK_SHAPE_INVALID')
    # Canvas.toDataURL produces RGBA PNG on all major browsers. Accept only
    # equal-channel opaque grayscale, otherwise FAIL rather than letting
    # colored/transparent brush pixels silently turn into a wrong print mask.
    if mask.ndim==3 and mask.shape[2]==4:
        if (not np.all(mask[:,:,3]==255) or not
                np.array_equal(mask[:,:,0],mask[:,:,1]) or not
                np.array_equal(mask[:,:,1],mask[:,:,2])):
            raise ValueError('PETEK_MASK_NOT_OPAQUE_GRAYSCALE')
        mask=mask[:,:,0].copy()
    elif mask.ndim!=2:
        raise ValueError('PETEK_MASK_NOT_GRAYSCALE')
    return mask

def _request_scene():
    payload=request.get_json(silent=True)
    if not isinstance(payload,dict):raise ValueError('PETEK_JSON_REQUIRED')
    file=_photo(payload.get('name'))
    if engine.digest(file)!=payload.get('source_sha'):
        raise ValueError('PETEK_SOURCE_CHANGED_RELOAD')
    return payload,file,engine.read_bgr(file)

def _fail(exc):
    return jsonify({'success':False,'error':str(exc)[:240]}),409

@petek_web.get('/api/petek/templates')
def list_templates():
    try:
        registry=Registry();items=[]
        folder=_working()
        if folder.is_dir():
            for file in sorted(folder.iterdir(),key=lambda x:x.name.casefold()):
                if file.is_symlink() or not file.is_file() or file.suffix.lower() not in SUFFIXES:
                    continue
                uid,sha=_identity(registry,file)
                status='NEW'
                if (registry.profiles/(uid+'.json')).is_file():
                    profile,_=registry.get(uid)
                    status=profile['status']
                items.append({'name':file.name,'uid':uid,'source_sha':sha,'status':status})
        return jsonify({'success':True,'category':'06_Petek_Kapama','items':items,
                        'folder':'2_SABLON_HAVUZU/Petek_Dolabi'})
    except (ValueError,OSError,engine.MaskError) as exc:return _fail(exc)

@petek_web.get('/api/petek/photo/<path:name>')
def photo(name):
    try:
        file=_photo(name)
        mime={'.png':'image/png','.webp':'image/webp','.jpg':'image/jpeg',
              '.jpeg':'image/jpeg'}[file.suffix.lower()]
        return send_file(file,mimetype=mime,conditional=False)
    except (ValueError,OSError) as exc:return _fail(exc)

@petek_web.get('/api/petek/detail/<path:name>')
def detail(name):
    try:
        file=_photo(name);r=Registry()
        uid,sha=_identity(r,file);scene=engine.read_bgr(file)
        row={'success':True,'name':file.name,'uid':uid,'source_sha':sha,
             'width':int(scene.shape[1]),'height':int(scene.shape[0]),
             'status':'NEW','quad':[],'mask':None,'base_mask':None,
             'curve_points':{'top':[],'bottom':[]},'physical_aspect':1.1163}
        if (r.profiles/(uid+'.json')).is_file():
            profile,mask=r.get(uid)
            row.update({'status':profile['status'],'quad':profile['quad'],
                'mask':_png_data(mask),'physical_aspect':profile['physical_aspect'],
                'curve_points':profile.get('curve_points') or {'top':[],'bottom':[]}})
            sha_base=profile.get('base_mask_sha')
            if sha_base:
                base=engine.decode_mask(r.masks/(sha_base+'.png'))
                if engine.mask_hash(base)!=sha_base:
                    raise ValueError('PETEK_BASE_MASK_SHA_MISMATCH')
                row['base_mask']=_png_data(base)
        return jsonify(row)
    except (ValueError,OSError,engine.MaskError) as exc:return _fail(exc)

@petek_web.post('/api/petek/auto-mask')
def auto_mask():
    try:
        body,file,scene=_request_scene()
        mask,qa=engine.auto_mask_candidate(scene,body.get('quad'))
        return jsonify({'success':True,'mask':_png_data(mask),'qa':qa})
    except (ValueError,OSError,TypeError,engine.MaskError) as exc:return _fail(exc)

@petek_web.post('/api/petek/curve-preview')
def curve_preview():
    try:
        body,file,scene=_request_scene()
        quad=engine.validated_quad(body.get('quad'),scene.shape)
        base=_decode(body.get('base_mask'),scene.shape)
        points=body.get('curve_points') or {}
        mask=curves.apply(base,quad,points.get('top',[]),
                          points.get('bottom',[]),require_ends=True)
        qa=engine.mask_check(mask,scene,quad)
        return jsonify({'success':True,'mask':_png_data(mask),'qa':qa})
    except (ValueError,OSError,TypeError,KeyError,engine.MaskError) as exc:return _fail(exc)

@petek_web.post('/api/petek/save-draft')
def save_draft():
    try:
        body,file,scene=_request_scene()
        r=Registry();uid,sha=_identity(r,file)
        if uid!=body.get('uid'):raise ValueError('PETEK_UID_CHANGED_RELOAD')
        if (r.profiles/(uid+'.json')).is_file():
            previous,_=r.get(uid)
            if previous['status']=='APPROVED':
                raise ValueError('APPROVED_PETEK_IMMUTABLE')
        quad=engine.validated_quad(body.get('quad'),scene.shape)
        mask=_decode(body.get('mask'),scene.shape)
        points=body.get('curve_points') or {}
        selected={kind:points.get(kind,[]) for kind in ('top','bottom')}
        base=None
        if any(selected.values()):
            base=_decode(body.get('base_mask'),scene.shape)
            expected=curves.apply(base,quad,selected['top'],selected['bottom'],require_ends=True)
            if not np.array_equal(expected,mask):
                raise ValueError('PETEK_CURVE_MASK_MISMATCH')
        value=float(body.get('physical_aspect',1.1163))
        p=r.save(uid,file,quad,mask,value,approved=False,
                 curve_points=selected,base_mask=base)
        return jsonify({'success':True,'uid':uid,'status':p['status'],
                        'mask_sha':p['mask_sha'],'qa':p['mask_qa']})
    except (ValueError,OSError,TypeError,KeyError,OverflowError,engine.MaskError) as exc:return _fail(exc)

@petek_web.post('/api/petek/approve')
def approve():
    try:
        body,file,scene=_request_scene()
        r=Registry();uid,sha=_identity(r,file)
        if uid!=body.get('uid') or sha!=body.get('confirmed_sha'):
            raise ValueError('PETEK_UID_OR_SHA_CHANGED_RELOAD')
        p=r.approve(uid,str(body.get('reviewer') or ''),str(body.get('confirm') or ''))
        return jsonify({'success':True,'uid':uid,'status':p['status'],
                        'mask_sha':p['mask_sha']})
    except (ValueError,OSError,TypeError,KeyError,engine.MaskError) as exc:return _fail(exc)
