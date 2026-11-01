"""Guided operator-only replacement from the explicitly selected chroma LAB.

No auto-apply on launch. Every physical change requires a side-by-side preview,
verified input hashes, typed confirmation and the transaction's own rollback.
PETEK is separate immutable registry and is intentionally not auto-overwritten.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from tkinter import Tk,messagebox,simpledialog
import webbrowser
from legacy_manager import preferred_runtime
from magenta_reconcile_v472 import LAB,CONFIRM,analyze,apply,write_report,html_comparison

ELIGIBLE=('READY_APPROVED_TRANSFER','READY_REQUIRES_REAPPROVAL')

def summary(plan):
    counts={}
    for item in plan['jobs']:
        st=item['status'];counts[st]=counts.get(st,0)+1
    accepted=sum(counts.get(key,0) for key in ELIGIBLE)
    return {'eligible':accepted,'total':len(plan['jobs']),
            'blocked':len(plan['jobs'])-accepted,'counts':counts}


def main():
    app=Tk();app.withdraw()
    try:
        workspace=preferred_runtime()
        if not LAB.is_dir():raise FileNotFoundError('MAGENTA_LAB_YOK: '+str(LAB))
        if not messagebox.askyesno('MAGENTA 6 KATEGORİ — ÖNCE GÜVENLİ ÖNİZLEME',
            'Kaynak: '+str(LAB)+'\n\nAna çalışma klasörü: '+str(workspace)+
            '\n\nİlk adım SADECE okuma/yan yana karşılaştırma. '
            'Bu ekran fotoğraf veya onay değiştirmez. '
            'PETEK ayrı maskeye sahiptir; bu işlem PETEK için uygulanmaz. Devam?',parent=app):
            return
        plan=analyze(workspace,LAB)
        stats=summary(plan)
        report=write_report(plan)
        page=html_comparison(report)
        if os.name=='nt':os.startfile(str(page))
        else:webbrowser.open(page.as_uri())
        msg=('Tam eşleşen ve değiştirilebilir: '+str(stats['eligible'])+
             '\nEngelli, eşleşmeyen veya zaten aynı: '+str(stats['blocked'])+
             '\nToplam LAB görseli: '+str(stats['total'])+
             '\n\nYan yana karşılaştırma: '+str(page)+
             '\nPlan: '+str(report)+
             '\n\nDeğiştirilebilir her görsel için eski dosya ayrı yerel rollback '
             'klasörüne saklanır. Ana orijinal yedek klasörü DEĞİŞMEZ. '
             'Yeni magenta fotoğrafların tamamı yeniden insan onayı bekler.')
        if stats['eligible']==0:
            messagebox.showwarning('MAGENTA — UYGUN EŞLEŞME YOK',msg,parent=app)
            return
        if not messagebox.askyesno('MAGENTA KARŞILAŞTIRMA TAMAMLANDI MI?',
            msg+'\n\nYan yana karşılaştırmadaki doğru fotoğrafları gördüğünü '
            'onaylıyor musun? Devam etmek gerçek dosyaların değiştirilmesine '
            'izin verme aşamasına geçer.',parent=app):
            return
        typed=simpledialog.askstring('SON GÜVENLİK ONAYI',
            'Onaylı maskeler otomatik korunmuş SAYILMAYACAK; yeni magenta fotoğraflar '
            'için yeniden insan onayı yapılacak.\n\nİşlemi başlatmak için bu ifadeyi '
            'aynen yaz:\n'+CONFIRM,parent=app)
        if typed!=CONFIRM:
            messagebox.showinfo('İPTAL','Dosyalar değiştirilmedi.',parent=app)
            return
        result=apply(report,typed,allow_review=True,force_reapproval=True)
        messagebox.showinfo('MAGENTA GÜVENLİ DEĞİŞTİRME',
            'Değiştirilen dosya: '+str(result['count'])+
            '\nDurum: '+result['status']+
            '\nGeri dönüş/yedek: '+str(result.get('backup','-'))+
            '\n\nEski onaylar yeni magenta fotoğraflara aktarılmadı. '
            'Şablon İnceleme ekranından yeniden otomatik dört köşe ve insan onayı ver.',
            parent=app)
    except (OSError,ValueError,PermissionError,RuntimeError) as exc:
        messagebox.showerror('MAGENTA İŞLEMİ DURDURULDU',
            str(exc)+'\n\nEski kaynak/yedeklerin güvenliğini ve varsa rollback günlüğünü kontrol edin.',
            parent=app)
    finally:app.destroy()

if __name__=='__main__':main()
