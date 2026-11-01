# PETEK V4.11.2 Kök Neden Raporu

Tarih: 2026-11-01  
Kapsam: Salt-okunur teşhis. Canlı kaynak fotoğrafı, onaylı maske, dört köşe,
SQLite, mağaza ataması, üretim geçmişi veya kod davranışı değiştirilmedi.

## 1. Workspace ve çalışma ortamı kanıtı

- Açık klasör:
  `C:\Users\oguzc\Downloads\GORSEL_7_KATEGORI_PETEK_V4112_HTTP_422_ONIZLEME_GUVENLI_WINDOWS_20261101\GORSEL_V4102_WINDOWS\GORSEL_V46_CANDIDATE`
- Kaynak kodu bu adayın altındaki `MERKEZ` ve `SABLON_V2_MIMARI` klasörlerindedir.
  Windows başlatıcısı [`SABLON_V2_MIMARI\v2_baslat.bat`](../SABLON_V2_MIMARI/v2_baslat.bat)
  runtime kökünü `MOCKUP_RUNTIME_WORKSPACE` ile ister ve
  `<runtime>\SABLON_V2_MIMARI\ayarlar.db` yoksa başlamaz.
- Kaynak kodu ile mutable runtime ayrımı
  [`SABLON_V2_MIMARI\app.py`](../SABLON_V2_MIMARI/app.py:18) içinde yapılır:
  `SOURCE_ROOT` kod köküdür; `MOCKUP_RUNTIME_WORKSPACE` varsa `BASE_DIR` olarak
  kullanılır.
- Bu workspace altında `.git` metadata, `ayarlar.db`, `.sqlite` veya
  `.sqlite3` dosyası bulunmadı. `MOCKUP_RUNTIME_WORKSPACE` ve
  `PETEK_V3_LOCAL_STATE` bu Windows oturumunda ayarlı değildi.
- PETEK web registry varsayılan yolu
  [`MERKEZ\PETEK_V3\registry.py`](../MERKEZ/PETEK_V3/registry.py:14):
  `%LOCALAPPDATA%\GorselMockup\PetekV3`. Sandbox oturumunda bu varsayılan
  klasör de mevcut değildi. Bu nedenle canlı makinenin gerçek runtime kökü,
  SQLite yolu, mağaza profili ve mevcut UID/SHA kayıtları bu oturumdan
  doğrulanamadı; aşağıdaki kayıt sonuçları canlı veri iddiası değildir.
- Çalışan HTTP sürecinin gerçekten V4.11.2 olduğu da bu oturumda
  doğrulanamadı; bunun için `PETEK_8080_TESHiS_WINDOWS.ps1` salt-okunur
  `/api/petek/service-status` kontrolünü kullanır.

## 2. V4.11.2 ve GitHub dalları karşılaştırması

Workspace paketlenmiş bir adaydır, Git checkout değildir. GitHub erişimi
salt-okunur `gh api` ile doğrulandı:

- Repo: `oguz13-tech/gorsel-mockup-automation-src`
- İlgili dallar: `release/v4102-approval-speed-and-ui-20261031`,
  `fix/vnext-petek-vent-geometry-and-selection-20261101`,
  `fix/petek-dynamic-preview-13-16-ui-20261101`,
  `fix/store-production-uid-diagnosis-20261101`.
- `release/v4102...fix/vnext-petek-vent-geometry-and-selection-20261101`
  karşılaştırması 59 commit ileridedir ve gerçek 13--16 yarık ölçümü,
  kaynak ölçümlü geometri, seçim regresyonları, VNext SHA manifesti ve
  Windows aday doğrulayıcılarını içerir.
- Store dalı 71 commit ileridedir ve ayrıca `store_selection_diagnostic_vnext.py`
  ile issue-79 fail-closed UID kimlik ön kontrolünü içerir.
- Preview dalı 70 commit ileridedir ve `preview-artwork` gerçek tasarım,
  13--16 dinamik sayım ve stale browser cache testlerini içerir.
- Yerel `V4112_KOD_DEGISIKLIKLERI.patch` yalnızca HTTP hata kurtarma dalındaki
  Python `locals()` kapsam tuzağını düzeltir; bu patch fiziksel geometri,
  SQLite veya mağaza kimliklerini düzeltmez.

Sonuç: Bu klasör, GitHub’daki en güncel PETEK/store dallarının tamamıyla
aynı olduğu kanıtlanmış bir checkout değildir. Canlıda hangi dalın çalıştığı,
kod kökü ve `/api/petek/service-status` ile ayrıca kanıtlanmalıdır.

## 3. Render, maske ve reddetme zinciri

### 3.1 Gerçek fiziksel yarık uyuşmazlığı

Çağrı zinciri:

1. Web preview:
   [`petek_web_v477.py`](../SABLON_V2_MIMARI/core/petek_web_v477.py:397)
   `render_petek_visual(...)` çağırır.
2. Batch:
   [`unified_batch.py`](../MERKEZ/URETIM_V4/unified_batch.py:846)
   aynı `render_petek_visual(...)` fonksiyonunu çağırır.
3. Ortak renderer:
   [`petek_visual_pipeline_vnext.py`](../MERKEZ/PETEK_V3/petek_visual_pipeline_vnext.py:89)
   her çağrıda önce `ensure_source_vent_mask_consensus(...)` çalıştırır.
4. Guard:
   [`petek_render_contract_v1.py`](../MERKEZ/PETEK_V3/petek_render_contract_v1.py:101)
   fotoğrafı perspektif olarak `900 x 900` dikdörtgene taşır, black-hat profil
   ve kaynak tepe/merkezlerini çıkarır; maskeyi aynı rectified uzayda ölçer.

Kritik davranış:

- Guard `slot_mode='off'` olsa bile çalışır. Bu kasıtlıdır; görsel yarık
  efektini kapatmak, fotoğraftaki gerçek koyu yarıkları baskıyla kapatma
  izni vermez.
- Kaynakta 12--28 aday bulunup maskede 13’ten az delik varsa ve merkez
  fit edilemiyorsa `PETEK_SOURCE_MASK_VENT_CONFLICT_REVIEW` üretilir
  (satır 119--128).
- Fit edilen merkezlerin uzun koyu çizgi kanıtı `supported > .38`, maskede
  korunma kapsamı ise `kept >= .48` ister (satır 145--178). Geçerli gerçek
  kaynak çizgisi maskede kapatılabilir durumda ise yine 422 reddi üretilir.

Kök neden sınıflandırması:

- Kod davranışı: fiziksel guard tüm preview ve batch yollarında ortak ve
  fail-closed'dur. Bu yüzden tek bir şablon-maske uyuşmazlığı o şablonun
  her tasarım denemesini reddeder.
- Kayıt/varlık ilişkisi: 14/16 gerçek yarık ile 5/7/9/12 maskeli açıklık
  gözlemi, onaylı maskenin gerçek fotoğrafın güncel byte/SHA'sına ait
  olmaması, eski geometri veya rectified koordinat/pitch farkı hipotezini
  destekler; ancak canlı fotoğraf ve maskeler bu workspace’te olmadığı için
  hangisi olduğu henüz kanıtlanmamıştır.
- Yanlış pozitif kanıtı yoktur: odaklı testler gerçek kaynak kanıtı,
  19/14 px replay, N1/N2/N3 ve 14/15 fiziksel çizgi reddini sınar; fakat
  test fixture’ları sentetiktir.

### 3.2 Neden 4 x 4 = 16 denemenin tamamı atlandı?

Batch her tasarım ve template çiftini ayrı dener; `MaskError` yakalanınca
ledger kaydı quarantine edilir ve sonraki çiftlere devam edilir
([`unified_batch.py`](../MERKEZ/URETIM_V4/unified_batch.py:913)).
Bu güvenli davranıştır. Aynı 4 template’in ortak source/mask kimliği veya
aynı fiziksel uyuşmazlığı varsa 4 tasarımın tamamı × 4 template = 16
denemenin aynı guard’da reddedilmesi beklenen sonuçtur. Bu bir rastgele
skip veya worker kaybı kanıtı değildir; gerçek ledger satırları olmadan
hangi 16 hata metninin yazıldığı doğrulanamaz.

### 3.3 Geçici maske ve gerçek tasarımlı preview

422 dalı plain fotoğrafı başarı gibi göstermez. Geçici maske
[`petek_render_contract_v1.py`](../MERKEZ/PETEK_V3/petek_render_contract_v1.py:188)
`cv2.min(mask, photo_mask)` ile yalnızca baskı iznini daraltır; maskeyi
genişletmez, kaydetmez ve `source_verified` olmadan reddeder.
HTTP dalı [`petek_web_v477.py`](../SABLON_V2_MIMARI/core/petek_web_v477.py:493)
bu geçici maskeyi deneyerek gerçek `artwork` ile teşhis önizlemesi üretir.

Bu nedenle "aynı şablon preview ve batch’te reddediliyor" gözleminin temel
nedeni: preview’nin güvenli fallback’i yalnızca teşhis ve kayıtsızdır;
batch ise onaylı/orijinal maskeyi değiştirmeden üretime izin vermez.

### 3.4 "Gerçek Tasarımla Önizle" seçili tasarımı göstermiyor

Tarayıcıdaki akış [`petek_editor_v477.js`](../SABLON_V2_MIMARI/static/js/petek_editor_v477.js:614)
dosya input’undan tek tasarımı okur, canvas’a küçültür ve
`artwork_png` olarak `/api/petek/preview-artwork` gönderir
(satır 654--661). HTTP tarafı da bu bytes’ları `cv2.imdecode` edip
renderer’a verir.

Kodda seçilen dosyanın gönderilmediğine dair kanıt yok. Bununla birlikte
iki somut ortam/UX nedeni var:

1. `service-status` contract/revision kontrolü eski 8080 sürecinde hata
   veriyor (satır 636--644); eski backend HTML/yanlış JSON döndürürse seçili
   tasarım hiç render edilmez.
2. 422 fallback’inde yalnız `diagnostic_artwork_applied` true ise
   `data.preview` canvas’a konur (satır 670--687). Guard veya geçici maske
   kanıtı başarısızsa UI bilinçli olarak fotoğrafı geri çizer; bu, seçili
   tasarımın kaybolduğu izlenimini verir ama güvenlik gereğidir.

Canlı network response ve tarayıcı console kaydı olmadan bunlardan hangisinin
gözlenen olay olduğu kesinleştirilemez.

## 4. UID/SHA ve `wudie` mağaza eşleşmesi

İki ayrı kimlik sistemi vardır:

- Web PETEK preview registry:
  [`petek_web_v477.py`](../SABLON_V2_MIMARI/core/petek_web_v477.py:47)
  fotoğrafın mevcut byte SHA’sını alır ve registry satırlarında
  `row['source_sha'] == sha` arar. Registry
  [`registry.py`](../MERKEZ/PETEK_V3/registry.py:14) altında
  `%LOCALAPPDATA%\GorselMockup\PetekV3`.
- Mağaza üretim profili:
  [`store_profiles_v47.py`](../MERKEZ/URETIM_V4/store_profiles_v47.py:19)
  anahtarı `category:uid@source_sha` olarak saklar; dosya runtime kökünde
  `store_profiles_v47.json` olur (satır 59--63).

Mağaza teşhisçisi bilerek tam `category + uid + source_sha` kesişmesi ister
([`store_selection_diagnostic_vnext.py`](../MERKEZ/URETIM_V4/store_selection_diagnostic_vnext.py:39)).
Aynı UID mevcut olsa bile SHA farklıysa `STALE_APPROVAL_OR_SHA`; UID seçimi
ile üretimde seçili UID kesişmiyorsa `NO_COMMON_UID` üretir.

Bu nedenle "kayıtlar mevcutken onaylı şablon sayısı 0" için kanıtlanmış
kod nedeni: UI’de UID-only görünürlük ile üretim profili full-key
(`UID@SHA`) üyeliği farklıdır. Gerçek kayıt nedeni ise mevcut değil:
runtime `store_profiles_v47.json`, PETEK profile JSON’ları ve SQLite bu
workspace’te bulunmadı. En olası iki ayrım canlıda ölçülmelidir:

1. `wudie` profil dosyası başka runtime kökünde okunuyor.
2. UID aynı, fakat source SHA değişmiş/stale; dolayısıyla tam anahtar
   kesişmiyor.

## 5. Ortak ticari çıktı SHA hatası

Ortak ticari/linkleme yolu output dosyasının SHA’sını ledger satırındaki
`output_sha` ile birebir karşılaştırır; uyuşmazsa yüklemeyi atlar
([`cloud_excel_v43.py`](../MERKEZ/URETIM_V4/cloud_excel_v43.py:167)).
Aynı artifact key farklı output SHA ile iki kez gelirse daha başlamadan
`BULUT_DUPLICATE_KEY_SHA_CONFLICT` üretir (satır 152--156).

Kod düzeyinde bu güvenlik kontrolü beklenen fail-closed davranıştır. Kök
neden adayı, ortak ticari listenin eski ledger snapshot’ındaki
`output_sha` ile yeniden üretilmiş/başka runtime’daki dosya SHA’sının
karıştırılmasıdır; fakat canlı ledger ve dosya mevcut olmadığı için bu
hipotez henüz kanıtlanmamıştır. Önce `key`, `output`, recorded SHA ve gerçek
dosya SHA’sı aynı runtime kökünde salt-okunur karşılaştırılmalıdır.

## 6. Doğrulama sonucu

Çalıştırılan komut:

```text
MERKEZ\.venv\Scripts\python.exe -m pytest -q
  tests/test_final_petek_contract_20261101.py
  tests/test_v4112_http_fallback_guard.py
  tests/test_vnext_petek_dynamic_photo_count.py
  tests/test_vnext_petek_preview_parity_and_recovery_20261101.py
```

Sonuç: **23 passed** (12.95 s).

Bu sonuç yalnızca kontrat ve sentetik regresyonları doğrular. Gerçek 14/16
fotoğraflar, gerçek onaylı maskeler, `wudie` kaydı ve canlı 8080 süreci test
edilmedi; dolayısıyla bunlar için "kod kesin bozuk" veya "kayıt kesin bozuk"
sonucu çıkarılmamalıdır.

## 7. Aşama 2 için izole düzeltme planı

Canlıya dokunmadan, ayrı bir kopya/runtime kökünde:

1. `PETEK_8080_TESHiS_WINDOWS.ps1` ve `/api/petek/service-status` ile
   gerçek `code_root`, `runtime_root`, contract/revision ve PID’yi kaydet.
2. `MOCKUP_RUNTIME_WORKSPACE` kökünde `SABLON_V2_MIMARI\ayarlar.db`,
   `store_profiles_v47.json`, PETEK registry `profiles`, `masks`,
   `active_revisions.json` ve ilgili source fotoğrafları yalnızca oku.
3. `wudie` için her kayıt üzerinde
   `category:uid@source_sha` ile mevcut approved row/source SHA’yı
   karşılaştır; sadece rapor üret, atamayı değiştirme.
4. Her gerçek 14/16 fotoğrafta rectified fotoğraf profili, merkezler,
   `source_good`, `kept`, mask merkezleri ve ilk uyuşmazlık koordinatlarını
   kaydet. 19/14 ve N1/N2/N3 testlerini koru; tolerans artırma veya guard
   kapatma yapma.
5. Aynı gerçek fixture ile preview ve batch’i çalıştır; preview’nin
   `diagnostic_preview`/`diagnostic_artwork_applied` değerlerini, gönderilen
   artwork SHA’sını ve batch quarantine reason’ını karşılaştır.
6. Ortak ticari SHA için ledger `output_sha`, gerçek output SHA, output path
   ve artifact key’i tek snapshot’ta karşılaştır; yalnız snapshot/identity
   üreticisi düzeltilsin.
7. Düzeltme ancak izole testte gerçek tasarımın response’ta göründüğü,
   orijinal fotoğraf/maskenin byte-identical kaldığı, dört template × dört
   tasarımın beklenen şekilde işlendiği, `wudie` full-key eşleşmesinin
   kanıtlandığı ve ticari SHA tekrar geçtiği gösterildikten sonra
   değerlendirilsin.

Bu raporda kod, SQLite, onaylı maske, kaynak fotoğraf, mağaza ataması veya
canlı üretim verisi değiştirilmemiştir.
