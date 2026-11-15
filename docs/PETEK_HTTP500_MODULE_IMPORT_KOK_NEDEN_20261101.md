# PETEK HTTP 500 – doğrulanmış Python modül yolu hatası (01.11.2026)

## Gerçek Windows logu

`POST /api/petek/preview-artwork` 500 ile başarısız. `petek_visual_pipeline_vnext.py` içinde `URETIM_V4.finish_material_v46` importu `No module named URETIM_V4` veriyor. Ardından alternatif `MERKEZ.URETIM_V4.finish_material_v46` importu, `URETIM_V4/__init__.py` modülünü çalıştırıyor. Bu modül `unlimited_selection.py` üzerinden üst düzey `PETEK_V3` paketi arıyor ve `No module named PETEK_V3` ile kapanıyor.

## Kesin kök neden

Flask editöründe proje kökü `sys.path` içindedir ve PETEK kodu `MERKEZ.PETEK_V3` adı altında import edilir. Tk merkezinin top-level `URETIM_V4` / `PETEK_V3` yapısı farklı arama yolu kullanıyor. Tekil, başka bağımlılığı olmayan `finish_material_v46.py` dosyasını paket `__init__` zinciri üzerinden import etmek güvenilir değil.

## Düzeltme

`MERKEZ/PETEK_V3/petek_visual_pipeline_vnext.py` yalnız kaynak ağacındaki sabit `MERKEZ/URETIM_V4/finish_material_v46.py` dosyasını `importlib.util.spec_from_file_location` ile paket yan etkisi olmadan okuyor. Yükleme yalnız malzeme efekti gerekiyorsa yapılıyor ve `lru_cache` ile tekrar kullanılıyor. Görsel efektin kendisi, maskeler, 4 köşeler, mağaza kayıtları, SQLite ve onaylar değiştirilmedi.

## Test ve geri dönüş

İlk kaynakta `PYTHONPATH=PROJECT_ROOT` koşulunda gerçek hata yeniden üretildi. Düzeltme sonrası 15 yarıklı tam render ve Belirgin (`strong`) profili aynı Flask-benzeri koşulda geçti; korunan pikseller aynı kaldı. Test: `tests/test_vnext_petek_flask_module_path_http500.py`.

Eski sürümü silmeyin veya üzerine kurmayın. Yeni ZIP'i ayrı klasöre çıkarın, `PETEK_HTTP500_DOGRULA_WINDOWS.bat` ve `PETEK_HTTP500_BASLAT_WINDOWS.bat` kullanın. Ana Merkez'den eski şablon servisini güvenle durdurup yenisini açın. `GET /api/petek/service-status` içindeki `code_root` değerinin yeni klasörü göstermesi gerekir. Sorun devam ederse logu paylaşın ve eski klasöre dönün. Bu dağıtımda **gerçek Windows uçtan uca testi yapılmadı (WINDOWS_NOT_VERIFIED)**.
