# GÖRSEL ÜRETİM MERKEZİ — V4.10.1 KANONİK DEVİR / AI BAŞLANGIÇ REHBERİ

**Tarih:** 2026-10-31 · **Release:** V4.10.1 WINDOWS_ADAY · **Canlı Windows durumu:** `WINDOWS_NOT_VERIFIED`.

## 0. Bu dosyayla başlayın

Bu dalın bütün kanonik dosyaları **V4.10.1 ZIP paketi** ile içerik olarak karşılaştırıldı: **482/482 Git blob SHA-1 eşleşti, 0 eksik / 0 farklı dosya.** ZIP SHA-256: `4b5b06fa8392aa28bf8d9fa70ccc90a799a8acb8681a69cd143aecdeec57a1f8`. Ayrıntılı kanıt: `docs/V4101_GITHUB_SYNC_PROOF.md`. Dal, eski V4.6 dalını temel aldığı için paket dışında **129 tarihsel Git dosyası da içerir**. Herhangi bir otomasyonun kanonik dosya kapsamını belirlerken ZIP’in `SHA256_MANIFEST.json` dosyasındaki yolları esas alın; aynı adlı tarihsel/legacy kaynakları çalıştırmayın.

## 1. Okuma sırası
1. `V4101_ILK_OKU.txt` — güvenli Windows kurulum ve çalıştırma.
2. `docs/V4101_ARCHITECTURE.md` — yedi kategori, modül haritası, veri akışları, güvenlik.
3. `docs/V4101_SOURCE_FILE_INDEX.md` — paket içindeki kaynak yolları.
4. `docs/V4101_CHANGELOG_AND_GAPS.md` — yapılan düzeltmeler ve dürüst açık/yarım işler.
5. `docs/V4101_WINDOWS_ACCEPTANCE.md` — kullanıcı bilgisayarında elle yapılacak kabul.
6. `V4101_TEST_VE_KABUL_RAPORU.md` ve `SHA256_MANIFEST.json` — teknik test ve kaynak doğrulama.
7. `docs/V4101_GITHUB_SYNC_PROOF.md` — GitHub dosya eşleşmesi.

## 2. Tek giriş ve ana modüller
- Başlat: `V4101_DOGRULA_WINDOWS.bat` → `V4101_BASLAT_WINDOWS.bat` → `BASLAT_V47_WINDOWS.bat` → `MERKEZ/merkez.py`.
- Tk ana ekran: `MERKEZ/premium_dashboard_v489.py`; UI sekmeleri/renk/atomik kalıcı JSON: `MERKEZ/ui_layout_v498.py`.
- Flask şablon inceleme: `SABLON_V2_MIMARI/app.py`, `templates/index.html`, `static/js/main.js`.
- PETEK istemci: `SABLON_V2_MIMARI/static/js/petek_editor_v477.js`; Flask endpoint: `SABLON_V2_MIMARI/core/petek_web_v477.py`; kaynak/maske/quad/UID kayıtları: `MERKEZ/PETEK_V3/registry.py`.
- PETEK liste boş dosya adı düzeltmesi: `SABLON_V2_MIMARI/static/css/v4101_unified.css`.
- 7 kategori durum filtresi: `SABLON_V2_MIMARI/static/js/v499_status_filter.js`.
- Seri üretim: `MERKEZ/URETIM_V4/gui_v4.py`; mağaza seçimi ve izolasyon: `store_assignment_ui_v410.py`, `store_assignment_v410.py`; 4K: `on_demand_4k_v495.py`.
- Test Merkezi: `MERKEZ/personal_hub_v493.py`; açıklamalı Tk hataları: `MERKEZ/error_advisor_v498.py`.
- Testler: `tests/test_v4101_release.py` + eski V4.9.x/PETEK/mağaza testleri.

## 3. Kesin güvenlik ve ürün kuralları
- **Asla** kullanıcının gerçek `2_SABLON_HAVUZU_ORIJINAL_YEDEK`, SQLite, 4 köşe onayları, PETEK immutable-approved kayıtları veya canlı üretim ledger'ının üzerine test/yeni ZIP yazmayın.
- Onaylı PETEK maskeyi düzeltme: mevcut approved kaydı silmek değil; yeni DRAFT revizyon, kaynak SHA/maske kimliği kontrolü, açık insan onayı, yeni etkin revizyon, yedekli geri dönüş. Dört köşe değişince eski maskeyi otomatik onaylamayın.
- PETEK toplu onay: **tek genel kullanıcı onayı; sekizli tur yok, her taslak için tik yok**. Sunucu içindeki parçalara ayırma kullanıcıdan tekrar onay istemek değildir; geçersiz maskeler DRAFT kalır.
- Kategori kısıtları: Wi-Fi 40×30 cm yüz/12 cm iç derinlik; cam dikey 60×90, yatay 90×60; ahşap 50×70 ince meşe; cam doğrama 25×35; ocak arkası 90×60 ve gerçek ocak; PETEK 15 koyu yarık, üst/alt kavis, beyaz yan/üst ve magenta baskı. Geometri sabit.
- Mağaza izolasyonu: aynı ham baskı tasarımını farklı mağazalarda **farklı mockuplarla** üretmek serbest; aynı kaynak mockup şablonu iki mağazaya atanamaz.
- Korunan canlı kabul: PETEK **15 koyu yarık/Orta yoğunluk**, **pembe temizliği**, seri üretim **hızlı açılış**, **Programı Kapat**. Bu motorlarda regresyon izni yok.

## 4. Bilinen durum / açık işler
- V4.10.1 seçili regresyon **124 PASS, 3 SKIP, 2 DESELECT**. Flask HTTP gerçek test için kurulu değildi; tarihsel ayar JSON testi ortamla uyuşmuyordu. Bunlar PASSED değil.
- Chromium 400 ve 1280px PETEK listesinde dosya adı göründü; gerçek Windows + kullanıcı verisinde kabul henüz yok.
- Antrasit ve 7 kategori renk/filtre görünümünü geliştirdik ancak PETEK editörü altı kategoriyle tamamen aynı JS bileşeni değildir.
- Ana ekranda sürükle-bırak sıralaması var; serbest piksel konumu ve kart boyutlandırma, üretim penceresindeki bütün kartlarda doğrudan sürükleme kısmi.
- Tk/Web/PETEK hata açıklamaları genişledi; bütün bağımsız BAT/araçlarda tek tık düzeltme yok.
- Cam yansıması, 1000+ batch, gerçek GPU 4K, mağaza Excel, OneDrive/SQLite yedek ve gerçek Windows PETEK onay/rollback uçtan uca kabulü açık.
- GitHub issues **#66–#72** durumları yalnız canlı Windows test/kabul sonuçlarına göre kapatılmalıdır; yalnız kodun varlığı kapanış gerekçesi değildir.

## 5. Geliştirici testi ve çalışma usulü
```bash
python scripts/v4101_verify_package.py
python -m compileall -q MERKEZ SABLON_V2_MIMARI scripts tests
find SABLON_V2_MIMARI/static/js -type f -name '*.js' -print0 | xargs -0 -n1 node --check
PYTHONPATH=.:MERKEZ pytest -q tests/test_v4101_release.py tests/test_v4100_store_assignment.py tests/test_v499_bulk_ui_and_revision.py
```
Bu testlerde Flask bağımlılığı olanları ayrıca kurulu ortamda çalıştırın. Sadece yeşil test toplamıyla final ilan etmeyin. Önce canlı veri yedeği/rollback, sonra Windows kabul.

## 6. GitHub dal disiplini
Bu dalı **taslak PR** olarak inceleyin; `main` tarihsel olarak eski olduğu için doğrudan `main` üzerine otomatik yazmayın. Source of truth bu dal ve tek ZIP'in manifest kayıtlarıdır. GitHub'daki 129 ekstra tarihsel dosya yanlışlıkla yeni kanonik kaynak ilan edilmesin. Bir AI/developer bug için önce reproducer+güvenli test oluşturmalı, kaynak düzeltmesi yapmalı, tekrar hash/QA doğrulamalı, Windows kullanıcı kabulü sonra çıkmalıdır.
