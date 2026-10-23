# GÖRSEL ÜRETİM MERKEZİ — V4.3 SON DÜZELTME / KURULUM VE KABUL

23.10.2026. KANONİK başlangıç V4.2.2 ZIP; bu ayrı bir **V4.3 aday sürümüdür**, canlı Windows kabulü yapılmadı. `main` ve kullanıcı dosyalarına in-place değişiklik YOK.

## Kullanıcının onayladığı mevcut durum
- Windows V4.2.2 7 kategoride birden fazla tasarımla görsel üretimi yaptı; görsel genel kalite kullanıcı tarafından iyi bulundu.
- Cam optik efekt görünmüyor; eski Excel sistemi gibi **bulut HTTPS görsel URL'si** ve Excel `Resim Linki` sütunu yazılmamış.
- Onaylı 4 köşe tekrar düzenlenip onaylanınca yeni aktif geometri hemen kullanılmalı (Seçenek B). Onaylı şablon için yeniden onay engellenmemeli.
- İş sınırı kaldırılmalı; fotoğraf ışığı / cam yansıması Kapalı/Açık net olmalı; köşe yuvarlatma 4 köşe onay ekranına taşınmalı; butonlar açıklanmalı.

## Eski Excel kaynak kodu gerçeği — neden V4.2.2 eksikti?
- `toplu_gorsel_linkle.py`: `ayarlar.json > bulut_ayarlari > imgbb_keys` ile **ImgBB** `https://api.imgbb.com/1/upload`; yanıt gerçek `https://...` link; `Gorsel_Linkleri.xlsx` içinde `Dosya Adı`, `Resim Linki`.
- `99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/pc_master_factory.py`: `AsyncCloudUploader` ImgBB çoklu anahtar, başarısızsa FreeImage; üretimden sonra URL, persist `UPLOADED_PENDING_EXCEL`, SKU→ Excel. Alanlar: `Stok Kodu`, `Barkod`, `Model Kodu`, `Kategori`, `Ham Baskı Dosyası`, `Mağaza Grubu`, `Ürün Adı`, `Açıklama`, `Mockup Dosya Adı`, `Resim Linki`, `Eklenme Zamanı`. URL başarısızsa satır link hazır sayılmaz; bir sonraki denemede render ve upload tekrarı istenmez.
- V4.2.2 `MERKEZ/PETEK_V3/excel_links_v42.py` ise `file:///` bilgisayar bağımlı yerel hyperlink yazıyordu. **Bu gerçek bulut/marketplace liste bağlantısı değildir.**

## V4.3 kod değişiklikleri
1. `MERKEZ/URETIM_V4/cloud_excel_v43.py`: kullanıcının açık onayı ile mevcut (SHA doğrulanmış) V4 çıktılarını orijinal bulut sağlayıcılarına göndermek için ayrı düğme; her SKU/output-sha için kalıcı `cloud_urls_v43.sqlite3` kayıt (yeni yerel V4 alanında); tekrar upload YOK; bağlantı yoksa Excel'e sahte URL yok; yeni `*_BULUT_LINKLI.xlsx` ve `.csv` dosyaları create-only. `Resim Linki` **HTTPS tıklanabilir**; mevcut `file:///` ayrıca `Yerel Dosya` kolonunda. Sütun isimleri eski fabrika sözleşmesine uyumlu; **SEO Açıklama mevcut V4 ledger'ında yok, boş bırakılıyor, uydurulmuyor.** Excel SKU/hyperlink okunup doğrulanıyor. Çıktılar otomatik pazaryerine gönderilmez.
2. `gui_v4.py`: iş sınırı alanı kaldırıldı (`max_jobs=None`, motor seçili şablon × tüm tasarımlar, başlama öncesi gerçek sayıyı gösterip onay ister); iki açık seçenek `Cam Yansıması AÇIK / Doğal Işık` ve `Efektler KAPALI / Orijinal Baskı`. A/B gerçek baskı önizleme düğmesi. Yarımlar/sha güvenlik butonları kaldırılmadı; anlaşılır yardım metinleri. Ayrı HTTPS/Excel düğmesi açık bulut onayı ister, mevcut renderı tekrarlamaz.
3. `finish_v42.py`: kontrollü geniş softbox + hafif çevre yansıması, açık ve koyu tasarımda görünür; yalnız cam kategorilerinin baskı maskesine, odanın/çerçevenin hiçbir pikselini değiştirmeden. Referanslar: Corning Museum glass lighting, Photoshop gradient overlay teknikleri; gerçek A/B görsel QA kullanıcıdan bekleniyor.
4. `SABLON_V2_MIMARI` editor: cam yuvarlatma seçimi 4 köşe onay düğmesinin önüne taşındı, cam dışı kategorilerde gizlendi. Aynı `template_profiles` satırı güncel köşelerle **APPROVED** kalır ve yeni kimlikle yeni üretim yapılır. Transaction içinde `approved_geometry_revisions` tablosuna önceki/yeni quad denetim izi eklenir. **Güvenli yedeklemeden sonra** kullanın; canlı OneDrive DB'de özel dikkat. Çalışan görüntü ve maske ham dosyaları dokunulmaz.
5. `design_proxy_v43.py`: 40 MP üstü yüksek çözünürlüklü JPEG için OpenCV azaltılmış DCT decode ve **yalnız yerel çalışma türevi**; orijinal baskı dosyası SHA identity ve dosya biçimi korunur. 415MP PNG güvenli decode edilmez: yanlışlıkla >1GB RAM harcamak yerine ad/piksel açık hata ve diğer tasarımlara devam. PNG sınırsız kabul iddiası YOK.
6. V4.3 yeni recipe `v4-3-...`: yeni görüntü çıktıları eski SKU/çıktı üzerine yazılmaz; onaylı köşe/efekt değişimi yeni kimlik üretir. Önceki V4.2.2 çıkışları Excel URL backfill için korunur.

## Kullanım ve dosya düzeni
1. Çalışan V4.2.2 açık işleri kapat; dört köşe onaylarını kaydet ve `SABLON_V2_MIMARI/ayarlar.db` ile WAL/SHM (varsa) güvenli DB yedeği al. Eski `2_SABLON_HAVUZU` ve yedekleri silme.
2. **Ayrı klasör** `C:\GorselMockup_V43` içine ZIP'i çıkar; aynı mevcut OneDrive ana çalışma klasörünü seç.
3. `BIRLESIK_V42_BASLAT_WINDOWS.bat` (V4.3 yazsa da dosya adı tarihî uyumluluk için aynı) ile aç.
4. `6 KATEGORİ — ŞABLON / 4 KÖŞE İNCELE`: onaylı cam şablonunda köşeleri düzenle, cam yuvarlatma seç, **Bu Şablonu Onayla**. Yeni onaylı quad hemen aktif; eski renderlar korunur.
5. `7 KATEGORİ`: cam A/B gerçek baskı önizleme + cam açıksa/güçlü değilse doğal efekt. İstenen şablonları seçip sınırsız üretimi toplam sayıyı doğrulayarak başlat.
6. `☁ Mevcut Çıktıları HTTPS Linke Çevir + Excel'e Yaz`: **ayrı açık onay** gerektirir. `ayarlar.json` içinde ImgBB/FreeImage anahtarı yoksa hiçbir görsel yüklenmez; yerel Excel (file:///) eski biçimde kalır. Yeni `*_BULUT_LINKLI.xlsx` gerçek `Resim Linki` (J sütunu), SKU (A), yerel yol (L) ve SHA (M) alanlarını içerir.
7. `Yarım İş / Kilit Kurtarma`: stale lock ve yarım PENDING/REVIEW_REQUIRED kontrolü; kullanıcı onay verince yalnız gerekli karantina/temizleme. `SHA Kayıtlarını Doğrula`: salt-okunur çıktılar/kayıt hash'leri, yeniden üretim/indirme yapmaz.

## Test sonuçları ve kabul
- 3 bağımsız TESTLER grubu: 70 PASS / 2 SKIP, 46 PASS, 46 PASS = **162 PASS / 2 SKIP**.
- `tests/test_user_tools.py`, `tests/test_p0_independent_release_safety.py`: **18 PASS**.
- V4.3 cloud+optik+quad 9 sentetik PASS (yukarıdaki sonuçların içinde). Bulut testi sahte HTTPS yanıt kullanmıştır, **gerçek ImgBB/FreeImage yüklemesi yapılmadı**.
- Tk sanal ekran smoke: yeni seri üretim penceresi açıldı, yeni bulut link düğmesi var, maksimum iş inputu yok.
- Tam tek turluk pytest denemesi uzun süren test nedeniyle zaman sınırına takıldı; gruplar ayrı tamamlandı. Windows + canlı DB + gerçek A/B, gerçek Excel HTTPS link ve gerçek bulut API henüz kabul edilmedi.
- Ticari GO için Windows'ta 1 Cam Dikey, 1 Cam Yatay, 1 Cam Doğrama, 1 Ocak Arkası yansımalı/kapalı A/B; 1 onaylı şablon tekrar dört köşe kaydet/onayla, yeni SKU ve geometri; 1 eskiden üretilmiş görsel için HTTPS URL doğrulama (yeni upload YOK); seçili 7 kategori seri / Excel çift tıklama testi zorunlu.
- **İlk pilotta `Tüm Şablonları Seç` tıklayıp kontrolsüz binlerce iş başlatmayın**; önce bir şablon + küçük tasarım klasörüyle deneyin. `İş Sınırı` bilinçli kaldırıldı, fakat yine güvenli durdurma mevcut.