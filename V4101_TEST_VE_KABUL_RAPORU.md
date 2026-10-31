# Görsel Üretim Merkezi V4.10.1 — Test ve Kabul Raporu

Tarih: 31.10.2026; paket durumu **WINDOWS_NOT_VERIFIED**.

## Yeni sürüm
- PETEK toplu seçimde boş görünen satırlar için 17px sabit checkbox + genişleyen dosya adı, Chromium 400/1280 görsel testi.
- Eski sekizli ve tek tek İnceledim dialogu JS/HTML'den kaldırıldı; bir toplu onay, arka uç kayıt bazlı maske/UID/SHA güvenliği.
- Antrasit ve yedi kategori ortak Yeni=mavi / Onaylı=yeşil / Taslak=sarı / Hatalı=kırmızı durum renkleri; kategori kodları bütünüyle ortaklaştırılmadı.
- Ana sayfa kartlarını taşı modu, UI ayrı JSON; kart boyutu/serbest yerleşim henüz tam değil.
- Hata neden/çözüm metinleri ve PETEK kritik hatalarında ilgili adıma götüren UI, bazı bağımsız araçlar eksik.
- Eski PETEK görüntü kalitesi motorları korunmuştur; onaylı revizyon/rollback V4.10.0 yolu korunmuştur.

## Gerçekleştirilen doğrulamalar
- Seçili regresyon: **124 PASSED, 3 SKIPPED, 2 DESELECTED**. Dışlananlar Flask HTTP testi (Flask paketi bu test ortamında yok) ve tarihsel ayar JSON dosyası beklentisidir. Başarılı gibi sunulmadılar.
- İlk geniş koşu: 122 geçti, 3 skipped; 2 hatalı popup eşlemesi düzeltildi, 1 Flask, 1 eski JSON dosya şartı vardı. Kapatma güvenliği regressiyonları tekrar geçti.
- `python -m compileall -q .`: PASS (bazı legacy SyntaxWarning, test başarısızlığı değil).
- `node --check`: Web ana JS dosyaları PASS.
- Tk arayüz smoke (sanal masaüstü): PASS; Chromium 400/1280 PETEK liste: PASS.
- ZIP SHA-256 manifest doğrulaması, ZIP CRC, ayrı klasöre çıkarma: paketleme sonrası tekrar raporlanacak.

## Bilinen açık kalan işler
- **WINDOWS_NOT_VERIFIED**: Kullanıcının gerçek bilgisayarında PETEK HTTP toplu onay, 4 köşe/maske revizyon, 4K GPU, mağaza→Excel son onay.
- Serbest kart ebat/konum, üretim ekranının tüm kartlarının doğrudan sürüklenmesi, bütün bağımsız araçlarda otomatik hata çözümü: kısmi.
- Yedi kategorinin HTML/JS kaynak bileşenleri ortak renge rağmen bütünüyle aynı kod değildir.
- Cam yansıması/1000+ batch/performance/backup canlı geniş kabul ve tam GitHub kaynak ZIP senkronu hâlâ açık olabilir. GitHub durumuna bakın.

## Kritik güvenlik
Kullanıcının orijinal arşivinin üzerine ZIP açılmaz. Onaylı kayıtlar otomatik bozulmaz. V4.9.5'te canlı kabul edilen 15 PETEK koyu yarık, Orta yoğunluk ve pembe temizlik motorları hash karşılaştırmasıyla korundu.
