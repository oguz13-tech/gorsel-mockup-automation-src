# GÖRSEL ÜRETİM MERKEZİ V4.9.5 — GÜVENLİ ADAY / YENİLİK VE KABUL

**Tarih:** 31 Ekim 2026  
**Kaynak:** V4.9.4 — bağımsız yeni ZIP, mevcut Windows/OneDrive çalışma dosyaları bu ortamda değiştirilmedi.  
**Durum:** `WINDOWS_NOT_VERIFIED`. Kod ve sentetik testleri geçmesi, gerçek üretimde kusursuzluk onayı değildir.

## Bu sürümde yapılanlar

1. **PETEK final pembe/iz temizliği:** Sol, sağ, üst ve alt maske sınırları ile dört köşe; yalnızca geometrik şeritlerde yüksek doygunluklu pembe magenta kalıntıları ve 15 koyu yarık kenarları. Orijinal fotoğraf komşuluğundan inpaint onarımı, tüm değişiklikler yalnızca *kopya üretim sonucunda*. Gerçek baskı tasarımının orta alanı, beyaz gövde, zemin/gölge ve onaylı maske korunur. Geniş/makul olmayan magenta alanında kalite kontrol ve kullanıcı incelemesi; otomatik başarı iddiası yok. **Şimdilik beyaza boyama/1–2 cm maske uzatma yok.**
2. **PETEK ızgara yoğunluğu:** Varsayılan **Orta** korunur. Önceden çalışan 15 yarığı gerçek deliklerle hizalama, gerekirse perspektifle tamamlayan mod korunur.
3. **PETEK Önce/Sonra:** Hem şablon maskesi önizlemesi hem Seri Üretim A/B işlemi aynı V4.9.5 kenar temizleme yöntemine bağlandı. A/B onayından önce kalıcı maskeyi değiştirmez.
4. **4K Real-ESRGAN:** Açılışta gereksiz 4K taraması yok. Kullanıcı 4K seçince kurulu motoru kontrol eder; doğrulama sonucunu yerel AppData önbelleğinde saklar. Eksik kurulumda mevcut resmi SHA-256 doğrulamalı kurucuya geçiş yapar. Kurulum seçilmeden normal üretim sürer. Kullanıcının bildirdiği kurulu 4K motoru eski ZIP klasöründe bulunabiliyorsa sınırlı konum aramasıyla kullanılabilir; GPU gerçek Windows testi hâlâ gereklidir. Ayrı 4K kurulum düğmesi zorunlu değildir.
5. **Birlikte pencere kullanımı:** Seri Üretim penceresi artık ana merkeze modal/transient kilitle bağlanmıyor. Açık olan pencerede tekrar tıklama onu öne getirir. Şablon İnceleme başlangıç önkontrolü/SQLite yedekleme UI ana iş parçacığında bekletilmez. Onay/snapshot ve veri koruma korunur.
6. **Performans:** Seri Üretim arayüzü önce hızlı açılır, motor ve şablon indeksleri arka planda yüklenir. Şablon İnceleme başlatma/önkontrolü, HAM tasarım taraması ve onaylı envanter kontrolü de UI'yi bloke etmeyen akışa ayrıldı. Gerçek kullanıcının 13 saniyelik Windows ölçümü ancak kendi PC'sinde doğrulanabilir.
7. **Seri Üretim görünümü:** Ana ekranla tutarlı koyu modern büyük başlıklı bölümler; şablon ve kategori filtresi, tasarım/mağaza seçimi, PETEK kalite, 4K, HTTPS/Excel ve süreç paneli; uzun formlarda kaydırma korunur.
8. **Onaylı şablonun tekrar dört köşesi:** Mevcut şablon inceleme sayfasında köşeleri düzeltip “Bu Şablonu Onayla” yapılabilir. PETEK için mevcut onaylı maskeden yeni revizyon taslağı oluşturulup yeniden onaylanır. Test Merkezi'ne adımları eklendi; önceki onay sessizce değiştirilmez.
9. **Kalıcı Yapmam Gereken Testler:** Altı yeni kabul kartı: çoklu pencere, Windows açılış hızları, modern üretim UI, PETEK pembe temizliği, 4K isteğe bağlı kontrolü, onaylı şablon revizyonu. Test kaydı program kaynak kodundan ayrı AppData'da; kullanıcının **Beklet/Sorun Var/Onayla** kayıtları otomatik işaretlenmez.
10. **Önceki özelliklerin korunması:** Doğrulanmış Programı Kapat; Notlarım ve Görevlerim; Özellik/Araç Ara; Güvenli Yeni Şablon Ekle; Yatay-Dikey-Kare Seçici; PETEK 15 çizgi; 7 kategori; şablon/onay; mağazaya göre Excel/HTTPS ve Magenta tek seferlik güvenli değiştirme aracı. Magenta'nın gerçek kullanıcının dosyaları üstüne başarıyla yazıldığı *iddia edilmez*.

## Kurulum

1. Mevcut V4.8.8/V4.9.4 çalışan yazılımı ve özellikle orijinal yedek klasörünü **SİLME / ÜZERİNE AÇMA**.
2. `GORSEL_V495_WINDOWS.zip` dosyasını ayrı boş, OneDrive dışı yerel klasöre çıkart.
3. ZIP içindeki `GORSEL_V495_WINDOWS\GORSEL_V46_CANDIDATE` klasöründe `V495_DOGRULA_WINDOWS.bat` çalıştır. İlk test için Python 3.11 gerekir. Kurulum sonrası doğrulamayı tekrarla.
4. Aynı klasörde `V495_BASLAT_WINDOWS.bat` ile aç. Mevcut ana çalışma klasörü yalnızca normal sistemin onaylı yolu ile seçilir.
5. **Yapmam Gereken Testler** ekranını aç; PETEK A/B (15 ızgara + 4 kenar), çoklu pencere, açılış süreleri, 4K GPU, dört köşe tekrar onay ve Magenta aktarımını sırayla test et. Sorun varsa **Sorun Var** kullan ve orijinal/önce/sonra ekran görüntülerini gönder.

## Gerçekten kontrol edilenler

- 113 seçili kaynak regresyonu, sentetik PETEK ve SQLite/arayüz bağlantıları geçti.
- Linux sanal masaüstünde: ilk ana görünüm ~0,35 sn, üretim yükleniyor penceresi ~0,014 sn; bunlar Windows'taki 13 saniyeyi ortadan kaldırdığının kanıtı değildir.
- ZIP'den tekrar çıkarıp SHA256/CRC ve seçili regresyonların test edilmesi paket oluşturucusunda zorunludur.

## Açık sınırlamalar

- Kullanıcının gerçek PETEK görüntülerinde pembe kalıntının tamamen kalktığı gözle doğrulanmadı. Sentetik ölçüm 1690/1690 temizdir ama gerçek kalite garantisi değildir.
- Gerçek Windows/OneDrive/SQLite verisiyle tüm pencerelerin aynı anda çalışması, 4K Vulkan GPU, 7 kategori uzun batch, gerçek HTTP/ImgBB/Trendyol Excel ve Magenta fiziksel dosya aktarımı henüz test edilmedi.
- Kapsamlı tarihsel test paketinde daha eski başlatıcı dosyaları ve ortam şartlarına bağlı başarısızlıklar tümüyle kapanmış değildir; seçili test PASS bütün evrenin PASS olduğu anlamına gelmez.
- Herhangi bir güvenlik kilidini kapatıp sessizce veri üzerine yazma yapılmaz; gerçek kullanıcı onayı sürer.
