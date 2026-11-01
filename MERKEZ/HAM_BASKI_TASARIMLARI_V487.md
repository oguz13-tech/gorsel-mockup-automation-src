# V4.8.7 — HAM BASKI TASARIMLARI

Ana çalışma klasöründe HAM BASKI TASARIMLARI otomatik oluşturulur. Yedi kategorili seri üretim kaynağı varsayılan olarak buraya bağlanır.

1. JPG/JPEG/PNG/WEBP dosyaları tek tek veya alt klasörlerle eklenebilir. Merkez açıkken yaklaşık üç saniyede bir kontrol yapılır. Dosyalar tamamen yazılmadan işlenmez.
2. Her giriş Ham1.jpg, Ham2.png, Ham3.webp ... olarak tek global sıra alır. Alt klasörler ayrı numara sırası açmaz; görseller alt klasörlerinde kalır. Format/dosya içeriği korunur.
3. İlk açılışta mevcut Ham300.jpg gibi dosyalar güvenle sahiplenilir; yeni fotoğraf Ham301 olur.
4. Ham301.jpg ve Ham301.png aynı numara kimliğidir. Çakışan numara ve farklı uzantılı aynı kaynak adı uyarı verir. Aynı fotoğraf byte'ları ikinci kez eklenirse SHA256 ile işaretlenir. Çıktı görsellerinde pHash kullanılmaz.
5. Bozuk dosya, symlink, kısmi indirme, beklenmeyen kaynak değişikliği ve desteklenmeyen biçimler uyarıyla korunur; hiçbir dosyanın üstüne yazılmaz.
6. Silinen numara yeniden kullanılmaz. Kalıcı numara defteri yerel %LOCALAPPDATA%/GorselMockup/HamBaski altında ve havuz içindeki _HAM_NUMARA_GECMISI.json dosyasında tutulur. İkisini de silmeyin.
7. Yeni numara dosya değişmeden ÖNCE kalıcı ayırtılır; elektrik kesilmesinde boş numara kalabilir ancak bu numara tekrar kullanılamaz.
8. Ham301-WifiKutusu-M5 stok/barkod, Ham301-M5-WifiKutusu model örneğidir. Başka tasarımlarla birleştirildikten sonra Ham dosyasının adını Windows Gezgini'nde değiştirmeyin.

Canlı Windows/OneDrive testi WINDOWS_NOT_VERIFIED. GitHub otomatik testleri sentetik fotoğraflarla çalışır.