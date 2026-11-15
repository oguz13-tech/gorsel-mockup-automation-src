"""Controlled, single-template PETEK final-style composite.

This preset deliberately does not call the general material or wall-shadow
engines. Every effect is bounded by an explicit region mask.
"""
from __future__ import annotations

import cv2
import numpy as np

from .petek_effect_assets import load_fields, manifest


def region_masks(shape, quad, approved_mask):
    h, w = shape[:2]
    panel = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(panel, np.asarray(quad, np.int32), 255)
    front_panel = (panel > 0) & (approved_mask > 0)
    slot_mask = (panel > 0) & (approved_mask == 0)
    q = np.asarray(quad, np.float32)
    y = np.arange(h, dtype=np.float32)[:, None]
    x0, x1 = float(np.min(q[:, 0])), float(np.max(q[:, 0]))
    top = float(np.min(q[:, 1]))
    bottom = float(np.max(q[:, 1]))
    pw, ph = x1 - x0, bottom - top
    top_strip = front_panel & (y <= top + (bottom - top) * 0.13)
    right_upper = front_panel & (y <= top + (bottom - top) * 0.42)
    right_upper &= (np.arange(w)[None, :] >= x0 + pw * .58)
    wall = np.zeros((h, w), bool)
    wall_x0, wall_x1 = int(min(w, x1 + pw * .015)), int(min(w, x1 + pw * .28))
    wall_y0, wall_y1 = int(max(0, top - ph * .16)), int(min(h, bottom - ph * .02))
    wall[wall_y0:wall_y1, wall_x0:wall_x1] = True
    # One shared perspective window: bars are the G3 frame; the spaces between
    # bars are the L1 light panes. Both sides use the same normalized geometry.
    frame = np.zeros((h, w), np.float32)
    for center, width in ((.10, .022), (.36, .018), (.63, .022), (.88, .018)):
        frame += np.exp(-.5 * (((x0 + center * pw) - np.arange(w)[None, :]) /
                               max(1.0, width * pw)) ** 2)
    frame = np.clip(frame, 0, 1)
    frame = cv2.GaussianBlur(frame, (0, 0), max(1.0, pw * .012))
    pane = np.clip(1.0 - frame, 0, 1)
    front_window = np.zeros((h, w), np.float32)
    front_window[int(max(0, top)):int(min(h, bottom)),
                 int(max(0, x0)):int(min(w, x1))] = pane[
                     int(max(0, top)):int(min(h, bottom)),
                     int(max(0, x0)):int(min(w, x1))]
    wall_window = np.zeros((h, w), np.float32)
    wall_window[wall_y0:wall_y1, wall_x0:wall_x1] = pane[wall_y0:wall_y1, wall_x0:wall_x1]
    return {
        "front_panel_mask": front_panel,
        "slot_mask": slot_mask,
        "top_strip_mask": top_strip,
        "right_upper_shadow_target_mask": right_upper,
        "safe_wall_spill_mask": wall & ~panel.astype(bool),
        "window_frame_field": frame,
        "window_pane_field": np.maximum(front_window, wall_window),
    }


def _blend_multiply(base, field, region, opacity):
    f = field.astype(np.float32) / 255.0
    out = base.astype(np.float32)
    amount = np.clip(f * opacity, 0, 1)
    out[region] *= (1.0 - amount[region, None])
    return np.uint8(np.clip(out + .5, 0, 255))


def _blend_screen(base, field, region, opacity):
    f = field.astype(np.float32) / 255.0
    out = base.astype(np.float32)
    amount = np.clip(f * opacity, 0, 1)
    out[region] += amount[region, None] * (255.0 - out[region])
    return np.uint8(np.clip(out + .5, 0, 255))


def apply_preset(base, quad, approved_mask, *, y3=True, g3=True, l1=True):
    masks = region_masks(base.shape, quad, approved_mask)
    fields = load_fields((base.shape[1], base.shape[0]))
    out = base.copy()
    if y3:
        texture = fields["Y3"].astype(np.float32)
        texture = cv2.GaussianBlur(texture, (0, 0), 2)
        texture = (texture - 128.0) / 127.0
        region = masks["front_panel_mask"]
        out[region] = np.uint8(np.clip(
            out[region].astype(np.float32) + texture[region, None] * 5.0, 0, 255))
    if g3:
        g3 = np.uint8(np.clip(fields["G3"].astype(np.float32) *
                              (0.25 + 0.75 * masks["window_frame_field"]), 0, 255))
        out = _blend_multiply(out, g3, masks["right_upper_shadow_target_mask"], .22)
        out = _blend_multiply(out, g3, masks["safe_wall_spill_mask"], .18)
    if l1:
        l1_field = np.uint8(np.clip(fields["L1"].astype(np.float32) *
                                    masks["window_pane_field"], 0, 255))
        out = _blend_screen(out, l1_field, masks["right_upper_shadow_target_mask"], .11)
        out = _blend_screen(out, l1_field, masks["safe_wall_spill_mask"], .095)
    # Physical slots are source-protected. The final black pass is therefore a
    # guard: it may verify darkness, but it never paints or invents a slot.
    slot_values = out[masks["slot_mask"]]
    black_pass = {
        "status": "SOURCE_PROTECTED_NO_WRITE",
        "slot_pixels": int(slot_values.shape[0]),
        "dark_slot_pixels": int(np.count_nonzero(np.mean(slot_values, axis=1) < 70))
        if slot_values.size else 0,
    }
    return out, masks, black_pass


def asset_report():
    return {
        "assets": manifest(),
        "blend_modes": {"Y3": "soft-light-like low amplitude", "G3": "multiply", "L1": "screen"},
        "opacity": {"Y3": 5.0 / 127.0, "G3_front": 0.16, "G3_wall": 0.14,
                    "L1_front": 0.10, "L1_wall": 0.06},
    }


def apply_single_vertical_shadow(base, quad, approved_mask, *, strength=0.16):
    """Apply one long, feathered, top-to-bottom window shadow on the panel."""
    h, w = base.shape[:2]
    q = np.asarray(quad, np.float32)
    x0, x1 = float(np.min(q[:, 0])), float(np.max(q[:, 0]))
    y0, y1 = float(np.min(q[:, 1])), float(np.max(q[:, 1]))
    pw, ph = max(1.0, x1 - x0), max(1.0, y1 - y0)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # One slightly slanted vertical band. Its center moves only a little over
    # the panel height, preserving the requested predominantly vertical axis.
    center = x0 + pw * (.72 + .055 * (yy - y0) / ph)
    width = max(1.0, pw * .105)
    band = np.exp(-0.5 * ((xx - center) / width) ** 2)
    along = np.clip((yy - (y0 - ph * .04)) / (ph * .90), 0.0, 1.0)
    fade = np.minimum(np.clip((y1 + ph * .05 - yy) / (ph * .18), 0.0, 1.0), 1.0)
    field = cv2.GaussianBlur(band * along * fade, (0, 0), max(2.0, pw * .018))
    panel = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(panel, q.astype(np.int32), 255)
    active = (panel > 0) & (approved_mask > 0) & (field > 0.01)
    out = base.astype(np.float32).copy()
    amount = np.clip(field * float(strength), 0.0, 0.24)
    out[active] *= (1.0 - amount[active, None])
    out = np.uint8(np.clip(out + .5, 0, 255))
    changed = np.any(out != base, axis=2)
    return out, {
        "status": "APPLIED" if int(changed.sum()) else "NO_INTERSECTION",
        "pixels": int(changed.sum()),
        "protected_changed_pixels": int(np.count_nonzero(changed & (approved_mask == 0))),
        "shadow_direction": "vertical_top_to_bottom",
        "shadow_count": 1,
        "strength": float(strength),
    }
