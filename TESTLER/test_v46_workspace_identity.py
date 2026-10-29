import io
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'MERKEZ'))
import legacy_manager as manager


def test_missing_selected_root_never_falls_back(tmp_path):
    env = {'LOCALAPPDATA': str(tmp_path)}
    state = manager.local_state_dir(env)
    state.mkdir(parents=True)
    selected = tmp_path / 'kayip seçili kök'
    (state / 'workspace.json').write_text(json.dumps({'path': str(selected)}))
    assert manager.preferred_runtime(env=env) == selected
    assert not selected.exists()


def test_server_requires_pid_token_and_both_roots(tmp_path):
    data = dict(pid=42, token='secret', runtime_root=str(tmp_path/'data'), code_root=str(tmp_path/'code'))
    def check(value):
        return manager.server_matches(tmp_path/'data', tmp_path/'code',42,'secret',
                                     opener=lambda *a,**k:io.StringIO(json.dumps(value)))
    assert check(data)
    for key,value in [('pid',43),('token','foreign'),('runtime_root',str(tmp_path/'other')),('code_root',str(tmp_path/'old'))]:
        assert not check({**data,key:value})
    assert not check({})


def test_unavailable_server_is_not_ready(tmp_path):
    def fail(*args,**kwargs):raise OSError('offline')
    assert not manager.server_matches(tmp_path,tmp_path,1,'x',opener=fail)


def test_online_backup_restore_preserves_source(tmp_path):
    import sqlite3,hashlib
    root=tmp_path/'runtime'; db=root/'SABLON_V2_MIMARI'/'ayarlar.db'
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE approvals(quad TEXT)')
        con.execute("INSERT INTO approvals VALUES('immutable')")
    before=db.read_bytes()
    result=manager.backup_database(root,env={'LOCALAPPDATA':str(tmp_path/'local')})
    assert db.read_bytes()==before
    with sqlite3.connect(result) as con:
        assert con.execute('SELECT quad FROM approvals').fetchone()==('immutable',)
    assert result.with_suffix('.sha256').read_text().startswith(hashlib.sha256(result.read_bytes()).hexdigest())


def test_identity_diagnostic_explains_mismatch_without_leaking_token(tmp_path):
    expected=dict(pid=51,token='only-in-memory',runtime_root=str(tmp_path/'data'),
                  code_root=str(tmp_path/'code'))
    def probe(data):
        return manager.server_identity_diagnostic(
            tmp_path/'data',tmp_path/'code',51,'only-in-memory',
            opener=lambda *a,**k:io.StringIO(json.dumps(data)))
    assert probe(expected)=={'ready':True,'reason':'MATCHED'}
    for key,wrong,reason in [
        ('pid',52,'IDENTITY_PID_MISMATCH'),
        ('token','other','IDENTITY_TOKEN_MISMATCH'),
        ('code_root',str(tmp_path/'wrong-code'),'IDENTITY_CODE_ROOT_MISMATCH'),
        ('runtime_root',str(tmp_path/'wrong-runtime'),'IDENTITY_RUNTIME_ROOT_MISMATCH'),
    ]:
        outcome=probe({**expected,key:wrong})
        assert outcome['ready'] is False
        assert outcome['reason']==reason
        assert 'only-in-memory' not in str(outcome)
        if key in ('code_root','runtime_root'):
            assert 'actual_path' in outcome and 'expected_path' in outcome


def test_identity_diagnostic_unauthorized_and_unreachable(tmp_path):
    import urllib.error
    def unauthorized(*a,**k):
        raise urllib.error.HTTPError('http://127.0.0.1:8080',403,'Forbidden',{},None)
    result=manager.server_identity_diagnostic(tmp_path,tmp_path,1,'secret',opener=unauthorized)
    assert result['reason']=='IDENTITY_HTTP_403'
    assert result['ready'] is False
    assert manager.server_identity_diagnostic(
        tmp_path,tmp_path,1,'secret',
        opener=lambda *a,**k:(_ for _ in ()).throw(TimeoutError())
    )['reason']=='IDENTITY_TIMEOUT'


def test_windows_redirector_accepts_verified_direct_child_only(tmp_path):
    expected = dict(pid=777, parent_pid=333, token='private-token',
                    runtime_root=str(tmp_path/'data'), code_root=str(tmp_path/'code'))
    def check(data, windows_redirector):
        return manager.server_identity_diagnostic(
            tmp_path/'data',tmp_path/'code',333,'private-token',
            opener=lambda *a,**k:io.StringIO(json.dumps(data)),
            windows_redirector=windows_redirector)
    result=check(expected,True)
    assert result['ready'] is True
    assert result['reason']=='MATCHED_WIN_VENV_REDIRECTOR'
    assert check(expected,False)['reason']=='IDENTITY_PID_MISMATCH'
    assert check({**expected,'parent_pid':334},True)['reason']=='IDENTITY_PID_MISMATCH'
    assert check({**expected,'token':'different'},True)['reason']=='IDENTITY_TOKEN_MISMATCH'
    assert check({**expected,'code_root':str(tmp_path/'wrong')},True)['reason']=='IDENTITY_CODE_ROOT_MISMATCH'
    assert check({**expected,'runtime_root':str(tmp_path/'wrong')},True)['reason']=='IDENTITY_RUNTIME_ROOT_MISMATCH'


def test_real_windows_venv_redirector_subprocess_pid(tmp_path):
    import subprocess
    import pytest
    if sys.platform != 'win32':
        pytest.skip('Only CPython Windows venv uses this redirector')
    root=tmp_path/'py_venv'
    subprocess.run([sys.executable,'-m','venv','--without-pip',str(root)],
                   check=True,timeout=40)
    venv_python=root/'Scripts'/'python.exe'
    proc=subprocess.Popen([str(venv_python),'-c',
        'import os,json; print(json.dumps({"pid":os.getpid(),"parent_pid":os.getppid()}))'],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    out,err=proc.communicate(timeout=20)
    assert proc.returncode==0,err
    data=json.loads(out.strip())
    # Windows virtual environment process launch is a redirector and the
    # Python interpreter it starts is the next process in the chain.
    assert data['pid'] != proc.pid
    assert data['parent_pid']==proc.pid
    data.update(token='t',runtime_root=str(tmp_path/'data'),code_root=str(tmp_path/'code'))
    result=manager.server_identity_diagnostic(
        tmp_path/'data',tmp_path/'code',proc.pid,'t',
        opener=lambda *a,**k:io.StringIO(json.dumps(data)))
    assert result['ready'] is True
    assert result['reason']=='MATCHED_WIN_VENV_REDIRECTOR'
