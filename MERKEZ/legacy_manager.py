"""Safely bridge Tk desktop center to the installed six-category Flask editor.

This module never creates/changes a production DB or template. The user
explicitly opens the editor after an SQLite online backup is verified.
"""
from __future__ import annotations
import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import socket
import sys

ROOT=Path(__file__).resolve().parent.parent
EMBEDDED=ROOT/'LEGACY_REFERANS_KOD'
CATEGORIES=(
 '01_Wifi_Kutusu','02_Cam_Tablo_Dikey','02_Cam_Tablo_Yatay',
 '03_Ahsap_Tablo','04_Cam_Dograma','05_Ocak_Arkasi')

class LegacyLaunchError(RuntimeError):
    pass


def local_state_dir(env=None) -> Path:
    env=os.environ if env is None else env
    base=env.get('LOCALAPPDATA')
    return (Path(base) if base else Path.home()/'.gorsel_mockup')/'GorselMockup'/'UnifiedCenter'


def preferred_runtime(userprofile=None, env=None) -> Path:
    env=os.environ if env is None else env
    if env.get('MOCKUP_RUNTIME_WORKSPACE'):
        return Path(env['MOCKUP_RUNTIME_WORKSPACE']).expanduser().absolute()
    state=local_state_dir(env)/'workspace.json'
    if state.is_file():
        try:
            selected=Path(json.loads(state.read_text('utf-8'))['path']).expanduser().absolute()
            if (selected/'SABLON_V2_MIMARI'/'ayarlar.db').is_file():return selected
        except (ValueError, KeyError, OSError, TypeError):pass
    user=Path(userprofile or env.get('USERPROFILE') or Path.home())
    places=[user/'OneDrive'/'Masaüstü'/'GörselÜretme-ve-Mockup Otomasyonu',
        user/'OneDrive'/'Desktop'/'GörselÜretme-ve-Mockup Otomasyonu',
        user/'Desktop'/'GörselÜretme-ve-Mockup Otomasyonu']
    for loc in places:
        if (loc/'SABLON_V2_MIMARI'/'ayarlar.db').is_file():return loc
    return places[0]


def store_runtime_choice(folder:Path,env=None)->Path:
    folder=Path(folder).absolute()
    if not (folder/'SABLON_V2_MIMARI'/'ayarlar.db').is_file():
        raise LegacyLaunchError('Seçilen ana çalışma klasöründe SABLON_V2_MIMARI/ayarlar.db yok.')
    if folder.is_symlink():raise LegacyLaunchError('Sembolik bağlantı çalışma klasörü kullanılmıyor.')
    target=local_state_dir(env);target.mkdir(parents=True,exist_ok=True)
    data=json.dumps({'path':str(folder)},ensure_ascii=False).encode('utf-8')
    tmp=target/('workspace-'+os.urandom(6).hex()+'.tmp')
    try:
        with tmp.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,target/'workspace.json')
    finally:
        tmp.unlink(missing_ok=True)
    return folder


def preferred_code(env=None)->Path:
    env=os.environ if env is None else env
    candidates=[]
    if env.get('MOCKUP_LEGACY_SOURCE_ROOT'):
        candidates.append(Path(env['MOCKUP_LEGACY_SOURCE_ROOT']))
    # The released editor must load from THIS version's tested package.
    # Otherwise an older C:/AI_WORK checkout silently defeats Group 1 fixes.
    candidates.append(ROOT)
    candidates.append(Path('C:/AI_WORK/gorsel-mockup-automation-src'))
    candidates.append(EMBEDDED)
    for cand in candidates:
        if (cand/'SABLON_V2_MIMARI'/'app.py').is_file() and (cand/'SABLON_V2_MIMARI'/'core'/'db.py').is_file():
            return cand.absolute()
    return candidates[-1]


def inspect(runtime=None,code=None)->dict:
    runtime=Path(runtime or preferred_runtime()).absolute()
    code=Path(code or preferred_code()).absolute()
    db=runtime/'SABLON_V2_MIMARI'/'ayarlar.db'
    problems=[];warnings=[];counts={}
    if runtime.is_symlink() or not runtime.is_dir():problems.append('Ana çalışma klasörü bulunamadı: '+str(runtime))
    for rel,label in [('SABLON_V2_MIMARI/ayarlar.db','Onay/veritabanı'),
                      ('2_SABLON_HAVUZU','Çalışma şablon havuzu'),
                      ('2_SABLON_HAVUZU_ORIJINAL_YEDEK','Orijinal şablon yedeği')]:
        item=runtime/rel
        if not item.exists() or item.is_symlink():problems.append(f'{label} bulunamadı veya güvenli değil: {item}')
    if not (code/'SABLON_V2_MIMARI'/'app.py').is_file():problems.append('Şablon inceleme kaynak kodu yok: '+str(code))
    if db.is_file() and not db.is_symlink():
        try:
            connection=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True,timeout=8)
            with connection:
                check=connection.execute('PRAGMA quick_check(1)').fetchone()
                if not check or check[0]!='ok':problems.append('SQLite veritabanı bütünlük kontrolünü geçemedi.')
                tables={x[0] for x in connection.execute('SELECT name FROM sqlite_master WHERE type="table"')}
                for t in ('categories','templates','settings','template_profiles','jobs','template_operation_locks','template_number_registry','analysis_cache'):
                    if t not in tables:problems.append('SQLite tablo eksik: '+t)
                for t in ('categories','templates','template_profiles'):
                    if t in tables:
                        counts[t]=int(connection.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0])
                if 'template_profiles' in tables:
                    for idx in connection.execute('PRAGMA index_list(template_profiles)').fetchall():
                        if not int(idx[2] or 0):continue
                        idx_name=str(idx[1] or '')
                        escaped=idx_name.replace('\"','\"\"')
                        if [r[2] for r in connection.execute('PRAGMA index_info(\"'+escaped+'\")').fetchall()]==['template_uid']:
                            problems.append('Eski template_uid UNIQUE kısıtı var; güvenli şema göçü gerekiyor.')
                    cols={r[1] for r in connection.execute('PRAGMA table_info(template_profiles)')}
                    for field in ('nominal_aspect','is_active'):
                        if field not in cols:problems.append('SQLite profil sütunu eksik: '+field+'; otomatik migration yapılmaz.')
            connection.close()
        except (OSError,sqlite3.Error) as exc:problems.append('Veritabanı salt-okunur incelenemedi: '+str(exc))
    return {'ready':not problems,'runtime':str(runtime),'code':str(code),
            'database':str(db),'problems':problems,'warnings':warnings,'counts':counts,
            'source':'Kurulu güncel kod' if code!=EMBEDDED else 'Paket içi PR12 referans kodu'}


def backup_database(runtime:Path,env=None)->Path:
    """Consistent SQLite online backup, saved OUTSIDE OneDrive; unique & verified."""
    runtime=Path(runtime).absolute();db=runtime/'SABLON_V2_MIMARI'/'ayarlar.db'
    if not db.is_file() or db.is_symlink():raise LegacyLaunchError('Canlı ayarlar.db bulunamadı veya güvenli değil.')
    root=local_state_dir(env)/'DB_YEDEK';root.mkdir(parents=True,exist_ok=True)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    path=root/('ayarlar_SNAPSHOT_'+stamp+'_'+os.urandom(5).hex()+'.db')
    source=None;backup=None
    try:
        source=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True,timeout=10)
        backup=sqlite3.connect(str(path),timeout=10)
        source.backup(backup,pages=256,sleep=.05)
        backup.commit()
        test=backup.execute('PRAGMA quick_check(1)').fetchone()
        if not test or test[0]!='ok':raise LegacyLaunchError('SQLite yedek bütünlüğü doğrulanamadı.')
        backup.close();backup=None;source.close();source=None
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        receipt=path.with_suffix('.sha256')
        with receipt.open('x',encoding='ascii') as f:f.write(digest+'  '+path.name+'\n')
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        if backup is not None:backup.close()
        if source is not None:source.close()


def launch_spec(runtime=None,code=None,python=None)->tuple[list[str],dict,str]:
    state=inspect(runtime,code)
    if not state['ready']:
        raise LegacyLaunchError('Başlatma engellendi:\n'+'\n'.join(state['problems']))
    exe=python or sys.executable
    env=dict(os.environ,MOCKUP_RUNTIME_WORKSPACE=state['runtime'],MOCKUP_NO_AUTO_BROWSER='1',
             MOCKUP_FLASK_DEBUG='0',PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    cmd=[str(exe),'-B',str(Path(state['code'])/'SABLON_V2_MIMARI'/'app.py')]
    return cmd,env,state['code']


def port_occupied(host='127.0.0.1',port=8080,timeout=.3)->bool:
    with socket.socket() as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host,port))==0
