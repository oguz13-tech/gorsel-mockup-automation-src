"""Reproducible source-only Windows candidate ZIP from a clean Git checkout.

Usage: python scripts/build_windows_factory.py --output /outside/repo/release.zip
No local workspace files, real templates, live DBs, credentials or user configs.
This packages a release candidate; it does not install or declare production readiness.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'.py','.md','.txt','.json','.toml','.ini','.yml','.yaml','.bat','.ps1','.js','.html','.css'}


def build(output,root=ROOT):
    root=Path(root).resolve();output=Path(output).resolve()
    if root==output or root in output.parents:raise ValueError('ZIP hedefi kaynak repo dışında olmalı.')
    dirty=subprocess.check_output(['git','-C',str(root),'status','--porcelain'],text=True)
    if dirty.strip():raise RuntimeError('Önce değişiklikleri commit edin; temiz checkout gerekli.')
    revision=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    files=subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode().split('\0')
    payload={}
    for rel in files:
        if not rel:continue
        p=Path(rel)
        if p.name in ('ayarlar.json','SETTINGS.json','CONFIG.json') or p.suffix.lower() not in ALLOWED:continue
        if p.parts[0] in ('.github','.vscode'):continue
        data=(root/p).read_bytes()
        if (root/p).is_symlink():raise RuntimeError('Bağlantılı kaynak kabul edilmedi: '+rel)
        payload['KAYNAK/'+rel]=data
    payload['BASLAT.bat']=b'@echo off\r\ncd /d "%~dp0KAYNAK"\r\npowershell -NoProfile -ExecutionPolicy Bypass -File "FABRIKA\\BASLAT.ps1"\r\npause\r\n'
    payload['KABUL_TESTI.bat']=b'@echo off\r\ncd /d "%~dp0KAYNAK"\r\npowershell -NoProfile -ExecutionPolicy Bypass -File "FABRIKA\\BASLAT.ps1" -Test\r\npause\r\n'
    payload['ONCE_OKU.txt']=('Görsel Üretim Fabrikası V3 — KABUL ADAYI\n'
        'ZIP dosyasını yeni ve boş bir klasöre açın. Eski çalışan klasörün üzerine kopyalamayın.\n'
        '1. KABUL_TESTI.bat: sentetik testler; gerçek şablon ve canlı DB açılmaz.\n'
        '2. BASLAT.bat: tek üretim ekranı. İlk PETEK şablonunu dört köşe ve maske ile inceleyin.\n'
        '3. Gerçek ilk çıktıları gözle kontrol edin. Windows kabulü tamamlanmadan gözetimsiz final değildir.\n'
        '4. Geri dönüş: bu uygulamayı kapatın, önceki çalışan BASLAT.bat dosyanızı açın.\n'
        'Kurulum/migration/pazaryeri gönderimi otomatik yapılmaz.\n'
        'Ayrıntılar: KAYNAK/docs/WINDOWS_RELEASE_STATUS.md\n').encode()
    manifest={name:hashlib.sha256(data).hexdigest() for name,data in sorted(payload.items())}
    payload['BUILD.json']=json.dumps({'source_commit':revision,'status':'CANDIDATE_WINDOWS_ACCEPTANCE_PENDING','files':manifest},indent=2).encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(payload.items()):
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
    with zipfile.ZipFile(output) as z:
        if z.testzip():raise RuntimeError('ZIP CRC başarısız.')
        for name,expected in manifest.items():
            if hashlib.sha256(z.read(name)).hexdigest()!=expected:raise RuntimeError('Paket SHA uyuşmazlığı.')
    return {'zip':str(output),'source_commit':revision,'files':len(payload),'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    print(json.dumps(build(parser.parse_args().output),indent=2))
