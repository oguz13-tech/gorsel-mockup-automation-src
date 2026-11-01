# PETEK — zorunlu A/B kaldırıldı, düz gerçek ızgara sınırları

**Sürüm:** PETEK_OPTIONAL_AB_STRAIGHT_VENTS_20261101  
**Başlangıç:** `MAGAZA_ESLESME_P0_DUZELTME_WINDOWS_20261101.zip` (önceki MOR, PETEK ve mağaza P0 kodu korunur).  
**Kabul:** Otomatik ilgili regresyon **127 passed / 1 skipped / 1 deselected** (Linux/Xvfb). **WINDOWS_NOT_VERIFIED**.

## Neler değişti?

- Seri Üretim > `PETEK gerçek yarık gölgesi (13–16)`: `orta` varsayılan. **İsteğe Bağlı: Izgara / Pembe Önce-Sonra Test**. Bu testi açıp onaylama koşulu `start()` içinden kaldırıldı. Kullanıcının gerçek **toplu üretim başlatma onayı** hâlâ zorunlu; PETEK şablonu/dört köşe/maske **APPROVED** ve kaynak/mask SHA geçerlilik denetimleri aynen devam eder.
- `petek_slot_geometry_vnext.py`: Gerçek delik kanıtından ölçülen eksen her yarık için **tek, doğrusal eksen**. Eski tek tek satırlardaki koyu tasarım lekelerine göre serbest kıvrılan poligon yolu kaldırıldı. Ölçülen orijinal yarık üst-alt sınırları kullanılır. Çok uzun aykırı sınırlar diğer gerçek yarıklara göre ılımlı biçimde kısılır; medyan fiziksel yarık boyunun %82'sinden daha kısa/belirsiz yarık şablon bazlı QA hatası verir.
- `petek_finish_v492.py`: Üst-alt uçlardaki çizgi ve yuvarlak kalem kapağı taşması geçici görüntüde fiziksel yarık uzunluğuyla sınırlandırılır. Yalnız izin verilen maske baskı pikselleri değişebilir. Onaylı maske/quad, orijinal fotoğraf, SQLite, mağaza JSON, render geçmişi değiştirilmez.
- Sayı hâlâ **13/14/15/16 gözlenen gerçek yarık**; eksik yarık 15'e tamamlanmaz. Aynı fiziksel görüntüye ek tasarım çizgileri veya yapay boy uzatması yapılmamalıdır.

## Hata ve işleyiş

1. Üretime başlamak için PETEK A/B düğmesini kullanmanız **gerekmez**.
2. Görsel QA sorunluysa **yalnız hatalı PETEK üretim kaydı** hata alır; başka şablon/işler üretim motorunun mevcut hata politikasıyla devam eder.
3. Gerçek delik verisi güvenilir değilse `PETEK_IZGARA_KONUMU_BELIRSIZ` / `PETEK_YARIK_BOYLARI_INCELEME_GEREKLI` / `PETEK_IZGARA_BOY_TUTARSIZ` görülebilir. Bu teknik korumalar test kilidi değildir. Şablon maskesi 4 Köşe İnceleme'den düzeltilmelidir. Acilen normal görsel üretmek için yalnız kullanıcı seçimiyle koyu ızgara modunu `off` yapabilirsiniz; diğer mask/SHA güvenliği kapanmaz.
4. **Gerçek Windows fotoğraf havuzunda** en az 13/14/15/16 yarıklı zor örnekler, %100/%125/%150 DPI ve A/B önizleme/gerçek render karşılaştırması henüz yapılmadı. Bu paket yalnız geliştirme adayıdır.

## Kurulum / geri dönüş

ZIP'i ayrı boş `C:\AI_WORK\PETEK_SERBEST_TEST` klasörüne ayıklayın. `GORSEL_V4102_WINDOWS\GORSEL_V46_CANDIDATE` altında `PETEK_SERBEST_DOGRULA.bat` ardından `PETEK_SERBEST_BASLAT.bat`. Mevcut sisteminizin üstüne açmayın; gerçek veri arşivini otomatik bağlamayın.

Geri dönüşte aday klasörünü kapatıp **değişmeden duran** önceki `MAGAZA_ESLESME_P0_DUZELTME_WINDOWS_20261101.zip` sürümünü ayrı klasörde kullanın. Kodun hiçbir aşamasında şablon ve mağaza kayıtlarını taşıma/migration yoktur. Hiçbir özgün fotoğraf GitHub veya bu ZIP'e konulmadı.
