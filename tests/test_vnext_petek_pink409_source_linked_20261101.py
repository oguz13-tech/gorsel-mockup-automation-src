"""PETEK HTTP409: intentful pink ink is not original marker leakage."""
import numpy as np
import cv2
from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual
from MERKEZ.PETEK_V3.final_cleanup_v495 import cleanup_petek_magenta


def _sample(*, photo_magenta=True):
    h, w = 420, 600
    photo = np.full((h, w, 3), (215, 222, 228), np.uint8)
    quad = np.float32([[60, 40], [539, 40], [539, 379], [60, 379]])
    mask = np.zeros((h, w), np.uint8)
    mask[40:380, 60:540] = 255
    photo[40:380, 60:540] = (255, 0, 255) if photo_magenta else (215, 222, 228)
    for x in range(90, 515, 28):
        mask[115:310, x-2:x+3] = 0
        photo[115:310, x-2:x+3] = (20, 22, 25)
    return photo, mask, quad


def _render(scene, mask, quad, art, **options):
    return render_petek_visual(scene, art, quad, mask, 1.1163,
                               slot_mode='off', **options)


def test_large_legitimate_magenta_artwork_does_not_trigger_409():
    scene, mask, quad = _sample()
    art = np.full((350, 500, 3), (230, 15, 230), np.uint8)
    orig_scene, orig_mask = scene.copy(), mask.copy()
    result, qa = _render(scene, mask, quad, art,
                         material_effect=False, lighting='off',pink_cleanup=True)
    assert qa['pink_qa']['legitimate_artwork_pink_pixels'] > 1000
    assert qa['pink_qa']['remaining_pixels'] == 0
    assert qa['pink_qa']['repaired_pixels'] == 0
    assert np.array_equal(result[mask == 0], scene[mask == 0])
    assert np.array_equal(scene, orig_scene) and np.array_equal(mask, orig_mask)


def test_real_new_source_magenta_leak_is_restored_from_print_not_inpaint():
    scene, mask, quad = _sample()
    art = np.full((350, 500, 3), 240, np.uint8)
    def unchanged_material(scene_copy, printed, mask_copy, quad_copy, category, *, enabled):
        return printed.copy()
    before, _ = _render(scene, mask, quad, art,material_fn=unchanged_material,
                         material_effect=True, lighting='strong',pink_cleanup=False)

    def inject_new_pink(scene_copy, already_printed, mask_copy, quad_copy, category, *, enabled):
        contaminated = already_printed.copy()
        contaminated[60:95, 62:65] = (255, 0, 255)
        return contaminated

    result, qa = _render(scene, mask, quad, art, material_fn=inject_new_pink,
                         material_effect=True, lighting='strong',pink_cleanup=True)
    assert qa['pink_qa']['repaired_pixels'] >= 100
    assert qa['pink_qa']['remaining_pixels'] == 0
    assert np.array_equal(result[60:95,62:65], before[60:95,62:65])
    assert np.array_equal(result[mask == 0], scene[mask == 0])


def test_opaque_pink_artwork_not_repainted_if_photo_is_neutral():
    scene, mask, quad = _sample(photo_magenta=False)
    art = np.full((350, 500, 3), (230, 15, 230), np.uint8)
    out, qa = _render(scene,mask,quad,art,lighting='strong',material_effect=True,
                      pink_cleanup=True)
    assert qa['pink_qa']['repaired_pixels'] == 0
    assert qa['pink_qa']['remaining_pixels'] == 0
    assert np.array_equal(out[mask == 0], scene[mask == 0])


def test_hue_179_source_magenta_is_not_reported_as_new_leak():
    """A one-step lighting hue shift must not turn source ink into a 409."""
    scene, mask, quad = _sample(photo_magenta=False)
    # OpenCV hue 179 is the upper endpoint of magenta/red wrap.  The rendered
    # effect moves it one bin lower (178), but both pixels are the same source
    # marker and must remain legitimate reference ink.
    scene[180, 250] = (6, 0, 120)
    reference = scene.copy()
    rendered = reference.copy()
    rendered[180, 250] = (9, 3, 121)
    out, qa = cleanup_petek_magenta(
        rendered, mask, quad, printed_reference=reference, source_scene=scene
    )
    assert qa['remaining_pixels'] == 0
    assert qa['repaired_pixels'] == 0
    assert np.array_equal(out, rendered)


def test_reference_cleanup_rejects_bad_shapes_without_writing():
    scene,mask,quad=_sample()
    image=scene.copy()
    bad_reference=scene[2:].copy()
    try:
        cleanup_petek_magenta(image,mask,quad,printed_reference=bad_reference,
                              source_scene=scene)
    except Exception as exc:
        assert 'PETEK_PINK_REFERENCE_INVALID' in str(exc)
    else:
        raise AssertionError('Bad reference should fail closed')
    assert np.array_equal(image,scene)


def test_15_real_vents_and_pink_art_under_strong_sunlight_end_to_end():
    from tests.test_vnext_petek_dynamic_photo_count import scene_with_count
    scene, mask, quad, centers = scene_with_count(15,complete_mask=True)
    art = np.full((600, 900, 3), (225, 20, 225), np.uint8)
    saved_scene, saved_mask = scene.copy(),mask.copy()
    result, qa = render_petek_visual(scene,art,quad,mask,1.1163,
                  lighting='strong', material_effect=True,slot_mode='orta',pink_cleanup=True)
    assert qa['slot_qa']['count'] == 15
    assert qa['pink_qa']['legitimate_artwork_pink_pixels'] > 1000
    assert qa['pink_qa']['remaining_pixels'] == 0
    assert np.array_equal(result[mask==0],scene[mask==0])
    assert np.array_equal(scene,saved_scene) and np.array_equal(mask,saved_mask)
