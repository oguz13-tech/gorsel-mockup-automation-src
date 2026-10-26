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

## 27.10.2026 — PETEK klasörleri, kullanıcı tarafından silinen çıktılar, HTTPS Excel

- Kullanıcı fiziksel PETEK fotoğraf klasörü **Petek_Dolabi** ise mevcut adı **değiştirmeyin**. İç kategori kimliği `06_Petek_Kapama` kalır. Ana merkez > **PETEK Klasörlerini Kontrol / Eksikleri Oluştur** ile
  `YENI-BOS MOCKUP SABLON HAVUZU`, `2_SABLON_HAVUZU`, `2_SABLON_HAVUZU_ORIJINAL_YEDEK` içinde hangi PETEK dizininin seçildiğini görüntüleyin. Eksikler yalnız açık onayla yaratılır.
- `Petek_Dolabi` ve `06_Petek_Kapama` klasörlerinin ikisi de aktif dosya içeriyorsa otomatik birleştirme yapılmaz; önce durun ve her iki dizini salt-okunur inceleyin. Elle klasör taşımayın/silmeyin.
- Yeni PETEK fotoğrafı yalnız güvenli otomatik alımdan geçip çalışma ve ham yedek fotoğrafı doğrulandıktan sonra PETEK maske düzenleyicisinde seçilmelidir. Maske çizimi, kavis/delikleri elle gözle inceleme ve **insan onayı** zorunludur; otomatik köşe önerisi maske onayı değildir. Maskeler ve SHA bağlı onaylar **LocalAppData/GorselMockup/PetekV3** içinde, ortak üretimler **LocalAppData/GorselMockup/UnifiedV4** içinde saklanır. PETEK fotoğraf klasörü bu yerel kayıt klasörlerinin yerine geçmez.
- Geçmişte **bilerek silinen** üretim dosyaları için, ana merkez > **GELİŞMİŞ ARAÇLAR / Bilerek Silinen Eski Çıktıları Arşivle**. Önce önizlemede eksik dosya sayısını kontrol edin; gerçekten hepsini kendiniz sildiyseniz onaylayın. İki DB için yeni SHA'lı online backup ve restore denemesi yapılır; üretim defteri satırları `USER_REMOVED` olur; mevcut şablon, eski ürün SHA ve kayıtları silinmez. Bu işleme geri dönüş ihtiyaç halinde uzman kontrollü ve ayrıca açık onay gerektirir. Eksik dosyanın gerçek nedeni bilinmiyorsa onaylamayın.
- Üretim ekranında 4K seçeneğinin hemen altında **Üretimden sonra HTTPS Linke Çevir + Excel'e Yaz** kutusu var. Varsayılan **KAPALI**. İşaretlendiğinde yalnız **bu üretim turundaki SHA doğrulanmış görseller** seçilir ve bulut yüklemesi başlamadan ayrıca açık kullanıcı onayı sorulur. Hayır derse görsel internete gönderilmez. Önceki bağımsız “Mevcut Çıktıları HTTPS Linke Çevir + Excel'e Yaz” düğmesi ise geçmiş kayıtlar için ayrı ve açık onaylıdır.
- Bilerek silinen 35 dosya `USER_REMOVED` yapıldıktan sonra G3 raporu `user_removed=35`, `missing=0` gösterebilir (sonradan başka eksik oluşmamışsa). Başka `REVIEW_REQUIRED` kaydı ve OneDrive çalışma alanı uyarısı **otomatik çözülmez**; bunları final kabulünün dışında bırakmayın.
