"""PETEK seventh-category Flask endpoints; reuse existing V3 mask registry.

Only the working Petek_Dolabi folder is exposed; private files, historic
originals and approved profiles are never overwritten. CSRF is handled by
the parent app's existing global guard.
"""
import base64
import re
from pathlib import Path
from functools import lru_cache
from time import perf_counter
import cv2
import numpy as np
from flask import Blueprint,current_app,jsonify,request,send_file
from MERKEZ.PETEK_V3 import engine,curves
from MERKEZ.PETEK_V3.magenta_quad_v479 import detect_magenta_quad
from MERKEZ.PETEK_V3.cutout_paste import render_with_cutout_paste
from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual
from MERKEZ.PETEK_V3.grille_guard_v482 import recommended_edge_feather,magenta_residue_report
from MERKEZ.PETEK_V3.petek_finish_v492 import draw_fifteen_slots, despill_lower_left_geometry_v493
from MERKEZ.PETEK_V3.final_cleanup_v495 import cleanup_petek_magenta
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
    # Atomic bytes snapshot: hash and JPEG/EXIF decoding MUST use the SAME
    # bytes; never report a newly changed file's hash for a previous raster.
    return payload,file,engine.read_bgr_snapshot(file,payload.get('source_sha'))

def _fail(exc):
    message=str(exc)[:240]
    code=message.split(':',1)[0]
    if any(k in code for k in ('SOURCE_CHANGED','UID_CHANGED','PROFILE_REVISION','SHA_MISMATCH')):
        http=409;severity='conflict';action='REFRESH_SOURCE_AND_REVISION'
    elif any(k in code for k in ('VENT_CONFLICT','GEOMETRY','IZGARA','SLOT','PROTECTED','PINK_CLEANUP','PINK_')):
        http=422;severity='review_required';action='INSPECT_MASK_AND_PHOTO'
    elif any(k in code for k in ('MISSING','UNAVAILABLE','DEPENDENCY')):
        http=503;severity='dependency';action='CHECK_LOCAL_COMPONENT'
    elif isinstance(exc, (ValueError,TypeError,KeyError)):
        http=400;severity='invalid_request';action='CHECK_INPUT'
    else:
        http=422 if isinstance(exc,engine.MaskError) else 500
        severity='review_required' if http==422 else 'internal_error'
        action='CHECK_MASK_OR_LOG' if http==422 else 'RESTART_AND_CHECK_LOG'
    return jsonify({'success':False,'error':message,'code':code,
                    'severity':severity,'action':action,
                    'preview_available':False,'production_allowed':False}),http

@lru_cache(maxsize=4096)
def _sidebar_digest(path, size, mtime_ns, ctime_ns, inode):
    """Only for non-authoritative list display. Save/approve/production rehash."""
    return engine.digest(Path(path))


def _sidebar_sha(file):
    stat=file.stat()
    if file.is_symlink():raise ValueError('PETEK_SIDEBAR_SYMLINK')
    return _sidebar_digest(str(file.resolve()),stat.st_size,stat.st_mtime_ns,
                           stat.st_ctime_ns,getattr(stat,'st_ino',0))


@petek_web.get('/api/petek/service-status')
def petek_service_status():
    """Read-only origin/version check for browser/client port ownership.

    No template, profile, mask, SQLite or job state is read or written here.
    Only the local loopback server's active source/workspace identity is shown.
    """
    return jsonify({'success':True,
        'contract':'PETEK_PREVIEW_API_VNEXT_JSON_20261101',
        'preview_ui_revision':'PETEK_REAL_ARTWORK_PREVIEW_V4112',
        'code_root':str(Path(__file__).resolve().parents[2]),
        'runtime_root':str(current_app.config.get('PETEK_WORKSPACE_V477','')),
        'preview_endpoint':'POST /api/petek/preview-artwork',
        'read_only':True})


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
                            'reviewed_batch_approval':True,
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
                'mask':_png_data(mask),'mask_sha':profile['mask_sha'],'physical_aspect':profile['physical_aspect'],
                'curve_points':profile.get('curve_points') or {'top':[],'bottom':[]},
                'revises_uid':profile.get('revises_uid'),'base_uid':profile.get('base_uid'),
                'is_current':r.is_current(uid)})
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
        # Web, Windows A/B and batch share the SAME render ordering/gradients.
        # Web editor has its own unsaved draft; it changes NO approved records.
        edge_px=recommended_edge_feather(scene,quad)
        profile=body.get('realism_profile','belirgin')
        if profile not in ('dogal','belirgin'):
            raise ValueError('PETEK_PREVIEW_LIGHTING_PROFILE_INVALID')
        material_effect=body.get('material_effect',True)
        if not isinstance(material_effect,bool):
            raise ValueError('PETEK_PREVIEW_MATERIAL_BOOLEAN_REQUIRED')
        lighting=('strong' if profile=='belirgin' else 'natural') if material_effect else 'off'
        cleanup=body.get('pink_cleanup',False)
        if not isinstance(cleanup,bool):
            raise ValueError('PETEK_PINK_CLEANUP_BOOLEAN_REQUIRED')
        slot_mode=body.get('fifteen_slot_strength','orta')
        if slot_mode not in ('off','hafif','orta','guclu'):
            raise ValueError('PETEK_SLOT_MODE_INVALID')
        is_ab=bool(body.get('fifteen_slot_ab',False))
        preview_extra={}
        if is_ab:
            result,base_qa=render_petek_visual(scene,art,quad,mask,ratio,
                placement='cover',lighting='off',material_effect=False,
                slot_mode='off',pink_cleanup=False)
            qa=base_qa['render_qa']
            after,after_qa=render_petek_visual(scene,art,quad,mask,ratio,
                placement='cover',lighting=lighting,material_effect=material_effect,
                slot_mode=slot_mode,pink_cleanup=cleanup)
            after_ok,after_png=cv2.imencode('.png',after,[cv2.IMWRITE_PNG_COMPRESSION,3])
            if not after_ok:raise ValueError('PETEK_15_PREVIEW_ENCODING_FAILED')
            preview_extra={'after':'data:image/png;base64,'+
                base64.b64encode(after_png.tobytes()).decode('ascii'),
                'slot_qa':after_qa['slot_qa'],'pink_qa':after_qa['pink_qa'],
                'pre_render_pink_qa':after_qa['pre_pink_qa'],
                'source_marker_fringe_qa':after_qa['fringe_qa'],
                'wall_shadow_qa':after_qa['wall_shadow_qa'],
                'effective_lighting':lighting,'material_effect':material_effect,
                'read_only':True}
        else:
            normal_slot_mode=body.get('preview_slot_mode',slot_mode)
            if normal_slot_mode not in ('off','hafif','orta','guclu'):
                raise ValueError('PETEK_PREVIEW_SLOT_MODE_INVALID')
            result,qa=render_petek_visual(scene,art,quad,mask,ratio,
                placement='cover',lighting=lighting,material_effect=material_effect,
                slot_mode=normal_slot_mode,pink_cleanup=cleanup)
            preview_extra={'slot_qa':qa['slot_qa'],'pink_qa':qa['pink_qa'],
                'source_marker_fringe_qa':qa['fringe_qa'],
                'wall_shadow_qa':qa['wall_shadow_qa'],
                'effective_lighting':lighting,'material_effect':material_effect}
            render_qa_for_protection=qa
            qa=qa['render_qa']
        # Evaluate the actual AFTER image: reporting the original source
        # marker count made successfully repaired seams look still broken.
        final_frame=after if is_ab else result
        source_fringe=magenta_residue_report(scene,quad,mask)
        fringe=magenta_residue_report(final_frame,quad,mask)
        # The renderer and HTTP endpoint independently verify that only
        # geometrically checked, narrow source-magenta fringe pixels may be
        # repaired outside the print mask; slots/curves remain unchanged.
        from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import verify_petek_source_protection
        protection_qa=verify_petek_source_protection(scene,result,mask,quad,
                       pink_cleanup=False if is_ab else cleanup,shadow_style='corner',
                       corner_side=(base_qa if is_ab else render_qa_for_protection)['corner_side'],
                       lighting='off' if is_ab else lighting,
                       material_effect=False if is_ab else material_effect)
        if is_ab:
            # BEFORE is untouched, but AFTER must satisfy identical verification.
            verify_petek_source_protection(scene,after,mask,quad,pink_cleanup=cleanup,
                  shadow_style='corner',corner_side=after_qa['corner_side'],
                  lighting=lighting,material_effect=material_effect)
        ok,png=cv2.imencode('.png',result,[cv2.IMWRITE_PNG_COMPRESSION,3])
        if not ok:raise ValueError('PETEK_PREVIEW_ENCODING_FAILED')
        return jsonify({'success':True,'preview':'data:image/png;base64,'+
                        base64.b64encode(png.tobytes()).decode('ascii'),
                        'source_sha':body['source_sha'],'uid':body['uid'],
                        'unsaved':True,'preview_available':True,
                        'production_allowed':False,
                        'quality_status':'PREVIEW_ONLY_REQUIRES_HUMAN_APPROVAL',
                        'render_plan_sha256': (after_qa if is_ab else render_qa_for_protection)['render_plan_sha256'],
                        'protected_pixels_unchanged':(protection_qa['authorized_marker_fringe_pixels']==0 and protection_qa['authorized_wall_shadow_pixels']==0),
                        'source_protection_qa':protection_qa,
                        'mask_qa':{'printable_fraction':qa['printable_fraction'],
                            'edge_feather_px':edge_px,
                            'protected_magenta_pixels':fringe['protected_magenta_pixels'],
                            'source_original_magenta_pixels':source_fringe['protected_magenta_pixels'],
                            'vent_and_curve_pixels_untouched':True},**preview_extra})
    except (ValueError,OSError,TypeError,KeyError,OverflowError,engine.MaskError) as exc:
        # A physically uncertain mask MUST NOT be painted. The read-only source
        # itself remains available for diagnostic inspection; never pretend it
        # is a completed print or silently fabricate missing slits.
        reason=str(exc)
        if ('PETEK_SOURCE_MASK_VENT_CONFLICT_REVIEW' in reason or
                'PETEK_IZGARA_KONUMU_BELIRSIZ' in reason or
                'PETEK_KAYNAK_IZGARA_ARALIKLARI_TUTARSIZ' in reason):
            if {'scene','body','art','mask','quad','ratio','lighting','material_effect','cleanup'}.issubset(locals()):
                # Do NOT replace the operator's artwork preview with a plain
                # magenta source photograph. Try an UNSAVED, strictly more
                # restrictive mask using photographed dark-vent evidence.
                try:
                    from MERKEZ.PETEK_V3.petek_render_contract_v1 import temporary_photo_protected_preview_mask
                    safe_mask,safe_mask_qa=temporary_photo_protected_preview_mask(scene,mask,quad)
                    candidate,candidate_qa=render_petek_visual(
                        scene,art,quad,safe_mask,ratio,placement='cover',
                        lighting=lighting,material_effect=material_effect,
                        slot_mode='off',pink_cleanup=cleanup)
                    # No automatic approval: the user's original mask has NOT
                    # passed physical QA, even when the preview looks good.
                    ok,png=cv2.imencode('.png',candidate,[cv2.IMWRITE_PNG_COMPRESSION,3])
                    if not ok:raise ValueError('PETEK_DIAGNOSTIC_PREVIEW_ENCODING_FAILED')
                    return jsonify({'success':True,
                        'preview':'data:image/png;base64,'+base64.b64encode(png.tobytes()).decode('ascii'),
                        'preview_available':True,'production_allowed':False,
                        'diagnostic_preview':True,'diagnostic_artwork_applied':True,
                        'diagnostic_mask_temporary':True,
                        'diagnostic_mask_qa':safe_mask_qa,
                        'code':'PETEK_SAFE_ARTWORK_DIAGNOSTIC_ONLY',
                        'detail':reason[:240],
                        'uid':body.get('uid'),'source_sha':body.get('source_sha'),
                        'unsaved':True,'quality_status':'DIAGNOSTIC_ARTWORK_NOT_APPROVED',
                        'render_plan_sha256':candidate_qa.get('render_plan_sha256')}),200
                except (ValueError,OSError,TypeError,KeyError,engine.MaskError) as safe_exc:
                    # A source-only diagnostic MUST NOT masquerade as actual
                    # printed artwork. The browser keeps the visible mask.
                    diagnostic_error=str(safe_exc)[:160]
                return jsonify({'success':True,
                         'preview_available':False,'production_allowed':False,
                         'diagnostic_preview':True,'diagnostic_artwork_applied':False,
                         'code':'PETEK_MASK_REVIEW_REQUIRED_NO_SAFE_PRINT',
                         'detail':reason[:240],
                         'diagnostic_detail':diagnostic_error,
                         'uid':body.get('uid'),'source_sha':body.get('source_sha'),
                         'unsaved':True,'quality_status':'DIAGNOSTIC_ONLY_NO_PRINT'}),200
        return _fail(exc)

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
    started=perf_counter()
    try:
        # Fast identity preflight: approval never uses source pixels to paint,
        # so do not decode the same large photo before Registry.approve.
        body=request.get_json(silent=True)
        if not isinstance(body,dict):raise ValueError('PETEK_JSON_REQUIRED')
        file=_photo(body.get('name'))
        uid=body.get('uid')
        if not isinstance(uid,str) or not re.fullmatch('[A-Za-z0-9_-]{1,96}',uid):
            raise ValueError('PETEK_SELECTED_UID_INVALID')
        sha=engine.digest(file)
        if sha!=body.get('source_sha') or sha!=body.get('confirmed_sha'):
            raise ValueError('PETEK_UID_OR_SHA_CHANGED_RELOAD')
        r=Registry()
        # This rechecks the real photo and SHA-bound immutable mask under the
        # exact UID. No profile-list shortcut can approve a wrong source.
        p=r.approve(uid,str(body.get('reviewer') or ''),str(body.get('confirm') or ''),source_override=file)
        changed=None
        if body.get('activate_revision') is True:
            parent=p.get('revises_uid')
            if not parent:raise ValueError('PETEK_REVISION_PARENT_REQUIRED')
            changed=r.activate_revision(parent,uid,
                  str(body.get('activate_confirm') or ''),source_override=file)
        duration_ms=round((perf_counter()-started)*1000,1)
        current_app.logger.info('PETEK_MASK_APPROVED uid=%s server_ms=%s',uid,duration_ms)
        return jsonify({'success':True,'uid':uid,'status':p['status'],
                        'mask_sha':p['mask_sha'],'active_revision':changed,
                        'approval_server_ms':duration_ms})
    except (ValueError,OSError,TypeError,KeyError,engine.MaskError) as exc:return _fail(exc)

# V4.9.8: manually inspected eight-at-a-time draft approval.
# A reviewer must positively acknowledge each independently previewed draft.
# A backend SHA / UID / mask lock is repeated immediately before every approval.
from threading import RLock
_PETEK_APPROVAL_LOCK=RLock()

def _approve_reviewed_draft(registry,item,reviewer):
    if item.get('reviewed') is not True:
        raise ValueError('PETEK_TOPLU_ONAY_GORSEL_INCELENMEDI')
    mask_sha=item.get('mask_sha')
    if not isinstance(mask_sha,str) or not re.fullmatch(r'[a-f0-9]{64}',mask_sha):
        raise ValueError('PETEK_TOPLU_ONAY_MASK_SHA_GEREKLI')
    file=_photo(item.get('name'))
    expected_sha=item.get('source_sha')
    if not isinstance(expected_sha,str) or engine.digest(file)!=expected_sha:
        raise ValueError('PETEK_TOPLU_ONAY_KAYNAK_DEGISTI')
    uid,sha=_identity(registry,file,item.get('uid'))
    if uid!=item.get('uid'):
        raise ValueError('PETEK_TOPLU_ONAY_UID_DEGISTI')
    # get() validates physical quad, mask SHA, source sha, and mask QA.
    profile,_=registry.get(uid,source_override=file)
    if profile['status']!='DRAFT':
        raise ValueError('PETEK_TOPLU_ONAY_YALNIZ_TASLAK')
    if profile['mask_sha']!=mask_sha:
        raise ValueError('PETEK_TOPLU_ONAY_MASK_DEGISTI_TEKRAR_INCELEYIN')
    if profile.get('source_sha')!=sha:
        raise ValueError('PETEK_TOPLU_ONAY_KAYNAK_DEGISTI')
    # Registry.approve cannot approve NEW/APPROVED. It rechecks the mask and
    # writes an atomic approved revision, never mutating source or mask bytes.
    approved=registry.approve(uid,reviewer,
          'I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR',source_override=file)
    return {'name':file.name,'uid':uid,'status':approved['status'],
            'mask_sha':approved['mask_sha']}

@petek_web.post('/api/petek/bulk-approve-reviewed')
def bulk_approve_reviewed():
    try:
        body,selected=_bulk_selected() # 1..8; reject dupes
        reviewer=str(body.get('reviewer') or '').strip()
        if not 1<=len(reviewer)<=80:
            raise ValueError('PETEK_TOPLU_ONAY_INCELEYEN_ADI_GEREKLI')
        if body.get('confirm')!='I_REVIEWED_EACH_PETEK_MASK_IN_THIS_BATCH':
            raise ValueError('PETEK_TOPLU_ONAY_INSAN_TEYIDI_GEREKLI')
        successes=[];failed=[]
        with _PETEK_APPROVAL_LOCK:
            registry=Registry()
            for item in selected:
                try:
                    successes.append(_approve_reviewed_draft(registry,item,reviewer))
                except (ValueError,OSError,KeyError,TypeError,engine.MaskError,cv2.error) as exc:
                    failed.append({'name':str(item.get('name') or '')[:180],
                        'uid':str(item.get('uid') or '')[:96], 'error':str(exc)[:200]})
        return jsonify({'success':True,'approved':successes,'failed':failed,
              'human_review_required':True,'auto_approve':False})
    except (ValueError,OSError,KeyError,TypeError,engine.MaskError) as exc:
        return _fail(exc)

@petek_web.post('/api/petek/bulk-approve-confirmed')
def bulk_approve_confirmed():
    """One user confirmation for the entire selection, processed in chunks.

    Server validates each DRAFT's source SHA, UID, mask SHA and physical mask;
    success/failure is per record and no existing APPROVED mask is overwritten.
    No checkbox or visual-review-flag from a client is trusted.
    """
    try:
        body,selected=_bulk_selected()  # internal 1..8 chunk, not user interaction
        reviewer=str(body.get('reviewer') or '').strip()
        if not 1<=len(reviewer)<=80:
            raise ValueError('PETEK_TOPLU_ONAY_INCELEYEN_ADI_GEREKLI')
        if body.get('confirm')!='I_APPROVE_ALL_VALID_PETEK_DRAFTS_IN_THIS_SELECTION':
            raise ValueError('PETEK_TOPLU_ONAY_TEK_INSAN_TEYIDI_GEREKLI')
        successes=[];failed=[]
        with _PETEK_APPROVAL_LOCK:
            registry=Registry()
            for item in selected:
                try:
                    file=_photo(item.get('name'))
                    if item.get('source_sha')!=engine.digest(file):
                        raise ValueError('PETEK_TOPLU_ONAY_KAYNAK_DEGISTI')
                    uid,sha=_identity(registry,file,item.get('uid'))
                    if uid!=item.get('uid'):
                        raise ValueError('PETEK_TOPLU_ONAY_UID_DEGISTI')
                    profile,_=registry.get(uid,source_override=file)
                    if profile.get('revises_uid'):
                        raise ValueError('Revizyon taslağı: tekil Güncel Onaylı Yap akışını kullanın')
                    if profile.get('status')!='DRAFT' or profile.get('source_sha')!=sha:
                        raise ValueError('PETEK_TOPLU_ONAY_YALNIZ_GECERLI_TASLAK')
                    successes.append(_approve_reviewed_draft(registry,{
                        'name':file.name,'uid':uid,'source_sha':sha,
                        'mask_sha':profile['mask_sha'],'reviewed':True},reviewer))
                except (ValueError,OSError,KeyError,TypeError,engine.MaskError,cv2.error) as exc:
                    failed.append({'name':str(item.get('name') or '')[:180],
                      'uid':str(item.get('uid') or '')[:96],'error':str(exc)[:200]})
        return jsonify({'success':True,'approved':successes,'failed':failed,
                        'total':len(selected),'user_bulk_confirmation':True})
    except (ValueError,OSError,KeyError,TypeError,engine.MaskError) as exc:
        return _fail(exc)

@petek_web.post('/api/petek/activate-approved-revision')
def activate_approved_revision():
    try:
        body,file,_=_request_scene()
        r=Registry();result=r.activate_revision(body.get('previous_uid'),body.get('uid'),
                       body.get('confirm'),source_override=file)
        return jsonify({'success':True,**result})
    except (ValueError,OSError,TypeError,KeyError,engine.MaskError) as exc:return _fail(exc)

@petek_web.post('/api/petek/restore-approved-revision')
def restore_approved_revision():
    try:
        body,file,_=_request_scene()
        r=Registry();result=r.restore_revision(body.get('base_uid'),body.get('uid'),
                 body.get('confirm'),source_override=file)
        return jsonify({'success':True,**result})
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
        r.link_draft_revision(uid,next_uid,source_override=file)
        return jsonify({'success':True,'uid':next_uid,'status':'DRAFT',
                        'original_approved_uid':uid,'source_sha':sha,
                        'mask_sha':cloned['mask_sha']})
    except (ValueError,OSError,TypeError,KeyError,engine.MaskError) as exc:return _fail(exc)
