"""Current UI contract — critical routes preserved, obsolete daily shortcut hidden.

Historical V3.14 source kept in GUNLUK for read-only reference; since V4.4 the
operator's one supported 7-category production entrance replaces it in the UI.
"""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from merkez import Center


def test_real_center_exposes_one_production_entry_and_review_tools():
    app=Center()
    try:
        app.root.update_idletasks()
        labels=[]
        def walk(w):
            try:
                if w.winfo_class()=='TButton':labels.append(w.cget('text'))
                for child in w.winfo_children():walk(child)
            except Exception:pass
        walk(app.root)
        for part in ('7 KATEGORİ — ŞABLON / 4 KÖŞE / PETEK MASKE', '6 KATEGORİ — PROFESYONEL',
                     '7 KATEGORİ — SERİ GÖRSEL ÜRET', 'PETEK — ŞABLON / MASKE',
                     'GELİŞMİŞ ARAÇLAR', 'Kurulum / Klasör / DB Durumu',
                     'Kesinti / Kilit Kurtarma'):
            assert any(part in title for title in labels),(part,labels)
        assert not any('GÜNLÜK SERİ ÜRETİM' in text or 'ONAYLI 10 ŞABLON' in text
                       for text in labels)
        assert not app.advanced_panel.winfo_manager()
        app.toggle_advanced()
        assert app.advanced_panel.winfo_manager()
        app.toggle_advanced()
        assert not app.advanced_panel.winfo_manager()
        assert app.runtime_text.get()
    finally:
        app.root.destroy()
