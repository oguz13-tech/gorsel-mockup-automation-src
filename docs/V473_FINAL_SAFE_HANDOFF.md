# V4.7.3 — güvenli kapanış / uygulanmadan önce kontrol listesi (27 Ekim 2026)

## Kod tarafında tamamlananlar
- Eski 3 başarısız CI grubu: önceden güvenlik kuralları değişince geçersiz hale gelen Flask CSRF, Bulut Excel test çıktı konumu ve PETEK fiziksel dizin varsayımları, güvenliği gevşetmeden düzeltildi.
- Magenta LAB `chroma_previews` fotoğrafı **yalnız gerçek çalışma havuzundaki aynı kategori+kimlikli tek fotoğraf** üzerine tek tek konur. Arşiv kaynakların eski haliyle kalır. Aktif klasörde aynı isim/farklı uzantı, aynı dosyanın başka kimlikle kullanımı, bir şablona birden fazla LAB kaynağı, eski SHA ile DB uyuşmazlığı ve farklı boyut gibi haller otomatik engellenir.
- Eski fotoğraf, tek tek SHA'lı ayrı yedekte; canlı `ayarlar.db` SQLite online snapshot'unda saklanır. Başarılı aktarımdan sonra yeni fotoğrafa ait SHA ve varsa LAB insan-onaylı köşe bilgisi güncellenir. İnsan onay kanıtı yoksa ve kullanıcı ayrı ikinci onayı seçerse `REVIEW_REQUIRED`; mevcut 4-köşe toplu algılama/onay ile sonradan onaylanabilir.
- **Mağaza profili kaynak SHA geçişi**: Immutable kategori/UID korunur, sadece eski SHA anahtarı yenilenir; sonraki üretim profilinde artık yanlış kaynak aramaz. Duplicated ID ve cross-store SHA çakışmaları işlem başlamadan reddedilir. Store JSON ve SQLite ayrı SHA yedekleri ve arıza halinde restore denemesi vardır.
- Eski sürüm klasör envanteri artık program kopyalarını, tek kalan Python/Windows araçlarını, model arşivlerini ve aktif şablon havuzundaki mükerrer isim/içerik kayıtlarını **sadece okur**. Orijinal arşiv meşru yedek sayılır, mükerrer aktif şablon sayılmaz. Hiçbir eski klasöre otomatik silinebilir etiketi verilmez.
- Eski test klasöründeki kodlar ancak kurtarma ön inceleme alanına kopyalanır. Kullanıcı yeni ZIP'i kullandığı sürece uygulama eski klasördeki eksik kodu arayarak gizlice eski sürüme dönmez.
- OneDrive üzerinde çalışan SQLite riski için **V4.7.3 iki aşamalı taşıma**: tüm gerçek çalışma alanını OneDrive dışındaki yeni klasöre **SHA doğrulanmış, yaratılabilir tek kopya** olarak hazırlar. SQLite online backup içerir. Sadece kullanıcının ikinci ayrı açık onayıyla yeni çalışma alanı seçilir. Eski dizin ve bütün yerel üretim/PETEK AppData silinmez ve kendiliğinden taşınmaz. Değişen kaynak ya da dosya SHA aktifleştirmeyi engeller.
- PETEK 45 fiziksel kabul ve yedi kategoride 255 gerçek görsel kullanıcı tarafından geçildiği için yeniden tam performans testi için zorunlu kullanıcı görevi yapılmaz. Yenilenmiş magenta kaynakların yeni görüntü onayı ayrıdır.

## Kullanıcıdan gereken son eylemler
1. Yeni Windows ZIP'i eski klasöre yazmadan ayrı kur. Ana çalışma dizini doğru mu G3 ile kontrol et.
2. `Gelişmiş Araçlar > Magenta / Eski Sürüm Güvenli Dosya Denetimi` penceresinde **1 Magenta karşılaştırması** ve **3 Eski klasör taraması** raporlarını oluştur. JSON raporları ve yan yana görsel HTML özetini paylaş. Bu iki düğme dosya değiştirmez.
3. Raporlarda `READY_APPROVED_TRANSFER` ya da güvenilir `READY_REQUIRES_REAPPROVAL` listelerini incele, mükerrer veya belirsiz isimleri karara bağla. **2 Onaylı planı uygula** isteğe bağlı ve açık onaydır; 255 eski üretim üzerine yazılmaz.
4. Farklı kod/dış veritabanları raporlanmadan hiçbir eski `C:\AI_WORK` veya Downloads klasörünü silme. Gerekli dosyalar `KURTARMA_ON_INCELEME` içine güvenle kopyalanabilir; otomatik aktifleştirme yok.
5. Onedrive çalışma alanı kopyalama için **5** düğmesi; yalnız yeni dış çalışma alanı dosya-baytlarını hazırlar. İkinci açık onayla **6** düğmesi çalışma alanını değiştirebilir. Doğrulamadan önce uygulama ve 8080 sunucusu kapalı olmalı. 7 kategori onaylı kaydı, ham dosyalar, PETEK, 35 USER_REMOVED kayıt, mağaza profilleri, tasarım klasörleri ve üretim SHA geçmişi korunmalıdır.
6. Canlı ImgBB/FreeImage HTTPS+Excel ve gerçek Vulkan GPU Real-ESRGAN 4K testleri yalnız kullanıcı hesabı/cihazında yapılabilir. Cam/ahşap/PETEK efektlerin yeni sürümle örnek A/B görsel kalite onayı da gerekir. Bunlara `WINDOWS_NOT_VERIFIED` denir; sentetik CI `PASS` bu anlamda değildir.

## Kapanış için geçilmesi gereken kanıtlar
- Tüm GitHub tam regresyon iş akışları, paket-içi Windows testleri PASS, SHA256 manifest PASS
- Şablon havuzunda aktif aynı kimlik/farklı uzantı ve farklı kimlikte aynen aynı dosya byte tekrarlarının raporları karara bağlanmış
- Önceden onaylanmış şablonlar, bütün orijinaller ve eski üretimler byte-identical; magenta değişen çalışma dosyaları için DB ve mağaza bağlantıları doğru
- Eksik dosyaların liste ve model dosyası dahil envanteri tamam; silinecek her klasör kullanıcı tarafından ayrıca onaylanmış
- SQLite yeni çalışma alanı geçişi ya da OneDrive riski kabul kararı kullanıcıya ait; kendiliğinden taşıma yok
