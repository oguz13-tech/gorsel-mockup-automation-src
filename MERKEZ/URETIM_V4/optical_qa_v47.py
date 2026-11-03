"""Objective, repeatable optical A/B QA; not a substitute for human approval.

Tracks printed-region effect visibility, clipping (white/black lost details),
input text-edge retention, and changes outside the protected print mask.
"""
from __future__ import annotations
import numpy as np
import cv2
from pathlib import Path
try:
    from .finish_material_v46 import GLASS, DAYLIGHT
except ImportError:  # standalone loader used by the PETEK HTTP preview
    # The HTTP preview loads this file directly to avoid importing the Tk/UI
    # package. Keep the category contract local in that mode.
    GLASS = frozenset(('02_Cam_Tablo_Dikey', '02_Cam_Tablo_Yatay',
                       '04_Cam_Dograma', '05_Ocak_Arkasi'))
    DAYLIGHT = frozenset(('03_Ahsap_Tablo', '06_Petek_Kapama'))


REFERENCE_PROFILES = {
    "glass": {
        "categories": sorted(GLASS),
        "targets": ("clean_rodaj_edge", "visible_soft_reflection", "no_hardware"),
    },
    "wood_mdf": {
        "categories": sorted(DAYLIGHT),
        "targets": ("thin_natural_frame", "matte_surface_texture", "clean_edge"),
    },
}
REFERENCE_ASSET_NAMES = {
    "glass": "cam_urunleri.png",
    "wood_mdf": "ahsaplar.png",
    "leak_examples": "sizintilar.png",
}


def _magenta_pixels(image: np.ndarray) -> np.ndarray:
    """Detect chroma-key magenta, not ordinary artwork pinks.

    The key is intentionally conservative: only highly saturated pixels whose
    red and blue channels agree are classified.  A print may contain pink or
    purple artwork inside the approved mask; only *new* key-colour pixels
    outside the printable region are a hard failure.
    """
    bgr = np.asarray(image)
    if bgr.ndim != 3 or bgr.shape[2] != 3:
        raise ValueError("REFERENCE_QA_IMAGE_SHAPE")
    b, g, r = [bgr[..., i].astype(np.int16) for i in range(3)]
    return (b >= 180) & (r >= 180) & (g <= 95) & (np.abs(b - r) <= 28)


def reference_quality_gate(before: np.ndarray, after: np.ndarray,
                           mask: np.ndarray, category: str) -> dict:
    """Measure concept-reference quality without copying reference pixels.

    The attached glass/wood examples define qualitative targets only. This
    gate therefore checks objective invariants (new magenta outside the print
    area, edge spill, and whether material effects have measurable signal) and
    leaves artistic similarity to human review.
    """
    if (before.shape != after.shape or before.dtype != np.uint8 or
            after.dtype != np.uint8 or mask.shape != before.shape[:2]):
        raise ValueError("REFERENCE_QA_SHAPE")
    printable = mask > 0
    if not np.any(printable):
        raise ValueError("REFERENCE_QA_EMPTY_MASK")
    source_magenta = _magenta_pixels(before)
    output_magenta = _magenta_pixels(after)
    new_magenta_outside = output_magenta & ~source_magenta & ~printable
    changed = np.any(before != after, axis=2)
    # A narrow perimeter score is diagnostic; category-specific wall shadows
    # are validated by their existing deterministic guards and are not
    # silently treated as magenta/edge failures here.
    perimeter = cv2.dilate(np.uint8(printable), np.ones((3, 3), np.uint8), 1) > 0
    edge_spill = changed & ~printable & perimeter
    gray = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY)
    inside_gray = gray[printable].astype(np.float32)
    gradient = cv2.Laplacian(gray, cv2.CV_32F)
    texture_signal = float(np.mean(np.abs(gradient[printable])))
    profile_name = "glass" if category in GLASS else ("wood_mdf" if category in DAYLIGHT else "generic")
    asset_root = Path(__file__).resolve().parents[2] / "Kalite_Kontrol_Gorselleri"
    asset_names = [REFERENCE_ASSET_NAMES[profile_name], REFERENCE_ASSET_NAMES["leak_examples"]] if profile_name in REFERENCE_ASSET_NAMES else []
    result = {
        "status": "FAIL" if int(np.count_nonzero(new_magenta_outside)) else "CHECK_HUMAN",
        "reference_profile": profile_name,
        "reference_is_concept_only": True,
        "new_magenta_outside_pixels": int(np.count_nonzero(new_magenta_outside)),
        "edge_spill_pixels": int(np.count_nonzero(edge_spill)),
        "inside_luma_std": round(float(np.std(inside_gray)), 3),
        "material_texture_signal": round(texture_signal, 3),
        "targets": list(REFERENCE_PROFILES.get(profile_name, {}).get("targets", ())),
        "reference_assets_present": {
            name: (asset_root / name).is_file() for name in asset_names
        },
        "reference_asset_policy": "CONCEPT_ONLY_NO_PIXEL_COPY",
        "human_review_required": True,
    }
    if result["status"] == "FAIL":
        result["reason"] = "NEW_CHROMA_MAGENTA_OUTSIDE_PRINT_AREA"
    elif category in GLASS and texture_signal < 1.0:
        result["review_flag"] = "GLASS_REFLECTION_SIGNAL_LOW"
    elif category in DAYLIGHT and texture_signal < 0.7:
        result["review_flag"] = "MATERIAL_TEXTURE_SIGNAL_LOW"
    return result

def measure_effect(before, after, mask, category):
    if before.shape!=after.shape or before.dtype!=np.uint8 or mask.shape!=before.shape[:2]:
        raise ValueError('OPTICAL_QA_SHAPE')
    selected=mask>0
    if not np.any(selected):raise ValueError('OPTICAL_QA_EMPTY')
    delta=np.abs(before.astype(np.int16)-after.astype(np.int16))
    outside=int(np.count_nonzero(np.any(delta>0,axis=2) & ~selected))
    signal=delta[selected]
    pre=cv2.cvtColor(before,cv2.COLOR_BGR2GRAY)
    post=cv2.cvtColor(after,cv2.COLOR_BGR2GRAY)
    edge=cv2.Canny(pre,70,140)>0
    important=edge & selected
    pixel_diff=signal.mean() if len(signal) else 0
    loss=float(np.mean(np.abs(post[important].astype(np.float32)-pre[important].astype(np.float32)))) if important.any() else 0.
    return {'category':category,'protected_pixel_changes':outside,
            'mean_inside_delta':round(float(pixel_diff),3),
            'p95_inside_delta':float(np.percentile(signal,95)),
            'detail_edge_delta':round(loss,3),
            'status':'FAIL' if outside else ('NO_VISIBLE_EFFECT' if pixel_diff<0.4 and category in GLASS|DAYLIGHT else 'CHECK_HUMAN')}
