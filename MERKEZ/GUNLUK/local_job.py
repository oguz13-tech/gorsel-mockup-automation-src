"""One real local render, then persistent reuse in a second Python process.

Uses the installed renderer, approval guard and StateManager. No cloud/Excel
completion is asserted: a local artifact is correctly left RENDERED.
"""
import importlib.util
import json
import math
from selection import compatible
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import traceback
from session_safety import atomic_json,digest,install_write_boundary


def execute(config,attempt):
    ART_SHA=config['artwork']['source_sha256']
    CATEGORY=config['selection']['category'];UID=config['selection']['uid'];REL=config['selection']['relative']
    temp=Path(config['temp']);output=Path(config['store']);code=Path(config['code']);runtime=temp/'RENDER_RUNTIME'
    tempfile.tempdir=str(temp)
    os.environ["TEMP"]=str(temp);os.environ["TMP"]=str(temp)
    install_write_boundary(temp,output)
    smoke_path=code/'scripts/epic3_six_template_smoke.py'
    spec=importlib.util.spec_from_file_location('p0_installed_smoke',smoke_path);smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)
    engine=smoke._load_renderer(runtime,code)
    if engine.RECIPE_VERSION!='v3_epic3_20261007_r12_fill_v1':raise RuntimeError('FILL_RECIPE_NOT_ACTIVE')
    import cv2
    import numpy as np
    from core.manual_production_guard import verify_approved_source
    from core.file_safety import copy_exclusive
    db=runtime/'SABLON_V2_MIMARI/ayarlar.db';conn=smoke._read_only_db(db)
    state=None
    try:
        rows=[dict(r) for r in conn.execute('SELECT * FROM template_profiles WHERE template_uid=? AND is_active=1',(UID,))]
        if len(rows)!=1:raise RuntimeError('EXPECTED_ONE_ACTIVE_APPROVED_PROFILE')
        row=rows[0]
        if row['review_status']!='APPROVED' or int(row['manually_verified'])!=1 or row['source_relative_path']!=REL or row['category']!=CATEGORY or row['orientation'] not in ('H','V') or row['has_occlusion']:
            raise RuntimeError('EXISTING_HUMAN_APPROVAL_ORIENTATION_OCCLUSION_GATE')
        nominal=float(row['nominal_aspect'])
        if not compatible(config['artwork']['width'],config['artwork']['height'],row):raise RuntimeError('APPROVED_ASPECT_GATE')
        source=runtime/'2_SABLON_HAVUZU'/REL
        if digest(source)!=row['source_asset_sha256']:raise RuntimeError('APPROVED_SOURCE_SHA_CHANGED')
        verify_approved_source(runtime,CATEGORY,source)
        if smoke._legacy_plan(conn,CATEGORY,source.name):raise RuntimeError('MANUAL_FOREGROUND_PLAN_REQUIRES_REVIEW')
        artwork=Path(config['artwork']['snapshot'])
        if digest(artwork)!=config['artwork']['snapshot_sha256']:raise RuntimeError('ARTWORK_SHA_CHANGED')
        import hashlib
        identity={'source_sha256':ART_SHA,'template_uid':UID,'template_sha256':row['source_asset_sha256'],
                  'surface_quad':json.loads(row['surface_quad']),'orientation':row['orientation'],
                  'nominal_aspect':nominal,'recipe':engine.RECIPE_VERSION,'local_profile':'DAILY_LOCAL_V1','preprocessing':'EXIF_TRANSPOSE_OPAQUE_RGB_V1','output_size':[1200,1600]}
        job_key=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        artifact_key='P0_LOCAL_'+job_key
        job_dir=output/'KAYITLAR'/job_key
        final=output/'GORSELLER'/CATEGORY/(ART_SHA[:12]+'__'+source.stem+'__'+job_key+'.jpg')
        meta_path=job_dir/'JOB.json'
        if attempt==0:
            return {'status':'INPUT_VALIDATED','template_uid':UID,'source_sha256':digest(source),'job_key':job_key,'render_calls':0}
        job_dir.mkdir(parents=True,exist_ok=True)
        final.parent.mkdir(parents=True,exist_ok=True)
        lock=job_dir/'JOB.lock'
        try:
            with lock.open('x',encoding='utf-8') as f:f.write(str(os.getpid()))
        except FileExistsError:raise RuntimeError('JOB_LOCK_EXISTS_RECOVERY_REQUIRED')
        state=engine.StateManager(db_path=job_dir/'STATE.db')
        prior=state.get_artifact(artifact_key)
        if prior:
            if not meta_path.is_file() or not final.is_file():raise RuntimeError('LOCAL_JOB_RECOVERY_REQUIRED_MISSING_OUTPUT_OR_MANIFEST')
            meta=json.loads(meta_path.read_text(encoding='utf-8'))
            if prior.get('status')!='RENDERED' or prior.get('local_output_path')!=str(final) or meta.get('job_key')!=job_key or meta.get('identity')!=identity or meta.get('output')!=str(final.relative_to(output)) or digest(final)!=meta.get('output_sha256'):
                raise RuntimeError('LOCAL_JOB_RECOVERY_REQUIRED_STATE_OR_SHA_MISMATCH')
            result={'status':'LOCAL_EXISTING_OUTPUT_REUSED','job_key':job_key,'artifact_key':artifact_key,
                    'render_calls':0,'output':str(final.relative_to(output)),'output_sha256':digest(final),
                    'mtime_ns':final.stat().st_mtime_ns,'local_state_status':'RENDERED','new_artifact_rows':0}
        else:
            if attempt!=1 or final.exists() or meta_path.exists():raise RuntimeError('LOCAL_OUTPUT_EXISTS_OR_RETRY_STATE_MISSING_NO_OVERWRITE')
            decoded=cv2.imdecode(np.fromfile(str(artwork),dtype=np.uint8),cv2.IMREAD_COLOR)
            if decoded is None or decoded.shape[:2]!=(config['artwork']['height'],config['artwork']['width']):raise RuntimeError('ARTWORK_DECODE_FAILED')
            prepared=engine.MockupRenderer.fit_artwork_fill(decoded,nominal)
            art=temp/'ARTWORK_PREPARED.png';ok,encoded=cv2.imencode('.png',prepared)
            if not ok:raise RuntimeError('PREPARED_ARTWORK_ENCODING_FAILED')
            art.write_bytes(encoded.tobytes())
            row.update(resolved_source=source,source_sha256_verified=digest(source))
            smoke.CATEGORY_UIDS[CATEGORY]=UID
            record=smoke._render_one(row,CATEGORY,engine,cv2,np,conn,temp,Path(config['backup_runtime']),prepared_artwork_path=art)
            if record.get('status')!='PASS':raise RuntimeError('REAL_RENDER_REJECTED:'+str(record))
            copy_exclusive(Path(record['output']),final)
            if digest(final)!=record['output_sha256']:raise RuntimeError('OUTPUT_EXPORT_SHA_MISMATCH')
            saved=state.save_render_artifact({'artifact_key':artifact_key,'sku':'LOCAL_RENDER_ONLY','source_identity':ART_SHA,
                'category':CATEGORY,'template_identity':UID+'_'+row['source_asset_sha256'],
                'local_output_path':str(final),'upload_url':'','status':'RENDERED'})
            if not saved:raise RuntimeError('LOCAL_STATE_WRITE_FAILED_OUTPUT_RETAINED')
            meta={'job_key':job_key,'identity':identity,'output_sha256':digest(final),'output':str(final.relative_to(output)),
                  'local_state_status':'RENDERED','full_commerce_completion':False}
            atomic_json(meta_path,meta)
            result={'status':'LOCAL_REAL_RENDER_PASS','job_key':job_key,'artifact_key':artifact_key,
                    'render_calls':1,'output':str(final.relative_to(output)),'output_sha256':digest(final),'mtime_ns':final.stat().st_mtime_ns,
                    'local_state_status':'RENDERED','new_artifact_rows':1,'dimensions':'1200x1600'}
        count=state.conn.execute('SELECT count(*) FROM render_artifacts').fetchone()[0]
        if count!=1:raise RuntimeError('LOCAL_STATE_UNEXPECTED_ARTIFACT_COUNT')
        result.update(template_uid=UID,artifact_rows=count,attempt=attempt,live_review_db_written=False,cloud_upload=False,excel_write=False,
                      full_factory_cli_executed=False,full_commerce_completion=False)
        if digest(db)!=config['review_copy_sha256']:raise RuntimeError('REVIEW_COPY_CHANGED')
        result.update(source_sha256=ART_SHA)
        lock.unlink()
        if lock.exists():raise RuntimeError('JOB_LOCK_RELEASE_FAILED')
        result['job_lock_released']=True
        return result
    finally:
        conn.close()
        if state is not None:state.conn.close()

if __name__=='__main__':
    config=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));attempt=int(sys.argv[2])
    try:report=execute(config,attempt)
    except BaseException as exc:report={'status':'BLOCKED_LOCAL_JOB','attempt':attempt,'error':str(exc),'traceback':traceback.format_exc()}
    atomic_json(Path(config['result_path']),report)
    print(report['status'],flush=True)
    sys.exit(0 if report['status'] in ('INPUT_VALIDATED','LOCAL_REAL_RENDER_PASS','LOCAL_EXISTING_OUTPUT_REUSED') else 2)
