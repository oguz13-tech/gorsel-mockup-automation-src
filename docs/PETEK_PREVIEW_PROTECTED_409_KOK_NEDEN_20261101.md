# PETEK_PREVIEW_PROTECTED_PIXELS_CHANGED — doğrulanmış kök neden

**Kaynak:** `MERKEZ/PETEK_V3/petek_visual_pipeline_vnext.py` ve
`SABLON_V2_MIMARI/core/petek_web_v477.py`.

## Gerçek hata zinciri

- Web önizleme, kaynak fotoğrafı `scene` ile `result[mask == 0]` piksellerini karşılaştırır.
- PETEK ortak motoru `despill_lower_left_geometry_v493` ile `render_scene` adlı geçici fotoğrafı
  değiştiriyordu. Düzeltme `mask == 0` (korunan) piksellerine uygulanıyordu.
- Motorun iç denetimi yanlışlıkla `render_scene` ile karşılaştırdığı için korunan piksel
  değişikliğini kabul ediyordu. Web kontrolü gerçek `scene` ile karşılaştırıp HTTP 409
  `PETEK_PREVIEW_PROTECTED_PIXELS_CHANGED` döndürüyordu.
- Tam olarak 90 korunan piksellik sentetik alt-sol magenta taşması ile önceki kodda hata yeniden
  üretildi. Sonucu web kontrolüne soktuğumuzda 90/90 piksel uyuşmazlığı ortaya çıktı.

## Kalıcı kod düzeltmesi

- Eski ön-des­pill işleminin korunan piksellerde yapacağı değişiklik **yalnız geçici çalışma
  görüntüsünde** bastırılıyor; gerçek `scene[mask==0]` geri konuluyor.
- Gerekli baskı içi işlemler, ızgara ve gölge efektleri aynen sürüyor.
- Tüm ortak güvenlik denetimleri **gerçek orijinal `scene`** ile yapılıyor.
- Eşleşmeyen korunan piksel oluşursa hata devam ediyor; maskenin dışını değiştiren diğer
  efektlerin hatası gizlenmiyor.
- `pre_pink_qa.suppressed_protected_pixels` sayısı kaydediliyor. Bu, korunan bölgede
  pembe taşma bulunduğunu ve **insan maske incelemesi** gerekebileceğini söyler.
- Korunan bölgelerdeki magenta kullanıcıya "temizlendi" diye raporlanmaz; çünkü onaysız
  boyamak, delik/üst-alt kavis/orijinal fotoğraf piksel korumasını ihlal eder.

## Sınırlar / test

- 7 yeni test: gerçek kaynak korunur; güçlü/doğal/kapalı aydınlatma; pembe açık/kapalı;
  fiziksel delik korumasını bozan bir efektin hâlâ reddedilmesi; API ile ortak karşılaştırma.
- 94 PETEK + UI + mağaza testi PASS. Ek 63 uyumluluk testi PASS; 1 SKIP, 1 DESELECT.
- Flask canlı Windows bağlantısı ve kullanıcının gerçek PETEK şablonu: **WINDOWS_NOT_VERIFIED**.
  Otomatik testlerle tüm sahnelerde garanti verilmez.

## Kurulum ve geri dönüş

1. Önce mevcut Ana Merkez'de Şablon İnceleme Servisini durdurup oturumu kapatın.
   8080 üzerinde başka çalışan uygulamayı PID doğrulamadan kapatmayın.
2. Bu ZIP'i **yeni boş klasöre** çıkarın; eski sistemin üstüne yazmayın.
3. `PETEK_PROTECTED409_DOGRULA_WINDOWS.bat` dosyasını çalıştırın. Manifest kontrolü
   `error: 0` sonucu vermeli.
4. `PETEK_PROTECTED409_BASLAT_WINDOWS.bat` ile Ana Merkez'i başlatın ve
   Şablonları İncele ve Onayla kısmına geçin.
5. `http://127.0.0.1:8080/api/petek/service-status` yanıtındaki `code_root` yeni
   kurulum klasörünü göstermeli. Tarayıcıda Ctrl+F5 ile yenileyin.
6. Aynı PETEK şablonunda pembe kenar temizliği açıkken A/B önizleme deneyin;
   ayrıca farklı PETEK şablonuyla 13/14/15/16 yarık ölçümünü kontrol edin.
7. Eski sürüme dönüş için yeni sürecin Şablon İnceleme Servisini arayüzden durdurun,
   eski klasördeki başlatıcıyı çalıştırın. **Veri taşıması yoktur.**

Orijinal fotoğraf, SQLite, mağaza ataması, kanonik şablon UID/SHA, onaylı dört köşe,
PETEK maske kayıtları ve yedekler bu ZIP ile değiştirilmez.
