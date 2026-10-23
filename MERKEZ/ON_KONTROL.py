"""Read-only current Windows runtime compatibility checker."""
from __future__ import annotations
import importlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'GUNLUK'))
from session_safety import digest, FILL_SHA
from daily import BASE,CODE


def report():
    environment={'python_version':sys.version.split()[0],'python_binary':sys.executable,
                 'status':'UNKNOWN','daily_ready':False,'petek_v3_ready':False,
                 'notes':[],'errors':[]}
    for package in ('numpy','PIL','cv2','openpyxl','tkinter','requests','flask'):
        try:importlib.import_module(package)
        except ImportError:environment['errors'].append('Eksik Python paket: '+package)
    file=CODE/'99_SISTEM_MOTORLARI_VE_KODLAR'/'SISTEM_MOTORU'/'pc_master_factory.py'
    environment['legacy_code_present']=file.is_file()
    environment['legacy_backup_present']=BASE.is_dir()
    if file.is_file():
        environment['legacy_fill_sha256']=digest(file)
        environment['expected_sha256']=FILL_SHA
        if digest(file)!=FILL_SHA:
            environment['notes'].append('Gunluk V2 motor hash i farklı. Gunluk kendisi kapsamli koruma kontrolu yapacak.')
    else:
        environment['notes'].append('Gunluk V2 icin kurulu C:\\AI_WORK kodu mevcut degil; PETEK V3 ayri calisabilir.')
    try:
        from PETEK_V3 import engine
        from PETEK_V3.registry import Registry
        environment['petek_v3_ready']=not any('Eksik Python paket' in x for x in environment['errors'])
    except Exception as exc:environment['errors'].append('PETEK import: '+str(exc))
    environment['daily_ready']=file.is_file() and BASE.is_dir() and not environment['errors']
    environment['status']='READY_FOR_LOCAL_STAGING' if environment['petek_v3_ready'] else 'BLOCKED_DEPENDENCIES'
    return environment

if __name__=='__main__':
    print(json.dumps(report(),ensure_ascii=False,indent=2))
