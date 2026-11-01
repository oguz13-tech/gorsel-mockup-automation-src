"""Offline read-only report for PETEK generated output and receipt consistency."""
from __future__ import annotations
import json
from pathlib import Path
from PETEK_V3.batch import Batch
from PETEK_V3.registry import Registry


def run_audit(registry=None, *, write_report=True):
    reg=registry or Registry()
    report=Batch(reg).audit()
    destination=None
    if write_report:
        import datetime
        stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        destination=reg.reports/('URETIM_GUVENLIK_DENETIMI_'+stamp+'.json')
        from PETEK_V3.engine import atomic_new_file
        atomic_new_file(destination,json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True).encode('utf-8'))
    return report,destination


if __name__=='__main__':
    r,p=run_audit()
    print('Toplam kayit:',r['summary']['total'])
    print('Dogrulanan:',r['summary']['verified'])
    print('Inceleme gerektiren:',r['summary']['review_required'])
    print('Rapor:',p)
    for problem in r['summary']['issues']:
        print('KONTROL_GEREKENLER:',problem['key'],problem['reason'])
