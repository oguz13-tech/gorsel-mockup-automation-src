# 2026-10-17 — Tam depo ve release kapısı denetimi

**Durum:** `DRAFT / PRODUCTION BLOCKED`. Bu çalışma bir release sertifikası değildir.

## Gerçek kapsam ve yöntem

- Referans: bağımsız PR #6 HEAD `bbf5a6ad12b88729b69458c7067fd942121544cc` (PR #5 üzerine).
- GitHub `git/trees` recursive envanteri: başlangıç dalında 214 toplam ağaç girdisi; son audit dalında 184 takip edilen dosya, 106 Python, 19 BAT, 2 JS, 36 `tests/` test dosyası. Son sayılar eklenen audit dosyalarına göre değişebilir.
- İncelenen alanlar: `99_SISTEM_MOTORLARI_VE_KODLAR/` render/cloud/excel/cache/legacy; `SABLON_V2_MIMARI/` Flask, JSON/SQLite, onay, geometri, analiz, numara, lifecycle, migration, işler, araçlar; `V2_KONTROL_MERKEZI/`; 8999 `SABLON_DUZELTICI.py`; BAT/PowerShell başlatıcılar; bağımsız sekiz BAT aracı; `AI_Kalite_Artirici`; altı kategori / dosya-isim kimlikleri; kritik testler.
- Test yaklaşımı: seçili 48-test CI'nin yanı sıra **tüm** `tests/` altında `python -m pytest -q --disable-warnings tests`, bütün takip edilen Python'larda `compileall -q -f .`, Windows ve Ubuntu matrisleri. Sentetik ve geçici veriler; kullanıcı OneDrive/gerçek veritabanı erişimi YOK.
- Kaynak kod envanteri gerçek kullanıcı OneDrive çalışma alanındaki tüm dosyaları **görmez**. Bu ayrı Windows canlı ön kontrol gerektirir.

## Denetimde doğrulanan gerçek sorunlar

| Kimlik | Sınıf | Kanıt | Düzeltme/kapı |
|---|---|---|---|
| AUD-A | P0 | `final_fix.py`, `ultimate_rescue.py` eski JPG/JPEG/WEBP dosyalarını, orijinal yedekler dahil `unlink()` ediyordu. | Altı eski kurtarma scripti kendi isimleriyle korunarak varsayılan read-only preview'a dönüştürüldü. Tam otomatik geri yükleme bu scriptlerden kaldırıldı; ayrı insan onaylı lifecycle gerekiyor. |
| AUD-B | P0 | `rollback.py`, `rescue_edits*.py`, `fix_json_keys.py` sabit tarihli JSON'u güncel ayarlara direkt yazıyordu. | Aynı altı giriş tehlikeli yazma yapmıyor, SHA ve sayım karşılaştırması üretiyor. |
| AUD-C | P0 | Eski `generate_test_13er_tane.py` test adıyla gerçek output oluşturup ImgBB'ye otomatik upload başlatabiliyordu. | Açık `--execute --runtime-root` zorunlu; otomatik cloud upload kesin kapalı; orijinal script korundu. |
| AUD-D | P1 | `SABLON_V2_MIMARI/v2_baslat.bat` otomatik pip install yapıyordu. | Açılışta paket kurulumu kaldırıldı; açık runtime ve ön bağımlılık kontrolü eklendi. |
| AUD-E | P0 | `INCELEME_MERKEZINI_AC.ps1` panel başlamadan eksik baseline dosyasını yazabiliyordu. | Örtülü `--ensure` kaldırıldı. |
| AUD-F | P0 | `tools_runner.rename_images` koruma sonrası tamamen ayrı DB'siz klasörde çalışmaz hale gelmişti. | Yalnız gerçek runtime işaretleri bulunmayan bağımsız klasörde geçici lokal isimlendirme; üretim kimliği/rezerve için DB şartı korunur. |
| AUD-G | P1 | Çoklu testte render smoke modülü global `sys.modules` üzerinden preflight olmayan örneği reuse edebiliyordu. | Testi izole child interpreter'a taşıyarak global state karışmasını engelleme. |
| AUD-H | P0 | `manuel_mockup_motoru.py` eski JSON'a bakarak `APPROVED` ve source hash doğrulamasını atlayabiliyordu, ayrıca `BASE_DIR` kaynağa bağlıydı. | `manual_production_guard.py` read-only SQLite, tam source-hash, tek aktif insan onayı ve geometri kontrolü; gerçek runtime zorunlu; script/BAT silinmedi. |

## Kapsamda kontrol edilen kullanıcı araçları (SİLİNMEDİ)

1. `01_GORSEL_ISIMLENDIRICI.bat` → `tools_runner.py rename`.
2. `02_FORMAT_CEVIRICI_PNG_JPG.bat` → `tools_runner.py convert`.
3. `03_OTOMATIK_FILIGRAN.bat` → `tools_runner.py watermark`.
4. `04_AI_4K_KALITE_ARTIRICI.bat` → `tools_runner.py 4k`.
5. `05_GORSEL_LINK_EXCEL.bat` → `tools_runner.py links`.
6. `06_SEO_URUN_ADI_URETICI.bat` → `tools_runner.py seo_titles`.
7. `07_SEO_ACIKLAMA_URETICI.bat` → `tools_runner.py seo_descriptions`.
8. `08_RECURSIVE_PNG_DONUSTURUCU.bat` → `tools_runner.py png_recursive`.
Ek: `TOPLU_GORSEL_LINKLEYICI.bat`, `4K_KALITE_YUKSELT_ESRGAN.bat`, `ARACLAR_MERKEZINI_AC.bat`, `MANUEL_GORSELLERDEN_MOCKUP_URET.bat`, `SISTEMI_BASLAT.bat`, `OTOMASYONU_CALISTIR.bat`, `YENI_SABLONLARI_HAZIRLA.bat`, `INCELEME_MERKEZINI_AC.bat/.ps1`, `v2_baslat.bat`, `00_KLASORLERI_VE_SABLONLARI_YENILE.bat`.

## Hâlâ üretim kapısını engelleyen doğrulamalar (yeşil CI olsa bile)

1. `SABLON_V2_MIMARI/app.py` import sırasında `init_db()` çağırır; `core/db.py` başlatırken şema migrasyonu ve WAL yazmaları yapabilir. Canlı DB'nin tam ve tutarlı **SQLite backup API** snapshot'u / migration planı ve schema differential test olmadan açılış salt okunur kabul edilmez. Bu davranış önceden vardı; bu audit dalında henüz güvenli ürün akışına dönüştürülmedi.
2. `safe_working_revision.py` hata/çökme aralığı, `_P0_WORKING_REVISIONS` recoverer'ı, `APPROVED` revizyonuyla SQLite atomikliği, fiziksel OneDrive kilidi ve çoklu-process race gerçek Windows NTFS altında koşulmalı. CI bu koşulların tamamını canlandıramaz.
3. Gerçek 6 kategori/11 seçilmiş insan onaylı şablonun perspektif/occlusion QA'sı ve görsel içerik kalitesi ayrı kanıt gerektirir. Cam doğrama ve ocak arkası için fiziksel sınır ve maskeler özellikle review.
4. Bulut ImgBB/failover, Trendyol formatlı Excel, SEO isim ve açıklama dağıtımı üçüncü taraf ağ üzerinde otomatik test edilmedi; şifreler ve prod dosyalar kullanılmadan gerçek ticari uçtan uca PASS ilan edilemez.
5. `ayarlar.json` kaynak kod deposunda en az üç ayrı kopyada duruyor. Kaynağın `JSON` mu `SQLite` mı olduğu yazma yönünde kesinleştirilmeli; otomatik eşitleme yok. GitHub bu kopyaları gerçek runtime'nın güncel veri kaynağı varsayamaz.
6. Ajanın/CI'nin göremediği fiziksel Windows OneDrive klasöründe dosya sayısı, yatay/dikey 492 şablon, yedek SHA, İNCELEME merkezi açılışı, gerçek görsellerin dosya ve geometri kalitesi ancak açık kullanıcı kontrollü testle teyit edilir.

## Öncelikli kabul sırası

1. PR #7 full-suite her iki işletim sisteminde PASS ve statik legacy güvenlik kontratları.
2. Argon'un bağımsız patch'i ile PR #6/7 tam SHAlı karşılaştırma, kod review.
3. 8080 `init_db` startup migration öncesi güvenli/geri alınabilir ayrık SQLite snapshot kapısı, gerçek schema rollback testleri.
4. Simüle OneDrive kesintisi, locked image, power-loss/RECOVERY_REQUIRED replayer, ikinci tekrar test.
5. Tek gerçek kontrollü Windows kurulum ve ilk 3:4 demo, ardından insan QA ve küçük üretim; kullanıcı açık izniyle.

**NET:** Kaynak kodun alt kısmına kadar denetim yapmak mümkündür; ancak tüm gerçek işletim sistemi ve üçüncü taraf etkileşimleri görülmeden sıfır sorun garantisi verilmez. PR #7 merge/kurulum için değil, audit + izole kod/test doğrulaması için taslaktır.
