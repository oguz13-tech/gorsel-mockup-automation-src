"""P0-G: old V4.3 console Python gentle-stop rejection must offer second prompt."""
import importlib.util
from pathlib import Path
from unittest import mock
import pytest

SRC = Path(__file__).resolve().parents[1] / 'MERKEZ' / 'port_transition_v46.py'
spec = importlib.util.spec_from_file_location('port_transition_v46_staging', SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
PID = 14556
OLD = {'ProcessId':PID,'Name':'python.exe','CommandLine':r'python.exe C:\GorselMockup_V43\SABLON_V2_MIMARI\app.py'}
OTHER = {'ProcessId':PID,'Name':'python.exe','CommandLine':r'python.exe C:\Other\SABLON_V2_MIMARI\app.py'}

@pytest.mark.parametrize('force,rc,owner,expected',[
    (False,1,OLD,False),   # previously raised before the second GUI prompt
    (True,1,OLD,'raises'), # explicit force fails, do not loop silently
    (False,1,None,True),  # listener vanished during taskkill
    (False,1,OTHER,'raises'), # PID switched to unknown owner
])
def test_safe_graceful_failure(force,rc,owner,expected):
    with mock.patch.object(m,'owner_of_8080',side_effect=[OLD,owner]), \
         mock.patch.object(m.subprocess,'run',return_value=mock.Mock(returncode=rc,stderr='force required',stdout='')) as proc:
        if expected=='raises':
            with pytest.raises(m.PortSafetyError):m.stop_old_server_if_same(PID,OLD['CommandLine'],force=force)
        else:
            assert m.stop_old_server_if_same(PID,OLD['CommandLine'],force=force) is expected
        assert proc.call_args[0][0] == (['taskkill.exe','/F','/PID',str(PID)] if force else ['taskkill.exe','/PID',str(PID)])

def test_never_kill_changed_owner_before_taskkill():
    with mock.patch.object(m,'owner_of_8080',return_value=OTHER), \
         mock.patch.object(m.subprocess,'run') as proc:
        with pytest.raises(m.PortSafetyError):m.stop_old_server_if_same(PID,OLD['CommandLine'],force=True)
        proc.assert_not_called()

def test_force_success_then_port_free():
    with mock.patch.object(m,'owner_of_8080',side_effect=[OLD,None]), \
         mock.patch.object(m.subprocess,'run',return_value=mock.Mock(returncode=0,stderr='',stdout='')):
        assert m.stop_old_server_if_same(PID,OLD['CommandLine'],force=True) is True
