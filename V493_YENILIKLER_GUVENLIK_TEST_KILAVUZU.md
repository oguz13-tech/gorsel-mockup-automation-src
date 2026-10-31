# Görsel Üretim Merkezi V4.9.3 — Güncellemeler, Test Merkezi ve Güvenli Kabul

**Durum:** Windows güvenli sürüm adayı. **WINDOWS_NOT_VERIFIED** — gerçek kullanıcı dosyaları, PETEK referans fotoğrafları, Vulkan/4K ve mağaza Excel servisleri bu derleme ortamında doğrulanmadı. Sıfır hata veya canlı üretim final onayı iddia edilmez.

**Kaynak:** V4.9.2 Windows aday kodunun ayrı bir kopyası. Çalışan V4.8.8, kullanıcıların eski onaylı dört köşeleri, `ayarlar.db`, orijinal şablon yedekleri ve PETEK maskeleri bu teslim sırasında değiştirilmedi.

## Yapılan / korunan işler

1. **Yeni kalıcı Yapmam Gereken Testler ekranı.** Testler sürümle birlikte ilk açılışta listelenir. Her kayıt: ne yapılacak, başarı ölçütü, nereye hangi rapor gönderilecek, açıklama/not. `Beklet`, `Sorun Var`, `Bekleyen Yap`, `Notu Kaydet`, `Test Ettim, Onayla ve Kaldır` ve `Tamamlananlar / Arşiv` durumları vardır. Onaylı test arşive taşınır ama silinmez. Bir sonraki sürüme geçildiğinde aynı kimlikli onaylı test otomatik yeniden açılmaz. Yeni sürümdeki yeni test kimlikleri görünür. Kullanıcının kendi elle onayı dışında PASS yok.
2. **Notlarım ve Görevlerim.** Not/görev kaydı, düzenleme, silme, görevi yapılmış işaretleme; Windows `%LOCALAPPDATA%\GorselMockup\PersonalCenter\personel_merkez_v493.sqlite3` içerisinde. Kod ZIP'i yenilense bile kişisel kayıtlar korunur. Üretim veritabanı kullanılmaz. Yedeklerken bu kişisel klasörü de ayrıca yedekleyin.
3. **Özellik / Araç Ara.** Ana işlem, şablon, PETEK, Excel, mağaza, 4K ve bağımsız görsel araçlarına hızlı arama. Yatay-Dikey, isimlendirici, format, filigran, 4K, bağlantılar, SEO ve recursive PNG için doğrudan Windows başlatıcıları.
4. **Güvenli Yeni Şablon Ekle** ana sayfada büyük hızlı kart. Yeni dosyaları `YENI-BOS MOCKUP SABLON HAVUZU/<kategori>` içine kopyalamak için mevcut güvenli aracı açar. Eski onaylı çalışma görsellerine veya orijinallere üzerine yazmaz; yeni görsellere otomatik onay vermez.
5. **Magenta tek seferlik aktarım** ana sayfanın kalıcı kartlarından çıkarıldı; işlem bitene kadar Test Merkezi'ndeki `Magenta Son Aktarım Aracı` düğmesiyle erişilebilir. 8080–8090 açık sunucu varken yazma kilidi kaldırılmadı. Program kendi **kimliği doğrulanmış** 4-köşe sunucusunu kullanıcının iki açık onayıyla güvenle durdurmayı teklif edebilir. Tanınmayan sunucuyu kapatmaz ve hiçbir dosyaya onaysız yazmaz. Kod burada gerçek PC'ye erişip şablonları değiştirmedi.
6. **PETEK 15 Izgara Geometri Kilidi.** Onaylı maske değişmeden, kaynak maskenin gerçek 15 yarığını perspektif ortamında arar. Bulunursa onlarla hizalanır. Yetersizse 4-köşe perspektifinden **15 sentetik gölge konumu** oluşturur; maske dışına, alt kavis/zemine ve fiziksel korunmuş yarıklara yazmaz. Hafif/Orta/Güçlü ayarlanabilir. Görsel doğruluk gerçek fotoğrafta incelenmelidir; fazladan/yanlış geometri riskine karşı A/B insan onayı gerekir.
7. **PETEK sol alt pembe kaçak.** Maskenin dışındaki yalnız dar alt-sol sınır koridorunda kalan neon-magenta kalıntıları, yakın nötr kaynak fotoğraf piksellerinden onarma; kaynak diskte değiştirilmez. Geniş/şüpheli alanı rastgele boyamaz; gerçek sahnede görsel kabul gerekir.
8. **PETEK Maske İnceleme sayfasında A/B.** `15 Izgara A/B Testi — Çalıştır`, `ÖNCE`, `SONRA`, güç seçimi ve isteğe bağlı pembe temizlik. Aynı gerçek tasarım ve maskeyle yalnız RAM'de çıktı üretir. Şablon ve maskeyi kaydetmez. Önizleme ve üretim ortak `draw_fifteen_slots` motorunu kullanır.
9. **Seri Mockup Üretimi** V4.9.2 filtre, arama, toplu seçim, sıralama, mağaza/Excel ve 4K düğmeleri korundu. PETEK için **Orta** başlangıç değeri gösterilir; kullanıcı A/B'yi kabul etmeden yeni efektli seri üretime geçilemez. 4K varsayılan kapalıdır.
10. **4K Real-ESRGAN**, Windows üzerindeki resmî NCNN Vulkan kurulum ve SHA-256 doğrulama BAT/PowerShell aracından açılır; model ağırlıkları bu ZIP içinde yoktur. Kullanıcının PC'sinde GPU/kurulum testi gereklidir. Normal 1200×1600 üretim korunur.
11. **YATAY - DİKEY GÖRSEL SEÇİCİ**, bağımsız araç başlatıcıları, 7 kategori şablon/maske onayı, PETEK kayıtları, üretim defteri, mağaza/Excel, HAM numara ve 4K opsiyonel motor mevcut V4.9.2 davranışıyla korunmuştur.
12. **Geri dönüş** `ESKI_GORUNUME_DON_WINDOWS.bat` yalnız görünümü döndürür; kod sürümünü geri almak için eski ZIP kopyasını ve ilgili veri yedeklerini tutun.

## Test Merkezi nasıl kullanılır?

- Ana ekrandan **Yapmam Gereken Testler**. Açılışta 14 adımlı test kartı var. Bunlar otomatik olarak PASSED sayılmaz.
- Solda test başlığına tıklayın, sağdaki ayrıntılı adımları takip edin. Hata çıkarsa not alanına girin ve **Sorun Var**. Henüz yapılamıyorsa **Beklet**.
- Her test başarı koşullarının tamamı gerçek bilgisayarda karşılandığında **Test Ettim, Onayla ve Kaldır**. Test ana listeden kaybolur, **Tamamlananlar / Arşiv** bölümünde saklanır.
- **Test Raporu Oluştur + Kopyala** düğmesi dosyayı `%LOCALAPPDATA%\GorselMockup\PersonalCenter\TEST_KABUL_RAPORU.txt` konumuna yazar ve panoya kopyalar. Raporu bu ChatGPT sohbetine yapıştırın veya dosya yükleyin; özellikle PETEK önce/sonra görsellerini de ekleyin.
- Notlar ve test durumları sürüm güncellemesinde mevcut ZIP klasöründe değil, ayrı kişisel AppData klasöründe saklanır.

## Güvenli kurulum / test sırası

1. V4.8.8'i ve güncel çalışan sürümünü **silme**. Yeni ZIP'i OneDrive dışındaki yeni, boş klasöre çıkar.
2. `GORSEL_V46_CANDIDATE\V493_DOGRULA_WINDOWS.bat` ile SHA-256 doğrulaması yap. Kod ve kullanıcı verisi değiştirilmez.
3. `GORSEL_V46_CANDIDATE\V493_BASLAT_TEK_TIK_WINDOWS.bat` ile başlat. Python 3.11 gerekebilir, ilk kurulumda internet gerekebilir.
4. Önce Test Merkezi ve Notlarım ekranında kapanıp açılma kalıcılığını kontrol et.
5. PETEK Şablon İncele ekranındaki **Orta / 15 Izgara A/B Testi** ile aynı şablonda önce/sonra. 15 gerçek fiziksel yarık hizası ve sol alt pembe kontrolünü yap. Onaylı maske ve orijinal fotoğrafı değiştirmez.
6. Magenta tek seferlik işlem için önce açık inceleme sunucusunu güvenle durdur, ardından Test Merkezi kısayolundan eşleşme ve yedek raporunu kontrol ederek uygula. **Gerçek PC dosyalarını burada uzaktan değiştiremiyoruz.**
7. 4K Durum/Kur/GPU Test ile resmî Real-ESRGAN EXE ve `.bin/.param` ağırlıklarını indirip yerleştir. Gerçek Vulkan test raporunu kontrol et.
8. Filtre/mağaza/Excel ve 7 kategori seri üretimini küçük test çıktılarıyla doğrula. Her kartı gerçek sonuçtan sonra onayla. Canlı üretim için GO kararı bütün kritik testlerden sonra verilebilir.

## Kanıt / otomatik test sınırları

- V4.9.3 yeni modüller + seçili eski PETEK, üretim, mağaza, HAM, magenta ve araç regresyonları: **97 PASS, 0 FAIL** (seçili kapsam; Linux test ortamı).
- Kalıcı Test Merkezi için AppData'dan bağımsız SQLite geçişi, onaylı arşiv ve yeniden açılış senaryosu test edildi.
- PETEK web API A/B sentetik görselle test edildi; kaynak dosya ve onaylı kayıt değişmedi.
- Windows gerçek kullanıcı kabulü: **WINDOWS_NOT_VERIFIED**.
- Geniş tarihsel takım bir test modülünde kaldırılmış eski `V2_KONTROL_MERKEZI/app.py` eksikliği yüzünden toplama aşamasında duruyor. Bu test çıkarılınca **278 PASS, 16 FAIL, 4 SKIP** aşamasında `--maxfail=16` ile durdu. Başarısızlıklar eski sürüm başlatıcıları, Git deposu varsayımı, eski arayüz adları ve 8080–8090 portunun dolu olması gibi nedenlerden kaynaklanıyor. Bunların tümü kapatılmadı; tam regresyon 0 hata olarak sunulmaz.
- **Kesin koşulsuz FINAL onayı yok.** Kodu ve test mekanizmasını teslim ediyoruz; gerçek fotoğraf kalitesi ve Windows üretimi insan kabulünde kontrol edilmelidir.
