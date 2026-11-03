"""Prepare the reported Gemini mask for visual review; never auto-approve it."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from PETEK_V3 import engine
from PETEK_V3.registry import Registry
from PETEK_V3.petek_render_contract_v1 import temporary_photo_protected_preview_mask

UID='Gemini_Generated_Image_65hptp65hptp65hp__2_'
EXPECTED_SOURCE='cd8e1d03d8207537b7d5a44fbc6e2aba9d5e23df56f09f56f3d910dbb2b190ae'


def prepare(registry):
    profile,mask=registry.get(UID)
    if profile['source_sha'] != EXPECTED_SOURCE:
        raise engine.MaskError('Beklenen Gemini kaynak fotoğrafı değil; otomatik taslak hazırlanmadı.')
    scene=engine.read_bgr(profile['source'])
    repaired,proof=temporary_photo_protected_preview_mask(scene,mask,profile['quad'])
    if proof['source_vent_count'] != 10:
        raise engine.MaskError('Kaynakta 10 yarık doğrulanamadı; taslak hazırlanmadı.')
    draft=dict(profile,uid=UID+'_r_v4_'+engine.mask_hash(repaired)[:10],status='DRAFT')
    return draft,repaired,proof


def main():
    import tkinter as tk
    from tkinter import messagebox
    from PETEK_V3.gui import MaskEditor
    root=tk.Tk()
    root.title('V4 — 10 yarıklı PETEK maske incelemesi')
    root.geometry('560x100')
    tk.Label(root,text='Kaynak fotoğraf ve mevcut onaylı maske korunur.\n'
             'Düzenleyicide önizle → taslak kaydet → kontrol edip üretime aç.').pack(pady=16)
    try:
        registry=Registry()
        draft,mask,proof=prepare(registry)
        editor=MaskEditor(root,registry=registry)
        editor.load(Path(draft['source']))
        editor.uid.set(draft['uid'])
        editor.mask=mask.copy()
        editor.quad=draft['quad']
        editor.curves={'top':[],'bottom':[]}
        editor.curve_base=None
        editor._loaded_approved=False
        editor.confirm.set(False)
        editor.status.set('10 yarık kaynaktan ölçüldü. Yeni maske henüz kaydedilmedi/onaylanmadı. '
                          'Gerçek desenle önizleyin, ardından 4 ve 5. adımları uygulayın.')
        editor.refresh()
    except Exception as exc:
        messagebox.showerror('Maske taslağı hazırlanamadı',str(exc),parent=root)
        root.destroy()
        return 1
    root.mainloop()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
