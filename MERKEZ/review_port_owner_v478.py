"""Windows-only canonical 8080 review-port ownership reclamation.

Never terminate an unknown listener. The user requested ONE stable 127.0.0.1:8080
address instead of accumulating 8081-8090 editor servers. We can reclaim an
old SIX/SEVEN review Flask process, but only on a strict multi-factor match:
the exact loopback socket, same Windows SID, verified Python argv pointing at
a real app.py in a genuine installed Mockup center, and zero active editor jobs.
No /T tree kill, no blanket Python kill, no deletion or DB writes.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request

PORT=8080

class PortOwnerError(RuntimeError):
    pass

_CIM_SCRIPT=r"""
$ErrorActionPreference='Stop'
$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$listeners=@(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue)
$rows=@()
foreach ($entry in $listeners) {
  $owning=[int]$entry.OwningProcess
  $proc=Get-CimInstance Win32_Process -Filter "ProcessId=$owning" -ErrorAction Stop
  if ($null -eq $proc) { throw "PORT_PROCESS_MISSING" }
  $sid=(Invoke-CimMethod -InputObject $proc -MethodName GetOwnerSid -ErrorAction Stop).Sid
  $rows+=@{ address=[string]$entry.LocalAddress; pid=$owning;
            command=[string]$proc.CommandLine; exe=[string]$proc.ExecutablePath;
            sid=[string]$sid; created=[string]$proc.CreationDate }
}
@{current_sid=$identity; listeners=@($rows)} | ConvertTo-Json -Compress -Depth 5
"""

# Windows subprocess quotes a script path only if it contains whitespace.
# Accept either a complete quoted drive path, or a complete unquoted token;
# reject arbitrary text that merely mentions app.py.
_SCRIPT_PATH=re.compile(
    r'(?i)(?:^|\\s)(?:"(?P<quoted>[A-Z]:\\\\[^"\\r\\n]+\\\\SABLON_V2_MIMARI\\\\app\\.py)"'
    r'|(?P<plain>[A-Z]:\\\\[^\\s"\\r\\n]+\\\\SABLON_V2_MIMARI\\\\app\\.py))(?=\\s|$)'
)

def _snapshot():
    if os.name!='nt':
        raise PortOwnerError('SADECE_WINDOWS_8080_DEVIR')
    completed=subprocess.run(
        ['powershell.exe','-NoProfile','-NonInteractive','-Command',_CIM_SCRIPT],
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=9,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if completed.returncode:
        raise PortOwnerError('WINDOWS_8080_SAHIP_TESPITI_BASARISIZ')
    try:
        result=json.loads(completed.stdout.strip())
        if not isinstance(result,dict) or not isinstance(result.get('listeners'),list):
            raise ValueError('wrong type')
        return result
    except (ValueError,TypeError) as exc:
        raise PortOwnerError('WINDOWS_8080_SAHIP_BILGISI_BOZUK') from exc

def _validated_owner(snapshot):
    listeners=snapshot.get('listeners') or []
    if len(listeners)!=1:
        raise PortOwnerError('8080_SAHIP_BELIRSIZ_BIRDEN_FAZLA_LISTENER')
    owner=listeners[0]
    if owner.get('address') not in ('127.0.0.1','::1'):
        raise PortOwnerError('8080_BASKA_AYGIT_VEYA_GENEL_AG_SERVISI')
    if not snapshot.get('current_sid') or owner.get('sid')!=snapshot['current_sid']:
        raise PortOwnerError('8080_FARKLI_WINDOWS_KULLANICISI')
    if Path(str(owner.get('exe',''))).name.casefold() not in ('python.exe','pythonw.exe'):
        raise PortOwnerError('8080_PYTHON_DISI_SERVIS')
    command=owner.get('command') or ''
    if not isinstance(command,str):
        raise PortOwnerError('8080_PROCESS_KOMUTU_YOK')
    match=_SCRIPT_PATH.search(command)
    if not match:
        raise PortOwnerError('8080_BIZIM_INCELEME_SERVISIMIZ_DEGIL')
    script=Path(match.group('quoted') or match.group('plain'))
    if (not script.is_file() or script.is_symlink() or
            not (script.parent.parent/'MERKEZ'/'merkez.py').is_file() or
            not (script.parent.parent/'MERKEZ'/'legacy_manager.py').is_file()):
        raise PortOwnerError('8080_ESKI_PAKET_KIMLIGI_DOGRULANAMADI')
    try:
        source=script.read_text(encoding='utf-8')
        if "SABLON_V2_MIMARI" not in source or "/api/jobs" not in source:
            raise ValueError('not recognized')
    except (OSError,UnicodeError,ValueError) as exc:
        raise PortOwnerError('8080_INCELEME_KODU_TANINMADI') from exc
    pid=owner.get('pid')
    if type(pid)!=int or pid<=0 or pid==os.getpid():
        raise PortOwnerError('8080_GECERSIZ_PID')
    return owner

def _jobs_clear():
    try:
        with urllib.request.urlopen(
            f'http://127.0.0.1:{PORT}/api/jobs?active=1&limit=100',timeout=2
        ) as resp:
            if resp.status!=200:
                return False
            body=json.load(resp)
        return body.get('success') is True and isinstance(body.get('jobs'),list) and not body['jobs']
    except (OSError,ValueError,TypeError,KeyError):
        return False

def ensure_canonical_8080(*, occupied, snapshot=None, jobs_clear=None,
                          terminate=None, sleep=None):
    """Reclaim ONLY an idempotently verified own old Flask listener.

    Dependency injection is for synthetic Windows/Ubuntu CI. Every real call
    re-checks process PID, creation time, SID and command-line immediately
    before termination, then checks the actual port was released.
    """
    if not occupied():
        return {'reclaimed':False,'port':PORT,'reason':'FREE'}
    snapshot=snapshot or _snapshot
    jobs_clear=jobs_clear or _jobs_clear
    terminate=terminate or _terminate_exact
    sleep=sleep or time.sleep
    first=_validated_owner(snapshot())
    if not jobs_clear():
        raise PortOwnerError(
            '8080_INCELEME_AKTIF_IS_VEYA_BELIRSIZ_DURUM: Eski sunucu otomatik kapatılmadı.')
    second=_validated_owner(snapshot())
    for field in ('pid','created','sid','command','exe','address'):
        if second.get(field)!=first.get(field):
            raise PortOwnerError('8080_SAHIP_SURECTE_DEGISTI')
    if not occupied():
        return {'reclaimed':False,'port':PORT,'reason':'ALREADY_RELEASED'}
    terminate(first['pid'])
    for _ in range(40):
        if not occupied():
            return {'reclaimed':True,'port':PORT,'pid':first['pid']}
        sleep(0.10)
    raise PortOwnerError('8080_ESKI_INCELEME_KAPANMADI')

def _terminate_exact(pid):
    # Verified individual owning process only, never /T or a blanket Python
    # kill. Windows /F is needed for a headless Python Flask process.
    result=subprocess.run(['taskkill.exe','/PID',str(pid),'/F'],
                          capture_output=True,text=True,timeout=6,
                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:
        raise PortOwnerError('8080_DOGRULANAN_ESKI_SERVIS_KAPATILAMADI')
