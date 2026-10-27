# V4.7.2: Magenta kaynak birleştirme + eski Windows sürüm/test klasörlerini denetleme

## Kullanıcının doğruladığı üretim kabulü

- PETEK: **45 gerçek baskılı görselde** kavis ve dikey çizgiler kabul edildi.
- Yedi kategori: **255 gerçek görsel** uzun seri üretimde başarılı.
- Bu dosyalar sistem kaynaklarını konsolide ederken korunur.

## Kullanıcının Windows yol örnekleri

- Canonical runtime: `C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu` (uygulamada **Ana Çalışma Klasörü** ile seçilendir).
- Magenta LAB fotoğrafları: `C:\AI_WORK\GORSEL_REFERENCE_LAB_20261024\approved_chroma_test_20261026_latest_db\chroma_previews`.
- Eski aday klasörleri: `C:\AI_WORK`, `%USERPROFILE%\Downloads` ve kullanıcının bildireceği diğer kökler.
- **Aktif kod**: çalışan `BASLAT_V47_WINDOWS.bat` paketi içindeki `MERKEZ`, ayrı ve korunan klasör.
- **Aktif yerel durum**: `%LOCALAPPDATA%\GorselMockup\UnifiedV4` (üretim), `%LOCALAPPDATA%\GorselMockup\PetekV3` (maske), `%LOCALAPPDATA%\GorselMockup\UnifiedCenter` (runtime seçimi/yedekler). Bunlar birer *eski/test* klasörü DEĞİL. OneDrive içine körlemesine taşımayın.

## Arayüz / İşlem adımları

1. V4.7.2 ZIP'i farklı, boş bir dizine çıkarıp bir kere `BASLAT_V47_WINDOWS.bat` ile çalıştırın. G3 backup+restore PASS olmalı.
2. Ana merkez > **Gelişmiş Araçlar > Magenta / Eski Sürüm Güvenli Dosya Denetimi**, veya ana program kapatıldıktan sonra ayrı `BAKIM_V472_MAGENTA_KLASOR_DENETIM_WINDOWS.bat`.
3. **1. Magenta ↔ Ana Önizleme / Rapor**: tamamen okuma. Dosya adı/kategori, boyutlar, SHA, SQLite profil eşleşmesi, varsa magenta laboratuvarındaki aynı SHA+UID insan onayı. Yerel HTML iki görseli yan yana gösterir. Önce bütün durumları inceleyin.
4. Status `READY_APPROVED_TRANSFER`: aynı kategori+isim, aynı boyut, aynı dosya baytları için güvenilir laboratuvar onayı; seçili dosya tek tek değişir, profilde kaynak SHA ve onaylı geometri **aynı lab SHA kanıtıyla** yenilenir.
5. Status `READY_REQUIRES_REAPPROVAL`: otomatik onay devredilmez. Varsayılan olarak DEĞİŞTİRİLMEZ. İsterseniz ikinci onay kutusuyla yeni görüntüyü yükler, `REVIEW_REQUIRED` ve `manually_verified=0` olur, eski dört köşe verisi saklanır ama yeni onay gerekir.
6. `DIMENSIONS_CHANGED...`, `MAIN_SOURCE_SHA_CONFLICT`, `AMBIGUOUS...`, `NO_EXACT_PROFILE` ve `ERROR`: **asla otomatik eşleştirme/değiştirme yok**. Dosya adına eklenen `_preview`, `_magenta` gibi değişiklikler varsa düzeltme/mapping insan kontrolü gerektirir. Etiketli JPEG/PNG farklı codec ise otomatik eski onay korunmaz.
7. **2. İncelediğim Planı Uygula**: önce tüm programları ve 8080 editörünü güvenle kapatın, onay metnini girin. Önce SQLite **online backup**, ardından her eski **çalışma görselinin ayrı SHA kontrollü kopyası** `%LOCALAPPDATA%\GorselMockup-MagentaRollback\...` konumuna alınır. Sonra yalnız doğru kimlikli çalışma görseli **tek tek** değiştirilir ve DB source SHA ilgili profile güncellenir. **Orijinal arşiv hiçbir zaman değiştirilmez.** Önceki üretilmiş 255 PNG ve PETEK maskesi değiştirilmez.
8. **3. Eski Klasörleri Salt-Okunur Tara**: gerçek Windows klasörlerinin mevcut kod paketine göre SHA envanteri; eski DB ve manifest ayrıntıları ile `EXTERNAL_SCAN_....json` raporu. Eski bir dosyanın yeni görünümlü olması onun aktif uygulamada çalıştığını ispatlamaz.
9. **4. Eksik/Farklı Kodları Kurtarma Alanına Kopyala**: yalnız açık onay sonrası farklı kaynak kod dosyalarının birebir kopyası çalışma alanındaki `KURTARMA_ON_INCELEME` klasöründe saklanır. Aktif kod **otomatik değiştirilmez**; karışık sürümden kör kopyalama 255 başarılı üretimi bozabilir. GitHub kod birleştirme ve bağımsız test gereklidir.
10. **Test klasörlerini henüz silmeyin.** Farklı kod, farklı DB veya aktif PETEK/üretim kayıtları rapordan çözülmeden `safe_to_delete` denmez. Silmek için ayrı bir kullanıcı kararı gerekir.

## Tekrarlanabilir testler

`TESTLER/test_v472_magenta_external_reconciliation.py`:
- Magenta/ana iki fotoğrafı yan yana okuma, asıl dosya ve DB SHA aynı kalır.
- LAB SHA+UID onay eşleşirse dosya bazlı güncelleme ve anlık geri dönüş kopyası.
- LAB onayı bulunmazsa varsayılan blok; ancak açık ikinci onay ile yeni şablon `REVIEW_REQUIRED` olur.
- Ölçü uyuşmazlığı / aynı isimden birden fazla DB profili güvenli şekilde engellenir.
- Eski kod ile güncel kodun SHA farkları bulunur; kopya sadece `KURTARMA_ON_INCELEME` içinde, aktif kod hiç değişmez.

## Açık kabul sınırları

Bu model internet/GitHub üzerinden kullanıcının `C:\...` disklerini okuyamaz. Lab ve eski klasörlerin gerçek envanterindeki dosya sayısını, önizlemelerin ölçülerini, onaylı LAB DB'nin gerçekten orada olup olmadığını **uygulama kullanıcının Windows PC'sinde çalışınca** öğrenebiliriz. Kullanıcı `MAGENTA_PLAN` ve `EXTERNAL_SCAN` raporlarını paylaşmalı. Yalnız ana çalışma yolu belirlemek, yerel AppData durumunu OneDrive içine taşımak anlamına gelmez. OneDrive SQLite P0 riski ayrıca ele alınmalıdır.
