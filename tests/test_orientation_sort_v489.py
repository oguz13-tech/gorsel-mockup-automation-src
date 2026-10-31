"""V4.9 tool tests with synthetic data only; never touch live user runtime."""
from pathlib import Path
from PIL import Image
import pytest
from SABLON_V2_MIMARI.orientation_sort_v489 import sort_folder,orientation


def make_image(path,shape,exif=None):
    img = Image.new('RGB',shape,color='magenta')
    path.parent.mkdir(parents=True,exist_ok=True)
    if exif is not None:
        e = Image.Exif(); e[274] = exif
        img.save(path,exif=e)
    else:
        img.save(path)


def test_three_categories_recursive_exif_and_preserve_originals(tmp_path):
    src=tmp_path/'input'
    dst=tmp_path/'output'
    make_image(src/'a.png',(120,90))
    make_image(src/'b.png',(90,120))
    make_image(src/'nested'/'c.png',(100,100))
    make_image(src/'nested'/'d.png',(100,99))
    make_image(src/'rotated.jpg',(140,80),exif=6)
    before={p:p.read_bytes() for p in src.rglob('*') if p.is_file()}
    result=sort_folder(src,dst)
    assert result.source_count==5
    assert result.errors==[]
    assert result.counts == {'YATAY':1,'DİKEY':2,'KARE':2}
    assert result.copied==5 and result.moved==0
    assert all(p.read_bytes()==data for p,data in before.items())
    assert result.report_path.exists()
    assert (dst/'KARE'/'c.png').exists()


def test_name_collision_existing_never_overwritten(tmp_path):
    src=tmp_path/'input';dst=tmp_path/'out'
    make_image(src/'a.png',(101,70))
    make_image(src/'nested'/'a.png',(101,70))
    (dst/'YATAY').mkdir(parents=True)
    prior = b'original data'
    (dst/'YATAY'/'a.png').write_bytes(prior)
    result=sort_folder(src,dst)
    assert (dst/'YATAY'/'a.png').read_bytes()==prior
    assert (dst/'YATAY'/'a__002.png').exists()
    assert (dst/'YATAY'/'a__003.png').exists()
    assert not result.errors


def test_move_verified_and_keep_source_when_target_restricted(tmp_path):
    src=tmp_path/'source';dst=tmp_path/'out'
    make_image(src/'a.png',(90,140))
    with pytest.raises(ValueError):
        sort_folder(src,dst,move=True,protected_roots=(src,))
    assert (src/'a.png').exists()
    result=sort_folder(src,dst,move=True)
    assert result.moved==1 and not (src/'a.png').exists()
    assert (dst/'DİKEY'/'a.png').exists()


def test_reject_nested_dest_and_protected_output(tmp_path):
    src=tmp_path/'in'
    make_image(src/'p.png',(100,100))
    with pytest.raises(ValueError):
        sort_folder(src,src/'output')
    with pytest.raises(ValueError):
        sort_folder(src,tmp_path/'protected'/'out',protected_roots=(tmp_path/'protected',))
    assert (src/'p.png').exists()


def test_broken_image_is_reported_without_any_copy(tmp_path):
    src=tmp_path/'in';dst=tmp_path/'out'
    src.mkdir()
    (src/'bad.png').write_bytes(b'NOT_A_REAL_IMAGE')
    result=sort_folder(src,dst)
    assert len(result.errors)==1
    assert not list((dst/'YATAY').iterdir())
    assert result.report_path.exists()


def test_exact_square_and_tolerance(tmp_path):
    f=tmp_path/'small.png'
    make_image(f,(100,99))
    assert orientation(f,.01)[0]=='KARE'
    assert orientation(f,0)[0]=='YATAY'
    with pytest.raises(ValueError): orientation(f,1.0)
