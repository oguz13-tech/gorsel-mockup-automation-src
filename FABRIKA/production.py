"""One production queue for existing six categories and source-preserving PETEK."""
import contextlib
import datetime
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import uuid
import zipfile

from . import petek_v3
from .queue_store import CATEGORIES,Store,export
from .safety import IntegrityError,ProcessLock,immutable,json_atomic,json_new,key,read_json,safe,separate,sha

HERE=Path(__file__).resolve().parent


def default_config():
    root=Path('C:/AI_LOCAL_OUTPUTS/GorselMockup') if os.name=='nt' else Path.home()/'GorselMockup'
    runtime=Path(os.environ.get('USERPROFILE',str(Path.home())))/'OneDrive'/'Masaüstü'/'GörselÜretme-ve-Mockup Otomasyonu'
    backups=Path('C:/AI_BACKUPS/GORSEL_MOCKUP')
    candidates=sorted((p for p in backups.glob('P0_*') if (p/'RUNTIME_BACKUP_SHA256.json').is_file() and (p/'PR9_SOURCE').is_dir()),reverse=True)
    return {'output':str(root/'FABRIKA_V3'),'legacy_store':str(root),
            'code': 'C:/AI_WORK/gorsel-mockup-automation-src','runtime':str(runtime),
            'backup':str(candidates[0]) if candidates else '', 'designs':'','categories':list(CATEGORIES),
            'profiles':[], 'legacy_templates':[], 'all_approved':False}


class LegacyAdapter:
    """Use established renderer, exact source approvals, and original artifact identities."""
    def __init__(self, config, notify):
        sys.path.insert(0,str(HERE/'legacy'))
        import daily
        os.environ['MOCKUP_RUNTIME_ROOT']=config['runtime']
        self.production=daily.Production(config['designs'],[c for c in config['categories'] if c!='06_Petek_Dolabi'],notify=notify)
        p=self.production;p.code=safe(config['code']);p.base=safe(config['backup']);p.store=safe(config['legacy_store'])
        if config.get('legacy_templates'):
            p.selection=[x for x in p.selection if x['uid'] in config['legacy_templates']]
        if not p.selection:raise ValueError('Eski kategoriler için şablon seçilmedi.')

    def prepare(self, all_approved=False):
        p=self.production;p.prepare()
        if all_approved:
            from selection import discover
            manifest={r['path']:r for r in read_json(p.base/'RUNTIME_BACKUP_SHA256.json')}
            selected,audit=discover(p.review,p.categories,set(),safe(os.environ['MOCKUP_RUNTIME_ROOT']),p.backup,manifest,limit=None)
            p.report['expanded_selection_audit']=audit
            p.selection=selected
            if not selected:raise ValueError('Yedek ve insan onayı koşullarını karşılayan şablon bulunamadı.')
            import sqlite3
            with contextlib.closing(sqlite3.connect(p.review.as_uri()+'?mode=ro',uri=True)) as c:
                for x in selected:
                    r=c.execute('SELECT nominal_aspect,source_asset_sha256,orientation FROM template_profiles WHERE template_uid=? AND is_active=1',(x['uid'],)).fetchone()
                    p.profiles[x['uid']]={'nominal_aspect':float(r[0]),'source_sha256':r[1],'orientation':r[2]}
                    for pool in ('2_SABLON_HAVUZU','2_SABLON_HAVUZU_ORIJINAL_YEDEK'):
                        source=safe(os.environ['MOCKUP_RUNTIME_ROOT'])/pool/x['relative'];p.protected[str(source)]=sha(source)
        return p.selection

    def render(self, asset, item):
        p=self.production
        before=p.child(asset,item,1);after=p.child(asset,item,2)
        if before['output_sha256']!=after['output_sha256'] or before['mtime_ns']!=after['mtime_ns'] or after['render_calls']!=0:
            raise IntegrityError('Eski kategori tekrar koruması başarısız.')
        return p.store/before['output'],{'legacy_job_key':before['job_key'],'repeat_verified':True,'new_render':bool(before['render_calls'])}

    def close(self):
        p=self.production
        try:p.verify()
        finally:
            if p.lock_owned:p.lock.unlink();p.lock_owned=False
            if p.temp and p.temp.exists():shutil.rmtree(p.temp)


def scan_designs(folder, snapshots):
    """Stable content snapshots plus explicit skips. Never follows links or renames input."""
    assets={}; skipped=[]
    for directory,dirs,files in os.walk(safe(folder),followlinks=False):
        for name in dirs:safe(Path(directory)/name)
        for name in sorted(files):
            p=safe(Path(directory)/name)
            if p.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):continue
            try:
                digest=sha(p)
                if digest in assets:assets[digest]['source_paths'].append(str(p));continue
                array=petek_v3.image(p)
                if min(array.shape[:2])<256:raise ValueError('Tasarımın kısa kenarı en az 256 piksel olmalı.')
                if sha(p)!=digest:raise IntegrityError('Tasarım okuma sırasında değişti.')
                target=snapshots/(digest+'.png');immutable(target,petek_v3.png(array))
                assets[digest]={'source_sha256':digest,'snapshot_sha256':sha(target),'snapshot':str(target),
                               'source_paths':[str(p)],'width':array.shape[1],'height':array.shape[0]}
            except IntegrityError:raise
            except Exception as exc:skipped.append({'source':str(p),'reason':str(exc)})
    return list(assets.values()),skipped


class Production:
    def __init__(self, config, notify=print, control=None):
        self.config=config;self.notify=notify;self.control=control

    def command(self):
        return read_json(self.control).get('command','run') if self.control and Path(self.control).exists() else 'run'

    def wait(self):
        while self.command()=='pause':
            self.notify('Duraklatıldı. Devam et düğmesini kullanabilirsiniz.');time.sleep(.5)
        return self.command()!='cancel'

    def run(self):
        c=self.config; root=safe(c['output']);designs=safe(c['designs'])
        if not designs.is_dir():raise ValueError('Tasarım klasörü bulunamadı.')
        for p in (root,HERE,safe(c['code']),safe(c['runtime'])):
            separate(designs,p)
        if c.get('backup'):separate(designs,safe(c['backup']))
        separate(root,HERE);separate(root,safe(c['runtime']));separate(root,safe(c['code']))
        if c.get('backup'):separate(root,safe(c['backup']))
        if not c.get('categories') or set(c['categories'])-set(CATEGORIES):raise ValueError('Geçerli kategori seçin.')
        root.mkdir(parents=True,exist_ok=True)
        session=root/'OTURUMLAR'/(datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]);session.mkdir(parents=True)
        report={'version':3,'status':'PREPARING','rendered':0,'reused':0,'failed':[], 'skipped':[], 'jobs':[],
                'cloud_upload':False,'marketplace_upload':False,'live_data_written':False,'human_visual_acceptance':'PENDING'}
        legacy=None;store=None
        def save():json_atomic(session/'RUN_REPORT.json',report)
        with ProcessLock(root/'PRODUCTION.lock'):
            try:
                store=Store(root);save()
                if any(k!='06_Petek_Dolabi' for k in c['categories']):
                    self.notify('Mevcut altı kategori: kurulu kod, onaylı yedek ve geometri doğrulanıyor.')
                    legacy=LegacyAdapter(c,self.notify);legacy.prepare(c.get('all_approved',False))
                    report['legacy_selection']=legacy.production.selection
                    report['legacy_selection_audit']=legacy.production.report.get('expanded_selection_audit',{})
                assets,report['skipped']=scan_designs(designs,root/'INPUT_SNAPSHOTS')
                planned=[];profiles=[]
                if '06_Petek_Dolabi' in c['categories']:
                    for name in c.get('profiles',[]):
                        try:
                            profile,_,_=petek_v3.load_profile(name)
                            for protected in (name,profile['source']):
                                separate(root/'GORSELLER',protected)
                            profiles.append((name,profile))
                        except IntegrityError:raise
                        except Exception as exc:report['failed'].append({'template':name,'reason':str(exc),'review_required':True})
                    if not profiles:report['skipped'].append({'category':'06_Petek_Dolabi','reason':'İnsan onaylı V3 maske bulunamadı; Şablon inceleme bölümünden ekleyin.'})
                for asset in assets:
                    if legacy:
                        from selection import compatible
                        for item in legacy.production.selection:
                            profile=legacy.production.profiles[item['uid']]
                            if not compatible(asset['width'],asset['height'],profile):
                                report['skipped'].append({'source':asset['source_paths'][0],'template':item['uid'],'reason':'Yön/oran onayıyla uyumsuz; %15 sınırı.'});continue
                            # Legacy worker computes/validates complete geometry-bound render key.
                            identity={'art':asset['source_sha256'],'template':item['uid'],'sha':profile['source_sha256'],
                                      'review_db':legacy.production.review_sha,'recipe':'legacy-fill-v1-queue-v3'}
                            product=store.product(item['category'],asset['source_sha256'],Path(asset['source_paths'][0]).stem)
                            payload={'route':'legacy','asset':asset,'item':item}
                            planned.append(store.enqueue(identity,product,payload))
                    for path,profile in profiles:
                        product=store.product('06_Petek_Dolabi',asset['source_sha256'],Path(asset['source_paths'][0]).stem)
                        identity={'art':asset['source_sha256'],'profile':profile['profile_key'],'recipe':petek_v3.RECIPE,'size':petek_v3.SIZE}
                        planned.append(store.enqueue(identity,product,{'route':'petek','asset':asset,'profile':str(path)}))
                planned=list(dict.fromkeys(planned));report['planned']=len(planned);report['unique_designs']=len(assets)
                if len(planned)>5000:raise ValueError('Tek seferde en fazla 5000 eşleşme desteklenir; daha küçük bir tasarım klasörü seçin.')
                report['status']='RUNNING';save()
                for index,job in enumerate(planned):
                    if not self.wait():report['status']='CANCELLED_SAFELY';break
                    row=store.row(job);payload=json.loads(row['payload']);asset=payload['asset']
                    self.notify(f'{index+1}/{len(planned)} | {Path(asset["source_paths"][0]).name} | {payload["route"]}')
                    try:
                        if sha(asset['snapshot'])!=asset['snapshot_sha256'] or any(sha(p)!=asset['source_sha256'] for p in asset['source_paths']):
                            raise IntegrityError('Tasarım veya çalışma kopyası değişti.')
                        prior=store.reuse(job)
                        if prior:
                            # Re-verify image even after a crash between render and verification.
                            store.rendered(job,prior['output'],json.loads(prior['quality']));report['reused']+=1
                        else:
                            store.status(job,'RUNNING',attempts=row['attempts']+1,error='')
                            if payload['route']=='petek':
                                profile,scene,mask=petek_v3.load_profile(payload['profile'])
                                result,quality=petek_v3.render(petek_v3.image(asset['snapshot']),scene,mask,profile['quad'],profile.get('aspect'))
                                if quality['protected_pixel_max_difference']!=0:raise IntegrityError('Orijinal detay koruma testi başarısız.')
                                target=root/'GORSELLER'/'06_Petek_Dolabi'/('PETEK_'+job+'.png')
                                immutable(target,petek_v3.png(result))
                                petek_v3.load_profile(payload['profile'])
                            else:
                                target,quality=legacy.render(asset,payload['item'])
                            if any(sha(p)!=asset['source_sha256'] for p in asset['source_paths']):raise IntegrityError('Kaynak üretim sırasında değişti.')
                            store.rendered(job,target,quality);report['rendered']+=int(quality.get('new_render',True));report['reused']+=int(not quality.get('new_render',True))
                        report['jobs'].append(job)
                    except IntegrityError:raise
                    except Exception as exc:
                        store.status(job,'FAILED',error=str(exc));report['failed'].append({'job':job,'reason':str(exc),'review_required':True})
                        # Legacy child reports integrity failures as RuntimeError: stop its batch.
                        if payload['route']=='legacy':raise IntegrityError('Eski motor güvenli şekilde durdu: '+str(exc)) from exc
                    save()
                if legacy:legacy.production.verify()
                report['export']=export(store,report['jobs'])
                if report['status']!='CANCELLED_SAFELY':
                    report['status']='LOCAL_COMPLETED_VISUAL_REVIEW_PENDING' if report['jobs'] and not report['failed'] else 'REVIEW_REQUIRED'
                report['completed']=len(report['jobs']);save()
            except Exception as exc:
                report.update(status='BLOCKED',error=str(exc));save()
            finally:
                if legacy:
                    try:legacy.close();report['legacy_sources_unchanged']=True
                    except Exception as exc:report.update(status='BLOCKED',closing_error=str(exc))
                save()
                if store:
                    rows=store.records(report['jobs'])
                    gallery=['<!doctype html><meta charset="utf-8"><title>Üretim sonuçları</title><h1>Görsel incelemesi bekleniyor</h1>']
                    for r in rows:
                        from urllib.parse import quote
                        url=quote(os.path.relpath(r['output'],session).replace(os.sep,'/'),safe='/.:')
                        gallery.append('<div style="display:inline-block;margin:12px"><a href="'+url+'"><img width="240" src="'+url+'"></a><p>'+html.escape(r['sku'])+'</p></div>')
                    immutable(session/'SONUCLAR.html',''.join(gallery).encode())
                    with zipfile.ZipFile(session/'SONUCLAR.zip','x',zipfile.ZIP_DEFLATED) as z:
                        z.write(session/'RUN_REPORT.json','RUN_REPORT.json')
                        for r in rows[:6]:z.write(r['output'],'GORSELLER/'+Path(r['output']).name)
                self.notify('RAPOR: '+str(session/'RUN_REPORT.json'))
        return report,session


def main():
    config=read_json(sys.argv[1]);control=sys.argv[2] if len(sys.argv)>2 else None
    # Runtime has no external upload operation. Explicit network denial also covers dependencies.
    def offline(event,args):
        if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('Üretim sırasında ağ bağlantısı kapalı.')
    sys.addaudithook(offline)
    report,_=Production(config,lambda text:print(text,flush=True),control).run()
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if report['status'] in ('LOCAL_COMPLETED_VISUAL_REVIEW_PENDING','CANCELLED_SAFELY','REVIEW_REQUIRED') else 2

if __name__=='__main__':sys.exit(main())
