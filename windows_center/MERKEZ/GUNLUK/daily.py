"""Local daily production. Reads pinned live references; writes isolated local store."""
import contextlib
import datetime
import hashlib
import html
import io
import json
from selection import discover, compatible
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import uuid
import warnings
import zipfile
from session_safety import atomic_json,digest,verify_installed
import checks
from helpers import idle

HERE=Path(__file__).resolve().parent
CODE=Path('C:/AI_WORK/gorsel-mockup-automation-src')
BASE=Path('C:/AI_BACKUPS/GORSEL_MOCKUP/SELECT_VERIFIED_BACKUP')
STORE=Path('C:/AI_LOCAL_OUTPUTS/GorselMockup')
COMMIT='37831c73eaf04cc729628ea5cff3ba45bb9d44df'
SELECTION=json.loads((HERE/'BATCH_SELECTION.json').read_text(encoding='utf-8'))
SPEC=json.loads((HERE/'INSTALLED_NUMBER_SPEC.json').read_text(encoding='utf-8'))
EXTENSIONS={'.jpg','.jpeg','.png','.webp'}
MAX_PIXELS=40_000_000


def contains(a,b):
    a,b=Path(a).resolve(),Path(b).resolve()
    return a==b or a in b.parents


def validate_input_root(folder,forbidden):
    folder=Path(folder).absolute();checks.no_redirect(folder)
    if not folder.is_dir():raise RuntimeError('Tasarim klasoru bulunamadi.')
    if any(contains(folder,p) or contains(p,folder) for p in forbidden):
        raise RuntimeError('Tasarim icin program, canli veri, yedek veya sonuc klasorunden ayri bir klasor secin.')
    return folder


def inventory(folder,temp,cancel):
    """Immutable normalized snapshots; source files are never renamed/written."""
    from PIL import Image,ImageOps
    assets={};skipped=[];protected={}
    def walk_error(error):raise error
    for directory,dirs,names in os.walk(folder,followlinks=False,onerror=walk_error):
        for name in dirs:checks.no_redirect(Path(directory)/name)
        for name in sorted(names):
            if cancel.is_set():return list(assets.values()),skipped,protected
            path=Path(directory)/name
            if path.suffix.lower() not in EXTENSIONS:continue
            checks.no_redirect(path)
            try:
                if path.stat().st_size>100*1024**2:raise ValueError('Dosya 100 MB sinirini asiyor.')
                raw=path.read_bytes();source_sha=hashlib.sha256(raw).hexdigest();protected[str(path)]=source_sha
                if source_sha in assets:
                    assets[source_sha]['source_paths'].append(str(path));continue
                with warnings.catch_warnings():
                    warnings.simplefilter('error',Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(raw)) as original:
                        if getattr(original,'n_frames',1)!=1:raise ValueError('Hareketli/cok sayfali gorsel desteklenmiyor.')
                        if original.width*original.height>MAX_PIXELS:raise ValueError('Gorsel 40 megapiksel sinirini asiyor.')
                        im=ImageOps.exif_transpose(original);im.load()
                        if min(im.size)<256:raise ValueError('En kisa kenar en az 256 piksel olmali.')
                        if 'A' in im.getbands() or 'transparency' in im.info:
                            if im.convert('RGBA').getchannel('A').getextrema()!=(255,255):raise ValueError('Saydam tasarim: once opak JPG/PNG hazirlayin.')
                        rgb=im.convert('RGB');target=temp/'INPUTS'/(source_sha+'.png');target.parent.mkdir(parents=True,exist_ok=True)
                        with target.open('xb') as f:rgb.save(f,format='PNG')
                        assets[source_sha]={'source_sha256':source_sha,'snapshot_sha256':digest(target),'snapshot':str(target),
                            'width':rgb.width,'height':rgb.height,'source_paths':[str(path)]}
            except (OSError,ValueError,Image.DecompressionBombWarning,Image.DecompressionBombError) as exc:
                skipped.append({'source':str(path),'reason':str(exc)})
    return list(assets.values()),skipped,protected


class Production:
    def __init__(self,folder,categories,notify=lambda text:None,cancel=None):
        self.folder=Path(folder);self.categories=set(categories);self.notify=notify;self.cancel=cancel or threading.Event()
        self.selection=[x for x in SELECTION if x['category'] in self.categories]
        if not self.categories:raise RuntimeError('En az bir kategori secin.')
        self.store=STORE;self.code=CODE;self.base=BASE;self.output=None;self.temp=None;self.protected={};self.source=None;self.tree=None;self.lock_owned=False
        self.report={'version':'DAILY_LOCAL_V2','status':'PREPARING','base_commit':COMMIT,'results':[],'skipped':[],
            'live_review_db_written':False,'templates_modified':False,'original_archives_modified':False,
            'approved_geometry_modified':False,'live_json_written':False,'code_installed_or_modified':False,
            'old_job_engine_started':False,'watcher_started':False,'cloud_upload':False,'excel_write':False,
            'full_commerce_acceptance':False,'selection':self.selection}

    def save(self):
        if self.output:atomic_json(self.output/'GUNLUK_URETIM_SONUC.json',self.report)

    def verify(self):
        for name,expected in self.protected.items():
            if digest(name)!=expected:raise RuntimeError('Korunan dosya degisti: '+name)

    def acquire_store_lock(self):
        checks.no_redirect(self.store);self.store.mkdir(parents=True,exist_ok=True)
        for name in ('OTURUMLAR','GORSELLER','KAYITLAR'):checks.no_redirect(self.store/name)
        self.lock=self.store/'RUNNING.lock'
        try:
            with self.lock.open('x',encoding='utf-8') as f:json.dump({'pid':os.getpid(),'folder':str(self.folder)},f)
        except FileExistsError:raise RuntimeError('Baska uretim veya kesinti kaydi var: '+str(self.lock)+'. Silmeyin; raporu sohbete gonderin.')
        self.lock_owned=True

    def prepare(self):
        if os.name!='nt' or sys.version_info<(3,10):raise RuntimeError('Windows ve Python 3.10+ gerekli.')
        idle()
        runtime=Path(os.environ['USERPROFILE'])/'OneDrive'/'Masaüstü'/'GörselÜretme-ve-Mockup Otomasyonu'
        self.folder=validate_input_root(self.folder,[runtime,self.code,self.base.parent.parent,self.store,HERE])
        self.acquire_store_lock()
        self.output=self.store/'OTURUMLAR'/(datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:10]);self.output.mkdir(parents=True)
        self.save();self.source=self.base/'PR9_SOURCE'
        if checks.git(self.source,'rev-parse','HEAD').strip()!=COMMIT:raise RuntimeError('Sabit PR9 kaynak dogrulamasi basarisiz.')
        self.tree=checks.source_tree(self.source)
        self.report['verified_code_files']=verify_installed(self.code,self.source,self.tree,SPEC,checks)
        manifest={row['path']:row for row in json.loads((self.base/'RUNTIME_BACKUP_SHA256.json').read_text(encoding='utf-8'))}
        self.report['selection_policy']='FIXED_10_INCLUDING_WINDOWS_TESTED_VERTICAL_GLASS'
        rels=['SABLON_V2_MIMARI/ayarlar.db','ayarlar.json']
        for x in self.selection:rels.extend(pool+'/'+x['relative'] for pool in ('2_SABLON_HAVUZU','2_SABLON_HAVUZU_ORIJINAL_YEDEK'))
        rels.extend('2_SABLON_HAVUZU_ORIJINAL_YEDEK/01_Wifi_Kutusu/Wifi_Kutusu_'+n+'.png' for n in ('005','135','137','188'))
        for rel in rels:
            p=runtime/rel;checks.no_redirect(p)
            if rel not in manifest or digest(p).upper()!=manifest[rel]['source_sha256'].upper():
                raise RuntimeError('Canli dosya onayli yedekten farkli; otomatik yenilenmedi: '+rel)
            self.protected[str(p)]=digest(p)
        for tail in ('-wal','-journal'):
            p=runtime/('SABLON_V2_MIMARI/ayarlar.db'+tail)
            if p.exists() and p.stat().st_size:raise RuntimeError('Canli DB gunlugu bos degil. Program/paneller kapali olmali.')
        if shutil.disk_usage(self.store).free<1024**3:raise RuntimeError('C diskinde en az 1 GB bos alan gerekli.')
        self.temp=Path(tempfile.mkdtemp(prefix='mockup-daily-v2-')).resolve();self.backup=self.base/'RUNTIME_BACKUP'
        self.review=self.temp/'REVIEW.db';old_db=self.backup/'SABLON_V2_MIMARI/ayarlar.db'
        if digest(old_db).upper()!=manifest['SABLON_V2_MIMARI/ayarlar.db']['backup_sha256'].upper():raise RuntimeError('Dogrulanmis DB yedegi degisti.')
        shutil.copyfile(old_db,self.review);self.review_sha=digest(self.review)
        with contextlib.closing(sqlite3.connect(self.review.as_uri()+'?mode=ro',uri=True)) as conn:
            if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('DB kopyasi integrity kontrolu basarisiz.')
            profiles={}
            for x in self.selection:
                rows=conn.execute('SELECT orientation,nominal_aspect,review_status,manually_verified,is_active,has_occlusion,source_asset_sha256 FROM template_profiles WHERE template_uid=? AND is_active=1',(x['uid'],)).fetchall()
                if len(rows)!=1 or rows[0][0] not in ('H','V') or rows[0][2]!='APPROVED' or rows[0][3]!=1 or rows[0][4]!=1 or rows[0][5]:raise RuntimeError('Sablon insan onayi/yon kontrolunu gecemedi: '+x['uid'])
                profiles[x['uid']]={'nominal_aspect':float(rows[0][1]),'source_sha256':rows[0][6],'orientation':rows[0][0]}
        for x in self.selection:
            for pool in ('2_SABLON_HAVUZU','2_SABLON_HAVUZU_ORIJINAL_YEDEK'):
                p=self.backup/pool/x['relative'];checks.no_redirect(p)
                if digest(p)!=self.protected[str(runtime/pool/x['relative'])]:raise RuntimeError('Sablon yedegi farkli: '+x['uid'])
            if profiles[x['uid']]['source_sha256']!=self.protected[str(runtime/'2_SABLON_HAVUZU'/x['relative'])]:raise RuntimeError('Onayli kaynak SHA farkli.')
        self.profiles=profiles;self.report['protected_live_reference_count']=len(self.protected);self.report['status']='INPUT_SCAN';self.save()

    def child(self,asset,item,attempt):
        """Each process has fresh render TEMP; persistent job output is content keyed."""
        temp=Path(tempfile.mkdtemp(prefix='worker-',dir=self.temp)).resolve();runtime=temp/'RENDER_RUNTIME'
        copied=runtime/'SABLON_V2_MIMARI/ayarlar.db';copied.parent.mkdir(parents=True);shutil.copyfile(self.review,copied)
        src=self.backup/'2_SABLON_HAVUZU'/item['relative'];dest=runtime/'2_SABLON_HAVUZU'/item['relative'];dest.parent.mkdir(parents=True);shutil.copyfile(src,dest)
        report_path=self.output/('IS_'+uuid.uuid4().hex+'.json')
        config={'code':str(self.code),'store':str(self.store),'temp':str(temp),'backup_runtime':str(self.backup),
            'review_copy_sha256':self.review_sha,'selection':item,'artwork':asset,'result_path':str(report_path)}
        config_path=temp/'CONFIG.json';atomic_json(config_path,config)
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8')
        with report_path.with_suffix('.txt').open('x',encoding='utf-8') as log:
            p=subprocess.run([sys.executable,'-B',str(HERE/'local_job.py'),str(config_path),str(attempt)],cwd=self.code,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        if not report_path.is_file():raise RuntimeError('Islem raporu olusmadi: '+str(report_path))
        value=json.loads(report_path.read_text(encoding='utf-8'))
        if p.returncode:raise RuntimeError(str(value.get('error') or value['status']))
        if not value.get('job_lock_released') or (self.store/'KAYITLAR'/value['job_key']/'JOB.lock').exists():raise RuntimeError('JOB_LOCK_RELEASE_NOT_CONFIRMED')
        self.verify();return value

    def execute(self):
        self.notify('Kurulu kod, yedek ve canli referanslar dogrulaniyor...');self.prepare()
        self.notify('Tasarim klasoru okunuyor; orijinaller degistirilmiyor...')
        assets,skipped,inputs=inventory(self.folder,self.temp,self.cancel)
        self.input_hashes=inputs;self.report['skipped']=skipped;self.report['unique_designs']=len(assets);self.report['input_files']=len(inputs)
        planned=[]
        for asset in assets:
            for item in self.selection:
                nominal=self.profiles[item['uid']]['nominal_aspect'];aspect=asset['width']/asset['height']
                if not compatible(asset['width'],asset['height'],self.profiles[item['uid']]):
                    self.report['skipped'].append({'source_paths':asset['source_paths'],'template_uid':item['uid'],'reason':'Sablona yon/oran uygun degil; yuzde 15 siniri korundu.'});continue
                planned.append((asset,item))
        self.report['planned_jobs']=len(planned);self.save()
        for i,(asset,item) in enumerate(planned):
            if self.cancel.is_set():break
            self.notify(str(i+1)+' / '+str(len(planned))+' | '+Path(asset['source_paths'][0]).name+' | '+item['uid'])
            first=self.child(asset,item,1)
            current={'source_paths':asset['source_paths'],'template_uid':item['uid'],'first':first,'repeat':None}
            self.report['results'].append(current);self.save()
            repeat=self.child(asset,item,2)
            if repeat['status']!='LOCAL_EXISTING_OUTPUT_REUSED' or repeat['render_calls'] or repeat['new_artifact_rows']:raise RuntimeError('Tekrar koruma testi basarisiz.')
            for key in ('job_key','artifact_key','output_sha256','mtime_ns'):
                if first[key]!=repeat[key]:raise RuntimeError('Tekrarda dosya veya kimlik degisti: '+key)
            current['repeat']=repeat;self.save()
        self.verify()
        self.report['input_files_unchanged']=all(digest(name)==value for name,value in self.input_hashes.items())
        if not self.report['input_files_unchanged']:raise RuntimeError('Calisma sirasinda tasarim klasorundeki bir dosya degisti. Ciktilar sabit kopyadan uretildi.')
        self.report.update(new_renders=sum(r['first']['render_calls'] for r in self.report['results']),
            reused_outputs=sum(r['first']['render_calls']==0 for r in self.report['results']),repeat_render_calls=0,
            completed_jobs=len(self.report['results']),status='STOPPED_AFTER_CURRENT_JOB' if self.cancel.is_set() else ('LOCAL_RENDER_PASS_VISUAL_REVIEW_PENDING' if self.report['results'] else 'NO_COMPATIBLE_INPUT'))

    def finish(self):
        if not self.output:return
        self.verify()
        if self.report.get('verified_code_files'):verify_installed(self.code,self.source,self.tree,SPEC,checks)
        self.report['protected_live_reference_hashes_unchanged_at_close']=bool(self.protected)
        self.save();gallery=['<!doctype html><meta charset="utf-8"><title>Mockup sonuçları</title><style>body{font:16px Arial;background:#f3f5f7;padding:24px}main{display:flex;flex-wrap:wrap;gap:20px}article{background:white;padding:12px;width:280px}img{width:280px}a{color:#1265af}</style><h1>Yerel üretim sonuçları</h1><p>1200 × 1600 · Görsel kalite kontrolünüz bekleniyor.</p><main>']
        for r in self.report['results']:
            target=self.store/r['first']['output'];relative=os.path.relpath(target,self.output).replace(os.sep,'/')
            from urllib.parse import quote
            url=quote(relative,safe='/.:')
            gallery.append('<article><a href="'+url+'"><img src="'+url+'"></a><p>'+html.escape(Path(r['source_paths'][0]).name)+'</p><small>'+html.escape(r['template_uid'])+'</small></article>')
        gallery.append('</main>');(self.output/'SONUCLAR.html').write_text(''.join(gallery),encoding='utf-8')
        summary='Durum: '+self.report['status']+'\nTamamlanan is: '+str(self.report.get('completed_jobs',len(self.report['results'])))+'\nYeni uretim: '+str(self.report.get('new_renders',0))+'\nMevcut kullanilan: '+str(self.report.get('reused_outputs',0))+'\nAtlanan dosya: '+str(sum('template_uid' not in x for x in self.report['skipped']))+'\nUyumsuz tasarim-sablon eslesmesi: '+str(sum('template_uid' in x for x in self.report['skipped']))+'\nGorseller: '+str(self.store/'GORSELLER')+'\nCanli veri degistirilmez. Bulut/Excel kullanilmaz.\n'
        (self.output/'OZET.txt').write_text(summary,encoding='utf-8')
        bundle=self.output/'GUNLUK_V2_SONUCLARI.zip'
        with zipfile.ZipFile(bundle,'x',zipfile.ZIP_DEFLATED) as z:
            for p in self.output.iterdir():
                if p.is_file() and p.suffix.lower() in ('.json','.txt'):z.write(p,p.name)
            for r in self.report['results'][:12]:
                p=self.store/r['first']['output'];z.write(p,'GORSELLER/'+p.name)
        self.report['result_bundle']=str(bundle)

    def run(self):
        try:self.execute()
        except Exception as exc:
            import traceback
            self.report.update(status='BLOCKED_OR_INTERRUPTED_DAILY_RUN',error=str(exc),traceback=traceback.format_exc())
        finally:
            self.report.update(new_renders=sum(r['first']['render_calls'] for r in self.report['results']),
                reused_outputs=sum(r['first']['render_calls']==0 for r in self.report['results']),
                completed_jobs=sum(r['repeat'] is not None for r in self.report['results']))
            try:self.finish()
            except Exception as exc:
                self.report.update(status='REVIEW_REQUIRED_FINAL_CHECK',closing_error=str(exc));self.save()
            if self.lock_owned:
                try:self.lock.unlink()
                except OSError as exc:self.report['lock_release_error']=str(exc);self.save()
        return self.report,self.output
