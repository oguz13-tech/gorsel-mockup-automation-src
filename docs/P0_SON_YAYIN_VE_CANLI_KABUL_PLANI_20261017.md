# P0 — SON YAYIN PLANI ve CANLI TESTE GEÇİŞ KAPILARI (17.10.2026)

**Durum: TASLAK — CANLI SİSTEME KURULMADI.** Bu belge, gerçek Windows/OneDrive ve bütün harici servisler test edilmeden sıfır hata garantisi vermez.

## Tek kod zinciri

PR #5 (numara/ham arşiv koruması) → PR #6 (P0-A/B/C/D/E) → PR #8 (tüm depo denetimi ve 309 test) → PR #9 (bu dal: release kapanışı).

Sürüm geçişi için tüm üst PR’ları tek tek canlıya kurmak YASAK. **Son entegre dalın yalnız bir doğrulanmış commit’ini** ayrı release kaynağından kur.

## PR #9 işlenen kapanışlar

1. **DB otomatik migration kapısı:** `SABLON_V2_MIMARI/app.py` importunda `init_db()` kaldırıldı; salt okunur `inspect_startup_schema()` ve hatalı şemada HTTP 503. Gerçek sistemde eksik şema otomatik oluşturulmaz.
2. **SQLite migration provası:** `scripts/p0_db_migration_gate.py --mode simulate` SQLite Backup API ile tutarlı kopya alır, migration’ı yalnız FAKE_RUNTIME üzerinde çalıştırır, satır sayılarını ve `integrity_check` kontrol eder. **Gerçek DB’ye APPLY YAPMAZ**; bu bilinçli izin sınırıdır.
3. **Önizleme ayrımı:** `_ONIZLEME_SABLONLAR`; watcher’ın işlediği `YENI-BOS` klasörüne önizleme yazılmaz.
4. **Yeni şablon ekle:** `BAGIMSIZ_ARACLAR/09_GUVENLI_YENI_SABLON_EKLE.bat` artık `tools_runner.py stage` komutunu açar. Dış kaynaklar değiştirilmez; SHA’lı benzersiz receipt ve create-only tam dosya yayını kullanılır.
5. **Güvenli kod dağıtımı:** `scripts/p0_release_transaction.py` plan, harici yedek, kullanıcı onaylı **yalnız kod kurulumu** ve SHA doğrulamalı **yalnız kod rollback** sağlar. `2_SABLON_HAVUZU`, `ORIJINAL_YEDEK`, `YENI-BOS`, runtime JSON ve SQLite bu kurulum sırasında değiştirilmez.
6. **Argon kalite tespitleri:** `visual_qa_audit.py` bilinen kusurlu kaynak hashlerini kodlar; geometrik/piksel kontrolü yalnız denetim üretir, insanın ticari kalite onayını taklit etmez. Önceki APPROVED kaydı olsa bile bilinen kusurlu SHA üretime girmez.
7. **Testler:** 8080/8999, SHA ve restore; bağımsız araçlar; sentetik staging; kontrollü release/snapshot/rollback; legacy SQLite migrasyon provası; görsel QA; bütün önceki regression testleri.

## Dört güvenli Windows başlatıcısı

- `P0_RELEASE_HAZIRLIK_ON_KONTROL.bat`: yalnız plan. Dosya ve DB değiştirmez.
- `P0_RELEASE_ONAYLI_YEDEK_AL.bat`: açık YEDEK onayı ile kod ve tutarlı DB snapshot. Yedek C:\AI_WORK\P0_RELEASE_KORUMALI_YEDEK altındadır, OneDrive'da değil.
- `P0_RELEASE_ONAYLI_KOD_KUR.bat`: ancak kullanıcı tarafından girilen snapshot ve açık KOD_ONAY ile. Kod checkout’u ve release kaynağı ayrı olmak zorunda.
- `P0_RELEASE_ONAYLI_KOD_GERI_AL.bat`: yalnız SHA'sı hâlâ bizim kurduğumuz kodları değiştirebilir; otomatik gerçek DB restore YOK (kod kurulumunda DB zaten değiştirilmez).

**ÖNEMLİ:** Bu .bat dosyaları hazırlanmış olmaları nedeniyle çalıştırılma izni kazanmaz.

## Canlı onaydan önce blokajlar

1. **Tek commit'e bağlı tam Windows + Ubuntu suite PASS**. Seçilmiş 48 testi veya Argon 301/301 iddiasını tek başına kanıt sayma.
2. **Gerçek kullanıcı çalışma kökü üzerinde yalnız salt okunur envanter**; yedek 005/135/137/188 SHA sabit. 8080/8999 ve watcher kapalı.
3. Kodu kurmak için önce harici tutarlı SQLite/JSON ve kod snapshot, SHA manifest, snapshot konumu doğrulama. Kaynak kod ile target kod klasörleri aynı olamaz.
4. Veritabanı şema migration simülasyonu o günkü gerçek DB’nin KOPYASI üzerinde PASS. Gerçek DB’ye migration canlı kabulün ayrıca onaylı adımıdır. Bu onay olmadan 8080 API şema uyumsuzsa 503 dönmesi doğrudur.
5. Güvenli kategorilerden bir değersiz gerçek örnekle 3:4 1200x1600 render, katman/perspektif/alpha QA; orijinal yedek ve approved kaynak SHA sabit.
6. İnsan kalite onayı ve 5–10 görsellik küçük batch; `04_Cam_Dograma` occlusion kanıtı olmadan BLOKLU.
7. Canlı OneDrive dosya kilidi, SQLite WAL ve dış bulut/Excel akışı için ayrı kabul; bunlar simüle CI PASS ile ticari PASS sayılamaz.

## Doğrudan sıradaki uygulama

- CI son HEAD Windows/Linux PASS → kaynak kodu sabitle → Argon ile PR diff karşılaştırmasını kapat → kullanıcının **ayrı ve açık canlı kurulum onayı** → salt okunur preflight + yedek + migrasyon provası → kontrollü kuruluma geçiş.
- Kullanıcı bu onayı vermeden **git merge/push to main, runtime silme/taşıma, SQLite apply veya gerçek görsel işlemeye başlama yok**.
