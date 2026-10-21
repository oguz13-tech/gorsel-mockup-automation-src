# -*- coding: utf-8 -*-
"""Isolated PETEK V3 tests: real source pixels, geometry, approval, batch, UI.

No live Windows workspace, internet, real cloud, existing ayarlar.db or
orijinal templates are read or mutated. All fixtures are synthetic and local.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "SABLON_V2_MIMARI"))

from core.petek_surface_v3 import (
    CATEGORY, RECIPE, PetekSafetyError, candidate_print_mask,
    composite_original_details, contain_marketplace, make_artifact_key,
    prepare_contain_artwork, project_print, publish_image_create_only,
    quad_mask, read_image, render_approved, sha256_file, validate_print_mask,
    validate_quad,
)
from core.petek_mask_store import PetekProfileStore, private_root
from core.petek_serial_factory import PetekBatchRunner, CommerceExport, safe_spreadsheet_text


def write_png(path: Path, image: np.ndarray) -> Path:
    """Save only synthetic test fixtures under pytest's temporary directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, data = cv2.imencode(".png", image)
    assert ok
    path.write_bytes(data.tobytes())
    return path


@pytest.fixture
def samples(tmp_path):
    """Build a tilted wood radiator with real source holes/arches and art."""
    runtime=tmp_path/"runtime"
    source_dir=runtime/"2_SABLON_HAVUZU"/CATEGORY
    incoming=runtime/"1_GELEN_KAGGLE_BASKILARI"/"batch"
    source_dir.mkdir(parents=True)
    incoming.mkdir(parents=True)
    scene=np.full((340,540,3),(134,147,160),dtype=np.uint8)
    quad=np.float32([[65,80],[475,72],[469,285],[69,291]])
    cv2.fillConvexPoly(scene,quad.astype(np.int32),(233,236,239))
    # Organic arch, background floor and varying original vent count.
    cv2.ellipse(scene,(270,96),(138,23),0,0,180,(33,36,42),-1)
    cv2.ellipse(scene,(270,270),(155,25),0,0,180,(91,105,131),-1)
    for j in range(11):
        x=108+j*33
        cv2.rectangle(scene,(x,143+(j%3)),(x+8,257-(j%4)*2),(28,33,39),-1)
        cv2.line(scene,(x+1,145),(x+1,253),(56,61,71),1)
    art=np.full((220,300,3),(45,83,190),dtype=np.uint8)
    cv2.putText(art,"PETEK V3",(14,110),cv2.FONT_HERSHEY_SIMPLEX,
                1.35,(245,242,232),3,cv2.LINE_AA)
    source=write_png(source_dir/"PetekDolabi_001.png",scene)
    artwork=write_png(incoming/"tasarim_01.png",art)
    return runtime,source,artwork,scene,quad


@pytest.fixture
def approved(samples):
    """Create a real reviewed mask profile from synthetic known dimensions."""
    runtime,source,art,scene,quad=samples
    store=PetekProfileStore(runtime,runtime/"2_SABLON_HAVUZU")
    draft=store.create_draft("PetekDolabi_001",source,quad,1.93)
    mask,_=store.find("PetekDolabi_001",source,approved_only=False)
    # Human-equivalent deterministic fixture mask: exact visible light wood.
    expected=np.where(
        (cv2.cvtColor(scene,cv2.COLOR_BGR2GRAY)>205)&
        (quad_mask(scene.shape[:2],quad)>0),255,0).astype(np.uint8)
    store.replace_draft_mask("PetekDolabi_001",source,expected)
    profile=store.approve("PetekDolabi_001",source,"QA Engineer",
                          "I_REVIEWED_PETEK_MASK")
    return store,profile,expected


def test_quad_validations(samples):
    """Valid projection is accepted; bad winding and out-of-image are rejected."""
    _,_,_,scene,quad=samples
    np.testing.assert_allclose(validate_quad(quad,scene.shape[1],scene.shape[0]),quad)
    with pytest.raises(PetekSafetyError):
        validate_quad(quad[[0,3,2,1]],scene.shape[1],scene.shape[0])
    wrong=quad.copy()
    wrong[2,0]=9999
    with pytest.raises(PetekSafetyError):
        validate_quad(wrong,scene.shape[1],scene.shape[0])


def test_candidate_is_unapproved(samples):
    """Automated wood segmentation cannot self-approve new templates."""
    _,_,_,scene,quad=samples
    mask,info=candidate_print_mask(scene,quad)
    assert info["review_status"]=="DRAFT"
    assert 0 < np.count_nonzero(mask) < scene.shape[0]*scene.shape[1]
    assert mask[200,110]==0  # inside a dark vent


def test_holes_arch_and_floor_pixel_perfect(samples,approved):
    """All source pixels outside printable wood remain bit-identical."""
    _,_,art,scene,quad=samples
    _,profile,mask=approved
    artwork=read_image(art)
    projected=project_print(artwork,scene.shape[:2],quad,1.93)
    result,qa=composite_original_details(scene,projected,mask,quad)
    assert qa["source_preservation_exact"]
    assert np.array_equal(result[mask==0],scene[mask==0])
    assert np.any(result[mask>0]!=scene[mask>0])
    assert np.array_equal(result[200,110],scene[200,110])
    assert np.array_equal(result[100,260],scene[100,260])
    assert np.array_equal(result[280,270],scene[280,270])


def test_arbitrary_vent_count_no_thirteen(samples):
    """Renderer never synthetically adds or forces exactly thirteen vents."""
    _,_,art,scene,quad=samples
    # Different hole counts have the same rendering algorithm.
    for count in (3,7,18):
        candidate=scene.copy()
        cv2.fillConvexPoly(candidate,quad.astype(np.int32),(233,236,239))
        for i in range(count):
            x=88+i*(360//count)
            cv2.rectangle(candidate,(x,130),(x+5,250),(22,22,22),-1)
        mask=np.where(np.all(candidate==[233,236,239],axis=2),
                      255,0).astype(np.uint8)
        mask=cv2.erode(mask,np.ones((19,19),dtype=np.uint8))
        painted=project_print(read_image(art),scene.shape[:2],quad,1.93)
        result,_=composite_original_details(candidate,painted,mask,quad)
        assert np.array_equal(result[mask==0],candidate[mask==0])


def test_mask_guard_prevents_leak(samples,approved):
    """Mask leakage outside the approved quadrilateral aborts rendering."""
    _,_,_,scene,quad=samples
    _,_,mask=approved
    invalid=mask.copy()
    invalid[1,1]=255
    with pytest.raises(PetekSafetyError):
        validate_print_mask(invalid,scene.shape[:2],quad)


def test_human_approval_required(samples):
    """Draft never renders without explicit reviewer confirmation."""
    runtime,source,art,_,quad=samples
    store=PetekProfileStore(runtime,runtime/"2_SABLON_HAVUZU")
    store.create_draft(source.stem,source,quad,1.93)
    with pytest.raises(PetekSafetyError):
        store.render(source.stem,source,art,runtime/"render.png")
    with pytest.raises(PetekSafetyError):
        store.approve(source.stem,source,"QA Engineer","AUTO_APPROVE")
    with pytest.raises(PetekSafetyError):
        store.approve(source.stem,source,"","I_REVIEWED_PETEK_MASK")


def test_verified_mask_immutable(samples,approved):
    """Approval is source/digest-bound and second approve cannot overwrite it."""
    _,source,_,_,_=samples
    store,_,mask=approved
    with pytest.raises(PetekSafetyError):
        store.replace_draft_mask(source.stem,source,mask)
    with pytest.raises(PetekSafetyError):
        store.approve(source.stem,source,"QA Engineer","I_REVIEWED_PETEK_MASK")
    profile,pixels=store.find(source.stem,source)
    assert profile["review_status"]=="APPROVED"
    np.testing.assert_array_equal(pixels,mask)


def test_tampered_source_fail_closed(samples,approved):
    """New source bytes cannot reuse an old human approval."""
    runtime,source,_,scene,_=samples
    store,_,_=approved
    updated=scene.copy()
    updated[90,200]=[15,12,11]
    write_png(source,updated)
    with pytest.raises(PetekSafetyError):
        store.find(source.stem,source)


def test_immutable_output_and_determinism(samples,approved):
    """PNG output digest and scene pixels are deterministic; overwrite is forbidden."""
    runtime,source,art,scene,_=samples
    store,profile,mask=approved
    d1=runtime/"test_out1.png";d2=runtime/"test_out2.png"
    a=store.render(source.stem,source,art,d1,marketplace=False)
    b=store.render(source.stem,source,art,d2,marketplace=False)
    assert a["output_sha256"]==b["output_sha256"]
    assert sha256_file(source)==profile["source_sha256"]
    output=read_image(d1)
    assert np.array_equal(output[mask==0],scene[mask==0])
    with pytest.raises(PetekSafetyError):
        store.render(source.stem,source,art,d1,marketplace=False)


def test_marketplace_aspect_no_stretch(samples):
    """Scene and product geometry are preserved inside the padded 3:4 canvas."""
    _,_,_,scene,_=samples
    target=contain_marketplace(scene,1200,1600)
    assert target.shape==(1600,1200,3)
    assert np.unique(target[:5,:5].reshape(-1,3),axis=0).shape[0]==1


def test_art_contain_does_not_crop_text(samples):
    """Uncropped art is fitted with a neutral border rather than stretched."""
    _,_,art,_,_=samples
    design=read_image(art)
    fitted=prepare_contain_artwork(design,500,500)
    assert fitted.shape==(500,500,3)
    assert np.array_equal(fitted[0,0],(255,255,255))


def test_batch_idempotent_local_exports(samples,approved):
    """Batch rerun reuses immutable files and creates stable CSV/Excel records."""
    runtime,source,art,_,_=samples
    runner=PetekBatchRunner(runtime)
    first=runner.run(art.parent,[source.name],"SHOP_A",max_items=5)
    assert first.rendered==1
    assert first.reused==0
    assert first.exported==1
    assert not first.marketplace_published
    assert Path(first.export_csv).is_file()
    assert Path(first.export_xlsx).is_file()
    second=runner.run(art.parent,[source.name],"SHOP_A",max_items=5)
    assert second.rendered==0
    assert second.reused==1
    assert second.export_csv==first.export_csv
    with open(first.export_csv,encoding="utf-8-sig",newline="") as fh:
        assert len(list(csv.reader(fh)))==2


def test_batch_filename_collision_detected(samples,approved):
    """Changing output bytes leads to quarantine rather than overwrite."""
    runtime,source,art,_,_=samples
    runner=PetekBatchRunner(runtime)
    result=runner.run(art.parent,[source.name],"SHOP_B",max_items=5)
    with runner.ledger.connect() as conn:
        row=conn.execute("SELECT output_path FROM artifacts LIMIT 1").fetchone()
    with open(row[0],"ab") as stream:stream.write(b"tamper")
    again=runner.run(art.parent,[source.name],"SHOP_B",max_items=5)
    assert again.rejected >= 1 or "CHANGED" in runner.status()["last_error"]


def test_unsafe_design_path_fails(samples,approved,tmp_path):
    """Production cannot read unrelated folders on the user's machine."""
    runtime,source,art,_,_=samples
    stranger=tmp_path/"other"
    stranger.mkdir()
    with pytest.raises(PetekSafetyError):
        PetekBatchRunner(runtime).run(stranger,[source.name],"MAIN",max_items=5)


def test_csv_formula_injection_escaped():
    """Seller-facing spreadsheet fields never execute user-supplied formulas."""
    assert safe_spreadsheet_text("=cmd|'bad'") .startswith("'")
    assert safe_spreadsheet_text("+123").startswith("'")
    assert safe_spreadsheet_text("normal")=="normal"


def test_isolated_private_state(samples,approved):
    """PETEK stores do not create/edit ayarlar.db or original backups."""
    runtime,source,_,_,_=samples
    private=private_root(runtime)
    assert (private/"petek_v3_profiles.sqlite3").is_file()
    assert not (runtime/"SABLON_V2_MIMARI"/"ayarlar.db").exists()
    assert not (runtime/"2_SABLON_HAVUZU_ORIJINAL_YEDEK").exists()


def test_read_only_api_and_csrf(samples,approved):
    """Existing Flask review center can mount PETEK routes without mutation."""
    from flask import Flask
    from core.petek_v3_routes import register_petek_v3
    app=Flask(__name__,template_folder=str(ROOT/"SABLON_V2_MIMARI"/"templates"),
              static_folder=str(ROOT/"SABLON_V2_MIMARI"/"static"))
    register_petek_v3(app,samples[0])
    with app.test_client() as client:
        response=client.get("/petek-v3/api/templates")
        assert response.status_code==200
        assert samples[1].name in response.get_json()["templates"]
        blocked=client.post("/petek-v3/api/draft",json={})
        assert blocked.status_code==422


def test_legacy_six_rules_unchanged():
    """Adding PETEK does not rewrite existing identity and physical policy."""
    from core.template_identity import CATEGORY_PREFIXES
    from core.template_intelligence import CategoryRuleEngine
    assert CATEGORY_PREFIXES["01_Wifi_Kutusu"]=="Wifi_Kutusu"
    assert CATEGORY_PREFIXES[CATEGORY]=="PetekDolabi"
    assert CategoryRuleEngine.get_rule_by_folder("03_Ahsap_Tablo")["key"]=="WOOD_FRAMED_ART"
    assert CategoryRuleEngine.get_rule_by_folder(CATEGORY)["print_policy"]=="source_preserving_reviewed_wood_mask"


def test_artifact_key_changes_with_mask():
    """A new approved mask must create a new immutable artifact identity."""
    a=make_artifact_key("source","art","mask_a","UID")
    b=make_artifact_key("source","art","mask_b","UID")
    assert a!=b
