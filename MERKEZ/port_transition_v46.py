"""Windows-only safe transition for an old V4.x template review server.

Always ask user before terminating anything; never touch arbitrary 8080 owners.
Do not treat a listening port as an authenticated V4.6 server.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import time
from pathlib import Path

class PortSafetyError(RuntimeError):
    pass


def classify_owner(owner: dict, this_script: Path) -> str:
    """Pure allow-list classifier; unknown owners fail closed."""
    if not isinstance(owner, dict):return 'unknown'
    name=str(owner.get('Name') or '').lower()
    cmd=str(owner.get('CommandLine') or '')
    if name not in ('python.exe','pythonw.exe') or not cmd:
        return 'unknown'
    normalized=cmd.lower().replace('/', '\\')
    # Compare explicit script path (not merely a version word).
    current=str(Path(this_script).resolve()).lower().replace('/', '\\')
    if current in normalized:
        return 'same_code' # workspace identity is not verifiable across processes
    match=re.search(r'(?i)([a-z]:\\[^"\r\n]*?\\SABLON_V2_MIMARI\\app\.py)',normalized)
    if not match:return 'unknown'
    path=match.group(1)
    # Only a known old GorselMockup V4.0..V4.5 directory is eligible.
    if re.search(r'(?i)\\gorselmockup_v4(?:0|1|2|3|4|5)(?:\\|_|-)',path):
        return 'old_review'
    return 'unknown'


def owner_of_8080() -> dict | None:
    if os.name != 'nt':raise PortSafetyError('Bu kontrol yalnızca Windows içindir.')
    ps = r'''$listeners=@(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue)
$pids=@($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
if ($pids.Count -gt 1) { Write-Output '{"error":"MULTIPLE_OWNERS"}'; exit 0 }
if ($pids.Count -eq 0) { Write-Output 'null'; exit 0 }
$p=Get-CimInstance Win32_Process -Filter "ProcessId=$($pids[0])"
if ($null -eq $p) { Write-Output '{"error":"OWNER_NOT_FOUND"}'; exit 0 }
$p | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress
'''
    try:
        r=subprocess.run(['powershell.exe','-NoProfile','-Command',ps],
            capture_output=True,encoding='utf-8',errors='replace',timeout=8)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise PortSafetyError('Port sahibi okunamadı: '+str(exc)) from exc
    if r.returncode or not r.stdout.strip():
        raise PortSafetyError('8080 port sahibi doğrulanamadı: '+r.stderr[-300:])
    try:
        result=json.loads(r.stdout.strip())
    except ValueError as exc:raise PortSafetyError('Port bilgisi JSON çözümlenemedi') from exc
    if result is not None and (not isinstance(result,dict) or result.get('error')):
        raise PortSafetyError('Birden fazla/sahibi belirsiz 8080 dinleyicisi var.')
    return result


def stop_old_server_if_same(pid: int, expected_cmd: str, *, force: bool=False) -> bool:
    """Re-read owner immediately before stop to reduce PID reuse danger."""
    fresh=owner_of_8080()
    if (not fresh or int(fresh.get('ProcessId',-1))!=int(pid)
         or str(fresh.get('CommandLine',''))!=expected_cmd
         or classify_owner(fresh,Path(__file__).parent/'..'/'SABLON_V2_MIMARI'/'app.py')!='old_review'):
        raise PortSafetyError('8080 port sahibi değişmiş. Yanlış süreç kapatılmadı.')
    args=['taskkill.exe','/PID',str(pid)]
    if force:args.insert(1,'/F')
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          text=True,errors='replace',timeout=8)
    if result.returncode:
        # Console Python processes often reject non-forced taskkill on Windows.
        # A failed gentle stop must NOT prevent the GUI's second, explicit
        # confirmation for force; only return False while the same allow-listed
        # process still owns the port. Never force or continue on PID reuse.
        now = owner_of_8080()
        if now is None:
            return True
        if (int(now.get('ProcessId', -1)) != int(pid)
                or str(now.get('CommandLine', '')) != expected_cmd
                or classify_owner(now, Path(__file__).parent / '..' / 'SABLON_V2_MIMARI' / 'app.py') != 'old_review'):
            raise PortSafetyError('8080 port sahibi değişmiş. Yanlış süreç kapatılmadı.')
        if not force:
            return False
        raise PortSafetyError('Eski inceleme sunucusu zorla da durdurulamadı: '
                              + (result.stderr or result.stdout)[-300:])
    for _ in range(30):
        now=owner_of_8080()
        if now is None:return True
        if int(now.get('ProcessId',-1))!=int(pid):
            raise PortSafetyError('Port sahibi değişti; yeni uygulamaya müdahale edilmedi.')
        time.sleep(.15)
    return False
