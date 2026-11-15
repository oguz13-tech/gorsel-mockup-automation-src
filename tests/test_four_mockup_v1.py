"""Geliştirme 13: 4 Farklı Mockup / 4 Farklı Final modu — tamamen izole (tmp) testler."""
from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))

from URETIM_V4 import four_mockup_v1 as fm  # noqa: E402
from URETIM_V4 import unified_batch as ub  # noqa: E402
from URETIM_V4 import uretim_gecmisi_v1 as history  # noqa: E402
from URETIM_V4.store_profiles_v47 import StoreProfiles  # noqa: E402
from PETEK_V3 import engine as petek_engine  # noqa: E402


def _png(path: Path, color, size=(1200, 1600)):
    arr = np.zeros((size[1], size[0], 3), np.uint8)
    arr[:] = color
    arr[::7, ::5] = (255 - color[0], color[1], 200)
    Image.fromarray(arr).save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _template(tmp: Path, uid: str, color):
    src = tmp / 'pool' / f'{uid}.png'
    src.parent.mkdir(exist_ok=True)
    sha = _png(src, color)
    return {'uid': uid, 'category': '06_Petek_Kapama', 'source': str(src), 'source_sha': sha,
            'mask_sha': 'm' * 64, 'engine_type': 'LEGACY', 'orientation': 'D',
            'quad': [[0, 0], [1, 0], [1, 1], [0, 1]], 'physical_aspect': 0.75, 'legacy_data': {}}


@pytest.fixture
def world(tmp_path, monkeypatch):
    state = tmp_path / 'state'
    engine = ub.UnifiedV4Batch(state)
    colors = [(30, 60, 90), (60, 90, 30), (90, 30, 60), (120, 120, 40), (10, 200, 80), (200, 10, 80),
              (50, 50, 200), (150, 80, 20)]
    templates = [_template(tmp_path, f'wudie_t{i}', colors[i]) for i in range(5)] + \
                [_template(tmp_path, f'omz_t{i}', colors[5 + i]) for i in range(3)]
    mgr = StoreProfiles(state)
    mgr.add_store('Adeno')
    mgr.assign('Adeno', templates[:5], all_approved=templates)
    mgr.add_store('OmzHome')
    mgr.assign('OmzHome', templates[5:], all_approved=templates)
    monkeypatch.setattr(engine, 'discover_templates',
                        lambda **kw: (list(templates), {'per_category_counts': {}, 'skipped': []}))
    monkeypatch.setattr(ub, '_build_legacy_category_mask',
                        lambda scene, quad, data: np.zeros(scene.shape[:2], np.uint8))
    calls = {'n': 0}

    def fake_render(**kw):
        calls['n'] += 1
        scene = kw['source_scene']
        return np.array(scene), {}, 'legacy'
    monkeypatch.setattr(ub, '_render_job_picture', fake_render)
    designs = tmp_path / 'designs'
    designs.mkdir()
    for i in range(1, 4):
        _png(designs / f'Ham{i}.png', (i * 40, 80, 120))
    return {'engine': engine, 'templates': templates, 'designs': designs, 'state': state,
            'calls': calls, 'tmp': tmp_path}


def _run(w, stores, four=True, designs=None, four_mockup=None, external_designs=False, **kw):
    stored = StoreProfiles(w['state']).load()['stores']
    uids = sorted({k.split(':', 1)[1].split('@', 1)[0] for st in stores for k in stored[st]['templates']})
    return w['engine'].run(designs or w['designs'], selected_uids=uids, selected_stores=stores,
                           group='LOCAL', external_designs=external_designs, four_mockup=(four_mockup or {}) if four else None, **kw)


def _rows(w):
    return [r for r in w['engine'].ledger.successful() if r['artifact_kind'] == 'overlay']


def test_label_bottom_right_zero_margin_and_pixels_preserved(tmp_path):
    clean = tmp_path / 'c.png'
    _png(clean, (100, 100, 100))
    data, manifest = fm.render_final_bytes(clean, '96CM', {'enabled': True})
    final = np.array(Image.open(io.BytesIO(data)).convert('RGB'))
    base = np.array(Image.open(clean).convert('RGB'))
    x, y = manifest['position']
    assert x + (1200 - x) == 1200 and y + (1600 - y) == 1600  # dokunuyor: sıfır boşluk
    assert not np.array_equal(final[y:, x:], base[y:, x:])
    assert fm.pixels_equal_outside_label(base, final, (x, y))
    assert manifest['text'] == 'Genişlik: 96 cm'


def test_overlay_off_keeps_every_pixel(tmp_path):
    clean = tmp_path / 'c.png'
    _png(clean, (100, 100, 100))
    data, manifest = fm.render_final_bytes(clean, '76CM', {'enabled': False})
    assert manifest['kind'] == 'off'
    assert np.array_equal(np.array(Image.open(io.BytesIO(data)).convert('RGB')),
                          np.array(Image.open(clean).convert('RGB')))


def test_custom_overlay_mismatch_blocked_unless_confirmed(tmp_path):
    clean = tmp_path / 'c.png'
    _png(clean, (100, 100, 100))
    overlay = tmp_path / 'overlay96.png'
    Image.new('RGBA', (200, 60), (255, 0, 0, 255)).save(overlay)
    with pytest.raises(fm.FourMockupError, match='UYUSMAZLIGI'):
        fm.render_final_bytes(clean, '76CM', {'enabled': True, 'path': str(overlay)})
    data, m = fm.render_final_bytes(clean, '96CM', {'enabled': True, 'path': str(overlay)})
    assert m['kind'] == 'custom' and m['position'] == [1000, 1540]
    _, m2 = fm.render_final_bytes(clean, '76CM', {'enabled': True, 'path': str(overlay), 'allow_mismatch': True})
    assert m2['mismatch_allowed']


def test_overlay_names_default_file_used(tmp_path):
    clean = tmp_path / 'c.png'
    _png(clean, (100, 100, 100))
    labels = tmp_path / fm.LABEL_FOLDER
    labels.mkdir()
    Image.new('RGBA', (150, 40), (0, 255, 0, 255)).save(labels / 'overlay116.png')
    _, m = fm.render_final_bytes(clean, '116CM', {'enabled': True}, label_dir=labels)
    assert m['kind'] == 'default_file' and m['file'] == 'overlay116.png'


def test_missing_templates_reported_never_repeated(world):
    plan = [('OmzHome', world['templates'][5:])]  # yalnız 3
    report = fm.preflight(plan, design_count=3)
    assert not report['ready'] and 'yalnız 3' in report['problems'][0]
    with pytest.raises(petek_engine.MaskError, match='DORT_MOCKUP_SABLON_EKSIK'):
        _run(world, ['OmzHome'])


def test_mutual_exclusion_with_old_overlay_mode(world):
    with pytest.raises(petek_engine.MaskError, match='DORT_MOCKUP_MOD_CAKISMASI'):
        _run(world, ['Adeno'], petek_overlay_enabled=True)


def test_one_design_one_store_four_outputs_codes_and_order(world):
    d = world['tmp'] / 'one'
    d.mkdir()
    _png(d / 'Ham1.png', (10, 20, 30))
    res = _run(world, ['Adeno'], designs=d)
    rows = sorted(_rows(world), key=lambda r: ub.excel_row_sort_key(r))
    assert len(rows) == 4 and res['four_mockup']['successful'] == 4
    assert [r['overlay_cm'] for r in rows] == ['76CM', '96CM', '116CM', '136CM']
    assert len({r['sku'] for r in rows}) == 4
    assert [r['sku'].split('-', 1)[0] for r in rows] == ['76', '96', '116', '136']
    assert len({r['uid'] for r in rows}) == 4  # dört farklı şablon
    for r in rows:
        assert Path(r['output']).is_file() and r['output'].endswith(f"__W{r['overlay_cm'][:-2]}.png")
    from URETIM_V4.store_identity_v485 import trendyol_codes, petek_measurement_codes
    base = trendyol_codes('Ham1.png', 'Adeno', '06_Petek_Kapama')
    models = {petek_measurement_codes(base, r['overlay_cm'])['model'] for r in rows}
    barcodes = {petek_measurement_codes(base, r['overlay_cm'])['barcode'] for r in rows}
    assert len(models) == 1 and len(barcodes) == 4
    assert res['status'] in ('LOCAL_READY', 'PARTIAL')
    # temiz görseller korunur ve ayrı klasörde
    clean = [r for r in world['engine'].ledger.successful() if r['artifact_kind'] == 'clean']
    assert len(clean) == 4 and all('Overlaysızlar' in r['output'] for r in clean)


def test_one_design_three_stores_isolation_twelve(world):
    # üçüncü mağaza: 4 yeni şablon
    extra = [_template(world['tmp'], f'wd_t{i}', (i * 20 + 5, 5, 5)) for i in range(4)]
    world['templates'].extend(extra)
    mgr = StoreProfiles(world['state'])
    mgr.add_store('Wudie')
    mgr.assign('Wudie', extra, all_approved=world['templates'])
    # OmzHome yalnız 3 şablon -> 4'e tamamla
    more = _template(world['tmp'], 'omz_t3', (77, 77, 7))
    world['templates'].append(more)
    mgr.assign('OmzHome', [more], all_approved=world['templates'])
    d = world['tmp'] / 'one'
    d.mkdir()
    _png(d / 'Ham1.png', (10, 20, 30))
    res = _run(world, ['Adeno', 'OmzHome', 'Wudie'], designs=d)
    rows = _rows(world)
    assert len(rows) == 12 and res['four_mockup']['successful'] == 12
    by_store = {}
    for r in rows:
        by_store.setdefault(Path(r['output']).relative_to(world['engine'].output).parts[0], set()).add(r['uid'])
    assert set(by_store) == {'Adeno', 'OmzHome', 'Wudie'}
    assert all(len(v) == 4 for v in by_store.values())
    assert not (by_store['Adeno'] & by_store['OmzHome'])  # mağaza izolasyonu


def test_resume_does_not_rerender_and_final_idempotent(world):
    d = world['tmp'] / 'one'
    d.mkdir()
    _png(d / 'Ham1.png', (10, 20, 30))
    _run(world, ['Adeno'], designs=d)
    renders = world['calls']['n']
    first = {r['key']: r['output_sha'] for r in _rows(world)}
    res = _run(world, ['Adeno'], designs=d)
    assert world['calls']['n'] == renders  # yeniden render yok
    assert res['four_mockup']['successful'] == 0 and res['four_mockup']['skipped'] == 4
    assert {r['key']: r['output_sha'] for r in _rows(world)} == first


def test_overlay_choice_change_does_not_rerender_clean_and_keeps_identity(world):
    d = world['tmp'] / 'one'
    d.mkdir()
    _png(d / 'Ham1.png', (10, 20, 30))
    _run(world, ['Adeno'], designs=d)
    renders = world['calls']['n']
    sku_before = sorted(r['sku'] for r in _rows(world))
    _run(world, ['Adeno'], designs=d, four_mockup={'overlays': {'96CM': {'enabled': False}}})
    assert world['calls']['n'] == renders
    assert sorted({r['sku'] for r in _rows(world)}) == sku_before  # kimlik aynı


def test_history_session_recorded(world):
    d = world['tmp'] / 'one'
    d.mkdir()
    _png(d / 'Ham1.png', (10, 20, 30))
    _run(world, ['Adeno'], designs=d)
    sessions = history.list_sessions(world['state'])
    assert len(sessions) == 1
    s = sessions[0]
    assert s['mode'] == 'four_mockup' and s['stores'] == ['Adeno'] and s['successful'] == 4
    assert s['design_folder'] == str(d.resolve()) and s['elapsed_seconds'] > 0
    assert s['per_store']['outputs'] == {'Adeno': 4}
    assert history.average_seconds_per_image(world['state'], 'four_mockup') is not None


# --- Excel uçtan uca ---------------------------------------------------------
def _fake_links(state: Path, skip_cm=None):
    import sqlite3
    with sqlite3.connect(state / 'cloud_urls_v43.sqlite3') as db:
        db.execute("""CREATE TABLE IF NOT EXISTS cloud_link (artifact_key TEXT PRIMARY KEY,
            output_sha TEXT NOT NULL, url TEXT NOT NULL, recorded_at TEXT, provider TEXT,
            remote_sha TEXT, remote_width INTEGER, remote_height INTEGER, remote_format TEXT)""")
    with sqlite3.connect(state / 'v4_ortak_uretim.sqlite3') as led, \
            sqlite3.connect(state / 'cloud_urls_v43.sqlite3') as db:
        led.row_factory = sqlite3.Row
        for r in led.execute("SELECT * FROM artifact WHERE status='RENDERED' AND artifact_kind='overlay'"):
            if skip_cm and r['overlay_cm'] == skip_cm:
                continue
            url = f"https://img.example.com/{r['overlay_cm']}/{r['key']}.png"
            db.execute("INSERT OR REPLACE INTO cloud_link (artifact_key, output_sha, url, provider) VALUES (?,?,?,?)",
                       (r['key'], r['output_sha'], url, 'imagekit'))


def _export(world, store='Adeno'):
    from openpyxl import load_workbook
    from URETIM_V4.store_excel_v485 import export_store_upload
    out = export_store_upload(None, world['state'], store_id=store, report_root=world['state'] / 'raporlar')
    wb = load_workbook(out['output'])
    ws = wb.active
    headers = [c.value for c in ws[1]]
    rows = [dict(zip(headers, [c.value for c in row])) for row in ws.iter_rows(min_row=2)]
    return out, rows


def test_excel_end_to_end_order_codes_and_link_matching(world):
    d = world['tmp'] / 'two'
    d.mkdir()
    _png(d / 'Ham1.png', (10, 20, 30))
    _png(d / 'Ham2.png', (30, 20, 10))
    _run(world, ['Adeno'], designs=d)
    _fake_links(world['state'])
    out, rows = _export(world)
    assert len(rows) == 8 and all(e['field'] == 'Ölçü' for e in out['errors'])  # yerleşik şablonda ölçü sütunu yok
    for i in (0, 4):
        block = rows[i:i + 4]
        assert [r['Stok Kodu'].split('-', 1)[0] for r in block] == ['76', '96', '116', '136']
        assert len({r['Model Kodu'] for r in block}) == 1          # ortak model
        assert len({r['Barkod'] for r in block}) == 4              # farklı barkod
        assert len({r['Stok Kodu'] for r in block}) == 4           # farklı stok
        for r, cm in zip(block, ('76', '96', '116', '136')):
            assert f'/{cm}CM/' in r['Görsel 1']                    # link doğru satırda
    assert len({r['Model Kodu'] for r in rows}) == 2


def test_failed_cloud_upload_isolated_no_false_completion(world):
    d = world['tmp'] / 'one'
    d.mkdir()
    _png(d / 'Ham1.png', (10, 20, 30))
    _run(world, ['Adeno'], designs=d)
    _fake_links(world['state'], skip_cm='116CM')
    out, rows = _export(world)
    assert len(rows) == 3 and out['errors']
    assert all('116' != r['Stok Kodu'].split('-', 1)[0] for r in rows)


def test_hundred_twenty_images_ten_designs_three_stores(world):
    extra = [_template(world['tmp'], f'wd_t{i}', (i * 20 + 5, 5, 5)) for i in range(4)]
    more = _template(world['tmp'], 'omz_t3', (77, 77, 7))
    world['templates'].extend(extra + [more])
    mgr = StoreProfiles(world['state'])
    mgr.add_store('Wudie')
    mgr.assign('Wudie', extra, all_approved=world['templates'])
    mgr.assign('OmzHome', [more], all_approved=world['templates'])
    d = world['tmp'] / 'ten'
    d.mkdir()
    for i in range(1, 11):
        _png(d / f'Ham{i}.png', (i * 10, 20, 30))
    res = _run(world, ['Adeno', 'OmzHome', 'Wudie'], designs=d)
    assert res['four_mockup']['successful'] == 120 and res['four_mockup']['failed'] == 0
    assert len(_rows(world)) == 120 and res['rendered'] == 120
    assert len({r['sku'] for r in _rows(world)}) == 120
    assert len({r['output'] for r in _rows(world)}) == 120


def test_per_design_template_rotation_wudie_and_adeno_three_designs(world):
    # Separate, store-assigned pools: no cross-store borrowing is allowed.
    wudie = [_template(world['tmp'], f'wudie_real_t{i}', (15 + i * 11, 25, 35))
             for i in range(5)]
    world['templates'].extend(wudie)
    mgr = StoreProfiles(world['state'])
    mgr.add_store('Wudie')
    mgr.assign('Wudie', wudie, all_approved=world['templates'])

    d = world['tmp'] / 'three-real'
    d.mkdir()
    for i in range(1, 4):
        _png(d / f'Ham{i}.png', (i * 17, 40, 80))
    _run(world, ['Adeno', 'Wudie'], designs=d)
    rows = _rows(world)
    assert len(rows) == 24
    by_store_design = {}
    for row in rows:
        store = Path(row['output']).relative_to(world['engine'].output).parts[0]
        by_store_design.setdefault((store, row['art_name']), []).append(row)
    for store in ('Adeno', 'Wudie'):
        combinations = []
        for design_index in range(1, 4):
            block = by_store_design[(store, f'Ham{design_index}.png')]
            assert len(block) == 4
            assert len({r['uid'] for r in block}) == 4
            assert [r['overlay_cm'] for r in sorted(block, key=lambda r: r['overlay_cm'])] == [
                '116CM', '136CM', '76CM', '96CM']
            combinations.append(frozenset(r['uid'] for r in block))
        assert len(set(combinations)) == 3
        other = 'Wudie' if store == 'Adeno' else 'Adeno'
        assert not ({r['uid'] for r in by_store_design[(store, 'Ham1.png')]} &
                    {r['uid'] for r in by_store_design[(other, 'Ham1.png')]})


def test_interrupted_run_resumes_from_checkpoint_without_rerender(world, monkeypatch):
    d = world['tmp'] / 'ten'
    d.mkdir()
    for i in range(1, 4):
        _png(d / f'Ham{i}.png', (i * 10, 20, 30))
    eng = world['engine']
    orig = ub._render_job_picture
    state = {'n': 0}

    def stopper(**kw):
        state['n'] += 1
        if state['n'] == 5:
            eng.request_stop()
        return orig(**kw)
    monkeypatch.setattr(ub, '_render_job_picture', stopper)
    first = _run(world, ['Adeno'], designs=d)
    assert first['status'] == 'STOPPED'
    done_before = len(_rows(world))
    assert 0 < done_before < 12
    monkeypatch.setattr(ub, '_render_job_picture', orig)
    before_calls = world['calls']['n']
    res = eng.resume_last_stopped()
    assert res['status'] in ('LOCAL_READY', 'PARTIAL') and len(_rows(world)) == 12
    assert world['calls']['n'] - before_calls <= 12 - state['n'] + 1   # biten işler tekrar render edilmedi
    assert len({r['output'] for r in _rows(world)}) == 12


def test_old_overlay_mode_signature_and_default_unchanged(world):
    # four_mockup verilmeden eski mod yolu: standart tek çıktı/tasarım, overlay türevi yok
    d = world['tmp'] / 'one'
    d.mkdir()
    _png(d / 'Ham1.png', (10, 20, 30))
    res = _run(world, ['Adeno'], four=False, designs=d)
    assert res['rendered'] == 1 and not _rows(world)
    assert res['four_mockup']['enabled'] is False
    assert history.list_sessions(world['state'])[0]['mode'] == 'standard'


# --- Arayüz duman testi --------------------------------------------------------
def test_panel_preflight_and_history_window_smoke(world):
    import tkinter as tk
    from types import SimpleNamespace
    from URETIM_V4.four_mockup_ui_v1 import FourMockupPanel, show_history_window
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk yok')
    root.withdraw()
    try:
        d = world['tmp'] / 'ui'
        d.mkdir()
        _png(d / 'Ham1.png', (1, 2, 3))
        _png(d / 'Ham2.png', (3, 2, 1))
        owner = SimpleNamespace(
            window=root, all_templates=world['templates'], batch_engine=world['engine'],
            design_folder=tk.StringVar(value=str(d)), petek_overlay_enabled=tk.BooleanVar(value=True),
            _chosen_stores=lambda: ['Adeno', 'OmzHome'], runtime_root=None,
            _refresh_selection_summary=lambda: None)
        panel = FourMockupPanel(owner, tk.Frame(root))
        panel.enabled_var.set(True)
        panel._toggled()
        assert owner.petek_overlay_enabled.get() is False          # iki mod aynı anda açık olamaz
        report = panel.preflight()
        assert not report['ready'] and 'OmzHome' in report['problems'][0]   # 3 şablon -> eksik bildirilir
        assert report['slots']['Adeno']['76CM'] == 'wudie_t0'
        owner._chosen_stores = lambda: ['Adeno']
        cfg, uids = panel.prepare_for_start()
        assert len(uids) == 4 and cfg['slots']['Adeno']['136CM'] == 'wudie_t3'
        assert report['formula'].startswith('2 tasarım')
        panel.open_settings()
        root.update()
        owner.petek_overlay_enabled.set(True)
        panel.overlay_mode_changed()
        assert not panel.enabled()
        show_history_window(owner)
    finally:
        root.destroy()


def test_cloud_callback_receives_only_four_finals_never_clean(world):
    d = world['tmp'] / 'one'
    d.mkdir()
    _png(d / 'Ham1.png', (10, 20, 30))
    got = []
    _run(world, ['Adeno'], designs=d, output_ready=got.append)
    assert len(got) == 4
    assert {r['overlay_cm'] for r in got} == {'76CM', '96CM', '116CM', '136CM'}
    assert all('__W' in Path(r['output']).name and 'Overlaysızlar' not in r['output'] for r in got)
    assert all(r['key'] and r['output_sha'] and r['sku'] for r in got)


# --- Gerçek test oturumundan çıkan hatalar -----------------------------------------
def test_big_custom_overlay_goes_bottom_right_scaled_down(tmp_path):
    clean = tmp_path / 'c.png'
    _png(clean, (100, 100, 100))
    big = tmp_path / '76CM' / '76grup4' / 'UST' / 'UST_76CM_GRUP04_1200x300.png'
    big.parent.mkdir(parents=True)
    Image.new('RGBA', (1200, 300), (255, 0, 0, 255)).save(big)
    data, m = fm.render_final_bytes(clean, '76CM', {'enabled': True, 'path': str(big)})
    out = np.array(Image.open(io.BytesIO(data)).convert('RGB'))
    x, y = m['position']
    assert x + 600 == 1200 and y + 150 == 1600                 # sağ alt, sıfır boşluk, 600x150'ye sığdırıldı
    base = np.array(Image.open(clean).convert('RGB'))
    assert fm.pixels_equal_outside_label(base, out, (x, y))


def test_twenty_overlay_pool_per_measure_stable_and_varied(tmp_path):
    clean = tmp_path / 'c.png'
    _png(clean, (100, 100, 100))
    pool_dir = tmp_path / fm.LABEL_FOLDER
    for cm in fm.VARIATIONS:
        folder = pool_dir / cm
        folder.mkdir(parents=True)
        for i in range(20):
            Image.new('RGBA', (180, 40), (i * 10, 50, 50, 255)).save(folder / f'overlay{fm.cm_number(cm)}_{i + 1:02d}.png')
    chosen = {}
    for n in range(60):
        _, m = fm.render_final_bytes(clean, '96CM', {'enabled': True}, label_dir=pool_dir, pick_key=f'tasarim{n}|Adeno')
        chosen[n] = m['file']
        assert m['kind'] == 'default_file' and m['pool_size'] == 20 and m['file'].startswith('overlay96_')
    assert len(set(chosen.values())) >= 10                      # havuzdan çeşitli seçim
    for n in (0, 7, 33):                                       # aynı anahtar → aynı dosya (devam güvenli)
        _, again = fm.render_final_bytes(clean, '96CM', {'enabled': True}, label_dir=pool_dir, pick_key=f'tasarim{n}|Adeno')
        assert again['file'] == chosen[n]
    # yanlış klasöre konmuş dosya (96CM içinde overlay76) engellenir
    Image.new('RGBA', (180, 40), (1, 2, 3, 255)).save(pool_dir / '96CM' / 'overlay76_x.png')
    with pytest.raises(fm.FourMockupError, match='UYUSMAZLIGI'):
        for n in range(200):
            fm.render_final_bytes(clean, '96CM', {'enabled': True}, label_dir=pool_dir, pick_key=f'k{n}')


def test_external_mode_long_design_name_still_makes_four_finals(world):
    d = world['tmp'] / 'ext'
    d.mkdir()
    _png(d / 'pexels-amirhadimanavimoghadam-21601506.png', (10, 20, 30))
    res = _run(world, ['Adeno'], designs=d, external_designs=True)
    assert res['four_mockup']['successful'] == 4 and res['four_mockup']['failed'] == 0
    assert res['four_mockup']['missing'] == []
    assert len(res['current_batch_rows']) >= 4
    assert len([o for o in res['current_batch_outputs'] if o.get('overlay_cm')]) == 4


def test_failed_slot_reported_as_missing_never_filled(world, monkeypatch):
    d = world['tmp'] / 'one'
    d.mkdir()
    _png(d / 'Ham1.png', (10, 20, 30))
    orig = ub._render_job_picture

    def flaky(**kw):
        if kw['item']['uid'] == 'wudie_t0':
            raise petek_engine.MaskError('PETEK_GENIS_MAGENTA_SACAK_MASK_INCELE')
        return orig(**kw)
    monkeypatch.setattr(ub, '_render_job_picture', flaky)
    res = _run(world, ['Adeno'], designs=d)
    assert res['four_mockup']['successful'] == 3 and len(_rows(world)) == 3
    assert res['four_mockup']['missing'] == ['Ham1.png · Adeno · 76 cm (wudie_t0)']
    assert res['status'] == 'PARTIAL'


def test_unhealthy_templates_skipped_in_auto_selection_and_blocked_when_pinned(world):
    plan = [('Adeno', world['templates'][:5])]
    bad = {'wudie_t0'}
    health = lambda t: (t['uid'] not in bad, 'PETEK_GENIS_MAGENTA_SACAK_MASK_INCELE')
    notes = []
    slots, problems = fm.plan_slots(plan, health=health, notes=notes)
    assert not problems and 'wudie_t0' not in slots['Adeno'].values()
    assert list(slots['Adeno'].values()) == ['wudie_t1', 'wudie_t2', 'wudie_t3', 'wudie_t4']
    assert notes and 'wudie_t0' in notes[0] and 'MAGENTA' in notes[0]
    pinned = {'Adeno': {'76CM': 'wudie_t0', '96CM': 'wudie_t1', '116CM': 'wudie_t2', '136CM': 'wudie_t3'}}
    _, problems = fm.plan_slots(plan, pinned, health=health)
    assert problems and 'sağlıksız şablon' in problems[0] and 'wudie_t0' in problems[0]
    # yeterli sağlıklı şablon yoksa üretim başlamaz, tekrar yapılmaz
    _, problems = fm.plan_slots(plan, health=lambda t: (t['uid'] == 'wudie_t4', 'x'))
    assert problems and 'sağlıklı' in problems[0]


def test_engine_health_blocks_pinned_unhealthy_before_any_render(world, monkeypatch):
    d = world['tmp'] / 'one'
    d.mkdir()
    _png(d / 'Ham1.png', (10, 20, 30))
    monkeypatch.setattr(world['engine'], 'template_health',
                        lambda item, **kw: (item['uid'] != 'wudie_t1', 'PETEK_GENIS_MAGENTA_SACAK_MASK_INCELE'))
    renders = world['calls']['n']
    # otomatik seçim sağlıksızı atlar ve 4 final üretir
    res = _run(world, ['Adeno'], designs=d)
    assert res['four_mockup']['successful'] == 4
    assert 'wudie_t1' not in {r['uid'] for r in _rows(world)}
    # sabitlenmiş sağlıksız şablon render'dan önce reddedilir
    pinned = {'Adeno': {'76CM': 'wudie_t1', '96CM': 'wudie_t0', '116CM': 'wudie_t2', '136CM': 'wudie_t3'}}
    calls_before = world['calls']['n']
    with pytest.raises(petek_engine.MaskError, match='sağlıksız şablon'):
        _run(world, ['Adeno'], designs=d, four_mockup={'slots': pinned})
    assert world['calls']['n'] == calls_before


def test_pool_scans_nested_group_folders(tmp_path):
    clean = tmp_path / 'c.png'
    _png(clean, (100, 100, 100))
    pool = tmp_path / fm.LABEL_FOLDER
    for g in ('76grup1', '76grup2'):
        f = pool / '76CM' / g / 'UST'
        f.mkdir(parents=True)
        Image.new('RGBA', (510, 63), (9, 9, 9, 255)).save(f / f'UST_76CM_{g.upper()}_510x63.png')
    (pool / '76CM' / '76grup1' / 'yan').mkdir()
    Image.new('RGBA', (510, 63), (1, 1, 1, 255)).save(pool / '76CM' / '76grup1' / 'yan' / 'x_76CM.png')
    assert len(fm.label_pool(pool, '76CM')) == 2
    _, m = fm.render_final_bytes(clean, '76CM', {'enabled': True}, label_dir=pool, pick_key='a')
    assert m['position'] == [1200 - 510, 1600 - 63]


def test_donor_fill_replaces_only_target_with_clean_neighbour_color():
    import cv2
    from PETEK_V3.final_cleanup_v495 import _donor_fill, _magenta_pixels
    img = np.full((40, 40, 3), (20, 30, 90), np.uint8)             # koyu kırmızı (magenta değil)
    img[10:14, 10:30] = (120, 20, 110)                              # mor kenar çizgisi
    target = _magenta_pixels(img)
    assert target.any()
    donors = ~target
    out, n = _donor_fill(img, target, donors)
    assert n == int(target.sum()) and not _magenta_pixels(out).any()
    assert np.array_equal(out[~target], img[~target])               # hedef dışı piksel değişmez
    assert tuple(out[11, 20]) == (20, 30, 90)                       # komşu tasarım rengi
    far = np.zeros((40, 40), bool); far[0, 0] = True                # donör >10 px uzaktaysa dokunma
    none = np.zeros((40, 40), bool); none[39, 39] = True
    same, k = _donor_fill(img, far, none)
    assert k == 0 and np.array_equal(same, img)
