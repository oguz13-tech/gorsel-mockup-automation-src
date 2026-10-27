# V4.7.7 — 7 kategorinin şablon/maske incelemesi TEK TARAYICI EKRANINDA

## Kullanıcının ilettiği eksiklik
- 6 kategori köşe incelemesi tarayıcıda, PETEK maskesi ayrı Tk penceresinde kalıyordu.
- Kullanıcı PETEK'e 7. kategori olarak ana şablon inceleme ekranında erişmek istiyor.
- Bu sürüm yalnız "PETEK için ayrı uygulamayı aç" kısayolu eklemez.

## Gerçek entegrasyon
- `SABLON_V2_MIMARI/templates/index.html` sol kategori sütununda
  **07_Petek_Dolabi — Şablon / Maske / Onay**.
- Aynı sayfadaki `petekV477Editor` orta alanda PETEK fotoğrafını, kaynak-piksel
  4 köşe işaretlemeyi, ön ahşap boyama ve delikleri siyah maskeleme,
  üst-alt bağımsız kavis noktalarını, otomatik maske taslağını,
  taslak kaydı ve kullanıcı incelemesini gösterir.
- `static/js/petek_editor_v477.js` mevcut Flask sunucusunun
  `/api/petek/*` rotalarına (aynı Host/Origin/CSRF) bağlanır.
- `core/petek_web_v477.py` **yeni DB oluşturmaz**: yalnız
  mevcut `MERKEZ/PETEK_V3/registry.py` ve `engine.py` maskelerini,
  kaynak SHA256 ve insan onaylarını okur/kaydeder.
- Bütün geçmiş onaylı PETEK profilleri **değişmez (immutable)**, web panelinde
  salt okunur açılır. Yeni/düzenlenmiş şablon önce DRAFT; operatör dört
  köşe, delik, üst-alt kavis, yan yüz, zemin kontrol kutusu ve adını
  doğrulamadan üretime APPROVED olarak girmez.
- Çalışma kaynak dosyası yalnız `2_SABLON_HAVUZU/Petek_Dolabi`
  (ya da aktif eski fiziksel alias); orijinal yedek ve gelen kutusu
  değiştirilmez. `YENI-BOS MOCKUP SABLON HAVUZU/Petek_Dolabi`
  gelen görsel havuzudur; PETEK kategori kimliği `06_Petek_Kapama`.
- Maske kaynak dışına taşıyorsa, boş veya şüpheli baskı alanı içeriyorsa
  `engine.mask_check` onay vermez. Browser RGBA PNG yalnız
  **tamamen opak ve eşit RGB kanallı** ise gerçek gri tona dönüştürülür.
  PETEK üst/alt kavisleri varsa kayıt öncesi `curves.apply` ile
  kesin maske bağıntısı doğrulanır.
- Maskeyi otomatik algılamak, **onaylı maske üretmez**.
- Sol kategoride PETEK'ten 6 kategoriye geçişte kayıtlı olmayan değişiklik
  varsa kullanıcı bilgilendirilir; 6 kategori şablonlarını ve veritabanını
  kaydetmez/değiştirmez.

## Güvenlik ve test kanıtı
- `TESTLER/test_v477_petek_browser_integration.py`: gerçek PETEK registry
  ile sentetik görsel/taslak/onay döngüsü, kaynağın SHA bağı, onaylı
  maskenin tekrar kaydedilememesi, sahte/şeffaf maskenin engellenmesi,
  yol dışına çıkma, yeni alias klasörü açılmaması.
- Windows/Linux gerçek ZIP çıkartma smoke testleri; browser JS için
  syntax denetimi ve sayfa markup testleri.
- Kullanıcının bildirdiği 45 onaylı PETEK görseli ve 255 üretim çıktısı
  **bu geliştirmede değiştirilmez**.
- Cam ve ahşap kategorilerinin köşe editörüne PETEK maske kurallarını
  uygulatmıyoruz: aynı arayüzde kategoriye göre doğru motor seçilir.

## Dürüst kabul durumu
- CI = kod ve sentetik dosya akışı doğrulanmış olabilir.
- Gerçek Windows tarayıcısı ve mevcut PETEK görselleriyle insan incelemesi
  hâlâ gerekir. Teslimde `WINDOWS_NOT_VERIFIED` ayrımı korunur.
- Önceki bağımsız denetimde tespit edilmiş **magenta uygulama rollback**
  ve **SQLite WAL çalışma alanı taşıma** riskleri çözülene kadar
  bakım merkezi 2, 5 ve 6 düğmeleri kullanılmamalıdır.
