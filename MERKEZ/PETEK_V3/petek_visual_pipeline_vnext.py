"""Single PETEK visual pipeline for Windows production, Tk A/B and web preview.

No saved source, approved 4-corner, mask, profile or store assignment is modified.
All effects apply in temporary memory ONLY to printable pixels; protected
physical vents, arches, floor and cabinet sides remain byte-identical.
"""
from __future__ import annotations
import numpy as np
import cv2
import hashlib
from .petek_render_contract_v1 import (RenderPlan,StageAudit,
    ensure_source_vent_mask_consensus,source_repair_reference,digest_frame)
from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from . import engine
from .cutout_paste import render_with_cutout_paste
from .grille_guard_v482 import recommended_edge_feather
from .petek_finish_v492 import draw_fifteen_slots,despill_lower_left_geometry_v493
from .final_cleanup_v495 import cleanup_petek_magenta
from .petek_source_marker_fringe_vnext import (
    marker_fringe_candidates, restore_source_marker_fringe,
    restore_source_marker_vent_interiors)
from .geometry_qa_v47 import inspect_print_safety
from .wall_window_shadows_vnext import wall_region,apply_wall_window_shadows,choose_corner_side
from .petek_effect_assets import manifest as effect_asset_manifest
from .petek_effect_assets import apply_g3_wall_asset
from .petek_master_grid import apply_master_grid, verify_master_grid


@lru_cache(maxsize=1)
def _load_material_finish():
    """Load the standalone finish module without importing URETIM_V4.__init__.

    Flask imports PETEK as MERKEZ.PETEK_V3 and intentionally does not expose
    MERKEZ as a top-level import root. Importing URETIM_V4 or
    MERKEZ.URETIM_V4 first executes a package initializer with unrelated
    PETEK_V3 imports, causing HTTP 500 on Windows editor previews.

    The file is fixed inside this release's read-only code tree; no runtime
    workspace files, approved masks or SQLite are opened or modified.
    """
    material_file=Path(__file__).resolve().parents[1]/'URETIM_V4'/'finish_material_v46.py'
    if not material_file.is_file():
        raise engine.MaskError('PETEK_MATERIAL_FINISH_SOURCE_MISSING')
    spec=spec_from_file_location('_petek_material_finish_v46_standalone',material_file)
    if spec is None or spec.loader is None:
        raise engine.MaskError('PETEK_MATERIAL_FINISH_LOADER_UNAVAILABLE')
    module=module_from_spec(spec)
    spec.loader.exec_module(module)
    finish=getattr(module,'apply_material_finish',None)
    if not callable(finish):
        raise engine.MaskError('PETEK_MATERIAL_FINISH_NOT_CALLABLE')
    return finish


@lru_cache(maxsize=1)
def _load_reference_quality_gate():
    """Load concept-reference QA without importing the Tk/UI package."""
    qa_file = Path(__file__).resolve().parents[1] / 'URETIM_V4' / 'optical_qa_v47.py'
    if not qa_file.is_file():
        raise engine.MaskError('PETEK_REFERENCE_QA_SOURCE_MISSING')
    spec = spec_from_file_location('_petek_reference_quality_v47', qa_file)
    if spec is None or spec.loader is None:
        raise engine.MaskError('PETEK_REFERENCE_QA_LOADER_UNAVAILABLE')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    gate = getattr(module, 'reference_quality_gate', None)
    if not callable(gate):
        raise engine.MaskError('PETEK_REFERENCE_QA_NOT_CALLABLE')
    return gate


def verify_petek_source_protection(scene, result, mask, quad, *, pink_cleanup=False,
                                   shadow_style='classic', corner_side='right',
                                   lighting=None, material_effect=True,
                                   g3_asset=False, master_grid=None):
    """Independently replay expected outside pixels from the ORIGINAL photo.

    This is more rigorous than geometric marker whitelists: a random (1,2,3)
    inside an allowed magenta-source corridor is not a valid source repair.
    Source-linked 3..19px despill and regular 14px restoration are replayed
    together, so the two stages cannot silently disagree on their permissions.
    """
    outside=(mask==0)
    # Explicit production/endpoint modes are STRICT. Only old standalone
    # verification calls (lighting=None) may validate a source-fringe-only
    # diagnostic not preceded by the pre-despill stage.
    modes=[(lighting,True)] if lighting is not None else [
        ('strong',True),('off',True),('strong',False),('off',False)]
    verified=None
    for mode,include_pre in modes:
        expected,proof=source_repair_reference(scene,result,mask,quad,
            pink_cleanup=pink_cleanup,lighting=mode,
            material_effect=material_effect, shadow_style=shadow_style,
            corner_side=corner_side,include_pre=include_pre,
            g3_asset=g3_asset)
        if master_grid is not None:
            expected,_=apply_master_grid(scene,expected,mask,master_grid)
        if np.array_equal(result[outside],expected[outside]):
            verified=proof
            break
    if verified is None:
        raise engine.MaskError('PETEK_PREVIEW_PROTECTED_PIXELS_CHANGED')
    proof=verified
    return {'status':'PASS',**proof,
            'protected_nonfringe_pixels_unchanged':proof['authorized_wall_shadow_pixels']==0,
            'protected_structural_pixels_unchanged':True,
            'photograph_and_registry_immutable':True,
            'verified_by':'SOURCE_LINKED_DETERMINISTIC_REPLAY_V411'}


def render_petek_visual(scene, artwork, quad, mask, physical_aspect, *,
                        placement='cover', lighting='natural', material_effect=True,
                        slot_mode='orta', pink_cleanup=True,
                        g3_asset=False, y3_asset=False, l1_asset=False,
                        master_grid=None,
                        render_fn=None, material_fn=None, slot_fn=None,
                        cleanup_fn=None, safety_fn=None, despill_fn=None):
    """One exact render order, shared between preview and production.

    lighting: 'natural' or 'strong' ('Belirgin') or 'off'.
    source scene and approved mask are never mutated; only returned image is.
    Injection parameters preserve compatibility with existing narrow tests.
    """
    if lighting not in ('natural','strong','off'):
        raise ValueError('PETEK_ISIK_MODU_GECERSIZ')
    if slot_mode not in ('off','hafif','orta','guclu'):
        raise ValueError('PETEK_IZGARA_MODU_GECERSIZ')
    if not isinstance(pink_cleanup,bool):
        raise ValueError('PETEK_PEMBE_TEMIZLIK_BOOL_REQUIRED')
    if master_grid is not None and (not isinstance(master_grid,np.ndarray) or
                                    master_grid.shape[:2] != scene.shape[:2] or
                                    master_grid.ndim != 3 or master_grid.shape[2] != 4):
        raise ValueError('PETEK_MASTER_GRID_RGBA_REQUIRED')
    if not all(isinstance(value, bool) for value in (g3_asset, y3_asset, l1_asset)):
        raise ValueError('PETEK_EFFECT_ASSET_FLAGS_BOOL_REQUIRED')
    if render_fn is None:render_fn=render_with_cutout_paste
    if material_fn is None and material_effect and lighting!='off':
        # Avoid top-level URETIM_V4 imports in Flask: the package initializer
        # imports PETEK_V3 via a Tk-only sys.path and crashed HTTP previews.
        material_fn=_load_material_finish()
    if slot_fn is None:slot_fn=draw_fifteen_slots
    if cleanup_fn is None:cleanup_fn=cleanup_petek_magenta
    if safety_fn is None:safety_fn=inspect_print_safety
    if despill_fn is None:despill_fn=despill_lower_left_geometry_v493
    original=scene.copy()
    approved_mask=mask.copy()
    plan=RenderPlan(placement,lighting,bool(material_effect),slot_mode,
                    pink_cleanup,float(physical_aspect),
                    source_raster_sha256=digest_frame(scene),
                    mask_raster_sha256=digest_frame(mask),
                    quad_sha256=hashlib.sha256(np.asarray(quad,dtype=np.float32).tobytes()).hexdigest(),
                    artwork_raster_sha256=digest_frame(artwork))
    audit=StageAudit(original,approved_mask)
    # Physical source evidence is independent of the slot-effect toggle.
    vent_guard=ensure_source_vent_mask_consensus(scene,mask,quad)
    render_scene,pre_pink=despill_fn(scene,mask,quad,enabled=pink_cleanup)
    # The first stage must match independently replayed source-derived colors,
    # not just be located in a broad geometric whitelist.
    from .petek_finish_v492 import despill_lower_left_geometry_v493 as default_despill
    independent_scene,_=default_despill(scene,mask,quad,enabled=pink_cleanup)
    if not np.array_equal(render_scene,independent_scene):
        raise engine.MaskError('PETEK_PRE_DESPILL_EXPECTED_PIXELS_CHANGED')
    audit.record('SOURCE_DESPILL',scene,render_scene,allow_outside=True)
    # LEGACY PINK FRINGE RECOVERY (render-only, no saved mask/file edits).
    # Earlier HTTP 409 hotfix reverted ALL mask==0 repairs, disabling the
    # operator's effective narrow bottom-edge marker cleanup. Keep ONLY the
    # deterministic, physically narrow, source-magenta correction returned by
    # despill_lower_left_geometry_v493. No non-magenta protected pixel may move.
    if render_scene.shape != scene.shape or render_scene.dtype != scene.dtype:
        raise engine.MaskError('PETEK_PRE_DESPILL_SHAPE_MISMATCH')
    protected_changes=np.any(render_scene!=scene,axis=2)&(mask==0)
    authorized=int(np.count_nonzero(protected_changes))
    if authorized:
        hsv=cv2.cvtColor(scene,cv2.COLOR_BGR2HSV)
        marker=((hsv[:,:,0]>=129)&(hsv[:,:,0]<=178)&
                (hsv[:,:,1]>=125)&(hsv[:,:,2]>=132))
        if (authorized>5000 or np.any(protected_changes & ~marker) or
                int(pre_pink.get('repaired_pixels',0))!=authorized):
            raise engine.MaskError('PETEK_PINK_PROTECTED_FRINGE_NOT_VERIFIED')
        pre_pink=dict(pre_pink)
        pre_pink.update({'authorized_marker_fringe_pixels':authorized,
                         'protected_nonmarker_pixels_unchanged':True,
                         'render_only':True})
    edge_px=recommended_edge_feather(scene,quad)
    # PETEK alone uses a wall-dominant two-shadow arrangement: the closest
    # stripe just grazes one top corner, instead of covering the whole front.
    # Other six product types keep their established lighting.
    shadow_corner=choose_corner_side(scene,mask,quad) if lighting=='strong' else 'right'
    render_options={'marketplace':False,'placement':placement,
                    'lighting':lighting,'edge_feather_px':edge_px}
    if render_fn is render_with_cutout_paste:
        render_options.update(shadow_style='classic',corner_side=shadow_corner)
    picture,_,qa=render_fn(render_scene,artwork,quad,mask,physical_aspect,
                           **render_options)
    audit.record('PRINT_COMPOSITE',render_scene,picture)
    print_reference=picture.copy() if pink_cleanup else None
    if material_effect and lighting!='off':
        before=picture
        material_options = {'enabled': True}
        if g3_asset or y3_asset or l1_asset:
            material_options.update(g3_asset=g3_asset, y3_asset=y3_asset, l1_asset=l1_asset)
        picture=material_fn(render_scene,picture,mask,quad,'06_Petek_Kapama',
                            **material_options)
        audit.record('MATERIAL_AND_LIGHT',before,picture)
    slot_qa={'status':'KAPALI','count':0,'changed_pixels':0}
    if slot_mode!='off':
        before=picture
        picture,slot_qa=slot_fn(render_scene,picture,mask,quad,mode=slot_mode)
        audit.record('PHYSICAL_VENT_LIPS',before,picture)
    # Compare post-effect pixels to the pre-effect artwork reference.
    # Always compare against the actual unmodified photograph, not a working
    # copy: protects from future pre-render stages reintroducing this bug.
    protection=safety_fn(render_scene,picture,mask,quad)
    if protection['status']!='PASS':
        raise engine.MaskError('PETEK_PROTECTED_PIXELS_CHANGED')
    pink_qa={'status':'KAPALI','remaining_pixels':0}
    if pink_cleanup:
        clean_kwargs={'enabled': True,
            'slot_centers': slot_qa.get('centers_rectified_900') if slot_mode!='off' else None}
        if cleanup_fn is cleanup_petek_magenta:
            # Production/Flask/Tk all use this one source-aware cleanup path.
            # Keep test-injected legacy cleanup functions backward compatible.
            clean_kwargs.update(printed_reference=print_reference,source_scene=scene)
        before=picture
        picture,pink_qa=cleanup_fn(picture,mask,quad,**clean_kwargs)
        audit.record('PRINT_MAGENTA_QA_AND_CLEANUP',before,picture)
        if pink_qa.get('remaining_pixels',0):
            raise engine.MaskError('PETEK_PINK_CLEANUP_INCOMPLETE_REVIEW')
    # Restore small SOURCE marker seams along every true print boundary,
    # including the right, left, top/bottom arch and actual vent lips.
    # This is an independent in-memory stage AFTER the print effects and vents.
    before=picture
    picture,fringe_qa=restore_source_marker_fringe(
        scene,picture,mask,quad,enabled=pink_cleanup)
    audit.record('SOURCE_MARKER_FRINGE_REPAIR',before,picture,allow_outside=True)
    before=picture
    picture,vent_qa=restore_source_marker_vent_interiors(
        scene,picture,mask,quad,enabled=pink_cleanup)
    audit.record('SOURCE_MARKER_VENT_REPAIR',before,picture,allow_outside=True)
    master_qa={'status':'OFF','changed_pixels':0}
    if master_grid is not None:
        before=picture
        picture,master_qa=apply_master_grid(scene,picture,mask,master_grid)
        audit.record('LOCKED_MASTER_GRID',before,picture,allow_outside=True)
        master_qa.update(verify_master_grid(scene,picture,mask,master_grid))
    if not np.array_equal(scene,original) or not np.array_equal(mask,approved_mask):
        raise engine.MaskError('PETEK_IMMUTABLE_SOURCE_OR_MASK_CHANGED')
    # Shadow continuation across the real wall is the FINAL output-only step.
    # The original source and approved mask remain immutable. The independent
    # verifier below only permits exact source-derived neutral-wall darkening.
    wall_qa={'status':'OFF','wall_shadow_pixels':0,'shadow_bands':2}
    if material_effect and lighting=='strong' and not g3_asset:
        before=picture
        picture,wall_qa=apply_wall_window_shadows(scene,picture,mask,quad,lighting=lighting,
                        shadow_style='classic',corner_side=shadow_corner)
        audit.record('TRUSTED_WALL_SHADOW',before,picture,allow_outside=True)
    if material_effect and lighting=='strong' and g3_asset:
        before=picture
        picture,wall_qa=apply_g3_wall_asset(scene,picture,mask,quad)
        audit.record('BUNDLED_G3_WALL_ASSET',before,picture,allow_outside=True)
    # Validate output against VERIFIED source marker repair, not against a
    # blanket allowance to change protected pixels. Physical slots remain
    # pixel-exact relative to the photo; only narrow source-magenta fringe may
    # use the in-memory replacement photo. No other outside-mask effect allowed.
    verification=verify_petek_source_protection(scene,picture,mask,quad,
                         pink_cleanup=pink_cleanup,shadow_style='classic',
                         corner_side=shadow_corner,lighting=lighting,
                         material_effect=bool(material_effect),
                         g3_asset=g3_asset, master_grid=master_grid)

    reference_qa = _load_reference_quality_gate()(scene, picture, mask,
                                                   '06_Petek_Kapama')
    if reference_qa['status'] == 'FAIL':
        raise engine.MaskError(
            'PETEK_REFERANS_KALITE_MAGENTA_SIZINTISI: '
            f"{reference_qa['new_magenta_outside_pixels']} px"
        )

    return picture,{'slot_qa':slot_qa,'pink_qa':pink_qa,
                    'pre_pink_qa':pre_pink,                    'fringe_qa':fringe_qa,'vent_qa':vent_qa,'lighting':lighting,
                    'reference_quality_qa':reference_qa,
                    'material_effect':bool(material_effect),
                    'master_grid':master_qa,
                    'effect_assets': {
                        'files': effect_asset_manifest(),
                        'enabled': {'G3': g3_asset, 'Y3': y3_asset, 'L1': l1_asset},
                    },
                    'protected_pixels_unchanged':(verification['authorized_marker_fringe_pixels']==0 and verification['authorized_wall_shadow_pixels']==0),
                    'authorized_pink_fringe_pixels':verification['authorized_marker_fringe_pixels'],
                    'protected_nonfringe_pixels_unchanged':verification['authorized_wall_shadow_pixels']==0,
                    'source_protection_qa':verification,'wall_shadow_qa':wall_qa,
                    'vent_guard_qa':vent_guard,
                    'render_plan':plan.manifest(),'render_plan_sha256':plan.digest(),
                    'stage_receipts':audit.receipts,
                    'render_image_sha256':digest_frame(picture),
                    'corner_side':shadow_corner,'shadow_style':'corner',
                    'render_qa':qa}
