"""Requires an X server (Windows / Xvfb)."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from merkez import Center

def test_real_center_exposes_all_critical_routes():
    app=Center();app.root.update_idletasks()
    labels=[]
    def walk(w):
        try:
            if w.winfo_class()=='TButton':labels.append(w.cget('text'))
            for child in w.winfo_children():walk(child)
        except Exception:pass
    walk(app.root)
    for part in ('6 KATEGORİ — ŞABLON / 4 KÖŞE','6 KATEGORİ — PROFESYONEL',
                 '6 KATEGORİ — GÜNLÜK', 'PETEK — ŞABLON / MASKE','PETEK — SERİ'):
        assert any(part in title for title in labels),(part,labels)
    assert '7 kategori / kurulum kontrolü' in labels
    assert app.runtime_text.get()
    app.root.destroy()
