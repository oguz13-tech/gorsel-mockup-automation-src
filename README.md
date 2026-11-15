# Görsel Üretim Merkezi — Kaynak Deposu

**E-ticaret ürün görsellerinin (mockup) üretimini, baskı tasarımını katmanlama, mağaza bazlı Excel listelerini ve bulut linkleme akışını otomatikleştiren Windows masaüstü sistemi.**

Bu depo yalnızca **kaynak kodu, dokümantasyon ve regresyon testlerini** içerir. Canlı veri (şu anki ayarlar, onaylı 4 köşeler, maskeler, üretim kayıtları, mağaza Excel'leri, gerçek ürün fotoğrafları) asla bu depoya girmez; bkz. [Güvenlik ve gizlilik](#güvenlik-ve-gizlilik).

---

## Proje ne yapar

1. **7 ürün kategorisi** için baskı tasarımını ürüne uygular (mockup üretimi):
   | # | Kategori |
   |---|----------|
   | 1 | Wi-Fi kutusu |
   | 2 | Dikey cam tablo |
   | 3 | Yatay cam tablo |
   | 4 | Ahşap tablo |
   | 5 | Cam doğrama |
   | 6 | Ocak arkası cam panel |
   | 7 | PETEK (radyatör) kapama dolabı — proje ana yükü; geometri, maskeleme ve gerçekçilik motoru burada |
2. Üretim sonrası **bulut yükleme + linkleme** (ImageKit / ImgBB / FreeImage) yapar ve **mağaza bazlı Excel** (Trendyol/pazaryeri listeleri) üretir.
3. Masaüstünde **Tkinter "Graphite Workbench"** ana arayüzünü ve **Flask tabanlı köşe/inceleme editörünü** (127.0.0.1:8080) barındırır.

---

## Depo haritası

```text
CODEX_ACTIVE/                      ← bu depo = kaynak root
├─ BASLAT.bat                      ← giriş noktası (V5)
├─ MERKEZ/                         ← ana uygulama paketi
│  ├─ merkez.py                    ← Tkinter ana pencere (form/kanvas köprüsü)
│  ├─ graphite_workbench_v500.py   ← V5 Graphite Workbench (ana arayüz)
│  ├─ workspace_contract.py         ← kod ↔ runtime yol çözümü (tek kanonik yer)
│  ├─ PETEK_V3/                    ← PETEK motoru: maske, geometri, render, overlay/QA
│  ├─ URETIM_V4/                   ← 7 kategorilik toplu üretim, Excel/pazaryeri, mağaza profilleri
│  └─ GUNLUK/                      ← günlük iş/izin yönetimi yardımcıları
├─ SABLON_V2_MIMARI/               ← Flask köşe editörü + SQLite tab şema (core/, static/, templates/)
├─ TESTLER/                        ← Türkçe regresyon/kabul testleri (pytest)
├─ tests/                          ← İngilizce birim/contract testleri (pytest)
├─ tests/js/                       ← Node tabanlı UI testleri
├─ scripts/                        ← release/doğrulama/bakım senaryoları
├─ tools/                          ← kullanıcı onayı gerektiren bakım/onarım araçları
├─ docs/                           ← mimari, hata kökü (RCA), kabul kayıtları ve v4→v6 notları
└─ ASSETS/PETEK/                   ← render-only PETEK alan maskeleri (ürün-nötr)
```

### Kod ↔ runtime ayrımı

`MERKEZ/workspace_contract.py`, kod kökünü (`CODEX_ACTIVE`) çalışma kökünden (canlı veritabanı, şablonlar, çıktılar) ayırır. İki kök birbirine karıştırılamaz: canlı veriye yazma yolu yalnızca runtime kökü vardır. Bu ayrımı bozacak hiçbir değişiklik kabul edilmez.

### Başlatma zinciri

```text
BASLAT.bat
  → MERKEZ/BASLAT.bat   (ortam değişkenleri: GORSEL_CODE_ROOT, GORSEL_RUNTIME_ROOT, V4_RENDER_WORKERS=2)
    → MERKEZ/.venv\Scripts\python.exe -B merkez.py
```
- Ana arayüz: Tkinter.
- Köşe editörü: `SABLON_V2_MIMARI/app.py` → Flask, `127.0.0.1:8080`.
- PETEK isolated doğrulama: `PETEK_ISOLATED_BASLAT_WINDOWS.bat` / `*_DOGRULA_WINDOWS.bat`.

---

## Kurulum (Windows 10/11)

1. **Python 3.11 veya 3.12** kurulu olsun (`py -3` veya varsayılan `python`).
2. Depoyu klonlayın veya açın.
3. `KURULUM.bat` çalıştırın — `MERKEZ\.venv` içinde bağımlılıkları kurar:
   `numpy, opencv-python-headless, Pillow, openpyxl, Flask, requests, pywebview, pytest`
   (tam liste: `MERKEZ/requirements.txt`).
4. `BASLAT.bat` ile ana uygulamayı, `SABLON_V2_MIMARI\v2_baslat.bat` ile köşe editörünü başlatın.

İlk çalıştırmada runtime kökünüz boşsa uygulama yalnızca kaynak-ağacında çalışır; gerçek üretim için canlı klasör ve veritabanının yerinde olması gerekir. Bu depoyu boş klasörde denemek için testler sentetik fixture kullanır.

## Testler

```bat
MERKEZ\.venv\Scripts\python.exe -m pytest tests TESTLER -q
```

- `tests/` kontrat/birim testleri; `TESTLER/` kategori ve güvenirlilik testleri.
- JS contract testleri Node ile: `node tests/js/<dosya>.cjs`.
- Testler canlı veriye yazmaz; geçici fixture (`tmp_fixtures/` gibi ignored klasörler) kullanır.
- **Not:** Bu ortamda GUI, gerçek mağaza Excel bağlantısı ve canlı PETEK master aktivasyonu doğrulanmadı; Windows kabul kayıtlarına bakın (bkz. `docs/WINDOWS_*.md`, `docs/V46_*.md`).

## Geliştirme akışı

1. Yeni dal açın (`feature/…`, `fix/…`); `main` doğrudan güncellenmez.
2. Küçük, hedefli değişiklik yapın; önce test yazın veya mevcut testlerle doğrulayın.
3. Kapsam: dokunduğunuz modülün testleri + üretim yoluna giren değişikliklerde tam regresyon.
4. PR açın; `main`'e merge'den önce testler yeşil olmalı.
5. Push'ta asla: canlı ayarlar, maskeler, SQLite/DB, `store_profiles_v47.json`, mağaza Excel'i, gerçek görseller, `ayarlar.json`.

## Güvenlik ve gizlilik

Bu depo **public**'tir. Şunlar asla commit edilmez (ve `.gitignore` bunları eler):

- **Canlı ayarlar:** `ayarlar.json`, `ayarlar.local.json`, `**/ayarlar.json` (şablon `ayarlar.local.example.json` kabul edilir).
- **Veritabanları:** `*.sqlite3`, `*.db`, `**/store_profiles_v47.json`, `**/v4_ortak_uretim.sqlite3`.
- **Maskeler ve onaylı 4 köşeler:** `PETEK_MASTER_REVISIONS/`, `2_SABLON_HAVUZU*/`, `HAM BASKI TASARIMLARI/`, `Overlay_Giydirme/`.
- **Üretim çıktıları ve kullanıcı görselleri:** `REVIEW_ARTIFACTS/`, `Kalite_Kontrol_Gorselleri/`, `runtime/`, `logs/`, `**/uretilen_gorseller/`.
- **Çıktı/paket dosyaları:** `*.jpg *.png *.xlsx *.csv *.zip *.rar *.exe *.pt *.onnx *.safetensors` (istisna: `ASSETS/PETEK/` altındaki ürün-nötr render-only alan maskeleri `git add -f` ile eklenir).
- **Yerel SHA manifestleri ve test raporları:** `SHA256_MANIFEST.json`, `PETEK_ISOLATED_*`, `WINDOWS_ACCEPTANCE_*.json`, `*_TEST_REPORT*.json`.

Gizli anahtarınızı accidentelle commit ederseniz anahtarı iptal edip yenileyin ve geçmişi ayrıca incelemeye alın.

## Kritik koruma kuralları (yapmayın)

- `ayarlar.json` / onaylı 4 köşe (`koseler`) değiştirilemez; toplu işlem öncesi `.bak_before_<işlem>` yedeği alınır; JSON anahtarları yeniden numaralandırılamaz.
- PETEK geometrisi, baskı tasarımı, öğe sırası ve ızgara doğallığı bozulamaz.
- Otomatik master aktivasyonu veya otomatik "approved" yoktur; insan onayı gerekir.
- Canlı üretim durdurulmadan kaynak dosyalar değiştirilmez; testte kanıt olmadan "düzeldi" denmez.
- İki kök (kod / runtime) karıştırılmaz; `workspace_contract.resolve_contract(validate=True)` dışı yol varsayılmaz.

## Belgeler

`docs/` altında kronolojik mühendislik notları bulunur:

| Dosya | İçerik |
|-------|--------|
| `V4101_ARCHITECTURE.md` | V4 mimarisi ve veri akışı |
| `V4101_SOURCE_FILE_INDEX.md` | Kaynak dosya envanteri ve sorumluluklar |
| `V4102_RELEASE_AND_AUDIT.md` | Sürüm kapıları, audit akışı |
| `V475_FINAL_CODE_DELIVERY.md` | Son kod teslimi ve kabul durumu |
| `PETEK_V4112_KOK_NEDEN_RAPORU_20261101.md` | PETEK 409/500 hata kökü analizleri |
| `V46_*.md`, `WINDOWS_*.md` | Windows kabul ve teslim kayıtları |
| `GOREV_TAKIP.md` | Devir ve açık görev takibi |

## Durum notu

Bu depo, yerel `C:\GorselUretimMerkezi\CODEX_ACTIVE` kaynak ağacının temiz bir senkronudur. Tarihsel `main` dalı **güncel sürüm değildir**. Gerçek canlı verilerle uçtan uca Windows kabulü, yerel ortamınızda ayrıca yürütülmelidir.

## Lisans

Tüm hakları saklıdır (özel/ticari kullanım). Yeniden dağıtım veya yayım öncesi sahibine sorun.
