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
