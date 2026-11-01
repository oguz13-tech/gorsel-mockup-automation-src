"""V4.9.5 PETEK selective photographic magenta restoration.

Only in-memory, post-render pixels in approved geometric corridors can change.
NEVER writes source/approved masks, does not whiten wood or expand masks.
Protects the rest of the scene byte for byte; operator A/B review is mandatory.
"""
from __future__ import annotations

import cv2
import numpy as np
from . import engine

RECIPE = 'petek-geometric-final-despill-v495-1'


def _magenta_pixels(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    b, g, r = [bgr[:, :, i].astype(np.int16) for i in range(3)]
    # Detect narrow saturated magenta/rose/purple leftovers, NOT pastel room light.
    return ((hsv[:, :, 0] >= 126) & (hsv[:, :, 0] <= 178) &
            (hsv[:, :, 1] >= 85) & (hsv[:, :, 2] >= 60) &
            (b + r > 2 * g + 44) & ((b > g + 16) | (r > g + 16)))


def cleanup_petek_magenta(rendered, mask, quad, *, slot_centers=None, enabled=True,
                          printed_reference=None, source_scene=None):
    """Correct narrow magenta along all 4 edges/corners and real vent lips.

    ``slot_centers`` is the 900px rectified geometry returned from the SAME
    draw_fifteen_slots call; this avoids fabricating a second vent row.
    Changes only saturated magenta candidates in a small geometric corridor.
    """
    engine.mask_check(mask, rendered, quad)
    if not enabled:
        return rendered.copy(), {'status': 'KAPALI', 'repaired_pixels': 0, 'remaining_pixels': 0}
    q = engine.validated_quad(quad, rendered.shape).astype(np.float32)
    h, w = mask.shape
    face = engine.polygon_mask(rendered.shape, q)
    face_pixels = max(1, int(np.count_nonzero(face)))
    height = max(float(np.linalg.norm(q[0] - q[3])), float(np.linalg.norm(q[1] - q[2])))
    width = max(float(np.linalg.norm(q[0] - q[1])), float(np.linalg.norm(q[3] - q[2])))
    # Narrow image-space corridor follows full contour: 4 corners, top, bottom,
    # left and right. No centimeter assumption for perspective photography.
    thickness = int(np.clip(min(width, height) * .018, 5, 20))
    contour = np.zeros((h, w), dtype=np.uint8)
    cv2.polylines(contour, [np.rint(q).astype(np.int32)], True, 255, thickness * 2)
    edge_corridor = contour > 0

    vent_corridor = np.zeros((h, w), dtype=np.uint8)
    if slot_centers is not None:
        positions = [float(c) for c in slot_centers]
        if not (13 <= len(positions) <= 16) or not np.isfinite(positions).all():
            raise engine.MaskError('PETEK_REAL_SLOT_GEOMETRY_INVALID')
        gw, gh = 900, 690
        rect = np.float32([[0, 0], [gw-1, 0], [gw-1, gh-1], [0, gh-1]])
        matrix = cv2.getPerspectiveTransform(rect, q)
        canonical = np.zeros((gh, gw), np.uint8)
        y0, y1 = round(gh * .14), round(gh * .83)
        for x in positions:
            px = int(round(x))
            cv2.rectangle(canonical, (px - 9, y0), (px + 9, y1), 255, -1)
        vent_corridor = cv2.warpPerspective(canonical, matrix, (w, h), flags=cv2.INTER_NEAREST)

    # Physical hole centers and a 2px vent lip may contain legacy pink spills.
    # Other artwork, scene, top plate, floor and room color are out of bounds.
    preserved = mask == 0
    vent_lips = cv2.dilate(preserved.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    allowed = edge_corridor | ((vent_corridor > 0) & vent_lips)
    # Exact same print *before* material/window/vent effects is the ground
    # truth for legitimate pink/magenta artwork. Old cleanup treated every
    # magenta edge pixel as a leaked marker and could reject legal pink art
    # with PETEK_PINK_CLEANUP_INCOMPLETE_REVIEW (HTTP 409).
    #
    # In the shared preview/production path we only repair NEW magenta that
    # (1) was absent from the artwork's base render, (2) matches magenta in
    # the *original source photograph*, and (3) is inside approved print +
    # geometrically eligible edge/vent lip. A legitimate pink design is never
    # changed. The legacy standalone mode remains compatible with older tests.
    if printed_reference is not None:
        if (source_scene is None or printed_reference.shape != rendered.shape or
            printed_reference.dtype != np.uint8 or
            source_scene.shape != rendered.shape or source_scene.dtype != np.uint8):
            raise engine.MaskError('PETEK_PINK_REFERENCE_INVALID')
        allowed &= (mask > 0)  # physical vents/cabinet must never be repainted
        base_pink = _magenta_pixels(printed_reference)
        actual_pink = _magenta_pixels(rendered)
        source_marker = _magenta_pixels(source_scene)
        target = allowed & actual_pink & (~base_pink) & source_marker
        initial = int(np.count_nonzero(target))
        out = rendered.copy()
        # Restore genuine printed artwork pixels instead of inpainting from
        # neighboring ORIGINAL magenta, which would make the bleed worse.
        out[target] = printed_reference[target]
        # A new purple/magenta artifact without a source marker is ALSO a
        # quality defect. Original source-only cleanup could wrongly say
        # TEMIZ for such colors. Intentional pink is kept by base_pink.
        unexpected_new = (mask>0) & _magenta_pixels(out) & (~base_pink)
        remaining = int(np.count_nonzero(unexpected_new))
        if not np.array_equal(out[mask == 0], rendered[mask == 0]):
            raise engine.MaskError('PETEK_FINAL_CLEANUP_PROTECTED_PIXELS_CHANGED')
        return out, {
            'status': 'KAYNAK_MAGENTA_TEMIZLENDI' if initial else 'TEMIZ',
            'repaired_pixels': initial, 'detected_pixels': initial,
            'remaining_pixels': remaining,
            'legitimate_artwork_pink_pixels': int(np.count_nonzero(allowed & base_pink)),
            'source_linked_cleanup': True, 'new_unexpected_magenta_pixels': remaining,
            'changed_outside_print': 0,
            'recipe': 'petek-source-linked-pink-v496-20261101',
        }
    marker = _magenta_pixels(rendered)
    target = allowed & marker
    initial = int(target.sum())
    if initial == 0:
        return rendered.copy(), {'status':'TEMIZ', 'repaired_pixels':0,
                                 'remaining_pixels':0, 'recipe':RECIPE}
    # Refuse accidental broad repainting of a legitimate pink design/room.
    if initial > max(650, int(face_pixels * .025)):
        return rendered.copy(), {'status':'GENIS_PEMBE_ALAN_INCELEME',
                                 'repaired_pixels':0, 'remaining_pixels':initial,
                                 'recipe':RECIPE}
    out = rendered.copy()
    changed = np.zeros((h, w), bool)
    # Work on a masked COPY, never on the source. Use actual adjacent photo
    # rather than flat white/black paint. Second pass only on still-pink pixels.
    for radius in (3, 5):
        outstanding = allowed & _magenta_pixels(out)
        if not np.any(outstanding):
            break
        # Refuse extending repair beyond the geometrically authorized region.
        if int(outstanding.sum()) > max(650, int(face_pixels * .025)):
            break
        # Expand INPAINT CONTEXT only; write back exclusively authorized pixels.
        # A 1-px mask around a saturated stripe would otherwise sample nearby
        # magenta from the same stripe and falsely report a partial repair.
        context = cv2.dilate(outstanding.astype(np.uint8),
                             np.ones((5, 5), np.uint8), iterations=1) * 255
        repaired = cv2.inpaint(out, context, float(radius), cv2.INPAINT_TELEA)
        out[outstanding] = repaired[outstanding]
        changed |= outstanding
    remaining = int(np.count_nonzero(allowed & _magenta_pixels(out)))
    if np.any(out[~changed] != rendered[~changed]):
        raise engine.MaskError('PETEK_FINAL_CLEANUP_OUTSIDE_ALLOWED_CHANGED')
    return out, {'status': 'TEMIZLENDI' if remaining == 0 else 'KISMI_TEMIZLIK_INCELE',
                 'repaired_pixels': int(np.count_nonzero(changed)),
                 'remaining_pixels': remaining, 'detected_pixels': initial,
                 'changed_outside_print': int(np.count_nonzero(changed & preserved)),
                 'recipe': RECIPE}
