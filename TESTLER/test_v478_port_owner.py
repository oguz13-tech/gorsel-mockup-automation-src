"""Do not kill any unknown listener while reclaiming canonical 8080."""
import inspect
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from review_port_owner_v478 import (
    ensure_canonical_8080,PortOwnerError,_validated_owner,_terminate_exact,
)

def test_windows_commandline_parser_works_for_quoted_and_unquoted_package_paths():
    from review_port_owner_v478 import _SCRIPT_PATH
    quoted=r'"C:\Code Files\python.exe" -B "C:\Code Files\GORSEL_V46_CANDIDATE\SABLON_V2_MIMARI\app.py"'
    plain=r'C:\Python311\python.exe -B C:\MOCKUP_V47\SABLON_V2_MIMARI\app.py'
    assert _SCRIPT_PATH.search(quoted).group('quoted').endswith(r'\SABLON_V2_MIMARI\app.py')
    assert _SCRIPT_PATH.search(plain).group('plain').endswith(r'\SABLON_V2_MIMARI\app.py')
    assert _SCRIPT_PATH.search(r'C:\Windows\python.exe -m http.server 8080') is None


def test_port_8080_free_never_queries_or_kills_anything():
    calls=[]
    r=ensure_canonical_8080(occupied=lambda:False,
        snapshot=lambda:calls.append('snapshot'),
        jobs_clear=lambda:calls.append('jobs'),
        terminate=lambda pid:calls.append(pid))
    assert r['reason']=='FREE' and r['port']==8080 and calls==[]

def test_nonowned_or_multiple_listeners_fail_closed():
    with pytest.raises(PortOwnerError,match='BELIRSIZ'):
        _validated_owner({'current_sid':'S-1','listeners':[{'pid':1},{'pid':2}]})
    with pytest.raises(PortOwnerError,match='FARKLI_WINDOWS_KULLANICISI'):
        _validated_owner({'current_sid':'S-1','listeners':[{
            'pid':50,'sid':'S-OTHER','address':'127.0.0.1',
            'exe':'C:\\Windows\\python.exe','command':'python.exe'
        }]})
    with pytest.raises(PortOwnerError,match='GENEL_AG'):
        _validated_owner({'current_sid':'S-1','listeners':[{
            'pid':50,'sid':'S-1','address':'0.0.0.0',
            'exe':'C:\\Windows\\python.exe','command':'python.exe'
        }]})
    with pytest.raises(PortOwnerError,match='PYTHON_DISI'):
        _validated_owner({'current_sid':'S-1','listeners':[{
            'pid':50,'sid':'S-1','address':'127.0.0.1',
            'exe':'C:\\Windows\\nginx.exe','command':'nginx.exe'
        }]})

def test_verified_owner_no_jobs_reclaims_only_pid_once(monkeypatch):
    import review_port_owner_v478 as review
    owner={'pid':88123,'sid':'SID','command':'exact','exe':'python.exe',
           'address':'127.0.0.1','created':'2026-10-29'}
    monkeypatch.setattr(review,'_validated_owner',lambda snap:snap['listeners'][0])
    stages=[True,True,False]
    killed=[]
    result=ensure_canonical_8080(
        occupied=lambda:stages.pop(0) if stages else False,
        snapshot=lambda:{'listeners':[dict(owner)]},
        jobs_clear=lambda:True,
        terminate=lambda pid:killed.append(pid),sleep=lambda t:None)
    assert result['reclaimed'] and result['port']==8080 and killed==[88123]

def test_busy_or_unverifiable_jobs_never_killed(monkeypatch):
    import review_port_owner_v478 as review
    monkeypatch.setattr(review,'_validated_owner',lambda snap:snap['listeners'][0])
    owner={'pid':88123,'sid':'SID','command':'exact','exe':'python.exe',
           'address':'127.0.0.1','created':'created'}
    called=[]
    with pytest.raises(PortOwnerError,match='AKTIF_IS'):
        ensure_canonical_8080(occupied=lambda:True,
            snapshot=lambda:{'listeners':[owner]},jobs_clear=lambda:False,
            terminate=lambda pid:called.append(pid))
    assert called==[]

def test_pid_reuse_or_process_changed_never_killed(monkeypatch):
    import review_port_owner_v478 as review
    monkeypatch.setattr(review,'_validated_owner',lambda snap:snap['listeners'][0])
    n=[{'pid':111,'created':'first','sid':'SID','command':'app'},
       {'pid':111,'created':'second','sid':'SID','command':'app'}]
    called=[]
    with pytest.raises(PortOwnerError,match='SURECTE_DEGISTI'):
        ensure_canonical_8080(occupied=lambda:True,
            snapshot=lambda:{'listeners':[n.pop(0)]},
            jobs_clear=lambda:True,terminate=lambda pid:called.append(pid))
    assert called==[]

def test_blocked_busy_port_does_not_silently_fallback_8083():
    source=inspect.getsource(ensure_canonical_8080)
    assert 'port=PORT' not in source or '8083' not in source
    assert '8083' not in source
    assert "['taskkill.exe','/PID',str(pid),'/F']" in inspect.getsource(_terminate_exact)
