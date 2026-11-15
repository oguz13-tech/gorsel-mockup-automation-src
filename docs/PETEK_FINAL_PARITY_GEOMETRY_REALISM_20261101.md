# PETEK A/B = Üretim Görünümü | 01.11.2026

## Doğrulanmış kod kusurları

- `petek_slot_geometry_vnext.py`: Önceki karar, fiziksel tek bir deliğin kayıtlı maskesi bozuk olsa bile orijinal fotoğrafın uç kanıtını dikkate almadan `PETEK_IZGARA_BOY_TUTARSIZ` fırlatıyordu. Bir hata bütün A/B önizlemeyi kapatıyordu.
- `gui_v4.py` PETEK A/B ışık modunu `natural` sabitliyordu. Seri üretim `petek_realism_profile='belirgin'` için `strong` kullandığından gölge, beyaz tonu ve efektler tutarsız görünüyordu. Web önizlemesi de normalde `natural` sabitliyordu.
- `engine.composite` magenta kaynaklı şablonda gri anti-alias maske piksellerinin opaklığını koruduğu için kaynak magentayı baskı beyazına geri karıştırıyordu.

## Yapılan kaynak düzeltmeleri

- Gerçek fotoğraf ve onaylı maskeden uç ölçümlerini AYRI değerlendir; uyumlu onaylı maskeyi tercih et, bozuk maske ucunu doğrulanmış fotoğraf ucu ile kurtar. İki uç da güvensizse o tekil yarık için **ilave gölge çizme**; orijinal delik ve kayıtlı maske korunur. Sahte 13–16 tamamlanmaz. Sonuç QA kaydında `endpoint_effect_suppressed_count` olarak sayılır.
- `PETEK_V3/petek_visual_pipeline_vnext.py`: Seri Üretim, Tk A/B ve Flask web önizleme ortak render sırasını kullanır: fotoğraftan salt-bellek pembe ön temizlik → render + gerçek beyaz uyumu / gradyan → malzeme günışığı → fiziksel yarık iç gölgesi → QA → isteğe bağlı pembe temizlik.
- Belirgin ışık ve uzun pencere gölgeleri önizlemeye iletilir; 3:4 canvas ve isteğe bağlı 4K yalnız teslim boyutlandırmasıdır.
- Gerçek `#FF00FF` kaynaklarda `mask>0` baskı pikselleri tam opak: pembe saçak oluşturacak alfa karışımı kaldırıldı. Kenar gölgesi/ton yumuşaması baskı sınırının içinde, fotoğrafı geri karıştırmadan uygulanır.
- Sahnedeki gerçek yan gövde beyazına göre baskı beyazı, mat görüntü, yumuşak ışık gradyanı, uzun pencere/yaprak gölgeleri korunur. Işık deseni fotoğrafik pencere konumu algılamaz; sabit kontrollü, deterministiktir.
- `PETEK_FINAL_DOGRULA_WINDOWS.bat` dosyasında Python `\v` kontrol karakteri sorunu önlendi. ASCII + CRLF gerçek `scripts\v4102_verify_package.py` yolu.

## Güvenlik ve kabul

- Kaynak fotoğraf, onaylı şablon/maskeler/4 köşeler, mağaza JSON'ları ve SQLite kaynak içeriğine yazma yok.
- 13/14/15/16 sentetik delik testleri; hatalı maske ucunun fotoğraftan kurtarılması; iki kanıt da bozuksa yalnız o şerit gölgesini bastırma; piksel-birebir aynı paylaşılan önizleme/üretim render fonksiyonu; magenta içeriğinin anti-alias maske üzerinden geri dönmemesi; genel PETEK/mağaza testleri çalıştırıldı.
- Tam proje testinin bazı alt kümeleri *kaynak pakette önceden bulunmayan* `V2_KONTROL_MERKEZI/app.py`, `MANUEL_GORSELLERDEN_MOCKUP_URET.bat` ve bu ortamda kurulu olmayan `flask` nedeniyle çalıştırılamadı. Bu eksikliği başarı olarak göstermiyoruz.
- Kullanıcının gerçek onaylı PETEK fotoğrafları ve Windows Tk/Flask canlı akışı burada doğrulanamadı: **WINDOWS_NOT_VERIFIED**.
- Onaylı gerçek yarık geometrisi kaynağından bozuksa, orijinali değiştirmeden sıfırdan fiziksel doğruluk garanti edilemez. Yeni düzenleyicide şablon kaynak kontrolü gerekebilir.

## Geri dönüş

Eski ZIP/kurulum değişmeden durur. Yeni ZIP yalnız yeni `C:\AI_WORK\PETEK_FINAL_TEST` çalışma klasörüne çıkarılır. Eski kurulum aynı haliyle kullanılabilir. Yeni test sürümünü silmek veri kaybı yaratmaz, ancak kullanıcının ayrı çalışma klasörü seçimi varsa oluşturduğu çıktıları yedekleyin.
