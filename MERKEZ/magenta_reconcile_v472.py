"""Image-by-image Magenta Lab reconciliation (NEVER folder overwrite).

Default: read-only report with actual image dimensions, hashes and lab profile
evidence. Apply: exact report checksum, explicit operator phrase, live service
stopped, G3 DB snapshot and original-image rollback copies OUTSIDE OneDrive.
Only approved source-SHA-matched LAB human profiles may remain APPROVED;
otherwise records are put in REVIEW_REQUIRED with four corners retained.
Never writes ORIGINAL_ARCHIVE; never touches PETEK's separate mask registry.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import tempfile
import unicodedata
import uuid
from pathlib import PurePosixPath
from PIL import Image
from URETIM_V4.store_profiles_v47 import StoreProfiles
from URETIM_V4.final_guard_v44 import store_v4_root

CATEGORIES=('01_Wifi_Kutusu','02_Cam_Tablo_Dikey','02_Cam_Tablo_Yatay',
            '03_Ahsap_Tablo','04_Cam_Dograma','05_Ocak_Arkasi')
EXT={'.png','.jpg','.jpeg','.webp'}
CONFIRM='GÖRSELLERİ TEK TEK DEĞİŞTİR, ESKİLERİ YEDEKLE'
LAB=Path(r'C:\AI_WORK\GORSEL_REFERENCE_LAB_20261024\approved_chroma_test_20261026_latest_db\chroma_previews')
FIELDS=('source_asset_sha256','surface_quad','outer_quad','nominal_aspect',
        'orientation','component_confidences','geometry_type','has_occlusion',
        'review_status','manually_verified')
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as fh:
        for block in iter(lambda:fh.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def safe(path, *, file=True):
    p=Path(path)
    if p.is_symlink() or any(parent.is_symlink() for parent in p.parents if parent.exists()):
        raise ValueError('SYMLINK_BLOCKED: '+str(p))
    if file and not p.is_file():raise FileNotFoundError(str(p))
    return p
def namekey(path):
    return unicodedata.normalize('NFC',Path(path).stem).casefold()
def png_info(path):
    with Image.open(path) as img:
        img.verify()
    with Image.open(path) as img:
        w,h=img.size
        # Preview thumbnails would invalidate coordinates; only full size.
        return [int(w),int(h)]
def local_reports():
    root=Path(os.environ.get('LOCALAPPDATA') or Path.home())/'GorselMockup'/'UnifiedCenter'/'MAGENTA_RECONCILIATION'
    root.mkdir(parents=True,exist_ok=True)
    return root
def lab_profiles(root):
    # Only explicitly associated candidate DBs, no recursive DB discovery.
    candidates=[root.parent/'SABLON_V2_MIMARI'/'ayarlar.db',
                root.parent/'ayarlar.db',root.parent.parent/'ayarlar.db',
                root.parent.parent/'SABLON_V2_MIMARI'/'ayarlar.db']
    found={}
    for db in candidates:
        if not db.is_file() or db.is_symlink():continue
        with sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True) as c:
            c.row_factory=sqlite3.Row
            try:rows=c.execute('SELECT * FROM template_profiles WHERE is_active=1').fetchall()
            except sqlite3.Error:continue
            for rec in rows:
                row=dict(rec)
                if row.get('review_status')!='APPROVED' or int(row.get('manually_verified') or 0)!=1:continue
                cat=str(row.get('category') or '')
                rel=str(row.get('source_relative_path') or '').replace('\\','/')
                if cat in CATEGORIES and rel and row.get('source_asset_sha256'):
                    found.setdefault((cat,namekey(rel),str(row['source_asset_sha256'])),[]).append(
                        {k:row.get(k) for k in FIELDS}|{'template_uid':row.get('template_uid'),'db':str(db)})
    return found
def db_rows(db):
    with sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True) as c:
        c.row_factory=sqlite3.Row
        if c.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('MAIN_DB_INTEGRITY_FAILED')
        return [dict(r) for r in c.execute('SELECT * FROM template_profiles WHERE is_active=1')]
def analyze(workspace,lab=LAB):
    workspace=Path(workspace).resolve()
    lab=Path(lab).resolve()
    if not workspace.is_dir() or not lab.is_dir():raise FileNotFoundError('MAIN_ROOT_OR_MAGENTA_LAB_MISSING')
    if workspace==lab or workspace in lab.parents:raise ValueError('LAB_CANNOT_BE_INSIDE_WORKSPACE')
    db=safe(workspace/'SABLON_V2_MIMARI'/'ayarlar.db')
    profiles=db_rows(db)
    originals=lab_profiles(lab)
    # DB identities are durable; active photo variants or duplicate incoming
    # pixels must never become new independent template numbers.
    known_sha={}
    for profile in profiles:
        source_hash=str(profile.get('source_asset_sha256') or '').lower()
        uid=str(profile.get('template_uid') or '')
        if source_hash and uid:
            known_sha.setdefault(source_hash,set()).add(uid)
    by_id={}
    for p in profiles:
        cat=str(p.get('category') or '')
        rel=str(p.get('source_relative_path') or '').replace('\\','/')
        parts=PurePosixPath(rel).parts
        if cat in CATEGORIES and len(parts)==2 and parts[0]==cat and parts[1] not in ('.','..'):
            by_id.setdefault((cat,namekey(rel)),[]).append(p)
    files=[p for p in lab.rglob('*') if p.is_file() and p.suffix.lower() in EXT and not p.is_symlink()]
    jobs=[]
    for source in sorted(files):
        item={'source':str(source),'source_sha':sha(source),'name':source.name}
        try:
            dim=png_info(source)
            item['dimensions']=dim
            # NO fuzzy names: exact filename stem within its category.
            possibilities=[(cat,prof) for (cat,stem),records in by_id.items()
                           if stem==namekey(source) for prof in records]
            if len(possibilities)!=1:
                item['status']='AMBIGUOUS_OR_NOT_REGISTERED' if possibilities else 'NO_EXACT_PROFILE'
            else:
                cat,prof=possibilities[0]
                item['category']=cat;item['uid']=prof['template_uid']
                item['db_relative']=str(prof['source_relative_path'])
                item['relative']=item['db_relative'].replace('\\','/')
                dest=safe(workspace/'2_SABLON_HAVUZU'/item['relative'])
                item['destination']=str(dest)
                item['old_sha']=sha(dest);item['old_dimensions']=png_info(dest)
                item['old_approved']=prof.get('review_status')=='APPROVED'
                item['expected_db_sha']=prof.get('source_asset_sha256')
                variants=[str(p) for p in dest.parent.iterdir()
                          if p.is_file() and not p.is_symlink()
                          and p.suffix.lower() in EXT and namekey(p)==namekey(dest)
                          and p.resolve()!=dest.resolve()]
                item['active_same_stem_variants']=variants
                other_uids=known_sha.get(item['source_sha'].lower(),set())-{str(item['uid'])}
                if variants:
                    item['status']='ACTIVE_SAME_NAME_DIFFERENT_EXTENSION'
                elif other_uids:
                    item['status']='INCOMING_BYTES_ALREADY_USED_BY_ANOTHER_TEMPLATE'
                    item['colliding_uids']=sorted(other_uids)
                elif item['expected_db_sha']!=item['old_sha']:
                    item['status']='MAIN_SOURCE_SHA_CONFLICT'
                elif item['dimensions']!=item['old_dimensions']:
                    item['status']='DIMENSIONS_CHANGED_REVIEW_COORDINATES'
                elif item['source_sha']==item['old_sha']:
                    item['status']='ALREADY_IDENTICAL'
                else:
                    lab_match=[x for x in originals.get((cat,namekey(source),item['source_sha']),[])
                               if x.get('template_uid')==prof['template_uid']]
                                        # Human approval binds exact bytes. PNG->JPG conversion
                    # changes the SHA and MUST NOT preserve APPROVED status.
                    same_codec = (source.suffix.lower() == dest.suffix.lower()
                                  or {source.suffix.lower(),dest.suffix.lower()}=={'.jpg','.jpeg'})
                    proof=lab_match[0] if len(lab_match)==1 and same_codec else None
                    if proof:
                        try:
                            quad=json.loads(proof['surface_quad']) if isinstance(proof['surface_quad'],str) else proof['surface_quad']
                            if (len(quad)!=4 or any(len(pt)!=2 or not
                                  (0<=float(pt[0])<dim[0] and 0<=float(pt[1])<dim[1])
                                  for pt in quad)):
                                proof=None
                        except (ValueError,TypeError,KeyError):
                            proof=None
                    item['trusted_lab_approval']=proof is not None
                    item['lab_record']=proof
                    item['status']='READY_APPROVED_TRANSFER' if proof else 'READY_REQUIRES_REAPPROVAL'
        except (OSError,ValueError,sqlite3.Error) as exc:
            item['status']='ERROR'
            item['reason']=str(exc)
        jobs.append(item)
    # Different target names containing identical incoming bytes are NOT two
    # independent templates. Report and require a human identity decision.
    grouped_sha={}
    for item in jobs:
        if item.get('destination') and item.get('source_sha'):
            grouped_sha.setdefault(item['source_sha'],[]).append(item)
    for duplicate_group in grouped_sha.values():
        if len({j['destination'] for j in duplicate_group})>1:
            for item in duplicate_group:
                item['status']='DUPLICATE_CHROMA_BYTES_DIFFERENT_TEMPLATE'
                item.pop('lab_record',None)
                item['trusted_lab_approval']=False
    # Two LAB files must never replace the same target, even if in separate
    # preview subfolders; fail safely instead of last-writer-wins.
    destinations={}
    for item in jobs:
        target=item.get('destination')
        if target:
            destinations.setdefault(target,[]).append(item)
    for group in destinations.values():
        if len(group)>1:
            for item in group:
                item['status']='MULTIPLE_LAB_IMAGES_FOR_ONE_TEMPLATE'
                item.pop('lab_record',None)
                item['trusted_lab_approval']=False
    plan={'schema':1,'timestamp':datetime.now(timezone.utc).isoformat(),
          'workspace':str(workspace),'lab':str(lab),'db_sha':sha(db),
          'jobs':jobs,'rule':'EXACT_STEM_AND_CATEGORY_ONLY_ORIGINAL_ARCHIVE_IMMUTABLE'}
    return plan
def write_report(plan,folder=None):
    report=Path(folder or local_reports())/('MAGENTA_PLAN_'+uuid.uuid4().hex[:12]+'.json')
    report.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
def html_comparison(report):
    """Generate up to 240 side-by-side local thumbnails for human approval."""
    from PIL import ImageOps, ImageDraw
    folder=report.with_name(report.stem+'_PREVIEWS')
    folder.mkdir(exist_ok=True)
    plan=json.loads(report.read_text(encoding='utf-8'))
    rows=[]
    for index,item in enumerate(plan['jobs']):
        name=item['name']
        status=item.get('status')
        thumbs=[]
        for tag,file in (('LAB',item.get('source')),('ANA',item.get('destination'))):
            if file and Path(file).is_file() and index<240:
                try:
                    with Image.open(file) as img:
                        thumb=ImageOps.contain(ImageOps.exif_transpose(img).convert('RGB'),(240,200))
                        canvas=Image.new('RGB',(250,228),'#202936')
                        canvas.paste(thumb,((250-thumb.width)//2,5))
                        ImageDraw.Draw(canvas).text((8,207),tag,fill='white')
                        imagefile=f'{index:04d}_{tag}.jpg'
                        canvas.save(folder/imagefile,quality=82)
                        thumbs.append(f'<img src="{folder.name}/{imagefile}">')
                except (OSError,ValueError):
                    thumbs.append('(görsel açılamadı)')
        import html
        rows.append('<tr><td>'+str(index+1)+'</td><td>'+
                    html.escape(name)+'</td><td>'+
                    html.escape(str(status))+'</td><td>'+
                    ''.join(thumbs)+'</td></tr>')
    css='<style>body{font:14px Segoe UI,Arial;background:#121722;color:#e7eaf0;padding:24px}table{border-collapse:collapse;width:100%}td,th{padding:9px;border:1px solid #42495c;text-align:left}img{max-width:240px;vertical-align:top;margin:5px}h1{font-size:22px}</style>'
    page='<meta charset="utf-8">'+css+'<h1>Magenta ↔ Ana şablon / yalnız önizleme</h1><p>Fotoğraflar ve DB bu raporla değiştirilmedi. Önce isim, ölçü ve onayı inceleyin.</p><table><tr><th>#</th><th>Dosya</th><th>Durum</th><th>LAB / ANA</th></tr>'+''.join(rows)+'</table>'
    out=report.with_suffix('.html')
    out.write_text(page,encoding='utf-8')
    return out

def app_busy():
    try:
        with socket.create_connection(('127.0.0.1',8080),timeout=.4):return True
    except OSError:return False
def apply(report,confirmation,*,allow_review=False):
    if confirmation!=CONFIRM:raise PermissionError('EXPLICIT_MAGENTA_CONFIRMATION_REQUIRED')
    report=safe(report)
    planned=json.loads(report.read_text(encoding='utf-8'))
    if planned.get('schema')!=1:raise ValueError('UNKNOWN_PLAN')
    workspace=Path(planned['workspace']).resolve()
    if app_busy():raise RuntimeError('STOP_4_KOSE_FLASK_8080_FIRST')
    local=Path(os.environ.get('LOCALAPPDATA') or Path.home())/'GorselMockup'
    production_root=store_v4_root()
    if (production_root/'V4_ORTAK_FABRIKA.lock').exists():
        raise RuntimeError('ACTIVE_PRODUCTION_LOCK')
    fresh=analyze(workspace,Path(planned['lab']))
    if fresh['db_sha']!=planned['db_sha']:
        raise RuntimeError('MAIN_DB_CHANGED_AFTER_REPORT')
    old={x['source']:x for x in planned['jobs']}
    # Compare report SHA of every input + original; never trust stale preview.
    for job in fresh['jobs']:
        a=old.get(job['source'])
        if a is None or (a['status'],a['source_sha'],a.get('old_sha'))!=(
                job['status'],job['source_sha'],job.get('old_sha')):
            raise RuntimeError('SOURCE_OR_DESTINATION_CHANGED_AFTER_REPORT')
    allowed={'READY_APPROVED_TRANSFER'}
    if allow_review:allowed.add('READY_REQUIRES_REAPPROVAL')
    selected=[j for j in fresh['jobs'] if j['status'] in allowed]
    if not selected:return {'status':'NO_ELIGIBLE_IMAGES','count':0}
    # Immutable template UID is preserved; source SHA is the only changing
    # store-membership key. Preflight cross-store conflicts BEFORE any writes.
    stores=StoreProfiles(production_root)
    replacements=[{'category':j['category'],'uid':j['uid'],
                   'old_sha':j['old_sha'],'new_sha':j['source_sha']}
                  for j in selected]
    # Re-encoding other formats changes bytes. Store profiles need the ACTUAL
    # resulting SHA, not the source-file digest. Those files are intentionally
    # not auto-applied: keep review-only until one canonical format is selected.
    for j in selected:
        if Path(j['source']).suffix.lower()!=Path(j['destination']).suffix.lower():
            if {Path(j['source']).suffix.lower(),Path(j['destination']).suffix.lower()}!={'.jpg','.jpeg'}:
                raise RuntimeError('CODEC_CHANGED_REENCODING_NEEDS_CANONICAL_FILE_REVIEW: '+j['name'])
    store_plan=stores.preview_rekey(replacements)
    db=workspace/'SABLON_V2_MIMARI'/'ayarlar.db'
    backup_root=local/'GorselMockup-MagentaRollback'/('BEFORE_'+uuid.uuid4().hex)
    backup_root.mkdir(parents=True,exist_ok=False)
    backup_db=backup_root/'ayarlar.before.sqlite3'
    backup_store=backup_root/'store_profiles_v47.before.json'
    original_store_exists=stores.path.is_file()
    if original_store_exists:
        if stores.path.is_symlink():raise ValueError('STORE_PROFILE_SYMLINK')
        shutil.copy2(stores.path,backup_store)
        if sha(backup_store)!=sha(stores.path):
            raise RuntimeError('STORE_PROFILE_BACKUP_SHA_MISMATCH')
    with sqlite3.connect(db) as src,sqlite3.connect(backup_db) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('DB_BACKUP_BAD')
    saved=[]
    # This marker stays on disk in case of electricity loss between SQLite
    # commit and JSON store membership replacement. Never auto-delete backups.
    pending=backup_root/'INCOMPLETE_MAGENTA_APPLY.json'
    pending.write_text(json.dumps({
        'db':str(db),'db_backup':str(backup_db),
        'store':str(stores.path),'store_backup':str(backup_store) if original_store_exists else None,
        'selected':[{'destination':j['destination'],'old_sha':j['old_sha'],
                     'new_sha':j['source_sha']} for j in selected]},
        ensure_ascii=False,indent=2),encoding='utf-8')
    store_saved=False
    # Never touch user's immutable ORIGINAL_ARCHIVE; save old working images
    # separately with original per-file SHA evidence.
    try:
        for job in selected:
            destination=Path(job['destination'])
            old_copy=backup_root/'working'/job['relative']
            old_copy.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(destination,old_copy)
            if sha(old_copy)!=job['old_sha']:raise RuntimeError('ROLLBACK_COPY_SHA_MISMATCH')
            saved.append((destination,old_copy,job))
        with sqlite3.connect(db,timeout=30) as con:
            con.execute('BEGIN IMMEDIATE')
            for destination,old_copy,job in saved:
                src=Path(job['source'])
                if sha(src)!=job['source_sha'] or sha(destination)!=job['old_sha']:
                    raise RuntimeError('CHANGED_DURING_APPLY')
                staged=destination.with_name('.magenta-'+uuid.uuid4().hex+destination.suffix)
                try:
                    shutil.copyfile(src,staged)
                    if sha(staged)!=job['source_sha']:raise RuntimeError('STAGED_SHA_MISMATCH')
                    # Extension differs? Preserve target pathname and use decoded
                    # Pillow to encode to TARGET format, with hash recomputed.
                    if src.suffix.lower()!=destination.suffix.lower() and not (
                            {src.suffix.lower(),destination.suffix.lower()}=={'.jpg','.jpeg'}):
                        with Image.open(staged) as im:
                            converted=destination.with_name('.magenta-convert-'+uuid.uuid4().hex+destination.suffix)
                            im.save(converted)
                        staged.unlink(missing_ok=True);staged=converted
                    os.replace(staged,destination)
                finally:staged.unlink(missing_ok=True)
                new_sha=sha(destination)
                lab=job.get('lab_record')
                approved=bool(job['status']=='READY_APPROVED_TRANSFER' and lab)
                extra=('APPROVED',1) if approved else ('REVIEW_REQUIRED',0)
                update=con.execute(
                    '''UPDATE template_profiles
                       SET source_asset_sha256=?,review_status=?,manually_verified=?,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE category=? AND template_uid=? AND source_relative_path=?
                         AND source_asset_sha256=? AND is_active=1''',
                    (new_sha,*extra,job['category'],job['uid'],job['db_relative'],job['old_sha']))
                if update.rowcount!=1:raise RuntimeError('MAIN_PROFILE_CHANGED_OR_DUPLICATE')
                if approved and lab['surface_quad']:
                    # Geometry is transferred only if the lab DB shows a human
                    # verified approval for precisely the new full-res SHA+UID.
                    con.execute('''UPDATE template_profiles
                          SET surface_quad=?,outer_quad=?,nominal_aspect=?,
                              orientation=?,component_confidences=?
                          WHERE category=? AND template_uid=? AND is_active=1''',
                        (lab['surface_quad'],lab['outer_quad'],lab['nominal_aspect'],
                         lab['orientation'],lab['component_confidences'],
                         job['category'],job['uid']))
                job['applied_sha']=new_sha
                job['result']='APPROVED_TRANSFERRED' if approved else 'REVIEW_REQUIRED'
            con.commit()
        if store_plan['changed_count']:
            stores.save(store_plan['new'])
            store_saved=True
        result={'status':'APPLIED','count':len(saved),'backup':str(backup_root),
                'store_assignments_rekeyed':store_plan['changed_count'],
                'original_archive_changed':False,'items':[
                    {k:j[k] for k in ('relative','result','applied_sha')} for *_,j in saved]}
    except BaseException:
        # File + DB + store JSON do not share a filesystem transaction.
        # Undo every part if any step fails; retain original evidence even
        # when an OS/filesystem issue stops the rollback.
        for target,backup,_ in saved:
            try:
                rollback=target.with_name('.rollback-'+uuid.uuid4().hex+target.suffix)
                shutil.copyfile(backup,rollback)
                os.replace(rollback,target)
            except OSError:pass
        try:
            with sqlite3.connect(backup_db) as source_db, sqlite3.connect(db) as target_db:
                source_db.backup(target_db)
                if target_db.execute('PRAGMA quick_check').fetchone()[0]!='ok':
                    raise RuntimeError('MAIN_DB_RESTORE_VERIFY_FAILED')
        except (OSError,sqlite3.Error) as error:
            (backup_root/'DB_RESTORE_REQUIRED.txt').write_text(str(error),encoding='utf-8')
        if store_saved:
            try:
                if original_store_exists:
                    stores.path.write_bytes(backup_store.read_bytes())
                else:
                    stores.path.unlink(missing_ok=True)
            except OSError as error:
                (backup_root/'STORE_RESTORE_REQUIRED.txt').write_text(str(error),encoding='utf-8')
        raise
    pending.unlink(missing_ok=True)
    (backup_root/'APPLY_RECEIPT.json').write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--workspace',required=True)
    p.add_argument('--lab',default=str(LAB))
    p.add_argument('--apply-plan')
    p.add_argument('--confirm',default='')
    p.add_argument('--allow-review',action='store_true')
    a=p.parse_args()
    if a.apply_plan:
        result=apply(Path(a.apply_plan),a.confirm,allow_review=a.allow_review)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        report=write_report(analyze(Path(a.workspace),Path(a.lab)))
        html_page=html_comparison(report)
        print('MAGENTA_READ_ONLY_REPORT='+str(report))
        print('MAGENTA_SIDE_BY_SIDE_HTML='+str(html_page))
        print('No images or DB were modified.')
if __name__=='__main__':main()
