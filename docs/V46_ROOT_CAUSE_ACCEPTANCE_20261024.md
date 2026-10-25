# V4.6 Kök Neden ve Kalan Kabul Matrisi

Tarih: 2026-10-24  
Dal: `feature/v46-safe-consolidation-20261024`  
Son kaynak commit: `27449cd`

## Sonuç

**RELEASE = NO-GO.** Kod, sentetik benchmark ve güvenli paketleme kanıtları
mevcut; ancak gerçek Win11 kabulü, gerçek Golden görseller, gerçek GPU
çalıştırması ve dış HTTPS/marketplace kabulü bu geliştirme kopyasında
kanıtlanmış değildir.

## Önceden bildirilen sandbox çelişkisi

| Kayıt | Sonuç | Kanıt |
|---|---|---|
| Windows sandbox/proxy yerel terminal engeli | Çözüldü | `27449cd` öncesinde PowerShell erişimi tekrar çalıştı; test, commit, ZIP üretimi ve doğrulama çalıştı |
| Final aday ZIP/manifest üretimi | PASS | `V46_FINAL_CANDIDATE.zip`; manifest SHA ve açma doğrulaması PASS |
| Eski `TEST_RESULTS.json` içindeki “ZIP yeniden üretilemedi” | Geçersiz tarihsel kayıt | Bu raporla kaldırıldı; güncel sonuç `artifacts/v46/TEST_RESULTS.json` içindedir |

Bu düzeltme yalnız geliştirme kopyasındaki raporları günceller. Canlı kurulum,
SQLite, APPROVED profiller, orijinal şablonlar veya müşteri görselleri
okunmadı ve değiştirilmedi.

## Kalan kabul maddeleri

| Test / özellik | Durum | Son kanıt ve veri türü | Neden tamamlanmadı | Agent'ın yapabileceği iş | Gerekli koşul |
|---|---|---|---|---|---|
| Port geçişi #49 | PASS | `TESTLER/test_port_transition_force_fallback.py`, 6 PASS; sentetik/izole süreç modeli | Kod ve izole güvenlik senaryoları tamamlandı; canlı kullanıcı PID'si denenmedi | Yeni kod değişikliği yok | Ayrı Windows kullanıcı kabulü |
| V4.6 review/bulk ve 4K UI regresyonu | PASS / SKIP | `TESTLER/test_v46_review_bulk_esrgan.py`, 4 PASS, 2 SKIP; `TESTLER/test_v44_group1_upscale_ui.py`, 8 PASS | 2 skip üretim DB güvenlik koruması nedeniyle | İzole fixture ile skip nedenini ayrıca sınıflandırabilir | Gerçek Windows kurulumunda GUI kabulü |
| Yedi kategori geometri | HUMAN_QA_REQUIRED | `tests/test_v46_all_category_geometry_benchmark.py`, 1 PASS; yalnız sentetik veri; gerçek Golden örnek 0 | Sentetik sonuçlar gerçek doğruluk iddiası değildir; Ocak Arkası 0/3, Cam Doğrama median IoU 0.3579 | Golden dosyaları gelince salt-okunur ölçüm çalıştırılabilir; yeni algoritma araştırması bu görevin dışında | Kaynak SHA'sı doğrulanmış Golden Dataset ve insan karşılaştırması |
| PETEK 34+ kalite | HUMAN_QA_REQUIRED | PETEK/regresyon seçkisi 63 PASS; sentetik/fixture kanıtı | Gerçek delik, bağımsız kavis ve maske dışı piksel kabulü gerçek örneklerle yapılmadı | Golden QA raporu üretilebilir | En az 34 gerçek, salt-okunur ve SHA doğrulanmış PETEK örneği |
| Real-ESRGAN / 4K GPU | NOT_RUN_AS_PASS | Önceki GPU smoke tarihsel kanıt olarak korunuyor; bu oturumda yeniden çalıştırılmadı | Model/EXE/GPU gerçek makine koşulu ve yeniden kurulum bu kopyada kanıtlanmadı | İzole Windows makinede kurulum ve tek örnek A/B çalıştırılabilir | NVIDIA/Vulkan makinesi, model ve gerçek çıktı kabulü |
| Gerçek HTTPS / marketplace XLSX / SKU | NOT_RUN_AS_PASS | 63 fixture/regresyon PASS; gerçek servis ve workbook kullanılmadı | Hesap, ağ ve müşteri workbook erişimi yok; özel veri yüklenmedi | Kullanıcı mock workbook veya güvenli test hesabı sağlarsa doğrulanabilir | Gerçek/izinli workbook, HTTPS hedefi ve bağlantı kabulü |
| Windows GUI + 7 kategori üretim | NOT_RUN_AS_PASS | Aday ZIP hazır; `V46_WINDOWS_KULLANIM.md` prosedürü mevcut | Bu oturumda izole Win11 GUI çalıştırılmadı | Kullanıcı adımlarıyla birlikte smoke/rollback kaydedilebilir | Yeni klasöre çıkarılmış izole Windows ortamı |
| Kesinti / yeniden başlatma / 100-1000 render | BLOCKED | Kaynak kod ve önceki regresyon kanıtları mevcut; gerçek batch sonucu yok | Gerçek veri ve uzun süreli Windows süreçleri güvenli kopyada çalıştırılmadı | Sentetik batch fixture ile süre ve resume ölçülebilir | Kullanıcı onaylı sentetik/izole batch kabul ortamı |
| G3 `missing=35` ve `template_profiles 590→591` | BLOCKED | Eski rapor referansı; bu kopyada canlı DB okunmadı | Kullanıcı bazı PNG'leri bilerek silmiş olabilir; 35 kaydın nedeni ve 590→591 değişimi kanıtlanmadı | Salt-okunur ledger/DB snapshot verilirse sınıflandırma raporu üretilebilir | Canlı DB'ye yazmadan, kullanıcı sağladığı kopya ve hash |
| Tek final ZIP + SHA | PASS (paketleme) / HUMAN_QA_REQUIRED (ürün kabulü) | `V46_FINAL_CANDIDATE.zip`; SHA256 `4232ed9397ab5a217ef5c6608ff2478358ba2d7123552b124d7bad940ed89778`; manifest PASS | ZIP'in varlığı tüm runtime kabullerinin geçtiğini göstermez | Yok; paket hazır | İzole Windows çıkarma, kurulum ve insan kabulü |

## Tek teslim paketi

- Yerel ZIP: `C:\AI_WORK\GORSEL_V46_PR52_SAFE_20261024\V46_FINAL_CANDIDATE.zip`
- SHA256: `4232ed9397ab5a217ef5c6608ff2478358ba2d7123552b124d7bad940ed89778`
- Manifest: ZIP içindeki `V46_FINAL_CANDIDATE/MANIFEST_SHA256.json`
- Kurulum/kabul prosedürü: [`V46_WINDOWS_KULLANIM.md`](./V46_WINDOWS_KULLANIM.md)

ZIP GitHub'a yüklenmedi. Kullanıcıya indirilebilir public release olarak
sunulmuyor; güvenli geliştirme klasöründeki izole adaydır.

## 25 Ekim 2026 final sprint doğrulaması

- Hedefli Issue #35 kabul grubu: **82 PASS / 2 SKIP**.
- Tam yerel `TESTLER tests` çalışması: **580 PASS / 10 FAIL / 4 SKIP / 12
  subtest PASS**. FAIL'ler gerçek üretim PASS'ı olarak gizlenmedi:
  Tk GUI eksikliği, Windows symlink ayrıcalığı, UTF-8/legacy encoding fixture,
  Git checkout beklentisi ve korunan kurulu V4.6 sürecinin 8080'i kullanması
  olarak ayrıştırıldı.
- 8080 sahibi PID 23936 salt-okunur incelendi; `C:\GorselMockup_V46_ADAY`
  altındaki kurulu `app.py` olduğu görüldü. Süreç durdurulmadı ve canlı kurulum
  değiştirilmedi.
- Güncel aday ZIP SHA256: `898f8432448667995af491b1e97950ae9661d3127616caf5a9e6d9349ff40570`.
  Eski `4232ed...` değeri tarihsel/stale olarak sınıflandırıldı.
- Güncel ZIP, `4193b2a` kaynak commit'ine bağlıdır; 389 manifest kaynağı +
  manifest ile 390 ZIP girdisi doğrulandı.
- Kullanıcının son kararıyla tarihsel `missing=35` olayı
  `USER_REPORTED_INTENTIONAL_DELETION` olarak sınıflandırıldı; receipt/ledger ve
  güvenlik guard'ları korunuyor, tek tek arama/restore yapılmadı.
- `template_profiles=590→591` için güvenli DB snapshot bulunmadığından aktif
  APPROVED/stale/source-SHA ayrımı **BLOCKED** kalmıştır. Canlı DB okunmadı veya
  değiştirilmedi.
- 8080 sahibi durdurulmadan `MOCKUP_PORT=8081` alternatif launcher ile izole
  sentetik runtime smoke PASS oldu. `V46_SAFE_LAUNCHER.bat` ve
  `scripts/v46_launcher_preflight.py` eklendi.
- Yeni commit bağlı ZIP: `V46_FINAL_CANDIDATE_54006B4.zip`, SHA256
  `bdb03b9271ad29b9026fa4b992e3d948693a35a5bd0f0c52730ec3f592713b4c`.
