"""GÖREV 09 — canlı ilerleme ekranı simülasyonu.

Gerçek üretim/linkleme koduna dokunmadan:
- bulut linkleme + Excel aşamasının phase='excel' ilerleme olaylarını,
- üretim/overlay/linkleme snapshot'larının GUI kartlarına doğru yansıdığını
simüle eder. Hiçbir canlı veriye/DB'ye yazmaz; tmp_path kullanır.
"""

import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "MERKEZ"))

import URETIM_V4.cloud_excel_v43 as cloud_module
from PETEK_V3 import engine as petek_engine
from URETIM_V4.cloud_excel_v43 import CloudExcel


def _rows(tmp_path, count=2, store=None, category="03_Ahsap_Tablo"):
    rows = []
    for index in range(count):
        if store:
            output_dir = tmp_path / "uretilen_gorseller" / store / category
        else:
            output_dir = tmp_path / "uretilen_gorseller" / "LOCAL" / category
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / f"image-{index}.png"
        Image.new("RGB", (64, 64), (index * 40, 120, 200)).save(output)
        rows.append({
            "key": f"key-{store or 'local'}-{index}",
            "sku": f"AHT-{store or 'LOCAL'}-{index:03d}",
            "category": category,
            "art_name": f"art-{index}.png",
            "output": str(output),
            "output_sha": petek_engine.digest(output),
        })
    return rows


def _fake_routes(monkeypatch):
    monkeypatch.setattr(
        cloud_module,
        "_provider_routes",
        lambda _runtime: [{"provider": "imgbb", "keys": ["test-only"]}],
    )


def _run(tmp_path, monkeypatch, rows, upload_fn=None):
    _fake_routes(monkeypatch)
    upload_fn = upload_fn or (lambda path, keys, backup: "https://i.ibb.co/sim.png")
    snapshots = []
    result = CloudExcel(tmp_path, tmp_path / "reports").publish_existing(
        rows, upload_fn=upload_fn, progress=snapshots.append,
    )
    return result, snapshots


def test_excel_phase_progress_is_emitted_after_uploads(tmp_path, monkeypatch):
    rows = _rows(tmp_path, count=2, store=None)
    result, snapshots = _run(tmp_path, monkeypatch, rows)

    assert result["uploaded"] == 2
    phases = [item.get("phase") for item in snapshots]
    assert "upload" in phases and "excel" in phases
    assert phases.index("upload") < phases.index("excel")

    excel_events = [item for item in snapshots if item.get("phase") == "excel"]
    assert excel_events, "Excel aşaması hiç ilerleme yayınlamadı"
    assert excel_events[0]["excel_total"] == 1  # yalnız ana (yerel) Excel birimi
    final = excel_events[-1]
    assert final["excel_index"] == final["excel_total"] == 1
    for event in excel_events:
        assert event["elapsed_seconds"] >= 0
        assert event["completed"] == 2 and event["total"] == 2
    # Yükleme aşamasındaki tamamlama sırası korunmalı (gerçek işlemler).
    live = [item for item in snapshots if item.get("phase") == "upload" and item.get("completed")]
    assert [item["completed"] for item in live] == [1, 2]


def test_store_excel_phase_tracks_each_store(tmp_path, monkeypatch):
    rows = _rows(tmp_path, count=1, store="Adeno") + _rows(tmp_path, count=1, store="Wudie")
    _fake_routes(monkeypatch)
    calls = []

    def fake_store_export(template, state_root, *, store_id, report_root,
                          sheet_name=None, records=None, progress=None):
        total_recs = len(records or [])
        if progress is not None:
            for done in range(1, total_recs + 1):
                progress(done, total_recs, store_id)
        calls.append(store_id)
        return {"store": store_id, "rows": 1, "images": 1,
                "output": str(tmp_path / f"{store_id}.xlsx"),
                "output_folder": str(tmp_path),
                "error_report": "", "errors": [], "status": "STORE_TEMPLATE_READY_REVIEW_MARKETPLACE_REQUIREMENTS"}

    monkeypatch.setattr(
        "URETIM_V4.store_excel_v485.export_store_upload", fake_store_export)

    snapshots = []
    result = CloudExcel(tmp_path, tmp_path / "reports").publish_existing(
        rows, upload_fn=lambda p, k, b: "https://i.ibb.co/sim.png",
        progress=snapshots.append)

    assert sorted(calls) == ["Adeno", "Wudie"]
    excel_events = [item for item in snapshots if item.get("phase") == "excel"]
    # 1 ana Excel birimi + 2 mağaza birimi
    assert excel_events[0]["excel_total"] == 3
    indices = [item["excel_index"] for item in excel_events]
    assert indices == sorted(indices), "Excel adımı geri gitmemeli"
    assert indices[-1] == 3
    item_events = [item for item in excel_events if int(item.get("excel_item") or 0) > 0]
    assert item_events, "Kayıt bazında ilerleme hiç yayınlanmadı"
    assert any(item["excel_item"] == item["excel_item_total"] for item in item_events)
    assert len(result["store_files"]) == 2


class _Var:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class _Bar:
    def __init__(self):
        self.kwargs = None
    def configure(self, **kwargs):
        self.kwargs = kwargs


def _bare_view():
    from URETIM_V4.gui_v4 import UnifiedV4BatchWindow
    view = UnifiedV4BatchWindow.__new__(UnifiedV4BatchWindow)
    view.live_progressbar = _Bar(); view.live_progress_percent = _Var()
    view.live_progress_counts = _Var(); view.live_progress_title = _Var()
    view.live_progress_detail = _Var(); view.live_progress_time = _Var()
    view.result_summary = _Var(); view.cloud_progressbar = _Bar()
    view.cloud_progress_percent = _Var(); view.cloud_progress_title = _Var()
    view.cloud_progress_detail = _Var(); view.cloud_progress_counts = _Var()
    view.cloud_progress_time = _Var()
    view.overlay_progressbar = _Bar(); view.overlay_progress_percent = _Var()
    view.overlay_progress_title = _Var(); view.overlay_progress_detail = _Var()
    view.overlay_progress_counts = _Var(); view.overlay_progress_time = _Var()
    view._last_progress_snapshot = None
    view._ready_overlay_started = None
    return view


def test_production_card_shows_total_index_stage_and_counts():
    view = _bare_view()
    view._apply_production_progress({
        "completed": 4, "total": 6, "index": 4, "stage": "üretim",
        "category": "03_Ahsap_Tablo", "operation": "UID-1 / kapak.png",
        "outcome": "success", "elapsed_seconds": 42.0, "eta_seconds": 21.0,
        "successful": 3, "failed": 1, "skipped": 0,
    })
    assert view.live_progress_counts.get().startswith("Toplam: 6 · İşlenen: 4")
    assert "Başarılı: 3" in view.live_progress_counts.get()
    assert "Hatalı: 1" in view.live_progress_counts.get()
    assert "Aşama: Üretim" in view.live_progress_detail.get()
    assert "Sıra 4/6" in view.live_progress_detail.get()
    assert "kapak.png" in view.live_progress_detail.get()
    assert view.live_progress_percent.get() == "67%"
    assert view.live_progressbar.kwargs["value"] == 4 / 6 * 100.0
    assert "Geçen:" in view.live_progress_time.get() and "Tahmini kalan:" in view.live_progress_time.get()


def test_cloud_card_excel_phase_shows_step_and_record_progress():
    view = _bare_view()
    view._apply_cloud_progress({
        "completed": 50, "total": 50, "phase": "excel", "stage": "excel",
        "excel_index": 1, "excel_total": 3, "excel_item": 10, "excel_item_total": 40,
        "operation": "Trendyol Excel · Adeno · kayıt 10/40",
        "elapsed_seconds": 30.0, "eta_seconds": 25.0,
        "uploaded": 44, "reused": 6, "failed": 0,
    })
    assert view.cloud_progress_title.get() == "Excel Yazılıyor"
    assert "Aşama: Excel" in view.cloud_progress_detail.get()
    assert "Kayıt: 10 / 40" in view.cloud_progress_counts.get()
    assert "Excel adımı: 1 / 3" in view.cloud_progress_counts.get()
    expected = (1 + 10 / 40) / 3 * 100.0
    assert view.cloud_progressbar.kwargs["value"] == expected


def test_cloud_card_upload_phase_keeps_turkish_decimal_percent():
    view = _bare_view()
    view._apply_cloud_progress({
        "completed": 2, "total": 3, "phase": "upload", "stage": "linkleme",
        "operation": "HTTPS link oluşturuldu · AHT-LOCAL-001",
        "elapsed_seconds": 5.0, "eta_seconds": 2.5,
        "uploaded": 1, "reused": 1, "failed": 0,
    })
    assert view.cloud_progress_title.get() == "Excel / Linkleme Çalışıyor"
    assert "Aşama: Bulut linkleme" in view.cloud_progress_detail.get()
    assert view.cloud_progress_counts.get().startswith("2 / 3 görsel")
    assert view.cloud_progressbar.kwargs["value"] == 2 / 3 * 100.0


def test_overlay_card_shows_stage_and_real_time():
    view = _bare_view()
    view._apply_overlay_progress({
        "completed": 2, "total": 8, "stage": "overlay",
        "category": "06_Petek_Kapama", "operation": "76 overlay",
        "elapsed_seconds": 12.0, "eta_seconds": 36.0,
        "successful": 2, "failed": 0, "skipped": 0,
    })
    assert "Aşama: PETEK overlay" in view.overlay_progress_detail.get()
    assert view.overlay_progressbar.kwargs["value"] == 25.0
    assert "Geçen:" in view.overlay_progress_time.get()
    assert "Tahmini kalan:" in view.overlay_progress_time.get()


def test_ready_overlay_card_shows_elapsed_and_eta():
    view = _bare_view()
    now = time.monotonic()
    view._ready_overlay_started = now - 40.0  # 40 sn önce başladı
    view._apply_ready_overlay_progress({
        "source": "C:/kaynak/urun-07.png", "source_index": 2, "source_total": 4,
        "cm": "96CM", "status": "success",
    })
    assert "urun-07.png" in view.overlay_progress_detail.get()
    assert "96CM" in view.overlay_progress_detail.get()
    # index 2, cm 96 → (2-1) + 2/4 = 1.5 / 4 = %37.5
    assert view.overlay_progressbar.kwargs["value"] == 37.5
    assert "2 / 4 görsel" in view.overlay_progress_counts.get()
    assert "Geçen:" in view.overlay_progress_time.get()
    assert "Tahmini kalan:" in view.overlay_progress_time.get()
    assert "Tahmini kalan: —" not in view.overlay_progress_time.get()
    # Dosya bittiğinde çubuk kesin adımda (index/total) olmalı
    view._apply_ready_overlay_progress({
        "source": "C:/kaynak/urun-07.png", "source_index": 2, "source_total": 4,
        "status": "file_done",
    })
    assert view.overlay_progressbar.kwargs["value"] == 50.0
    assert "dosya tamamlandı" in view.overlay_progress_detail.get()


def test_upscale_4k_emits_real_progress(tmp_path, monkeypatch):
    import types
    import URETIM_V4.upscale4k_v44 as upscale

    state_root = tmp_path / "state"
    out_dir = state_root / "uretilen_gorseller" / "LOCAL" / "03_Ahsap_Tablo"
    out_dir.mkdir(parents=True)
    records = []
    for index in range(2):
        src = out_dir / f"src-{index}.png"
        Image.new("RGB", (1200, 1600), (index * 80, 90, 120)).save(src)
        records.append({"key": f"k-{index}", "sku": f"AHT-LOCAL-{index:03d}",
                        "output": str(src), "output_sha": upscale.sha256(src)})
    engine = tmp_path / "realesrgan.exe"
    engine.write_bytes(b"fake-engine")

    def fake_run(cmd, **_kwargs):
        trial = Path(cmd[cmd.index("-o") + 1])
        src = Path(cmd[cmd.index("-i") + 1])
        if src.name == "src-1.png":
            return types.SimpleNamespace(returncode=1, stdout="", stderr="boom")
        Image.new("RGB", (2880, 3840), (180, 180, 180)).save(trial)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(upscale, "preflight", lambda **_kwargs: engine)
    monkeypatch.setattr(upscale.subprocess, "run", fake_run)

    events = []
    result = upscale.process(records, state_root=state_root, enabled=True,
                             model="photo", progress=events.append)

    assert result["upscaled"] == 1 and result["failed"] == 1
    assert events[0]["outcome"] == "running" and events[0]["total"] == 2
    live = [event for event in events if event["outcome"] != "running"]
    assert [event["index"] for event in live] == [1, 2]
    assert live[0]["outcome"] == "success" and live[1]["outcome"] == "failed"
    assert all(event["operation"] for event in live)


def test_local_excel_emits_record_progress(tmp_path):
    import hashlib
    import sqlite3

    state = tmp_path / "state"
    out_dir = state / "uretilen_gorseller" / "LOCAL" / "03_Ahsap_Tablo"
    out_dir.mkdir(parents=True)
    image = out_dir / "img-0.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(image)
    sha = hashlib.sha256(image.read_bytes()).hexdigest()
    rows = [{"key": "k-0", "sku": "AHT-LOCAL-000", "category": "03_Ahsap_Tablo",
             "art_name": "art-0.png", "output": str(image), "output_sha": sha}]

    with sqlite3.connect(state / "v4_ortak_uretim.sqlite3") as connection:
        connection.execute(
            "CREATE TABLE artifact (key TEXT PRIMARY KEY, status TEXT, sku TEXT, "
            "output TEXT, output_sha TEXT, art_name TEXT, category TEXT)")
        connection.execute(
            "INSERT INTO artifact VALUES (?,?,?,?,?,?,?)",
            ("k-0", "RENDERED", "AHT-LOCAL-000", str(image), sha, "art-0.png", "03_Ahsap_Tablo"))
    with sqlite3.connect(state / "cloud_urls_v43.sqlite3") as connection:
        connection.execute(
            "CREATE TABLE cloud_link (artifact_key TEXT PRIMARY KEY, url TEXT, output_sha TEXT)")
        connection.execute(
            "INSERT INTO cloud_link VALUES (?,?,?)",
            ("k-0", "https://i.ibb.co/sim.png", sha))

    from openpyxl import Workbook
    template = tmp_path / "template.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Stok Kodu", "Barkod", "Model Kodu", "Kategori", "Görsel 1"])
    wb.save(template)

    from URETIM_V4.marketplace_excel_v45 import export_from_template
    report_root = state / "raporlar"
    report_root.mkdir()
    events = []
    result = export_from_template(
        template, state, rows, report_root=report_root,
        progress=lambda done, total, name: events.append((done, total, name)))

    assert result["rows"] == 1
    assert events and events[-1] == (1, 1, "LOCAL")


def test_production_card_shows_4k_stage_without_clobbering_summary():
    view = _bare_view()
    view.result_summary.set("Plan: 6 · İşlenen: 6 · Çıktı: 6")
    view._apply_production_progress({
        "completed": 3, "total": 5, "index": 3, "stage": "4K upscale",
        "category": "4K", "operation": "AHT-LOCAL-000 · digest_4k.png",
        "outcome": "success", "elapsed_seconds": 9.0, "eta_seconds": 6.0,
        "successful": 2, "failed": 1, "skipped": 0,
    })
    assert view.live_progress_title.get() == "4K Upscale Çalışıyor"
    assert "Aşama: 4K upscale" in view.live_progress_detail.get()
    assert "3/5" in view.live_progress_detail.get()
    assert view.result_summary.get() == "Plan: 6 · İşlenen: 6 · Çıktı: 6"


def test_ready_overlay_folder_emits_file_done_events(tmp_path, monkeypatch):
    import URETIM_V4.petek_overlay_variations_v1 as overlay_module

    source_folder = tmp_path / "kaynak"
    source_folder.mkdir()
    output_folder = tmp_path / "cikti"
    for index in range(2):
        Image.new("RGB", (1200, 1600), (index * 60, 100, 160)).save(source_folder / f"src-{index}.png")

    monkeypatch.setattr(overlay_module, "validate_overlay_folder",
                        lambda _root: {"ready": True, "grouped": True, "groups": {}})
    monkeypatch.setattr(overlay_module, "preflight", lambda _root: {})

    def fake_process_source(source_row, validation, output_root, *, source_sha=None,
                            protection_mask=None, on_progress=None):
        if on_progress:
            for cm in ("76CM", "96CM"):
                on_progress({"cm": cm, "status": "success"})
        return {"source": source_row["output"], "source_sha": source_sha,
                "design": "d", "results": [{"cm": cm} for cm in ("76CM", "96CM")]}

    monkeypatch.setattr(overlay_module, "process_source", fake_process_source)

    events = []
    result = overlay_module.process_folder(
        source_folder, tmp_path / "overlay-root", output_folder,
        on_progress=events.append)

    assert result["successful"] == 2 and result["failed"] == 0
    kinds = [item.get("status") for item in events]
    assert kinds.count("file_done") == 2
    file_done = [item for item in events if item.get("status") == "file_done"]
    assert [item["source_index"] for item in file_done] == [1, 2]
    assert all(item["source_total"] == 2 for item in file_done)
