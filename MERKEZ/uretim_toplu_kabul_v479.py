"""One-click, read-only Windows production readiness report for all seven categories.

NO writes to the user's working directory, SQLite, template assets, private mask
registry or production ledger. Only the dated text report is written OUTSIDE
OneDrive in LOCALAPPDATA/GorselMockup/TopluKabul.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.request
import urllib.error

from legacy_manager import preferred_runtime
from petek_folders_v46 import SECTIONS, petek_directory

CATEGORIES=('01_Wifi_Kutusu','02_Cam_Tablo_Dikey','02_Cam_Tablo_Yatay',
            '03_Ahsap_Tablo','04_Cam_Dograma','05_Ocak_Arkasi')
SUFFIXES={'.png','.jpg','.jpeg','.webp'}


def run(root=None,registry_root=None,probe=None):
    workspace=Path(root if root is not None else preferred_runtime())
    local=Path(os.environ.get('LOCALAPPDATA') or (Path.home()/'AppData'/'Local'))
    private=Path(registry_root) if registry_root is not None else local/'GorselMockup'/'PetekV3'
    lines=['GORSEL URETIM MERKEZI — 7 KATEGORI TEK TOPLU KABUL',
           'Yalniz salt-okunur kontrol; onay, maske, fotoğraf, SQLite veya ciktida degisiklik YOK.',
           'Calisma klasoru: '+str(workspace),'']
    report={'workspace':str(workspace),'results':{},'warnings':[]}
    def status(key,ok,note):
        report['results'][key]={'ok':ok,'detail':str(note)}
        lines.append(('PASS' if ok else 'INCELE')+' | '+key+' | '+str(note))
    exists=workspace.is_dir() and not workspace.is_symlink()
    status('Ana calisma klasoru',exists,str(workspace))
    db=workspace/'SABLON_V2_MIMARI'/'ayarlar.db'
    if db.is_file() and not db.is_symlink():
        try:
            connection=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
            try:
                ok=connection.execute('PRAGMA quick_check(1)').fetchone()[0]=='ok'
            finally:connection.close()
            status('SQLite quick_check',ok,'ayarlar.db (salt-okunur)')
        except (OSError,sqlite3.DatabaseError,ValueError) as exc:
            status('SQLite quick_check',False,type(exc).__name__+': '+str(exc)[:150])
    else:status('SQLite quick_check',False,'ayarlar.db yok veya symlink')
    for category in CATEGORIES:
        folder=workspace/'2_SABLON_HAVUZU'/category
        images=sorted(p for p in folder.iterdir() if p.is_file() and not p.is_symlink() and p.suffix.lower() in SUFFIXES) if folder.is_dir() and not folder.is_symlink() else []
        status(category,folder.is_dir() and not folder.is_symlink(),
               str(len(images))+' fiziksel fotoğraf / '+str(folder))
    for section in SECTIONS:
        try:
            folder=petek_directory(workspace,section)
            status('PETEK '+section,folder.is_dir(),
                   str(folder))
        except (OSError,ValueError) as exc:
            status('PETEK '+section,False,str(exc)[:200])
    try:
        working=petek_directory(workspace,'2_SABLON_HAVUZU')
        photos=[p for p in working.iterdir() if p.is_file() and not p.is_symlink() and p.suffix.lower() in SUFFIXES] if working.is_dir() else []
        sources={}
        for file in photos:
            try:
                if file.stat().st_size>80_000_000:
                    report['warnings'].append('Fazla buyuk PETEK fotoğrafı: '+file.name)
                    continue
                with file.open('rb') as f:
                    sha=hashlib.file_digest(f,'sha256').hexdigest()
                sources.setdefault(sha,[]).append(file.name)
            except OSError as exc:
                report['warnings'].append(file.name+': '+str(exc)[:100])
        approved=0;draft=0;matched=0;unmatched=[]
        profiles=private/'profiles'
        for path in sorted(profiles.glob('*.json')) if profiles.is_dir() else []:
            if not path.is_file() or path.is_symlink():continue
            try:
                row=json.loads(path.read_text(encoding='utf-8'))
                if row.get('status')=='APPROVED':
                    approved+=1
                    if row.get('source_sha') in sources:matched+=1
                    else:unmatched.append(str(row.get('uid') or path.stem))
                else:draft+=1
            except (OSError,ValueError,TypeError):report['warnings'].append('Okunamayan PETEK profil: '+path.name)
        status('PETEK fotograflari',bool(photos),str(len(photos))+' fotoğraf')
        status('Eski PETEK onay eslesmesi',True,
               str(approved)+' onaylı registry profili, '+str(matched)+
               ' SHA eşleşen, '+str(len(unmatched))+' eşleşmeyen; '+str(draft)+' diğer profil')
        if unmatched:
            lines.append('NOT: Eski onayli PETEK profili ile yeni fotoğrafin SHA eslesmemesi otomatik maske kaybi demek degildir.')
            lines.append('Eslesmeyen ilk profiller: '+', '.join(unmatched[:12]))
    except (OSError,ValueError) as exc:
        status('PETEK kaynak ve onay envanteri',False,type(exc).__name__+': '+str(exc)[:150])
    port='http://127.0.0.1:8080/api/petek/templates'
    if probe is None:
        def probe():
            with urllib.request.urlopen(port,timeout=3) as resp:
                if resp.status!=200:raise RuntimeError('HTTP '+str(resp.status))
                return json.load(resp)
    try:
        server=probe()
        if not isinstance(server,dict) or server.get('success') is not True:
            raise ValueError('PETEK_API_BEYANI_GECERSIZ')
        count=len(server.get('items',[]))
        status('Tek 8080 PETEK servisi',True,str(count)+' kayıt, '+str(server.get('scanned_photos','?'))+' fotoğraf')
        if server.get('runtime_root') and Path(server['runtime_root']).resolve()!=workspace.resolve():
            status('8080 calisma klasoru eslesmesi',False,str(server['runtime_root']))
        else:status('8080 calisma klasoru eslesmesi',True,str(workspace))
    except (OSError,ValueError,TypeError,RuntimeError) as exc:
        status('Tek 8080 PETEK servisi',False,
               'Guncel 7 kategorili servis 8080 uzerinde dogrulanamadi: '+str(exc)[:150])
    code_root=Path(__file__).resolve().parents[1]
    magenta=(code_root/'MERKEZ'/'PETEK_V3'/'magenta_quad_v479.py').is_file()
    status('Magenta 4 kose motoru',magenta,
           'Guncel kod paketinde var' if magenta else 'Bu paket magenta PETEK otomatik 4 kose desteklemiyor')
    if report['warnings']:
        lines.append('');lines.append('EK UYARILAR:');lines.extend(report['warnings'][:20])
    lines.extend(['','SONUC: Bu rapor tek basina gercek magenta maske/uretim onayi DEGILDIR.',
                  'Gercek Windows kabul: 8080/PETEK ekraninda magenta taslak -> gozle kontrol -> 1 kucuk demo uretim.',
                  'Eski 45 basarili uretilmis gorsel veya maske profil sayisi birbirine esit varsayilamaz.'])
    return '\n'.join(lines)+'\n',report


def main():
    text,report=run()
    local=Path(os.environ.get('LOCALAPPDATA') or (Path.home()/'AppData'/'Local'))/'GorselMockup'/'TopluKabul'
    local.mkdir(parents=True,exist_ok=True)
    path=local/('TOPLU_URETIM_KABUL_'+time.strftime('%Y%m%d_%H%M%S')+'.txt')
    path.write_text(text,encoding='utf-8')
    print(text)
    print('RAPOR: '+str(path))
    if os.name=='nt':
        try:subprocess.Popen(['notepad.exe',str(path)],close_fds=True)
        except OSError:pass
    return 0


if __name__=='__main__':
    sys.exit(main())
