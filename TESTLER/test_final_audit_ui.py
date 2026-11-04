import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from PETEK_V3.registry import Registry
from petek_denetle import run_audit


def test_audit_cli_no_artifacts_and_unique_create_only_reports(tmp_path):
    reg=Registry(tmp_path/'private')
    before=list(reg.reports.glob('*'))
    data,p=run_audit(reg)
    assert data['summary']=={'total':0,'verified':0,'review_required':0,'issues':[]}
    assert p.is_file() and p not in before
    data2,p2=run_audit(reg)
    assert data2==data and p2!=p
    assert len(list(reg.reports.glob('URETIM_GUVENLIK_DENETIMI_*.json')))==2
