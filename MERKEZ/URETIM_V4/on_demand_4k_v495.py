"""V4.9.5 demand-only Real-ESRGAN probe; user-local cache, no startup scanning.

Authoritative photo/fast model checks remain in upscale4k_v44.preflight.
The cache only remembers validated engine location and quick file metadata;
if anything changes the authoritative preflight is rerun.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
from . import upscale4k_v44 as core


def user_state_path(env=None):
    env = os.environ if env is None else env
    parent = Path(env.get('LOCALAPPDATA') or Path.home()/'.gorsel_mockup')
    return parent / 'GorselMockup' / '4k_kurulum_durumu.json'


def model_files(executable, model):
    exe = Path(executable)
    stem = core.MODELS[model]
    return (exe, exe.parent/'models'/f'{stem}.bin', exe.parent/'models'/f'{stem}.param')


def file_signatures(paths):
    result=[]
    for path in paths:
        if path.is_symlink(): raise core.UpscaleError('4K sembolik bağlantı reddedildi.')
        info=path.stat()
        if not path.is_file() or info.st_size<=0:raise core.UpscaleError('4K eksik: '+str(path))
        result.append([str(path.resolve()),info.st_size,info.st_mtime_ns])
    return result


class OnDemand4K:
    def __init__(self, state_file=None):
        self.state_file=Path(state_file) if state_file is not None else user_state_path()
        self.session={}

    def _read(self):
        try:
            data=json.loads(self.state_file.read_text(encoding='utf-8'))
            return data if isinstance(data,dict) else {}
        except (OSError,ValueError):
            return {}

    def _remember(self, model, exe):
        exe=Path(exe).resolve()
        entry={'engine':str(exe),'files':file_signatures(model_files(exe,model))}
        self.session[model]=entry
        try:
            state=self._read();state[model]=entry
            self.state_file.parent.mkdir(parents=True,exist_ok=True)
            # Atomic user-local write; never touches template DB, mask, ledger.
            with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=self.state_file.parent,
                                             prefix='.4k-',suffix='.tmp',delete=False) as tmp:
                json.dump(state,tmp,ensure_ascii=False,indent=2)
                temporary=Path(tmp.name)
            try:os.replace(temporary,self.state_file)
            finally:temporary.unlink(missing_ok=True)
        except OSError:
            pass  # Cache is optional, functional 4K must not depend on it.
        return exe

    def verify(self, model='photo'):
        if model not in core.MODELS:
            raise core.UpscaleError('Bilinmeyen Real-ESRGAN modeli')
        entry=self.session.get(model) or self._read().get(model,{})
        if isinstance(entry,dict) and entry.get('engine'):
            try:
                exe=Path(entry['engine'])
                if file_signatures(model_files(exe,model))==entry['files']:
                    # Safe engine location discovered earlier; no full scan.
                    self.session[model]=entry
                    return exe.resolve(), 'ONBELLEK_HAZIR'
            except (OSError,KeyError,ValueError,core.UpscaleError):
                pass
        # Engine may be installed in this ZIP, system PATH, or REAL_ESRGAN_EXE.
        # If the cached location moved, fall through to normal authoritative probe.
        found=core.preflight(enabled=True,model=model)
        return self._remember(model,found), 'DOGRULANDI'
