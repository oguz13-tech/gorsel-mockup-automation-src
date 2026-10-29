"""PETEK seventh-category Flask endpoints; reuse existing V3 mask registry.

Only the working Petek_Dolabi folder is exposed; private files, historic
originals and approved profiles are never overwritten. CSRF is handled by
the parent app's existing global guard.
"""
import base64
import re
from pathlib import Path
from functools import lru_cache
import cv2
import numpy as np
from flask import Blueprint,current_app,jsonify,request,send_file
from MERKEZ.PETEK_V3 import engine,curves
from MERKEZ.PETEK_V3.magenta_quad_v479 import detect_magenta_quad
from MERKEZ.PETEK_V3.cutout_paste import render_with_cutout_paste
from MERKEZ.PETEK_V3.grille_guard_v482 import recommended_edge_feather,magenta_residue_report
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

def _identity(registry,file,selected=None):
    sha=engine.digest(file)
    matches=[row for row in registry.list() if row['source_sha']==sha]
    if selected is not None:
        if not isinstance(selected,str) or not re.fullmatch('[A-Za-z0-9_-]{1,96}',selected):
            raise ValueError('PETEK_SELECTED_UID_INVALID')
        if any(row['uid']==selected for row in matches):
            return selected,sha
        if matches:raise ValueError('PETEK_UID_NOT_BOUND_TO_SOURCE_SHA')
    if matches:
        if len(matches)>1:raise ValueError('PETEK_SELECT_PROFILE_REVISION')
        return matches[0]['uid'],sha
    uid=re.sub('[^A-Za-z0-9_-]','_',file.stem)[:80] or 'petek'
    if (registry.profiles/(uid+'.json')).is_file():
        uid=uid[:61]+'_'+sha[:16]
        if (registry.profiles/(uid+'.json')).exists():
            raise ValueError('PETEK_UID_SOURCE_CONFLICT')
    if selected is not None and selected!=uid:
        raise ValueError('PETEK_NEW_UID_CHANGED_RELOAD')
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

@lru_cache(maxsize=4096)
def _sidebar_digest(path, size, mtime_ns, ctime_ns, inode):
    """Only for non-authoritative list display. Save/approve/production rehash."""
    return engine.digest(Path(path))


def _sidebar_sha(file):
    stat=file.stat()
    if file.is_symlink():raise ValueError('PETEK_SIDEBAR_SYMLINK')
    return _sidebar_digest(str(file.resolve()),stat.st_size,stat.st_mtime_ns,
                           stat.st_ctime_ns,getattr(stat,'st_ino',0))


@petek_web.get('/api/petek/templates')
def list_templates():
    """Unified PETEK sidebar statuses; only reads working/backup/profile bytes.

    Unlike legacy six-category UI, PETEK profiles are in an immutable V3
    registry, so report actual values instead of inventing SQLite indicators.
    """
    try:
        registry=Registry();items=[];warnings=[];seen=0
        folder=_working()
        history=registry.list()
        profiles={}
        for row in history:profiles.setdefault(row['source_sha'],[]).append(row)
        # A missing original archive is reported, NEVER silently fabricated.
        root=Path(current_app.config['PETEK_WORKSPACE_V477'])
        try:
            archive=petek_directory(root,'2_SABLON_HAVUZU_ORIJINAL_YEDEK')
        except (OSError,ValueError) as exc:
            archive=None
            warnings.append({'file':'ORIGINAL_ARCHIVE','error':str(exc)[:200]})
        if folder.is_dir():
            for file in sorted(folder.iterdir(),key=lambda x:x.name.casefold()):
                if file.is_symlink() or not file.is_file() or file.suffix.lower() not in SUFFIXES:
                    continue
                seen+=1
                try:
                    sha=_sidebar_sha(file)
                    backup='MISSING'
                    if archive is not None and archive.is_dir():
                        original=archive/file.name
                        if original.is_symlink():
                            backup='UNSAFE'
                        elif original.is_file():
                            backup='MATCH' if _sidebar_sha(original)==sha else 'DIFFERENT'
                    matches=profiles.get(sha,[])
                    if matches:
                        for match in matches:
                            try:
                                profile,_=registry.get(match['uid'],source_override=file)
                                status=profile['status'];mask_ok=True
                            except (ValueError,OSError,KeyError,engine.MaskError) as exc:
                                status='REVIEW_REQUIRED';mask_ok=False
                                warnings.append({'file':file.name,'uid':match['uid'],
                                                 'error':str(exc)[:200]})
                            items.append({'name':file.name,'uid':match['uid'],
                                'source_sha':sha,'status':status,
                                'working_ok':True,'backup_status':backup,
                                'mask_verified':mask_ok,'approved':status=='APPROVED'})
                    else:
                        uid,_=_identity(registry,file)
                        items.append({'name':file.name,'uid':uid,
                            'source_sha':sha,'status':'NEW','working_ok':True,
                            'backup_status':backup,'mask_verified':False,'approved':False})
                except (ValueError,OSError,engine.MaskError) as exc:
                    # A single corrupt item never hides the other PETEK photos.
                    warnings.append({'file':file.name,'error':str(exc)[:200]})
        counts={key:sum(i['status']==key for i in items)
                for key in ('APPROVED','DRAFT','NEW','REVIEW_REQUIRED')}
        counts['backup_missing']=sum(i['backup_status']=='MISSING' for i in items)
        counts['backup_different']=sum(i['backup_status'] in ('DIFFERENT','UNSAFE') for i in items)
        return jsonify({'success':True,'category':'06_Petek_Kapama','items':items,
                        'folder':'2_SABLON_HAVUZU/Petek_Dolabi',
                        'working_path':str(folder),'runtime_root':str(root),
                        'scanned_photos':seen,'counts':counts,'warnings':warnings,
                        'registry_profiles_total':len(history),
                        'registry_approved_total':sum(row['status']=='APPROVED' for row in history),
                        'matched_approved_records':sum(item['status']=='APPROVED' for item in items),
                        'unmatched_approved_records':sum(row['status']=='APPROVED' and
                             not any(item['uid']==row['uid'] for item in items) for row in history),
                        'bulk_capabilities':{
                            'select':True,'status_filter':True,'read_only_audit':True,
                            'magenta_corner_mask_proposals':True,
                            'approval_requires_individual_review':True,
                            'legacy_bulk_delete':False}})
    except (ValueError,OSError,engine.MaskError) as exc:return _fail(exc)

def _bulk_selected():
    body=request.get_json(silent=True)
    if not isinstance(body,dict) or not isinstance(body.get('items'),list):
        raise ValueError('PETEK_BULK_JSON_ITEMS_REQUIRED')
    selected=body['items']
    if not 1<=len(selected)<=8:raise ValueError('PETEK_BULK_LIMIT_1_TO_8')
    seen=set()
    for item in selected:
        if not isinstance(item,dict):raise ValueError('PETEK_BULK_INVALID_ITEM')
        identity=(item.get('name'),item.get('uid'))
        if identity in seen:raise ValueError('PETEK_BULK_DUPLICATE_SELECTION')
        seen.add(identity)
    return body,selected


def _bulk_propose_one(registry,item,save_new):
    file=_photo(item.get('name'))
    if engine.digest(file)!=item.get('source_sha'):
        raise ValueError('PETEK_BULK_SOURCE_SHA_CHANGED')
    uid,sha=_identity(registry,file,item.get('uid'))
    if uid!=item.get('uid'):raise ValueError('PETEK_BULK_UID_CHANGED')
    # Read-only suggestions can examine unapproved DRAFT geometry, but only
    # NEW entries may be written. Old APPROVED/DRAFT profiles stay immutable.
    registered=(registry.profiles/(uid+'.json')).exists()
    if registered and save_new:
        raise ValueError('PETEK_BULK_EXISTING_PROFILE_NOT_OVERWRITTEN')
    if registered:
        previous,_=registry.get(uid,source_override=file)
        if previous['status']=='APPROVED':
            raise ValueError('PETEK_BULK_APPROVED_IMMUTABLE')
    scene=engine.read_bgr(file)
    suggestion=detect_magenta_quad(scene)
    mask,mask_qa=engine.auto_mask_candidate(scene,suggestion['quad'])
    safety=engine.mask_check(mask,scene,suggestion['quad'])
    result={'name':file.name,'uid':uid,'source_sha':sha,
            'quad':suggestion['quad'],'method':suggestion['method'],
            'coverage':suggestion['coverage'],
            'mask_status':'TASLAK','mask_fraction':safety['printable_fraction'],
            'saved':False}
    if save_new:
        # Source SHA is revalidated on save. No automatic human approval.
        profile=registry.save(uid,file,suggestion['quad'],mask,1.1163,
                              approved=False,curve_points={'top':[],'bottom':[]})
        result['saved']=True
        result['mask_sha']=profile['mask_sha']
        result['status']='DRAFT'
    return result


@petek_web.post('/api/petek/bulk-propose')
def bulk_propose():
    """Eight-at-a-time, unsaved PETEK MAGENTA quad + grille mask QA proposals."""
    try:
        _,selected=_bulk_selected()
        registry=Registry()
        successes=[];failed=[]
        for item in selected:
            try:successes.append(_bulk_propose_one(registry,item,False))
            except (ValueError,OSError,KeyError,TypeError,engine.MaskError,cv2.error) as exc:
                failed.append({'name':str(item.get('name') or '')[:180],
                               'uid':str(item.get('uid') or '')[:96],
                               'error':str(exc)[:200]})
        return jsonify({'success':True,'proposals':successes,'failed':failed,
                        'read_only':True,'human_approval_required':True})
    except (ValueError,OSError,TypeError,KeyError,engine.MaskError) as exc:return _fail(exc)


@petek_web.post('/api/petek/bulk-save-new-drafts')
def bulk_save_new_drafts():
    """Optional, explicit NEW-only write. Never APPROVE or overwrite any mask.

    Partial successes are reported individually; each registry.save is atomic.
    """
    try:
        body,selected=_bulk_selected()
        if body.get('confirm')!='CREATE_NEW_DRAFTS_ONLY_NO_APPROVAL':
            raise ValueError('PETEK_BULK_DRAFT_EXPLICIT_CONFIRM_REQUIRED')
        registry=Registry()
        successes=[];failed=[]
        for item in selected:
            try:successes.append(_bulk_propose_one(registry,item,True))
            except (ValueError,OSError,KeyError,TypeError,engine.MaskError,cv2.error) as exc:
                failed.append({'name':str(item.get('name') or '')[:180],
                               'uid':str(item.get('uid') or '')[:96],
                               'error':str(exc)[:200]})
        return jsonify({'success':True,'drafts':successes,'failed':failed,
                        'created_count':len(successes),
                        'approved_count':0,'human_approval_required':True})
    except (ValueError,OSError,TypeError,KeyError,engine.MaskError) as exc:return _fail(exc)


@petek_web.get('/api/petek/thumbnail/<path:name>')
def thumbnail(name):
    """Tiny lazy thumbnail for bulk PETEK selection; no full-size image delivery.

    Read only, 136px JPEG; never emit private mask/registry/source paths.
    """
    try:
        import io
        from PIL import Image,ImageOps,UnidentifiedImageError
        photo=_photo(name)
        with Image.open(photo) as original:
            original.draft('RGB',(136,136))
            original=ImageOps.exif_transpose(original)
            original.thumbnail((136,136),Image.Resampling.LANCZOS)
            output=io.BytesIO()
            original.convert('RGB').save(output,format='JPEG',quality=72,optimize=True)
        output.seek(0)
        response=send_file(output,mimetype='image/jpeg',download_name='petek-preview.jpg')
        response.cache_control.private=True
        response.cache_control.max_age=90
        return response
    except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError) as exc:
        return _fail(exc)


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
        uid,sha=_identity(r,file,request.args.get('uid'));scene=engine.read_bgr(file)
        row={'success':True,'name':file.name,'uid':uid,'source_sha':sha,
             'width':int(scene.shape[1]),'height':int(scene.shape[0]),
             'status':'NEW','quad':[],'mask':None,'base_mask':None,
             'curve_points':{'top':[],'bottom':[]},'physical_aspect':1.1163}
        if (r.profiles/(uid+'.json')).is_file():
            profile,mask=r.get(uid,source_override=file)
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

@petek_web.post('/api/petek/preview-artwork')
def preview_artwork():
    """Real PETEK V3 render, returned as a private unsaved PNG preview.

    Upload bytes exist only in request memory; does not create a file, mask,
    profile, approval, production artifact, or mutate the live workspace.
    """
    try:
        body,file,scene=_request_scene()
        if body.get('uid')!=_identity(Registry(),file,body.get('uid'))[0]:
            raise ValueError('PETEK_PREVIEW_UID_CHANGED_RELOAD')
        encoded=body.get('artwork_png')
        if not isinstance(encoded,str) or not encoded.startswith('data:image/png;base64,'):
            raise ValueError('PETEK_PREVIEW_PNG_REQUIRED')
        encoded=encoded.partition(',')[2]
        if len(encoded)>12_000_000:raise ValueError('PETEK_PREVIEW_ARTWORK_TOO_LARGE')
        try:raw=base64.b64decode(encoded,validate=True)
        except (ValueError,TypeError) as exc:raise ValueError('PETEK_PREVIEW_BAD_ARTWORK') from exc
        if not 0<len(raw)<=8_000_000:raise ValueError('PETEK_PREVIEW_ARTWORK_TOO_LARGE')
        art=cv2.imdecode(np.frombuffer(raw,dtype=np.uint8),cv2.IMREAD_COLOR)
        if (art is None or art.ndim!=3 or min(art.shape[:2])<100 or
                art.shape[0]*art.shape[1]>16_000_000):
            raise ValueError('PETEK_PREVIEW_ARTWORK_INVALID')
        quad=engine.validated_quad(body.get('quad'),scene.shape)
        mask=_decode(body.get('mask'),scene.shape)
        ratio=float(body.get('physical_aspect',1.1163))
        # Use the EXACT same PETEK cutout renderer and edge rule as new batch
        # production. The web preview is source-resolution; marketplace may
        # later place it on a 1200x1600 canvas or enable optical finish.
        edge_px=recommended_edge_feather(scene,quad)
        result,_,qa=render_with_cutout_paste(scene,art,quad,mask,ratio,
            marketplace=False,lighting='natural',placement='cover',
            edge_feather_px=edge_px)
        fringe=magenta_residue_report(scene,quad,mask)
        # The physical print protects all source pixels outside the mask.
        if not np.array_equal(result[mask==0],scene[mask==0]):
            raise ValueError('PETEK_PREVIEW_PROTECTED_PIXELS_CHANGED')
        ok,png=cv2.imencode('.png',result,[cv2.IMWRITE_PNG_COMPRESSION,3])
        if not ok:raise ValueError('PETEK_PREVIEW_ENCODING_FAILED')
        return jsonify({'success':True,'preview':'data:image/png;base64,'+
                        base64.b64encode(png.tobytes()).decode('ascii'),
                        'source_sha':engine.digest(file),'uid':body['uid'],
                        'unsaved':True,'protected_pixels_unchanged':True,
                        'mask_qa':{'printable_fraction':qa['printable_fraction'],
                            'edge_feather_px':edge_px,
                            'protected_magenta_pixels':fringe['protected_magenta_pixels'],
                            'vent_and_curve_pixels_untouched':True}})
    except (ValueError,OSError,TypeError,KeyError,OverflowError,engine.MaskError) as exc:return _fail(exc)

@petek_web.post('/api/petek/auto-corners')
def auto_corners():
    """Compute a source-SHA-bound PETEK MAGENTA four-corner suggestion only.

    Never write geometry or mask and never edit an APPROVED profile.
    """
    try:
        body,file,scene=_request_scene()
        uid,sha=_identity(Registry(),file,body.get('uid'))
        if uid!=body.get('uid'):
            raise ValueError('PETEK_UID_CHANGED_RELOAD')
        registered=Registry()
        if (registered.profiles/(uid+'.json')).is_file():
            previous,_=registered.get(uid,source_override=file)
            if previous['status']=='APPROVED':
                raise ValueError('APPROVED_PETEK_IMMUTABLE')
        proposal=detect_magenta_quad(scene)
        return jsonify({'success':True,'uid':uid,'source_sha':sha,**proposal})
    except (ValueError,OSError,TypeError,KeyError,engine.MaskError) as exc:return _fail(exc)

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
        r=Registry();uid,sha=_identity(r,file,body.get('uid'))
        if uid!=body.get('uid'):raise ValueError('PETEK_UID_CHANGED_RELOAD')
        if (r.profiles/(uid+'.json')).is_file():
            previous,_=r.get(uid,source_override=file)
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
        r=Registry();uid,sha=_identity(r,file,body.get('uid'))
        if uid!=body.get('uid') or sha!=body.get('confirmed_sha'):
            raise ValueError('PETEK_UID_OR_SHA_CHANGED_RELOAD')
        p=r.approve(uid,str(body.get('reviewer') or ''),str(body.get('confirm') or ''))
        return jsonify({'success':True,'uid':uid,'status':p['status'],
                        'mask_sha':p['mask_sha']})
    except (ValueError,OSError,TypeError,KeyError,engine.MaskError) as exc:return _fail(exc)

@petek_web.post('/api/petek/new-revision')
def new_revision():
    """Human-initiated copy of APPROVED mask to a fresh DRAFT (_r2 etc).

    Existing V3 immutable approved masks are NEVER overwritten. Revision
    carries source SHA, verified base mask, curves and geometry into new UID.
    """
    try:
        body,file,scene=_request_scene()
        r=Registry()
        uid,sha=_identity(r,file,body.get('uid'))
        old,mask=r.get(uid,require_approved=True,source_override=file)
        if body.get('confirmed_sha')!=sha:
            raise ValueError('PETEK_SOURCE_SHA_CONFIRM_REQUIRED')
        next_uid=''
        for num in range(2,100):
            candidate=uid[:70]+'_r'+str(num)
            if not (r.profiles/(candidate+'.json')).exists():
                next_uid=candidate
                break
        if not next_uid:raise ValueError('PETEK_REVISION_UID_EXHAUSTED')
        base=None
        if old.get('base_mask_sha'):
            base=engine.decode_mask(r.masks/(old['base_mask_sha']+'.png'))
            if engine.mask_hash(base)!=old['base_mask_sha']:
                raise ValueError('PETEK_BASE_MASK_SHA_INVALID')
        cloned=r.save(next_uid,file,old['quad'],mask,old['physical_aspect'],
                      approved=False,curve_points=old.get('curve_points'),base_mask=base)
        return jsonify({'success':True,'uid':next_uid,'status':'DRAFT',
                        'original_approved_uid':uid,'source_sha':sha,
                        'mask_sha':cloned['mask_sha']})
    except (ValueError,OSError,TypeError,KeyError,engine.MaskError) as exc:return _fail(exc)
