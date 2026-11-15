# -*- coding: utf-8 -*-
"""No access to live user's Windows data. G2 private test fixtures only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from SABLON_V2_MIMARI.tools_runner import extend_to_portrait_3x4, _write_g2_report_create_only, TOOLS
from SABLON_V2_MIMARI.core.file_safety import sha256_file
from SABLON_V2_MIMARI.core.group2_quality import inventory_review_folder,evaluate_golden_case,evaluate_private_golden_manifest


def test_g2_tools_connected_and_safe_file_layer():
    for name in ("portrait_3x4","review_folder","golden_audit"):
        assert name in TOOLS
    app=(ROOT/'SABLON_V2_MIMARI/app.py').read_text('utf-8')
    assert all('"'+name+'"' in app for name in ("portrait_3x4","review_folder","golden_audit"))
    html=(ROOT/'SABLON_V2_MIMARI/templates/tools.html').read_text('utf-8')
    assert all('launchTool(\''+name+'\'' in html for name in ("portrait_3x4","review_folder","golden_audit"))


@pytest.mark.parametrize('method',["blur","mosaic","frosted"])
def test_extend_image_no_crop_no_original_write(tmp_path,method):
    workspace=tmp_path/'live'
    workspace.mkdir()
    folder=tmp_path/'photos';folder.mkdir()
    photo=folder/'long_frame.jpg'
    Image.new('RGB',(300,120),(122,30,170)).save(photo)
    before=sha256_file(photo)
    with Image.open(photo) as decoded: expected=decoded.getpixel((150,60))
    dest,outputs=extend_to_portrait_3x4([photo],method=method,runtime_root=workspace)
    assert len(outputs)==1
    assert outputs[0].parent==dest
    assert sha256_file(photo)==before
    with Image.open(outputs[0]) as im:
        assert im.size==(1200,1600)
        assert im.getpixel((600,800))==expected
        assert im.getpixel((600,10)) != (0,0,0)


def test_3x4_name_collision_create_only_and_protected(tmp_path):
    root=tmp_path/'runtime';working=root/'2_SABLON_HAVUZU';working.mkdir(parents=True)
    src=tmp_path/'old.png';Image.new('RGB',(80,40)).save(src)
    _,result1=extend_to_portrait_3x4([src],runtime_root=root)
    b=sha256_file(result1[0]);_,result2=extend_to_portrait_3x4([src],runtime_root=root)
    assert result2[0]!=result1[0]
    assert sha256_file(result1[0])==b
    with pytest.raises(ValueError):extend_to_portrait_3x4([src],method='none',runtime_root=root)
    bad=working/'approved.png';Image.new('RGB',(60,40)).save(bad)
    with pytest.raises(ValueError):extend_to_portrait_3x4([bad],runtime_root=root)


def test_selected_review_no_moves_no_db_and_same_name_not_approved(tmp_path):
    root=tmp_path/'runtime';folder=root/'KONTROL_GEREKENLER'/'yeniden';folder.mkdir(parents=True)
    src=folder/'Wifi_Kutusu_123.png';src.write_bytes(b'improper image but inventory bytes')
    working=root/'2_SABLON_HAVUZU'/'01_Wifi_Kutusu';working.mkdir(parents=True)
    same=working/src.name;same.write_bytes(b'DIFFERENT bytes')
    report=inventory_review_folder(root,folder,'01_Wifi_Kutusu')
    assert report['count']==1 and report['auto_approved']==0 and report['auto_moved']==0
    assert report['files'][0]['matches_by_name_only'][0]['pool']=='WORKING'
    assert src.read_bytes()!=same.read_bytes()
    assert not (root/'SABLON_V2_MIMARI').exists()
    with pytest.raises(ValueError):inventory_review_folder(root,tmp_path,'01_Wifi_Kutusu')
    with pytest.raises(ValueError):inventory_review_folder(root,folder,'BAD_CAT')


def test_review_report_writes_create_only(tmp_path):
    target=tmp_path/'report.json'
    _write_g2_report_create_only(target,{'count':1})
    with pytest.raises(FileExistsError):_write_g2_report_create_only(target,{'count':2})
    assert json.loads(target.read_text('utf8'))['count']==1


def test_private_golden_mask_outside_check(tmp_path):
    root=tmp_path/'golden';root.mkdir()
    original=Image.new('RGB',(100,80),(1,2,3));original.save(root/'source.png')
    original.save(root/'render.png')
    mask=Image.new('L',(100,80),0)
    for y in range(10,50):
        for x in range(10,70):mask.putpixel((x,y),255)
    mask.save(root/'mask.png')
    case={'id':'test','category':'06_Petek_Kapama','source':'source.png','render':'render.png','mask':'mask.png'}
    result=evaluate_golden_case(case,root)
    assert result['mask_outside_pixel_check']=='PASS' and result['human_acceptance']=='PENDING'
    changed=original.copy();changed.putpixel((20,20),(3,2,1));changed.save(root/'render.png')
    assert evaluate_golden_case(case,root)['mask_outside_pixel_check']=='PASS'
    changed.putpixel((0,0),(5,6,7));changed.save(root/'render.png')
    assert evaluate_golden_case(case,root)['mask_outside_pixel_check']=='FAIL'


def test_golden_mismatched_dimensions_and_manifest_no_approval(tmp_path):
    root=tmp_path/'golden';root.mkdir()
    Image.new('RGB',(80,80),'white').save(root/'source.png')
    Image.new('RGB',(120,160),'white').save(root/'render.png')
    Image.new('L',(80,80),0).save(root/'mask.png')
    cases=[{'category':'03_Ahsap_Tablo','source':'source.png','render':'render.png','mask':'mask.png'},
           {'category':'05_Ocak_Arkasi','source':'missing.jpg','render':'render.png'}]
    (root/'manifest.json').write_text(json.dumps({'cases':cases}),encoding='utf8')
    report=evaluate_private_golden_manifest(root/'manifest.json',root)
    assert report['count']==2 and report['fail_count']==1 and report['auto_approved']==0
    assert report['results'][0]['mask_outside_pixel_check']=='NOT_COMPARABLE_DIFFERENT_IMAGE_SIZE'
    assert report['results'][0]['output_is_3x4']
    assert report['results'][1]['error']


def test_private_golden_blocks_outside_and_symlink(tmp_path):
    root=tmp_path/'golden';root.mkdir()
    Image.new('RGB',(20,30)).save(root/'a.png')
    with pytest.raises(ValueError):evaluate_golden_case({'category':'01_Wifi_Kutusu','source':'../a.png','render':'a.png'},root)
    (root/'fake.png').symlink_to(root/'a.png')
    with pytest.raises(ValueError):evaluate_golden_case({'category':'01_Wifi_Kutusu','source':'fake.png','render':'a.png'},root)


def test_review_rescan_proposal_never_approves_or_changes_db(tmp_path,monkeypatch):
    from SABLON_V2_MIMARI.core import group2_quality as g2
    root=tmp_path/'runtime'; folder=root/'KONTROL_GEREKENLER';folder.mkdir(parents=True)
    image=folder/'OcakArkasi_065.png'
    Image.new('RGB',(90,60),'white').save(image)
    class FakeAnalyzer:
        def analyze(self,path,category,manual_geometry_prior=None):
            assert manual_geometry_prior is None
            assert Path(path)==image
            return {'surface_quad':[[10,10],[70,10],[70,40],[10,40]],'confidence_total':.75,
                    'analyzer_version':'g2-test','surface_mode':'WHITE','review_status':'AUTO_PROPOSED'}
    monkeypatch.setattr('SABLON_V2_MIMARI.core.template_intelligence.TemplateAnalyzer', FakeAnalyzer)
    before=sha256_file(image)
    report=g2.propose_review_folder_corners(root,folder,'05_Ocak_Arkasi')
    assert report['scanned']==1
    assert report['proposals'][0]['approval_status']=='DRAFT_REQUIRES_HUMAN_APPROVAL'
    assert report['auto_approved']==0 and report['auto_moved']==0
    assert not (root/'SABLON_V2_MIMARI').exists()
    assert sha256_file(image)==before


def test_review_scan_petek_does_not_hallucinate_mask(tmp_path):
    from SABLON_V2_MIMARI.core.group2_quality import propose_review_folder_corners
    root=tmp_path/'runtime';folder=root/'KONTROL_GEREKENLER';folder.mkdir(parents=True)
    Image.new('RGB',(40,80)).save(folder/'petek.png')
    report=propose_review_folder_corners(root,folder,'06_Petek_Kapama')
    assert report['rescan_status']=='PETEK_REQUIRES_MASK_EDITOR'
    assert report['auto_approved']==0
