# V4.7.6 — Altı kategori inceleme penceresi ve PETEK görüntülenebilirlik düzeltmesi

## Kullanıcının Windows ekranında görülen somut durum (27 Ekim 2026)
- Altı kategori dört köşe inceleme düğmesi `8080 port sahibi doğrulanmış eski V4.x inceleme sunucusu değil` uyarısıyla açılmıyor. Bu **koruyucu uyarıdır**, veri kaybı veya bozuk şablon kanıtı değildir.
- PETEK maskesi editörü açılıyor, fakat sol araç sütunu dar olduğu için metin ve düğmeler sıkışıyor.
- Kullanıcı `YENI-BOS MOCKUP SABLON HAVUZU/Petek_Dolabi` klasörünü oluşturmuş. Bu sistemde desteklenen **doğru PETEK gelen-kaynak klasörüdür**.

## Kod değişikliği
- `MERKEZ/legacy_manager.py`: `choose_review_port()`, kullanımdaki 8080'a müdahale etmez; boş 8081–8090 arası lokal port seçer. Kimlik kontrolü seçilen portta yine **özel token, PID, çalışma ve kod kökünü** zorunlu doğrular.
- `MERKEZ/merkez.py`: portu `MOCKUP_PORT` ile **mevcut** Flask uygulamasına geçirir; tarayıcıyı seçilen doğrulanmış adreste açar. 8080 sahibini okumaya, kapatmaya ya da taskkill yapmaya artık ihtiyaç yoktur. Altı kategori `/tools` ekranı da aynı adresi kullanır.
- `MERKEZ/PETEK_V3/gui.py`: kontrol sütunu normal ekranda 310–370px ve pencere minimum eni 930px'e kadar genişletildi; başlık ve notlar dar kolondaki kesilmeyi azaltacak biçimde güncellendi. Tekerlek, PETEK araç kolonu içinde çalışır.
- Bunlar hiçbir çalışma şablonu, orijinal yedek, eski onay, maske veya SQLite kaydı üzerinde değişiklik yapmaz.
- PETEK fiziksel klasör haritası:
  1. `YENI-BOS MOCKUP SABLON HAVUZU/Petek_Dolabi`: gelen yeni görseller
  2. `2_SABLON_HAVUZU/Petek_Dolabi`: aktif çalışma şablonları
  3. `2_SABLON_HAVUZU_ORIJINAL_YEDEK/Petek_Dolabi`: korunmuş orijinaller.
- Dahili kategori ID'si `06_Petek_Kapama`; bu **yeni ikinci fiziksel klasör açma talimatı değildir**. Onaylı maske AppData/GorselMockup/PetekV3 dizininde saklanır. İki farklı alias dizininde aktif görsel bulunursa sistem otomatik birleştirme yerine güvenlik hatası verir.

## Kabul sınırları
- `TESTLER/test_v476_review_port_petek_ui.py` yerel port seçimi, sunucu kimlik tokenı, ana merkez yanlış süreci durdurmama ve doğru PETEK klasör haritasını sınar. Tk GUI içerikleri Windows kullanıcısının kendi çözünürlük/DPI ayarında ayrıca görülmelidir.
- V4.7.5 bağımsız audit ile bulunan ve henüz kapatılmayan üç P0 risk sürmektedir: canlı SQLite WAL taşıma, taşıma sonrası eski DB güncellenmesi, magenta işleminde mağaza JSON rollback. Kullanıcı **2. Magenta Uygula / 5. Çalışma Alanını Taşıma Kopyası / 6. Etkinleştir** işlemlerini kullanmamalı. Bunlar ayrı düzeltme gerektirir.
- ZIP ayrı **boş** klasöre çıkarılmalı; eski sürüm ve orijinal çalışma klasörü üzerine yazılmamalı. `GORSEL_V46_CANDIDATE/BASLAT_V47_WINDOWS.bat` başlangıç dosyası uyumluluk nedeniyle eski adını taşır. Mevcut Ana Çalışma Klasörü seçiminde hiçbir değişiklik gerekmez.
