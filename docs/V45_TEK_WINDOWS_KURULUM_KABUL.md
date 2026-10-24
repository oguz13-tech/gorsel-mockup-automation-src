# V4.5 — TEK WINDOWS PAKETI / GÜVENLİ KURULUM VE KABUL

**Dağıtım:** Grup 1 + Grup 2 + Grup 3 + V4.5 kod geliştirmeleri *tek arşivde*. Gerçek üretim verilerini içine koymaz. Tek ZIP, EXE kurulum sihirbazı değildir; uygulama Python 3.11 + bağımlılıklar gerektirir.

## İşletim güvenliği
1. Onaylı 4 köşeleri kaydet. 8080 dahil eski uygulamayı bütünüyle kapat. OneDrive'ın çalışmasını ve yeni inbox dosyası gelmesini durdur.
2. Mevcut `SABLON_V2_MIMARI/ayarlar.db` SQLite veritabanına ait **tutarlı çevrimiçi yedek** ve normal görsel/maske klasörlerinin birebir yedeğini al. Yedek/hash kontrolü olmadan geçiş yapma. WAL/SHM dosyalarını çalışan SQLite'dan rastgele kopyalayarak veri bütünlüğü garanti edilmez.
3. ZIP'i `C:\GorselMockup_V45_ADAY` altında ayrı klasöre çıkar. Eski `C:\GorselMockup_V422` / V43 / V44 üzerine yazma, eski klasörü silme.
4. `BASLAT_V45_TEK_MERKEZ_WINDOWS.bat` dosyasına çift tıkla. Python 3.11 varsa tercih edilir; ilk açılışta bağımlılık kurulumu için internet gerekebilir. **Başlatma, yeni görsel inbox izlemesini otomatik başlatır**; bu aşamada inbox'a yeni şablon atma.
5. Gerçek ana çalışma klasörün: `C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu`. Kopya/DB yedeği doğrulanmadan buradaki kayıtlara yazan hiçbir editör işlemi yapma.
6. Gelişmiş Araçlar → G3 salt-okunur veri/SHA denetimi çalıştır; ardından G3 onaylı iki DB yedek + geri yükleme provasını yap. Bir hata varsa **NO GO** ve çalışan eski sürüme geri dön.
7. Tek onaylı Wi-Fi şablonu ve bir tasarımla deneme; yeni PNG, SHA makbuz, yerel Excel kontrolü. Ardından Cam A/B, PETEK, diğer kategoriler; onaylı köşeyi değiştirdikten sonra yeni görselle aynı geometri testi (eski çıktı korunmalı).
8. HTTPS Excel için ayrıca ImgBB/FreeImage bilgileri ve **görsellerin internete yüklenmesi konusunda açık kullanıcı onayı** gerekir. Pazaryeri XLSX için platformdan alınmış **boş orijinal şablonu** seç; barkod/SEO gibi eksik zorunlu alanları doldurmadan platforma yükleme.
9. İsteğe bağlı 4K için resmi `realesrgan-ncnn-vulkan.exe` + uyumlu `models` dosyaları ayrıca kurulmalıdır. Bu ZIP'te model ve exe **yoktur**. Normal görüntü 4K kapalıyken güvenle üretilir.
10. Çok büyük PNG/WebP'de otomatik düşük kaliteli işleme yoktur. İsteğe bağlı resmi ImageMagick kurulumu ve `MAGICK_EXE` tam dosya yoluyla bellek/disk sınırlı çalışma kopyası mümkündür; orijinal görüntü ve SHA değişmez.

## Yeni V4.5 ek arayüz
- **⏸ Duraklat:** sürmekteki görseli güvenle bitirir, bir sonraki işi bekletir.
- **▶ Devam Et:** kaldığı iş kaydından aynı Windows çalışmasında devam eder.
- **■ Güvenli Durdur:** duraklama hâlinde de beklemeyi sonlandırır; doğrulanmış çıktılar korunur.
- **Operasyon Özeti:** Salt-okunur kategori/durum/SHA/disk alanı, hiçbir içerik oluşturmaz.
- **Pazaryeri Excel Şablonuna Aktar:** HTTPS linki hazır SKU'ları kullanıcının boş XLSX başlıklarıyla eşler. Asıl XLSX değişmez.

## GO / NO-GO
Kullanıcının gerçek Windows ortamında 100/200/1000 gerçek görüntü, canlı SQLite yedek/kurtarma, 4K GPU, HTTPS Excel ve PETEK 34+ Golden kabulü yapılmadı. Bu paket **kod bakımından test edilmiş Windows kabul adayıdır**, koşulsuz ticari final değildir. Eski çalışan sürümü en azından kabul sonuna kadar sakla.
