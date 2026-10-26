# V4.6 Windows aday paket — WINDOWS_NOT_VERIFIED

Bu paket ticari final kabulü değildir. 346/346 eski magenta görselin kullanıcı
kabulü korunur; bunları tekrar onaylamanız istenmez. Yeni giriş/üretim kabulü ayrıdır.

1. ZIP'i yeni, boş bir yerel klasöre çıkarın. Mevcut programın üstüne çıkarmayın.
2. Python 3.11 kurulu olmalı. BASLAT_V46_WINDOWS.bat dosyasına çift tıklayın.
   İlk açılış internetten yalnız bu paketin .venv ortamına kilitli paketleri kurar.
3. Ana merkezde ANA ÇALIŞMA KLASÖRÜ alanından mevcut gerçek veri kökünü seçin.
   Eksik/boş izole deneme havuzunu seçmeyin. Kod klasörü veri klasörü değildir.
4. Yeni görsel alımı ve editör açılışı için ekrandaki yedek/onay adımını okuyun.
   SQLite online yedeği LocalAppData/GorselMockup/UnifiedCenter/DB_YEDEK içinde
   saklanır; ayrı geçici kopyada geri yükleme/bütünlük testi yapılır. Canlı DB'ye
   otomatik geri yükleme/migration yoktur.
5. Yeni köşesiz magenta şablonların önerileri taslaktır; gerçek baskı yüzeyini
   gözle onaylamadan üretime açılmaz. PETEK fiziksel ön/slot/kavis maskesi gerekir.

## Kabul ve rapor
Gerçek Windows'ta yeni giriş, onay, tek 1200x1600 üretim, Excel görsel bağlantısı,
UI ve PETEK görsel kalitesi halen doğrulanmalıdır. İlk gerçek görsel kabulünden
önce gözetimsiz 100/1000 seri üretime geçmeyin. Bulut/pazaryeri gönderimi yapmayın.
4K isteğe bağlıdır; GPU çalıştırması bu ortamda test edilmedi. 4K kapalı normal
üretim bağımsızdır. KUR_REAL_ESRGAN_4K_WINDOWS.bat ayrı isteğe bağlı kurucudur.

## Güvenli geri dönüş
İşlemi güvenli durdurun, bu merkezin açtığı editörü merkezden kapatın, programdan
çıkın. Eski program klasöründeki başlatıcıyı kullanın. Aday ZIP eski kaynakları
ve onayları taşımadığı için kod geri dönüşü veri kopyalamayı gerektirmez.
DB geri yüklemesi gerekiyorsa otomatik kopyalama yapmayın: tüm yazıcılar kapalı,
mevcut DB/WAL/SHM korunmuş ve yedek SHA doğrulanmış olmalı; ayrı açık onayla
uzman kontrolünde gerçekleştirilir. Orijinal/yedek/çıktı klasörlerini silmeyin.
