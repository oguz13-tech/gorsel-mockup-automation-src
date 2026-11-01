"""Actionable read-only interpretation of Factory Doctor warnings.

Core doctor warnings are never suppressed. This module never installs packages,
modifies a runtime baseline, edits SQLite, or adjusts any master design.
"""
from __future__ import annotations

import sys
from pathlib import Path


def doctor_guidance(report: dict, *, executable: str | None = None) -> dict:
    if not isinstance(report, dict):
        report = {}
    warnings = report.get("warnings") or []
    codes = {str(x.get("code") or "") for x in warnings if isinstance(x, dict)}
    details = report.get("checks") or {}
    version = details.get("runtime_versions") or {}
    exe = str(executable if executable is not None else sys.executable)
    baseline_path = Path(str(details.get("runtime_root") or ".")) / "SABLON_V2_MIMARI" / "runtime_ai_baseline.json"
    notes: list[dict] = []

    if "RUNTIME_VERSION_DRIFT" in codes:
        mismatches = version.get("mismatches") or []
        components = ", ".join(str(x.get("component", "?")) for x in mismatches if isinstance(x, dict))
        notes.append({
            "code": "RUNTIME_VERSION_DRIFT",
            "title": "Python / çekirdek paket sürümü farklı",
            "explanation": "Factory Doctor, şu an bu editörü çalıştıran Python yorumlayıcısını kilitli sürümlerle karşılaştırıyor. Uyarı tek başına dosya kaybı veya üretim arızası demek değildir.",
            "action": "İşleyen ortamda Python/NumPy sürümünü zorla değiştirmeyin. Yeni kurulumda mümkünse ayrı sanal ortam için Python 3.11 seçin, bağımlılık testini çalıştırın. Uyarı ancak uyumluluk doğrulanınca değerlendirilmelidir.",
            "evidence": f"Farklı bileşenler: {components or 'ayrıntı için üstteki liste'}; kilit: {version.get('lock_path') or 'bilinmiyor'}",
        })

    if "GPU_RUNTIME_DRIFT" in codes:
        changes = version.get("gpu_changes") or []
        absent = [str(x.get("component", "?")) for x in changes if isinstance(x, dict) and x.get("actual") is None]
        altered = [str(x.get("component", "?")) for x in changes if isinstance(x, dict) and x.get("actual") is not None]
        if absent:
            notes.append({
                "code": "GPU_RUNTIME_DRIFT",
                "title": "GPU/AI bileşenleri bu Python ortamında bulunamıyor",
                "explanation": "Önceki baseline dosyasında kayıtlı Torch, Transformers veya CUDA sürümleri şu anki editör Python'ında bulunamamış. Bir GPU'nun fiziksel olarak bozulduğu ya da normal dört köşe ekranının çalışamayacağı anlamına gelmez; GPU tabanlı özellikler etkilenebilir.",
                "action": "GPU modelini kullanan görev varsa hangi Python ortamından çalıştığını ve o ortamın sürücülerini ayrı kontrol edin. Torch/Transformers'ı otomatik olarak yüklemeyin; baseline dosyasını sırf uyarı silinsin diye sıfırlamayın.",
                "evidence": f"Bu ortamda eksik görünenler: {', '.join(absent)}; baseline: {baseline_path}",
            })
        if altered:
            notes.append({
                "code": "GPU_RUNTIME_DRIFT_CHANGED",
                "title": "GPU bağımlılığı baseline sürümünden farklı",
                "explanation": "Bazı GPU/AI bileşenleri mevcut; fakat ilk başarılı baseline ile sürüm eşleşmiyor.",
                "action": "GPU gerektiren bir işte kontrollü karşılaştırma testi yapmadan sürümü yükseltmeyin veya düşürmeyin.",
                "evidence": "Sürümü değişen bileşenler: " + ", ".join(altered),
            })

    if "SYNCED_RUNTIME_DB_RISK" in codes:
        notes.append({
            "code": "SYNCED_RUNTIME_DB_RISK",
            "title": "OneDrive / bulut eşitlemesi altında SQLite",
            "explanation": "Bu bir önleyici risk uyarısıdır. OneDrive'daki canlı ayarlar.db ve WAL eşitleme/kilit çatışmasına yatkın olabilir; doktor bu nedenle çalışma klasörünün yolunu işaretliyor.",
            "action": "Onaylı köşe ve eski üretimler devam ederken SQLite'ı elle taşımayın. Mevcut SQLite online yedeğini doğrulayın; daha sonra uygulamanın bütün DB yolları ve WAL kullanımıyla birlikte ayrı bir bakım geçişi planlayın. Görseller mevcut yerde kalabilir.",
            "evidence": "Çalışma kökü: " + str(details.get("runtime_root") or "bilinmiyor"),
        })

    if "MASTER_ASPECT_BLEED_ADAPTATION" in codes:
        hit = next((x for x in warnings if isinstance(x, dict) and x.get("code") == "MASTER_ASPECT_BLEED_ADAPTATION"), {})
        examples = hit.get("examples") or []
        sample_lines = []
        for item in examples[:5]:
            if isinstance(item, dict):
                sample_lines.append(f"{item.get('master_id', '?')} / {item.get('category', '?')} / {item.get('source_orientation', '?')} (sapma %{float(item.get('relative_error') or 0) * 100:.1f})")
        notes.append({
            "code": "MASTER_ASPECT_BLEED_ADAPTATION",
            "title": "Master tasarımın oranı ürün oranına uymuyor",
            "explanation": "Bu, r7'nin tasarımı esnetmeden bleed uyguladığını açıklayan bir kalite uyarısıdır. Kendi başına onaylı dört köşeyi veya görsel verilerini değiştirmez.",
            "action": "Şimdilik üretim geometrisine dokunmayın. Ürün başına oranı doğru H/V master hazırlamak kaliteyi yükseltir; önce tek deneme çıktısını görsel olarak değerlendirin.",
            "evidence": "; ".join(sample_lines) if sample_lines else "Örnekler ayrıntılı doktor raporundadır.",
        })

    return {
        "read_only": True,
        "interpreter": exe,
        "python_version": sys.version.split()[0],
        "runtime_lock_path": str(version.get("lock_path") or ""),
        "ready": bool(report.get("ready")),
        "recommendations": notes,
        "notice": "Bu öneriler yalnız teşhis amaçlıdır; paket veya canlı dosyalarda otomatik onarım yapılmaz.",
    }
