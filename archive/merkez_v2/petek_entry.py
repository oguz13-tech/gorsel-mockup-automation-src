"""PETEK integration: reviewed geometry, fixed local state, no remote publishing."""
import dataclasses
import json
import os
from pathlib import Path
import sys
import tempfile
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/'GUNLUK'),str(HERE/'PETEK')]
from checks import no_redirect
from session_safety import install_write_boundary
import petek_ticari_fabrika as bridge


def prepare_config(manifest,output,designs=None):
    manifest=Path(manifest).absolute();output=Path(output).absolute()
    no_redirect(manifest);no_redirect(output)
    config=bridge.ConfigurationLoader.load(manifest)
    if config.upload_enabled:
        raise RuntimeError('Bu merkez yerel uretim icindir. Bulut acik bir PETEK plani kabul edilmedi.')
    source=Path(designs).absolute() if designs else config.designs
    no_redirect(source)
    if not source.is_dir():raise RuntimeError('Tasarim klasoru bulunamadi.')
    paths=[source,*[p for t in config.templates for p in (t.image,t.geometry)]]
    if config.source_approval_db:paths.append(config.source_approval_db)
    for p in paths:
        no_redirect(p)
        a,b=p.resolve(),output.resolve()
        if a==b or a in b.parents or b in a.parents:
            raise RuntimeError('Kaynak ve sonuc klasorleri ic ice olamaz.')
    return dataclasses.replace(config,designs=source,state=output,upload_enabled=False,upload_approved=False)


def execute(manifest,output,designs=None):
    config=prepare_config(manifest,output,designs)
    config.state.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='temp-',dir=config.state));tempfile.tempdir=str(temp)
    install_write_boundary(temp,config.state,live_db=config.source_approval_db)
    report=bridge.CommercialBridge(config).execute()
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['status']=='LOCAL_RENDER_AND_EXCEL_READY_REVIEW_REQUIRED' else 2

if __name__=='__main__':
    try:
        if len(sys.argv) not in (2,3):raise RuntimeError('PETEK onayli uretim plani secilmedi.')
        raise SystemExit(execute(sys.argv[1],Path('C:/AI_LOCAL_OUTPUTS/GorselMockup/PETEK_TICARI_LOCAL'),sys.argv[2] if len(sys.argv)==3 else None))
    except Exception as exc:
        print('DURDU:',exc);raise SystemExit(2)
