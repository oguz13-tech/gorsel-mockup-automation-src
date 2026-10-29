"""Windows review port conflict regression and PETEK user-created folder map.

Tk GUI opening is statically guarded on CI because hosted Linux has no window
server; real Windows screenshot acceptance remains user-local.
"""
from __future__ import annotations
import inspect
import json
from pathlib import Path
import sys
import types
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from legacy_manager import (choose_review_port,server_identity_diagnostic,
                            LegacyLaunchError)
from petek_folders_v46 import petek_directory,prepare_petek_folders,SECTIONS
import merkez
from PETEK_V3.gui import MaskEditor


def test_review_port_defaults_to_8080_and_falls_back_8081_without_stopping_8080():
    attempts=[]
    def occupied(port):
        attempts.append(port)
        return port==8080
    assert choose_review_port(occupied=occupied)==8081
    assert attempts==[8080,8081]
    assert choose_review_port(occupied=lambda port:False)==8080


def test_review_port_all_busy_refuses_without_kill():
    with pytest.raises(LegacyLaunchError,match='dol[uı]'):
        choose_review_port(candidates=(8080,8081),occupied=lambda _:True)
    with pytest.raises(LegacyLaunchError,match='PORTU_GECERSIZ'):
        choose_review_port(candidates=(9,),occupied=lambda _:False)


def test_authenticated_editor_identity_is_strictly_bound_to_selected_port(tmp_path):
    requests=[]
    expected_token='unit-test-random'
    expected_pid=4131
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def read(self):return json.dumps({
            'pid':expected_pid,'parent_pid':0,
            'code_root':str(tmp_path),'runtime_root':str(tmp_path),
            'token':expected_token,
        }).encode('utf-8')
    def open_request(request,timeout):
        requests.append(request.full_url)
        return Response()
    result=server_identity_diagnostic(tmp_path,tmp_path,expected_pid,expected_token,
                   opener=open_request,port=8081,windows_redirector=False)
    assert result['ready'] and requests==['http://127.0.0.1:8081/api/center_identity']
    def mismatched(request,timeout):
        class Wrong(Response):
            def read(self):
                return Response.read(self).replace(b'unit-test-random',b'wrong-server')
        return Wrong()
    blocked=server_identity_diagnostic(tmp_path,tmp_path,expected_pid,expected_token,
                   opener=mismatched,port=8081,windows_redirector=False)
    assert blocked['reason']=='IDENTITY_TOKEN_MISMATCH'


def test_center_canonical_8080_uses_verified_reclaim_and_correct_browser_url():
    source=inspect.getsource(merkez.Center._open_legacy)
    poll=inspect.getsource(merkez.Center.poll)
    assert 'ensure_canonical_8080' in source
    assert 'editor_port=8080' in source
    assert 'MOCKUP_PORT' in source
    assert 'port=editor_port' in source
    assert 'choose_review_port()' not in source
    assert 'taskkill' not in source
    assert "webbrowser.open(f'http://127.0.0.1:{self.editor_port}'+value)" in poll
    assert "webbrowser.open('http://127.0.0.1:8080'+value)" not in poll


def test_user_petek_friendly_inbox_is_separate_from_working_and_archive(tmp_path):
    root=tmp_path/'Ana'
    (root/'SABLON_V2_MIMARI').mkdir(parents=True)
    (root/'SABLON_V2_MIMARI'/'ayarlar.db').write_bytes(b'placeholder')
    user_created=root/'YENI-BOS MOCKUP SABLON HAVUZU'/'Petek_Dolabi'
    user_created.mkdir(parents=True)
    prepared=prepare_petek_folders(root)
    assert prepared['paths'][SECTIONS[0]]==str(user_created)
    assert prepared['paths'][SECTIONS[1]]==str(root/'2_SABLON_HAVUZU'/'Petek_Dolabi')
    assert prepared['paths'][SECTIONS[2]]==str(root/'2_SABLON_HAVUZU_ORIJINAL_YEDEK'/'Petek_Dolabi')
    assert prepared['logical_category']=='06_Petek_Kapama'
    assert user_created.is_dir()


def test_petek_editor_has_wider_scrollable_control_rail():
    source=inspect.getsource(MaskEditor.__init__)
    assert 'control_width = min(370, max(310' in source
    assert 'self.window.minsize(min(930, window_w)' in source
    assert "self.tools_scroll.bind('<MouseWheel>',scroll_tools)" in source
    assert 'self.runtime_root' in source
