# [24.10.2026] V4.4 — GRUP 1 + 2 + 3 TEK WINDOWS KABUL ADAYI

- **Güncel** GitHub kaynak `feature/v44-group3-release-safety-20261024` / [taslak PR #47](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/47). Zincir: PR #45 (Grup 1) → PR #46 (Grup 2) → PR #47 (Grup 3). Main auto merge YOK.
- **Tek ZIP adayı** `GORSEL_URETIM_MERKEZI_V44_GRUP1_GRUP2_GRUP3_TEK_WINDOWS_KABUL_ADAYI.zip`: 403 üye, SHA-256 `cbda27f321d637a29a76cb1809004c12c2b08eec721c2876766744f1eda41234`, CRC/extract PASS; özel ChatGPT Library `/Gorsel-Uretim-Merkezi/V4.4-G3/`. İçinde 402 dosyalık SHA manifesti. Bu gerçek Windows GO değil.
- G3 yeni kod: salt-okunur `final_guard_v44.py` ve GUI iki buton; SQLite `ayarlar.db` + `v4_ortak_uretim.sqlite3` WAL online backup/izole restore prova, manifest SHA. Sıfır otomatik canlı DB migration. G3 Windows tek-tık read-only BAT.
- Lokal **194 PASS / 2 SKIP**, temiz ZIP çıkarımında **32 G1/G2/G3 odaklı PASS**; 1000 sentetik ledger receipt/SHA/idempotence, iki kesinti karantina ve OS kilit testi. Bunlar **1000 gerçek fotoğraf render** değildir. CI son durumu Actions'tan doğrula.
- Açık: 100/200/1000 gerçek görüntü batch, iki gerçek Windows kill/restart ve çift süreç, live OneDrive iki DB backup/restore, dosya/Excel/SKU ticari mapping, PETEK 34+ Golden ve gerçek cam A/B, ImgBB/FreeImage HTTPS Excel, 4K Vulkan model/exe, offline wheel, approved 4 köşe reapproval, eksik PNG/WebP. Bunlar #35 gerçek kabul kapısını BLOKlar.
- **Oku:** `docs/THREE_GROUP_103_TASK_PLAN.md` → `docs/V44_GRUP2_41_ITEM_STATUS.md` → `docs/V44_GRUP3_19_GOREV_DURUMU.md` → `docs/V44_BIRLESIK_WINDOWS_KURULUM_VE_GERI_DONUS.md` → `docs/V44_GRUP3_DEVIR_GITHUB.md`.

---

# [GÜNCEL 2026-10-23] V4.4 ÜÇ GRUP KONTROL NOKTASI — ÖNCE BUNU OKU

- **103 görevün tamamı** `docs/THREE_GROUP_103_TASK_PLAN.md`: Grup 1 maddeler 1–40,101–103 (43); Grup 2 41–75,95–100 (41); Grup 3 76–94 (19).
- **Aktif:** Grup 1; taslak [PR #45](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/45), branch `feature/v44-group1-ui-upscale-20261023`. Grup 2 [#43](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/43) ve Grup 3 [#44](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/44) *sırada*, tamamlandı değiller.
- G1 kod checkpoint: ana merkez tek 7 kategori üretim, eski 10 şablon GUI shortcut kaldırıldı, bakım araçları gizlenebilir alanda; isteğe bağlı Real-ESRGAN-NCNN 4K 2880×3840 ayrı SHA korumalı çıktı + yerel Excel; katı salt-okunur SHA denetimi. Gerçek `.exe`/model dosyaları ZIP'e dahil değil; kullanıcı güvenli şekilde temin etmeli.
- Yerel **107 seçili regresyon PASS**; ayrıca GitHub Windows/Linux G1 test workflow'su eklenmiştir, anlık CI sonucunu GitHub Actions'tan doğrula. Sentetik ≠ gerçek kullanıcı kabulü.
- Grup 1 **PENDING**: gerçek cam A/B (4 cam kategori), HTTPS ImgBB/FreeImage ağ + Excel tıklama, canlı DB approved köşe revizyon testi, 415MP PNG/WebP stratejisi, Real-ESRGAN gerçek GPU ve 4K A/B, ticari Excel SEO/mağaza sütunları.
- G2 **PENDING**: eski araçlar/şablon tarama/SAM denemeleri/PETEK maske ve Golden Dataset. G3 **PENDING**: 1000 iş, 2x crash, SQLite backup/restore, iki process, 8080, factory doctor, Windows rollback, tek final ZIP. `main` değiştirme; PR auto merge yapma.
- Grup 1 test/checkpoint paketi **final değildir**. 386 dosya, SHA256 `61cb1f434cc7937c6c72814da2cb8d0b7e869ead735fb7344c630f922cea9de6` ve özel Library `/Gorsel-Uretim-Merkezi/V4.4-G1/`. Eski kullanıcı V4.2.2/V4.3 ve onaylı `ayarlar.db`, orijinal fotoğraflar, maskeler korunuyor.
- G1 kabul bitince G2'ye, G2 kabul bitince G3'e geç; final GO yalnız #35 gerçek Windows kabulüyle.

---

# GÖRSEL ÜRETİM MERKEZİ — KANONİK TEKNİK DEVİR / V4.2.2

**Tarih:** 2026-10-23 · **Durum:** Kod paketi oluşturuldu ve sentetik testler uygulandı; gerçek kullanıcı Windows kabulü **yapılmadı**.  
**ANA GÖREV:** #36 · **KABUL:** #35 · **KAYNAK BİRLEŞİMİ:** #29 · **Taslak geçmiş:** PR #37.  
**Bu belgenin amacı:** Sohbet/agent kotası dolduğunda bütün yapılan işleri, kaynak dosyaları, güvenlik sınırlarını, testleri ve sonraki adımları başka bir ajan **uydurmadan ve sıfırdan tekrar yazmadan** devam ettirebilsin.

## 0. Kaynak doğruluğu — kesin ayrımlar

1. **Kanonik teslim arşivi:** `GORSEL_URETIM_MERKEZI_V422_GRUP1_GRUP2_FACTORY_DOCTOR_GUVENLI_FINAL_WINDOWS.zip`, **1,299,480 bayt**, SHA-256 `ad33e3219c5e2c6e1f6185a2b726730276eb9e2386abd6a78d49b97df566f7ee` ve ZIP CRC kontrolü başarılı. İçinde **379 dosya** bulunur, kişisel fotoğraf ya da `.db` içermez; ancak tarihsel `ayarlar.json` / elle hazırlanmış geometri türü kayıtlar ve referans veri barındırabilir. Bu nedenle tam paket **public GitHub'a doğrudan koyulmaz**.
2. **Kalıcı özel proje arşivi:** ChatGPT Library: `/Gorsel-Uretim-Merkezi/V4.2.2/` altında kanonik ZIP ve **379 satırlık** tam SHA envanteri `V422_FULL_PACKAGE_FILE_MANIFEST.csv`, `V422_FULL_PACKAGE_FILE_MANIFEST.json`. İlerideki ajan Library üzerinden dosyayı bulup materialize edebilir. GitHub dokümantasyonunun yanında gerçek paket için bu arşiv kanoniktir.
3. **GitHub kaynak devir dalı:** `handoff/v422-complete-20261023`. ZIP'ten ayıklanan **293 Python/BAT/PowerShell/HTML/JS/CSS/YAML kod dosyası** bu dalda ayrıca takip edilir. JSON/DB/kişisel görseller gibi veri dosyaları ve bazı tarihî dokümanlar intentionally public dalına alınmaz; bunların tamamı *Library ZIP* içinde isim ve hash ile izlenir. GitHub `main` otomatik değiştirilmez. Bu dalda gerçek Windows üretim kabulü yoktur.
4. **Sürüm tarihçesi:** V3.14 (eski 6 kategori + PETEK pilot); V3.15 dinamik onay seçim; V4.0 ortak üretim ve kuyruk adayı; V4.1 güvenli fotoğrafsız geçmiş; V4.2 Grup 1 + Grup 2; V4.2.1 final denetim; **V4.2.2 Factory Doctor bilgi/güvenli başlatıcı**. Eski ZIP'lerin üzerinde katmanlı kurulum yapılmaz.
5. **ÖNEMLİ:** GitHub issue ve PR metinleri tarihsel anın bilgisidir. #36 / #37 hâlâ V4.0 talimatı içerebilir. Bu belge ve V4.2.2 SHA, yeni kaynak paket için güncel referanstır; gerçek Windows kabul edilmediği sürece #35 kapanmaz.

## 1. Ürün hedefi ve yedi kategori

- Windows üzerinde tek ana merkezden gerçek fotoğraf üstüne baskı/mockup; **3:4 dikey**, perspektif/occlusion koruma, onaylı 4 köşe/maskeler, dinamik şablon, toplu SKU/CSV/Excel ve kalıcı işlem kanıtı.
- `01_Wifi_Kutusu`: 40×30 cm **gövde dış ölçü**, 12 cm **iç** derinlik; sağa sürgülü ince MDF. Dış derinlikle karıştırma.
- `02_Cam_Tablo_Dikey`: 60×90 cm dikey, sınırlı yansıma.
- `02_Cam_Tablo_Yatay`: 60×90 cm yatay, sınırlı yansıma.
- `03_Ahsap_Tablo`: 50×70 cm dikey çerçeve/gölge.
- `04_Cam_Dograma`: 25×35 cm tezgâh/cam; **yeni/onaysız** kayıt H (yatay) varsayılan; mevcut onaylı V **değişmez**.
- `05_Ocak_Arkasi`: ocak arkası cam panel; kaynak sahnenin kenarlarını koru.
- `06_Petek_Kapama`: gerçek doğal delikler ve üst/alt kavis, fırça maskesi; **sabit 13 yarık üretme**. PR #11 prototipini kanonik yapma.

## 2. Çalışma yolları — veri korunacak

- Kullanıcının canlı çalışma kökü Windows OneDrive Masaüstü altında `GörselÜretme-ve-Mockup Otomasyonu` klasörüdür. **Kullanıcının kişisel profil yolunu public issue'ya taşımayın.**
- `SABLON_V2_MIMARI/ayarlar.db`: insan onaylı SQLite profilleri ve köşeler; **asla paketle gelen örnek DB ile değiştirme**.
- `2_SABLON_HAVUZU`: çalışma fotoğrafları; `2_SABLON_HAVUZU_ORIJINAL_YEDEK`: ham yedek; `YENI-BOS MOCKUP SABLON HAVUZU`: yeni gelen dosyalar. `KONTROL_GEREKENLER`, `BAGIMSIZ_ARACLAR`, `99_SISTEM_MOTORLARI_VE_KODLAR` ve PETEK maskeleri korunur.
- Birincil Windows program kodu **ayrı yeni klasöre çıkarılır**. Eski kurulu sürüm ve canlı SQLite/SHM/WAL üzerine in-place yazma yapılmaz. Açık 8080 editörü ve yeni sürüm eşzamanlı canlı DB açmamalı; kaydedilmemiş dört köşe ayarını kaybettirme.
- GitHub deposu **public**. Kullanıcının fotoğrafları, maskeleri, live DB, çalışma çıktı/SKU'ları, kişisel dosya yolları, anahtarlar, veri içeren JSON/ZIP ve geçmişi public push edilmez; mevcut eski public geçmişin hijyen denetimi ayrı iştir.

## 3. Güncel teknik modüller (dosya atlamsız envanter ayrıca CSV'de)

**Ana merkez:** `MERKEZ/merkez.py`, `MERKEZ/legacy_manager.py`, `MERKEZ/inbox_auto_v42.py`, `MERKEZ/dark_theme_v42.py`, `MERKEZ/help_v42.py`, `MERKEZ/merkez_saglik.py`, `MERKEZ/BASLAT.*`.  
**7 kategori toplu üretim:** `MERKEZ/URETIM_V4/gui_v4.py`, `unified_batch.py`, `unlimited_selection.py`, `crash_recovery.py`, `manual_geometry.py`, `finish_v42.py`.  
**PETEK:** `MERKEZ/PETEK_V3/gui.py`, `batch.py`, `engine.py`, `realism.py`, `curves.py`, `brush_tools.py`, `viewport.py`, `registry.py`, `cutout_paste.py`, `safety_audit.py`, `excel_links_v42.py`.  
**Eski Flask 4-köşe + /tools:** `SABLON_V2_MIMARI/app.py`, `tools_runner.py`, `templates/index.html`, `templates/tools.html`, `static/js/main.js`; `core/` altında `template_intelligence.py`, `template_identity.py`, `safe_working_revision.py`, `file_safety.py`, `db.py`, `factory_doctor.py`, `doctor_guidance.py`, `workspace_consistency.py`, `lifecycle_reconciliation.py`, `job_engine.py`, `runtime_migration.py`, `runtime_lock.json`, `analysis_cache.py`, `vision.py` vb.  
**Günlük/eskiler:** `MERKEZ/GUNLUK/`, `99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/pc_master_factory.py`, `BAGIMSIZ_ARACLAR/`, `V2_KONTROL_MERKEZI/`, `LEGACY_REFERANS_KOD/`; eski araçlar bağımsız kullanım için korunmalıdır.  
**Başlatıcı:** `BIRLESIK_V42_BASLAT_WINDOWS.bat`; kurulum ve kurtarma BAT/PS1 dosyaları paket içerisinde.  
**Testler:** `TESTLER/` (birleşik V4 testleri), `tests/` (EPIC-3, watcher, SHA, geri dönüş, dosya güvenliği, PETEK, GUI).  
**Tam liste:** Library `V422_FULL_PACKAGE_FILE_MANIFEST.csv` (379 dosya / SHA256 / boyut). Kaynak kodun GitHub'a aktarılmış altkümesi 293 dosyadır; ayrımı görünür tut.

## 4. Tamamlanmış kod işleri — TEST SONUCU ≠ gerçek Windows kabulü

**Grup 1:** kayıtlı gerçek 4 köşelerle toplu onay; manuel küçük geçerli dörtgen kabulü (`Too small` alan eşiği yalnız manuelde kaldırılır); 7 kategori `YENI-BOS...` otomatik gelen dosya watcher'ı, isim+SHA karşılaştırmalı `ALREADY_WORKING` / `IMPORTED_NEEDS_CORNERS` / `CONFLICT_REVIEW` / `INVALID_IMAGE_REVIEW`, create-only arşiv; kendi sürümünden Flask başlatma; 7 kategori Görsel İsimlendirici son kullanılan numara/çakışma sicili; `Ham Orijinali Geri Yükle` eksik çalışma PNG'sini yedekten güvenli create-only kurma.

**Grup 2:** cam kategorilerinde kontrollü yansıma; PETEK/Wi-Fi/ahşap doğal sahne ışığı; cam baskı köşesinde kapatılabilen radius ve yumuşak antialias (orijinal onaylı köşeler sabit); gerçek şablon minik önizlemesi; Türkçe buton açıklamaları; eski isteklerin yeni görüntüyü bozmaması için token/yenileme kontrolü; Cam Doğrama yeni H varsayımı; koyu Tk/Flask tema; PETEK ve ortak üretim `.xlsx` `file:///` hyperlink, `_LINKLI.xlsx` adı ve eski dosyaya dokunmama.

**V4.2.1:** tek bozuk/kayıp şablonun batch'i düşürmemesi, REVIEW_REQUIRED; GUI alanlarının start öncesi ana thread'de snapshot alınması; aynı UID/geri alınmış onay için net blok; yarım kalmış `.venv` bağımlılık onarımı; version/manifest doğruluğu.

**V4.2.2:** Factory Doctor Python ve NumPy lock drift, GPU baseline `None`, OneDrive SQLite sync ve master aspect bleed uyarılarını saklamadan, Türkçe tanı açıklaması ve gerçek interpreter yolu; yeni sanal ortam için `py -3.11` tercihi, mevcut `.venv` değişmez; GPU paketleri zorla kurulmaz, DB otomatik taşınmaz, master esnetilmez.

## 5. Kullanıcının rapor ettiği spesifik olaylar

- `WORKING_PNG_NOT_FOUND_OR_UNSAFE`: Ocak Arkası'nda "Ham Orijinali Göster" yedekte görüntü bulabiliyordu ama çalışma PNG'si eksikti, eski geri yükleme mevcut çalışma kopyası beklediği için başarısızdı. V4.2 Grup 1 noktasal düzeltme create-only kurtarma yolunu ekledi; gerçek Windows'ta birebir vaka tekrar testi **bekliyor**. Kaynak dosyanın geçmişte neden eksildiği kesinleşmedi.
- Factory Doctor: beklenen Python 3.11, mevcut 3.14; NumPy beklenen 2.4.6, mevcut 2.5.4; torch baseline 2.5.1+cu121, transformers 5.17.0, torch_cuda 12.1, güncel doktor sürecinde `None`; OneDrive DB riski; H/V master bleed oranı. Bunlar diagnostik uyarılardır; **uyarıyı kapatmak için baseline değiştirme**.
- "Eski onaylı sayı uyuşmazlığı" ve "yeni onayın üretime düşmemesi" kullanıcı tarafından çözüldü sayılmıştır; yalnız regresyon kontrolü gerekir.
- "KONTROL_GEREKENLER yeniden tarat", tarama progress/rapor/iptal, yedek havuzu eşitleme, kaynak dosya isim uzantı kimliği, KONTROL_GEREKENLER klasör seçimi ve profesyonel araçların görünürlüğü tarihî kritik kabul konularıdır. V4.2.2'nin gerçek Windows ortamında tüm eski fonksiyonlarla karşılaştırılması bitmemiştir; otomatik tamamlandı işaretleme.

## 6. Kaydedilmiş sentetik test kanıtı ve eksikler

- V4.2 birleştirme raporu: üç ayrık Linux/Xvfb oturumunda `TESTLER` toplam **142 PASSED / 2 SKIPPED**, ayrıca eski testlerden **18 PASSED**. Tek uzun test turu zaman aşımına uğradı.
- V4.2.1 denetim raporunda 38 odaklı + 30 ilave PASS; tekrar çıkarılmış ZIP'te 40 test PASS olarak bildirildi. Öncekilerle örtüşebilir; bunları tek bir benzersiz toplam gibi toplama.
- V4.2.2 Factory Doctor güncellemesi ile ilişkili 65 odaklı eski/yeni test PASS olarak bildirildi. **Test kayıtları paket içindeki tarihli raporlardır; bağımsız Windows CI kanıtı değildir.**
- Bu devir çalışması kodu/fotoğrafı Windows'ta çalıştırmadı; yeni dalın GitHub CI sonuçları ayrıca okunmalı. Canlı DB SHA ön/son karşılaştırma, gerçek 7 kategori görsel kalite, PETEK maskesi/Excel hyperlink, 1000 batch, kesinti-kurtarma, 8080 uçtan uca, Python/CUDA ortam ve OneDrive DB kontrolü **bekliyor**.

## 7. GitHub issue/PR izlenebilirliği

- Ana: [#36](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/36); [#29](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/29) kaynak uzlaştırma; [#30](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/30) 7 kategori; [#31](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/31) Flask/araçlar; [#32](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/32) PETEK; [#33](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/33) veri güvenliği; [#34](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/34) UX/Windows; [#35](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/35) kabul.
- Tarihî görevler: #15–#24, eski EPIC-3 #4–#10, PR #9 #12 #13 #14 #26 #27 #28, plan PR #37. PR #11 sabit delik prototipi **kullanılmayacak**. Tarihî issue'ları yanlışlıkla kapatma; kod bitmiş olması gerçek Windows ticari kabulü değildir.
- Devir sonrası ajanın oturumunda: bu branch HEAD / PR'nin dosya listesi / `git status`/CI koşullarını kontrol et, SHA manifestine göre kaynak dosyaları karşılaştır, sonra test ve kabul raporunu güncelle. `main` birleştirmesi ve otomatik deployment için kullanıcı kabulü gerekir.

## 8. Bekleyen işler — GO/NO-GO

1. **P0**: Gerçek Windows'ta canlı SQLite **salt-okunur envanter**, eşzamanlı program kapatma, kilit/OneDrive WAL durumunu ve backup+rollback provası; değişiklik öncesi SHA.
2. **P0**: 7 kategoride küçük birer gerçek onaylı örnekten üretim; mevcut onaylı 4 köşe, PETEK maske/airholes, görsel gerçekçilik, optik efekt çevre-piksel korunması.
3. **P0**: Orijinal restore eksik çalışma PNG'si ve isim/uzantı çakışması; otomatik importer idempotency, 7 kategori no-overwrite; isimlendirici son numara doğruluğu.
4. **P0**: `file:///` Excel linklerini Windows Excel'de deneme; SKU/dosya eşleşmesi, eski Excel üzerine yazmama, PETEK ve tüm kategoriler.
5. **P0**: 1000 sentetik batch, process kill iki kez, queue resume, create-only receipt, UUID/SKU, disk doluluk/DB lock ve insan onayı idempotency.
6. **P0**: Flask 8080 gerçek UI, toplu dört köşe onayı, F5/önizleme yarışı, koyu tema ve araç menüsünün tüm fonksiyonları; 7 kategori esnek H/V.
7. **P1**: Python3.11/NumPy lock gerçek uyumluluğu; GPU gerçekten kullanılıyor mu, doğru ortamda torch/transformers test; ancak otomatik kurma/force migration yapma.
8. **P1**: OneDrive dışı SQLite taşımayı yalnız backup/transaction/checkpoint/rollback planından ve kullanıcı onayından sonra değerlendirme. Master H/V oranları için gerçek golden görsel benchmark.
9. **P1**: PR geçmişi ile bu dalın source diff/CI ve kamuya açık geçmiş hijyen denetimi; `docs/` dosyalarını GitHub üzerinde kullanıcıya okunur tut.

**Açık gerçek:** Kod paketinin mevcut olması ve sentetik testler **production GO değildir**. Buradaki hedef sonraki kişinin doğrudan kaynağı alıp gerçek Windows kabulüne geçmesidir.