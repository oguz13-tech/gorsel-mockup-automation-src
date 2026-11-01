# Mağaza–Üretim P0 Issue #79 — Test Kanıtı

**01.11.2026 / STORE_P0_ISSUE79_20261101 / GELİŞTİRME ADAYI**

## Uygulanan kontrol
- Mağaza profil anahtarı `category:uid@source_sha`, Python `StoreProfiles.plan` ve `UnifiedV4BatchWindow.start` ile aynı motor/store yolu.
- Üretim ön kontrolü **gerçekte start() çağrısında kullanılan seçili UID** listesini ve mağazaları alır; profil dosyasını diskten tekrar okur ve yol + SHA256 gösterir.
- Hatalı ekstra şablon üretim planına sessizce atılmaz; sadece mağaza grubuyla tam eşleşmiş plan geçer. Filtreleme önceden işaretli UID'leri sessizce değiştirmez.
- Sol atama / sağ kaldırma ayrımı, ön seçili bağlam ve mağaza kaynak sahipliği güvenle test edilir.

## Gerçek test komutu (Linux, izole)
```
xvfb-run -a env PYTHONPATH=. pytest -q \
 tests/test_v4100_store_assignment.py tests/test_vnext_store_bulk_unassign.py \
 tests/test_vnext_store_selection_diagnosis.py tests/test_vnext_store_preflight_p0.py \
 tests/test_v498_ui_and_approval_safety.py tests/test_v499_bulk_ui_and_revision.py \
 tests/test_v493_persistent_acceptance_and_fifteen.py tests/test_v494_safe_exit.py \
 tests/test_v4101_release.py tests/test_vnext_review_ui_only.py \
 tests/test_vnext_review_browser.py tests/test_vnext_mor_theme_tokens.py \
 tests/test_vnext_petek_vent_and_selection_guard.py tests/test_vnext_petek_selection_browser.py \
 tests/test_vnext_petek_photo_measured_geometry.py tests/test_vnext_petek_dynamic_preview_ui.py \
 -k 'not test_web_endpoint_read_only_15_slots'
```

**109 PASS · 1 SKIP · 1 DESELECT** (Linux/Xvfb, 16 ilgili test dosyası).
- Atlanan test: koşullu grafik/ortam.
- Hariç tutulan test: Flask HTTP entegrasyonu için modül bu test ortamında kurulu değil.
- `python -m compileall` güncel Python kodu PASS.
- Kaynak ZIP yerel SHA256 + temiz çıkarım + Python doğrulayıcı ayrıca PASS.

## Windows kabul (henüz yapılmadı)
- [ ] Wudie 3 atama ve 1 seçili gerçek fotoğrafta UID/SHA eşleşmesi / gerçek çıktının üretilmesi.
- [ ] Üretim Başlat'ta seçili UID ile raporda görünen UID kimliğinin aynı olduğunun kullanıcı makinesinde kontrolü.
- [ ] Gerçek profil yolu ve SHA raporunun aynı store dosyasını göstermesi.
- [ ] Eski UID, iki mağaza, değişmiş kaynak SHA, filtre değişimi / yeniden açılış, 4K/Excel, gerçek PETEK maskeleri.
- [ ] Windows %100/%125/%150 DPI, üretim esnasında performans ve güvenli kapatma.

**WINDOWS_NOT_VERIFIED** · **GERÇEK wudie KÖK NEDENİ SAHADA KESİNLEŞMEDİ** · **NO-GO for real production without user's acceptance**.

## Rollback
Eski V4.10.2/MOR/PETEK ZIP'i ve kullanıcı mağaza JSON/SQLite/maske yedeklerini ayrı saklayın; yeni ZIP'i var olan program klasörüne **kesinlikle üzerine çıkarmayın**. Bu sürüm yeni veritabanı şeması yazmaz. Teşhis/filtre işlemleri salt okunur; atama kaydı yalnız açık ve ayrıca onaylanan kullanıcı eyleminde değişebilir.
