# Görsel Üretim Merkezi V4.7.5 — Bütünlük ve birleştirilmiş Windows teslimi

**Teslim türü: KOD FİNAL ADAYI.** GitHub Windows/Linux CI ve açılmış ZIP bütünlük
testleriyle doğrulanır. Müşterinin Windows diskindeki canlı dosyaları okunmadığı
ve açık geçiş onayları verilmediği için **PRODUCTION_FINAL değil**.
Önceden onaylanan 45 PETEK ve 255 genel seri üretim görseli KABUL bilgisi
korunur; hiçbir eski görsele bu teslim sırasında dokunulmadı.

## 1. Kod entegrasyonu: gerçekten dahil olanlar

- Tek başlangıç: `BASLAT_V47_WINDOWS.bat`, iç `GORSEL_V46_CANDIDATE`
  klasörü yalnız geriye uyumluluk amacıyla adını korur.
- Güncel merkez, 4 köşe Flask editörü, 7 kategori üretim motoru,
  PETEK V3 insan onaylı maske kayıtları, mağaza grupları, şablonların
  SHA kimliği, optik efektler, duraklat/devam, Real-ESRGAN isteğe bağlı
  4K, HTTPS+Excel isteğe bağlı bulut bağlantısı, G3 denetimleri,
  magenta görüntü bazlı aktarım, tarihsel 35 USER_REMOVED onay akışı
  ve iki aşamalı OneDrive dışı çalışma alanı taşınması paketlenir.
- **Yeni tespit edilip düzeltilen gerçek paket eksikliği:**
  `MERKEZ/GUNLUK/INSTALLED_NUMBER_SPEC.json` GitHub'da vardı,
  fakat eski kod-only paketleme filtreleri bunu atlıyordu.
  Yeni pakette SHA doğrulanarak bulunur.
- GitHub'da takip edilen önceki top-level .bat/.ps1 dosyaları
  çalıştırılabilir olarak değil
  `LEGACY_LAUNCHERS_REFERENCE/*.reference.txt` altında orijinal
  byte'larıyla korunur. Böylece eski C:\AI_WORK yoluna sessizce
  geri dönülmez; kayıp araçların tarihsel içerikleri tek pakette vardır.
- `MERKEZ/GUNLUK/BATCH_SELECTION.json` GitHub'da bulunmuyor ve
  Günlük V2'nin sabit PR9 snapshot/backupları ayrıca gerekli.
  Eski Günlük V2 bu yüzden **doğrulanmadan çalışır sayılmaz**.
  Güncel yedi-kategori üretimi `MERKEZ/URETIM_V4` üzerinden yapılır.
- **Gizli/kişisel ayarlar.json, canlı ayarlar.db, çıktı resimleri,
  PDF/PSD/kişisel fotoğraf, bulut API anahtarları ve maskeler**
  GitHub ZIP'ine alınmaz. Bu gerçek veri yerel çalışma ortamında
  korunur. Paket içindeki source manifest dosya listesi tüm kaynakları
  SHA256 ile doğrular.

## 2. Bütünlük denetimi ve kapsam

Bakım aracı: `BAKIM_V472_MAGENTA_KLASOR_DENETIM_WINDOWS.bat`.

**9. SQLite / Şablon / Mağaza / PETEK / Kod / Çıktı SHA Raporu**:
- SQLite `ayarlar.db`: active profile, APPROVED, REVIEW_REQUIRED,
  benzersiz UID ve orijinal arşiv/çalışma kopyası SHA uyumluluğu.
- Ana `2_SABLON_HAVUZU`: aynı kategori+isim/farklı uzantı, dosya
  baytı aynı fakat farklı şablon kimliği ve DB kaydı bulunmayan dosyalar.
  Orijinal arşiv kopyalarını yanlışlıkla mükerrer saymaz.
- Mağazalar: kaynak-SHA'ya bağlanan atamaların güncel approved template
  veya insan onayı bekleyen template ile uyumu; yanlış SHA bloke edilir.
- PETEK: `%LOCALAPPDATA%\GorselMockup\PetekV3` profillerinin kaynak
  SHA, maske hash'i, panel maskesi ve onay statüsü ayrı kontrol edilir.
  PETEK kaynağı eski LAB/test klasöründe kaldıysa dış bağımlılık
  uyarısı verilir, silme izni verilmez.
- Üretim: `%LOCALAPPDATA%\GorselMockup\UnifiedV4` ledgeri:
  RENDERED, USER_REMOVED, PENDING, SHA/eksik dosya ve güvenli yol kontrolleri.
  Şablonun yeni sürüme geçmesi eski geçerli teslimleri otomatik hata saymaz.
- Kod: zorunlu Python/HTML/JS/bat dosyaları, paket SHA256 manifesti
  ve eski Windows launcher arşivi.
- Eski test/deneme klasörü envanteri **yoksa** `REVIEW_PENDING`;
  rapor asla `safe_to_delete_old_test_folders=true` işaretlemez.

**Yalnız OKUMA:** 9 numaralı işlem hiçbir gerçek fotoğraf, veritabanı,
mağaza JSON veya maske kaydını güncellemez. JSON raporu ayrı
`%LOCALAPPDATA%\GorselMockup\UnifiedCenter\FULL_INTEGRITY` dizinindedir.

## 3. Teslim ve onay süreci

1. Windows ZIP'i yeni boş klasöre çıkartın, mevcut çalışma klasörünün
   veya OneDrive veritabanının üzerine açmayın.
2. `BASLAT_V47_WINDOWS.bat` ile 7 kategori güncel merkezi açın.
3. Bakım merkezi **1 Magenta Raporu**, **3 Eski Dizin Envanteri**
   ve **9 Tam Sistem Bütünlük** tuşlarını sırayla çalıştırın.
   JSON raporları ChatGPT'ye iletin. Hepsi ilk aşamada salt okunurdur.
4. Magenta gerçekten güvenli SHA/UID eşleşiyorsa *ayrı açık onay* ile
   eski çalışma görüntüsünün yerine tek dosya yazın. SQLite profili
   + mağaza ataması + ayrı geri dönüş kopyası birlikte yönetilir.
   Yeniden dört köşe onayı gerekebilir.
5. OneDrive'dan çıkmak için **5 Yeni Kopyayı Hazırla** ardından
   **6 Doğrulanmış Kopyayı Etkinleştir** adımları iki ayrı açık onay
   gerektirir; kaynak orijinaller korunur.
6. Eski/test sürüm klasörlerinin bir kısmında tek kalan model veya
   kod dosyaları ancak envanterde listelenirse incelenebilir.
   Bunları otomatik olarak canlı programa enjekte etmek, kullanıcının
   çalışan 255 çıktısını riske atabileceğinden yasaktır.
   **Gerçek C:\AI_WORK envanteri paylaşılmadan burada kalan bilinmeyen
   özel dosyaların tamamının taşındığı iddia edilemez.**
7. 35 USER_REMOVED kaydı yalnız sahibin açık onayıyla işlem görür.
   Eski üretim resimleri ve geçmiş ledgeri değiştirilmez/silinmez.
8. Son gerçek Windows kabulü: 4K Vulkan GPU, canlı HTTPS+Excel,
   cam/ahşap/PETEK yansıma A/B ve bağımsız kurulumu kontrol edin.

## 4. Teslim kanıtı

GitHub Actions **Windows + Ubuntu** aday iş akışı; hem kaynak kod
testleri hem çıkarılmış ZIP testleri, tam suite testleri, dosya SHA256
ve ZIP CRC sonuçları. Test sonuçları ilgili commit/run referansından
okunmalıdır; kullanıcı onayları CI sonuçlarından türetilemez.

Final karar seviyeleri:
- `CODE_AND_ZIP_CI_PASS`: makine üzerinde kod/paket kanıtlandı.
- `REAL_WINDOWS_WORKSPACE_NOT_AUDITED`: kullanıcı makinesindeki
  veri seti için henüz kesin bütünlük iddiası yok.
- `EXTERNAL_VERSION_FOLDERS_NOT_CLEARED`: eski klasörleri silme
  izni yok, rapor ve dosya karşılaştırması bekleniyor.
- `PRODUCTION_FINAL_APPROVED`: yalnız gerçek kabul raporlarından sonra.
