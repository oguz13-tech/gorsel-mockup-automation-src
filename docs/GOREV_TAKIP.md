# GÖRSEL ÜRETİM MERKEZİ V5 — GÖREV TAKİBİ

Durumlar: ⬜ BEKLİYOR · 🟡 YAPILIYOR · ✅ YAPILDI. Aynı anda yalnız bir ana görev YAPILIYOR olur.

| No | Görev | Durum | Sonuç |
|---|---|---|---|
| 1 | Geliştirme 13 — 4 Farklı Mockup / 4 Final Modu | ✅ YAPILDI | 18 izole test + gerçek şablon + gerçek bulut yükleme (4/4 link, Excel 76→136 doğru satır) geçti; canlı veri değişmedi. |
| 2 | Tüm sistemde maksimum performans | 🟡 YAPILIYOR | V5 cache/arka plan altyapısı korunuyor; Graphite kabukta ağır ekran yeniden oluşturma azaltıldı, karşılaştırmalı üretim ölçümü devam ediyor. |
| 3 | Ana menü navigasyonunu onar | 🟡 YAPILIYOR | `/` artık V6 ortak inceleme yüzeyi; Graphite modülleri tek kabukta, PETEK uyumluluk rotası kontrollü. Tüm modül kabul turu devam ediyor. |
| 4 | Mağaza profilleri ve Excel & Link işlemleri | 🟡 YAPILIYOR | Mağaza, üretim ve rapor çalışma alanları aynı Graphite yüzeyinde; Excel/link canlı veri kabulü ayrıca tamamlanacak. |
| 5 | Görsel üretim ekranını modernleştir | 🟡 YAPILIYOR | Üretim formu Graphite ana içerik alanını kullanıyor; sabit canlı işlem özeti ve günlük akış başlangıç düzeni eklendi. |
| 6 | Gerçek zamanlı üretim ve linkleme takibi | 🟡 YAPILIYOR | Üretim/linkleme/overlay ilerlemesi Graphite alt durum çubuğuna yansıtılıyor; canlı Windows kabul turu devam ediyor. |
| 7 | Üretim kayıtları (operasyon merkezi) | ✅ YAPILDI | Üretime hazır: Graphite "✓ Üretim Kayıtları" sekmesi artık son üretimler, ayrı Başarılı/Başarısız görsel listeleri, hata nedenleri, yarım kalan güvenle devam, SHA-256 ile yeniden üretim yok; canlı veriye dokunmadan test edildi. |
| 8 | Araçlar ve diğer bozuk modüller | 🟡 YAPILIYOR | `/tools` Graphite gömülü kabuk sözleşmesine alındı; kalan yardımcı araç kabulleri devam ediyor. |
| 9 | Raporlar ve tarama | 🟡 YAPILIYOR | Salt-okunur rapor/kurtarma çalışma alanı Graphite sekmesine bağlı; tam tarama/kanıt kabulü devam ediyor. |
| 10 | Ekran yüksekliği ve yerleşim | 🟡 YAPILIYOR | Ana panel operasyon kartları, tam genişlik çalışma alanı, gömülü WebView ve merkezi işlem çipi eklendi; 1366/1920 canlı turu devam ediyor. |
| 11 | Şablon İnceleyiciyi güvenle kapat | ⬜ BEKLİYOR | — |
| 12 | Kapsamlı sistem regresyon denetimi | 🟡 YAPILIYOR | Yetki: **Codex** (GOREV_TAKIP.md 2026-11-13'te devredildi). Kapsam ve test envanteri belirlendi. |

## Görev 1 — Kayıtlar

### Kararlar
- Varyasyon kimliği **slottan** gelir (slot 1=76, 2=96, 3=116, 4=136; şablonlarda ölçü bilgisi yok). Overlay dosyası (`overlayNN.png`) yalnız etiketi belirler; kapalı olsa da kimlik/Excel değişmez. Özel overlay dosya adı slotla çelişirse üretim engellenir, kullanıcı onaylarsa (`allow_mismatch`) devam eder.
- İsimlendirme **yeni algoritma yok**: final görseller ledger'a `artifact_kind='overlay'` + `overlay_cm` ile yazılır; mevcut `trendyol_codes` + `petek_measurement_codes` + `excel_row_sort_key` kullanılır (ortak model, farklı barkod/stok, 76→136 sıralı satır).
- Mod çakışması: `four_mockup` ile `petek_overlay_enabled` birlikte verilirse `DORT_MOCKUP_MOD_CAKISMASI` hatası; arayüzde biri seçilince diğeri kapanır.
- Eksik şablon: mağazada 4 benzersiz (SHA'sı farklı) PETEK şablonu yoksa `DORT_MOCKUP_SABLON_EKSIK`; tekrar veya başka mağaza şablonu kullanılmaz.
- Temiz render `…/06_Petek_Kapama/Overlaysızlar/4_Mockup/`, final `…/06_Petek_Kapama/4_Mockup/<ad>__W76.png`. Sabit klasör adı yeniden çalıştırmada ledger çakışmasını önler. Bulut/Excel yalnız final görselleri alır.
- Slotlar ve overlay tercihleri checkpoint `config`'ine yazılır (sabitlenir); devam ederken aynı seçim kullanılır.
- Geçmiş: mevcut `v4_ortak_uretim.sqlite3` içine yalnız ek `production_session` tablosu (mod, mağazalar, klasör, adet, süre, sn/görsel, durum). Mevcut tablolara dokunulmadı.

### Değişen dosyalar
- Yeni: `MERKEZ/URETIM_V4/four_mockup_v1.py`, `four_mockup_ui_v1.py`, `uretim_gecmisi_v1.py`, `tests/test_four_mockup_v1.py`
- Ek bağlantı: `unified_batch.py` (yedek: oturum geçici `/tmp`), `gui_v4.py`
- Ek düzeltme: `resume_last_stopped` checkpoint'teki `petek_overlay_batch_folder` anahtarını `run()`'a geçirip TypeError veriyordu; ayıklandı (eski overlay modunda da devam etmiyordu).

### Testler (izole, geçici klasör; canlı veriye yazmaz)
- ✅ 18 yeni test: etiket sağ alt/sıfır boşluk, etiket dışı piksel korunumu, overlay kapalı, özel overlay uyuşmazlığı, varsayılan `overlayNN` dosyası, eksik şablon, mod çakışması, 1×1×4, 1×3×12 (mağaza izolasyonu), 10×3×120, ortak model/farklı barkod+stok, Excel 76→136 sıra ve link-satır eşleşmesi, hatalı bulut linki (eksik satır Excel'e girmez), yarım kalan işten devam (biten işler tekrar render edilmedi), overlay değişince temiz yeniden render edilmez, bulut geri çağrısı yalnız 4 final, eski modun değişmemesi, geçmiş kaydı, arayüz duman testi.
- Eski testler: `tests/test_vnext_*`, `TESTLER/test_v45*`, `test_trendyol_final_excel`, `test_v485_multistore_design_excel` geçti. 4 test başarısız; **bu değişiklikten önceki kodla da aynı şekilde başarısız** (A/B ile doğrulandı): `test_v40_*` (2 — PETEK render 42 yerine 2) ve 2 arayüz testi (`petek_overlay_enabled` özniteliği sahte pencerede yok). Codex'in commit edilmemiş PETEK çalışmasıyla ilgili olabilir; takip listesinde.

### Ölçümler
- Eklenen final aşaması (etiket + PNG kodlama, 1200×1600): ortalama **0,18 sn/görsel** (≈ %2 ek yük; render ile çakışır çünkü render işçileri arka planda çalışır).
- Gerçek şablonla render süresi (≈10 sn/görsel) canlı veri kuralı nedeniyle **ölçülmedi**; dört mockup render maliyeti şablon başına doğal olarak vardır. Mevcut tasarım ön belleği (tasarım bir kez hazırlanır, 4 şablonda yeniden kullanılır), şablon ön belleği ve render işçileri aynen kullanılıyor.

### Gerçek şablon doğrulaması (2026-11-09, kopya durum; canlı veri değişmedi)
- Yöntem: canlı `PetekV3` ve `store_profiles` **kopyalandı** (`%TEMP%\e2e_four`), ortam değişkenleriyle tüm yazma geçici klasöre yönlendirildi; şablonlar/baskı yalnız okundu. Mağaza `adeno`, tasarım `Yatay_Tasarim001`. Öncesi/sonrası SHA+mtime: canlı DB'ler, `store_profiles`, `ayarlar.db` **değişmedi**.
- Slotlar: 76=Petek_Dolabi_037, 96=038, 116=041, 136=042 (4 benzersiz şablon, 4 benzersiz çıktı SHA).
- Doğruluk: 4 final 1200×1600; etiket dışı pikseller temiz render ile birebir aynı; etiket sağ altta (x+genişlik=1200, y+yükseklik=1600), SHA'lar ledger ile uyumlu; gözle kontrol edildi.
- Excel (sahte HTTPS linklerle): 4 satır, sıra 76→96→116→136, ortak model `Yatay_Tasarim001_ADN_Pet`, farklı barkod/stok, her link kendi ölçü satırında.
- Süre (aynı makine): standart 1 görsel render işleme ≈ 2,9 sn; 4 Mockup 4 görsel: render işleme toplamı ≈ 15 sn (4×≈3,7), 2 işçiyle duvar süresi ≈ 9 sn ⇒ ≈ 2,2 sn/final; final etiket aşaması toplam 0,63 sn. Sabit başlangıç ≈ 19–20 sn (`queue_prepare`: 364 PETEK şablonu keşfi) her çalıştırmada bir kez — Görev 2 adayı.
- Kaynak: CPU ort. ≈ %126 çekirdek (2 işçi), tepe RAM ≈ 1,3 GB (2 işçi + önbellek).
- Not: "≈10 sn/görsel" iddiası bu makinede ölçülmedi; ölçülen render işleme ≈ 3 sn/görsel, toplam çalıştırma süresinin çoğu sabit başlangıç.

### Kalan / takip
- ~~Gerçek bulut yüklemesi~~ **DOĞRULANDI (2026-11-09)**: kopya durum + gerçek sağlayıcı yolu (anahtarlar okunmadı/yazdırılmadı). 4 final üretimle birlikte akışta yüklendi (4 yüklendi, 0 hata, yükleme ≈ 6,2 sn/görsel, toplam üretim+yükleme ≈ 48 sn; üretim ≈ 28 sn). 4 benzersiz HTTPS URL, mağaza Excel'inde her link kendi ölçü satırında, ortak model, farklı barkod/stok, 76→136 sıra. Canlı veri SHA/mtime değişmedi. Test için hesaba 4 görsel yüklendi (ImgBB).
- Gözlem (Görev 4/6 adayı): ImageKit yerine **ImgBB'ye düşüldü** (mevcut failover sırası imagekit→imgbb→freeimage); ImageKit'in neden kullanılmadığı (kota/ayar/hata) incelenmedi, anahtarlara bakılmadı. ImgBB yolunda `remote_width/height/sha` boş kalıyor (mevcut davranış, yeni kodla ilgisiz).
- Gerçek (onaylı) şablonlarla uçtan uca üretim + gerçek bulut sağlayıcı doğrulaması (kullanıcı onayıyla, kopya veriyle).
- Takip: `test_v40_*` ve 2 arayüz testi önceden kırık (Görev 12'de ele alınacak).
- Yerleşik Excel şablonunda "Ölçü" sütunu yok → "Şablonda geçerli ölçü alanı yok" uyarısı üretiliyor (mevcut davranış; mağaza şablonlarında sütun varsa uyarı çıkmaz).

### Görev 1 — Canlı panel testi sonrası düzeltmeler (2026-11-09, OP-20261109-125933-39740425)
Kullanıcı 1 tasarım (harici klasör) × 3 mağaza ile denedi: overlay yansımadı, link oluşmadı, wudie'de 3 görsel çıktı. Kök nedenler (rapor/günlükle doğrulandı):
1. **Hiçbir final üretilmemişti** (yalnız temiz `Overlaysızlar` dosyaları vardı): harici tasarım adı (`pexels-…21601506`) kod uzunluk sınırını aştı (`PETEK_KOD_UZUNLUK`, barkod 49/40). Harici modda motor zaten `EXT-<işlem>` kimliği kullanır; final aşaması gerçek dosya adını kullandığı için 11/11 final reddedildi. → Final aşaması harici modda aynı `EXT-` kimliğini kullanır.
2. **Link oluşmadı**: finaller olmadığı için bulut kuyruğuna bir şey gitmedi; ayrıca "Üretimden sonra HTTPS Linke Çevir + Excel'e Yaz" kutusu varsayılan kapalıydı. → 4 Mockup modu işaretlenince bu kutu otomatik işaretlenir (başlangıçta yine yükleme onayı sorulur).
3. **Seçilen özel overlay'ler (ÜST 1200×300 şeritler)** ölçü etiketi gibi küçültülüp sağ alta konacaktı. → Özel overlay yerleşimi role göre: klasör/dosya adında `UST` → üstte tam boy, `ALT` → altta, diğer → sağ alt küçük etiket.
4. **wudie 3 görsel**: wudie 76 cm slotundaki şablon (`8fa31037…_r_mastergrid`) bu tasarım+ayarla (orta yarık + pembe temizlik + belirgin doğallık) PETEK motorunun mevcut `PETEK_GENIS_MAGENTA_SACAK_MASK_INCELE` kalite korumasına takıldı (aynı şablon varsayılan ayarlarla geçiyor). Eksik varyasyon başka şablonla doldurulmaz; artık sonuç özetinde ve günlükte "4 MOCKUP EKSİK FİNALLER" olarak listelenir.
- Doğrulama: aynı senaryo kopya durumda yeniden üretildi — varsayılan ayarlarla 12/12 final; kullanıcının ayarlarıyla 11 final + eksik wudie 76 listelendi. Yeni testler: ÜST/ALT yerleşim, harici mod uzun ad, eksik slot raporu (toplam 21 test geçti). Canlı veri değişmedi.

### Görev 1 — Koruma incelemesi ve overlay havuzu (2026-11-09)
- **Koruma** (`PETEK_V3/petek_source_marker_fringe_vnext.py`, `PETEK_GENIS_MAGENTA_SACAK_MASK_INCELE`): yalnız "pembe temizlik" açıkken çalışır, tasarımdan bağımsızdır; kaynak fotoğraftaki magenta işaret pikselleri baskı alanı çevresinde `max(9000, %6,5 × baskı alanı)` pikseli aşarsa şablonu reddeder. 415 atanmış PETEK şablonundan yalnız `wudie 8fa31037…_r_mastergrid` eşiği aştı (768×1024 düşük çözünürlük, baskı alanı 167 bin px ⇒ eşik 10.884; aday 12.808 px = 1,18×; diğer şablonlar 0,28–0,51×). Ölçümde ayrıca `wudie Petek_Dolabi_242` farklı bir şablon kontrolünde (`PETEK_DIAGNOSTIC_PHYSICAL_VENT`) hata verdi. Koruma gevşetilmedi (magenta sızıntısı kabul edilmez kuralı).
- **Kalıcı önlem (kalite korumaları değişmeden):** `UnifiedV4Batch.template_health` üretimle aynı şablon-seviyesi korumaları (üretim maskesi, pembe sacak, gerçek yarık ölçümü) üretimden önce dener. Otomatik slot seçimi sağlıksız şablonu atlar (neden bildirilir), sabitlenmiş sağlıksız şablon render'dan önce engellenir, ön kontrol ekranı listeler. Kullanıcının ayarlarıyla gerçek veride 3 mağaza × 4 = 12/12 final, wudie 76 slotu otomatik sağlıklı şablonla.
- Sınır: tasarıma bağlı render hataları önceden bilinemez; bunlar "4 MOCKUP EKSİK FİNALLER" olarak listelenir, başka şablonla doldurulmaz.
- **Overlay havuzu:** ÜST/ALT yerleşimi geri alındı (yalnız sağ alt, sıfır boşluk; büyük dosya 50% genişliğe sığdırılır). Ölçü başına çok dosyalı havuz: `Overlay_Giydirme\olcu_etiketleri\<76CM|96CM|116CM|136CM>\*.png`; tasarım+mağaza+ölçü anahtarıyla sabit seçim (devam güvenli), yanlış ölçü adlı dosya engellenir. Eski overlay doğrulayıcısı bu klasörü görmez. 24 test geçti.

### Görev 1 — 12 hatalı üretim analizi (OP-20261109-143414-31033756, 2026-11-09)
- 12/12 hata `PETEK_PINK_CLEANUP_INCOMPLETE_REVIEW`, render aşamasında (4 Mockup final aşamasına gelinmedi). Tasarım: `pexels-fariborzart-8158752.jpg` (6000×4028, koyu kırmızı/mor tonlu). Kopya durumda yeniden üretildi: pembe temizlik açık 0/2, kapalı 2/2 ⇒ hata tasarım×pembe-temizlik kombinasyonu, şablon/mağaza değil.
- Ölçüm (adeno Petek_Dolabi_037): temizlik 402 sızıntı pikselini onardı, 259 piksel vent koridorunda "magenta" kaldı. 258'i üretim öncesi baskı referansında da magenta (tasarım koyu mor/kırmızı) ve aynı konumda kaynak şablon da magenta; çıktı referanstan farklı (4/258 aynı).
- Görsel kontrol (temizliksiz çıktı): slot kenarlarında ince mor/magenta çerçeve görünüyor ⇒ koruma gerçek bir kusuru yakalıyor; yalnız "yanlış alarm" denemez. Kalan pikseller TELEA ile onarılsa da komşu koyu mor tasarım rengine kopyalandığı için tekrar magenta eşiğine düşüyor (`_magenta_pixels` renk-sınıfı testi koyu mor tasarım tonlarını ayıramıyor).
- Koruma/eşikler DEĞİŞTİRİLMEDİ (magenta sızıntısı kabul edilmez). Karar bekliyor: onarımı iyileştirme (donör renk ile) / bu tasarımı pembe temizliksiz çalıştırma / atlama.
- **Çözüm (2026-11-09):** `PETEK_V3/final_cleanup_v495.py` → `_donor_fill`: vent koridorunda onarım sonrası hâlâ magenta sınıfında kalan pikseller, baskı içindeki en yakın sızıntısız tasarım pikseliyle (≤10 px) doldurulur (TELEA gibi komşu mor ortalaması yok). Eşikler/koruma kontrolleri değişmedi; donör yoksa piksel dokunulmaz ve koruma yine hata verir. Yedek: oturum `/tmp`. Kopya durumda aynı tasarım 4/4 final, slot kenarındaki mor çerçeve gözle kayboldu. Testler: 26 yeni/4 Mockup testi geçti; ilgili 7 mevcut test dosyasında 2 başarısız (`test_v499_bulk…`, `test_vnext_seven_category_scene_daylight…byte_identical`) değişiklikten ÖNCEKİ kodla da aynı şekilde başarısız (karşılaştırmalı doğrulandı).

## Görev 7 — Üretim kayıtları (YAPILDI 2026-11-13)

### Ne yapıldı (Graphite üst menüsü → "✓ Üretim Kayıtları")
- `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py`: salt okunur SQLite + checkpoint okuyucu; hiçbir ledger/bulut kaydına yazılmaz, silinmez veya karantinaya alınmaz.
- `MERKEZ/graphite_workbench_v500.py`: `reports` sekmesi gerçek operasyon merkezine bağlandı (`_set_records_layout`, `_ensure_records_workspace`); hata olursa sessiz kalmaz, ekranda hata paneli + durum çubuğu mesajı gösterir.
- Panel içeriği: Son 40 üretim oturumu; ayrı **Başarılı** / **Başarısız** sekmeleri (thumbnail, SKU, kategori, tarih); **Hata Nedenleri** kutusu (en sık 12, `_normalize_reason` ile gruplu); devam banner'ı (`COMPLETED`/`STOPPED`/`RUNNING`/`INTERRUPTED`/`CHECKPOINT_INVALID`); **Yarım Kalanı Devam Ettir** düğmesi (onaylı `resume_batch` akışına delege eder); **Kesinti Kurtarma Denetimi** ve **Sistem Sağlığı** düğmeleri; **Yenile**.
- Devam mekanizması: `v47_last_batch_resume.json` + `V4_ORTAK_FABRIKA.lock` PID denetimi (`crash_recovery._inspect_lock_file` ile salt okunur); `PENDING` satırsa banner uyarı verir. Yarım kalan tur durdurulmuşsa tek kod yoluyla `resume_batch` çağrılır.
- Tamamlanan görseller SHA-256 ile doğrulanır, yeniden üretilmez.
- Link ve Excel çıktılarına dokunulmadı.
- Canlı kapanıp açılınca durum `production_session` + `v4_ortak_uretim.sqlite3` + checkpoint dosyasından yeniden yüklenir; RUNNING/INTERRUPTED oturumlar localhost'ta çalışıp sonra kapanan uygulamada **"yarıda kalmış olabilir"** etiketiyle görünür.

### Doğrulama
- Yeni test seti `tests/test_uretim_kayitlari_v1.py` (11 test, izole tmp) + `test_graphite_workbench_contract.py` + kesinti→devam (STOPPED → resume, biten işler yeniden render edilmedi) + `test_graphite_panel_layout_contract.py` — hepsi PASS.
- Canlı durum (yalnız salt okunur): 13.456 RENDERED · 662 REVIEW_REQUIRED · 0 PENDING; son tur `OP-20261110-232338-8200B36B` COMPLETED (3540 deneme / 3244 başarılı); Excel/bağlantı dosyaları değişmedi.
- Canlı üretim başlatılmadı; canlı DB'ye yazılmadı.

### Kapsam dışı / takip
- ~70 kırık test dosyası olduğu gibi bırakıldı (örn. `test_p0_*`, `TESTLER/*` eski koda bağlı, canlı 8080, eksik legacy dosyaları); bunlar **Görev 12**'ye devredildi.
- Testlerdeki yerel `ayarlar.local.json` okunmasın diye `.gitignore`'a eklendi ve `tests/test_p0_regressions.py` bu dosyayı atlamaya ayarlandı.
- `MERKEZ/URETIM_V4/ui_table_v1.enhance_tree` içindeki `Treeview.takefocus` hatasına karşı panel `try/except AttributeError` kullandı; Codex tarafında ayrı düzeltme gerekebilir.

## Görev 12 — Kapsamlı sistem regresyon denetimi (EN KARARLISI BUDUR)

### Test envanteri (per-file watchdog, 150s/150ms)
```text
tests/epic3_six_template_real_renderer        1 failed
tests/factory_doctor                           1 failed, 3 passed
tests/full_inventory_manual_guard              1 failed, 2 passed
tests/lifecycle_reconciliation                 1 failed, 7 passed
tests/number_guard_v2                          4 failed, 34 passed
tests/p0_app_8080                               1 failed
tests/p0_independent_release_safety            2 failed, 5 passed
tests/p0_isolated_factory_render               1 failed
tests/p0_legacy_full_inventory_guards          8 failed, 1 passed
tests/p0_numbering_archive_stress              4 failed, 2 passed
tests/p0_regressions                            51 failed, 2 passed
tests/p0_release_transaction                    5 failed
tests/p0_review_endpoints                       6 failed, 6 passed
tests/p0_sqlite_migration_simulation           1 failed
tests/p1_p15_suite                              13 failed, 24 passed
tests/quality_power_tool                       3 errors
tests/runtime_infrastructure                    1 failed, 7 passed
tests/runtime_migration                         1 failed, 4 passed
tests/runtime_workspace_routing                2 failed, 3 passed
tests/t1_client                                4 failed, 4 passed
tests/user_tools                               1 failed, 10 passed
tests/v493_persistent_acceptance_and_fifteen   1 failed, 12 passed
tests/vnext_petek_belirgin_bat_fix             1 failed, 2 passed
tests/vnext_petek_optional_ab_straight         1 failed, 4 passed
tests/vnext_petek_wall_corner_graze            1 failed, 3 passed
tests/vnext_store_preflight_p0                 1 failed, 12 passed
TESTLER/codex_active_safety                    2 failed, 3 passed
TESTLER/emergency_release                       1 failed, 3 passed
TESTLER/final_audit_ui                          1 failed
TESTLER/v314_legacy_bridge                      6 failed
TESTLER/v314_tk_menu                            1 failed
TESTLER/v36_viewport_undo_lighting              1 failed, 5 passed
TESTLER/v41_private_git_and_guidance           1 failed, 4 passed
TESTLER/v42_final_audit_fixes                  2 failed, 4 passed
TESTLER/v42_group2_combined                     1 failed, 11 passed
TESTLER/v422_factory_doctor_guidance           1 failed, 4 passed
TESTLER/v44_group2_safe_tools                  1 failed, 11 passed
TESTLER/v46_package                            1 failed, 1 passed
TESTLER/v46_petek_folders_and_user_deleted     1 failed, 9 passed
TESTLER/v46_review_bulk_esrgan                 2 failed, 4 passed
TESTLER/v46_workspace_identity                 2 failed, 6 passed
TESTLER/v47_audit_integrity                    2 failed, 2 passed
TESTLER/v47_material_store_random              2 failed, 9 passed
TESTLER/v47_p1_p2_acceptance                   3 failed, 11 passed
TESTLER/v47_pause_stop_resume                  4 failed, 2 passed
TESTLER/v473_runtime_relocation                8 failed, 2 passed
TESTLER/v475_package_completeness              2 failed, 2 passed
TESTLER/v475_system_integrity                  1 failed, 7 passed
TESTLER/v476_review_port_petek_ui              1 failed, 5 passed
TESTLER/v477_petek_browser_integration         11 failed, 6 passed
TESTLER/v479_grouped_windows_acceptance         1 failed, 1 passed
TESTLER/v480_petek_workspace_tools             2 failed, 2 passed
TESTLER/v483_petek_grille_guard                2 failed, 4 passed
TESTLER/v484_petek_bulk_ops                    3 failed, 4 passed
TESTLER/v487_ham_designs                       1 failed, 13 passed
TESTLER/v488_home_readability                   2 failed, 1 passed
```

### Kurumsal kök neden
- Böylece bu testler üç kümede toplanır:
  1. **Eksik Legacy İzolasyonu** (CODEX_ACTIVE'de `99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/*.py` yerine künye/stub kodu bulunuyor)
     → `test_p0_*`, `test_p0_review_endpoints`, `test_lifecycle_reconciliation`, `test_number_guard_v2`, `test_epic3_six_template_real_renderer`, `test_quality_power_tool`, `test_p0_regressions` (2/53), `test_full_inventory_manual_guard`, `test_v314_legacy_bridge`
  2. **Canlı 8080 / 8999 portunun meşgul olması** (iş uygulaması veya Codex'in açık web sunucusu bu testleri çalıştırıyorsa bloke olur; bu testler sunucu kapalı olmak zorunda)
     → `test_p0_app_8080`, `test_p0_release_transaction`, `test_p0_sqlite_migration_simulation`, `test_p0_isolated_factory_render`, `test_v473_runtime_relocation`, `test_v476_review_port_petek_ui`, `test_v477_petek_browser_integration`, `test_v41_private_git_and_guidance`
  3. **Eksik canlı veri / masaüstü erişimi** (pytest hidden mode'da thumbnail/Tk, ekran yokluğu, eksik runtime DB)
     → `test_runtime_infrastructure`, `test_runtime_migration`, `test_runtime_workspace_routing`, `test_surface_mode_detection`, `test_v488_home_readability`, `test_v314_tk_menu`, `test_v314_legacy_bridge`, `test_user_tools`, `test_v493_persistent_acceptance_and_fifteen` ve yukarıdaki port/http testlerinin bir kısmı
- `docs/GOREV_TAKIP.md` Görev 1 eski kayıtları olan "ana panel testlerinden 4 kırık test (test_v40 vb.)" ifadesiyle çelişmez: bunlar Görev 12'ye devredilmemiştir ve bu denetim sırasında iki dosya `test_v40_unified_seven_category` ile `test_vnext_seven_category_scene_daylight_20261101` ve `test_v42_group2_combined` tamir edildi.

### Yetki ve süreç
- **Yetki sahibi: Codex** (2026-11-13 kullanıcı tarafından atandı).
- Değişen davranışın testi değiştirmeden sonuca ulaşmaması; büyük sonuç şüpheli testlerde **kırmızı → yeşil** yerine **rapor** tercih edilmesi önerilir.
- Codex `AGENTS.md` kapsamındaki çalışma kürelerini (`scripts/`, `SABLON_V2_MIMARI/`) kullanır; bana veya diğer ajanlara düşen: kapsamı git'e kaydetmek (`git status`); canlı `ayarlar.json`, `SABLON_DUZELTICI.py`, `99_SISTEM_MOTORLARI/` ve `%LOCALAPPDATA%\GorselMockup\**` dışı değişiklik yok.
- Başarısız kategori sınırları belli: (1) Eksik Legacy İzolasyonu, (2) Canlı port çakışması (8080/8999), (3) Eksik canlı veri/Tk ekranı. Bu üç sınıf dışındaki hatalar gerçek kod kusurudur; Codex kendi çalışma iznim dahilinde inceler.

## Harness GitHub senkronizasyonu (2026-11-15)

- Dal: `harness/github-sync-20261114` (public repo, orphan snapshot) · Snapshot: `430f360` (431 dosya, 93.585 ekleme) · Test sözleşme düzeltmesi: `c3da6db` · Takip issue: #86 (Refs #82, Relates #83)
- Kapsanmayanlar: maskeler (`PETEK_MASTER_REVISIONS/`), kullanıcı görselleri (`Kalite_Kontrol_Gorselleri/`, `REVIEW_ARTIFACTS/`), canlı DB/mağaza profilleri, `ayarlar.local.json`, SHA manifestleri, `scripts/` ve `tools/` (AGENTS.md dikkatli bölge), `requirements.txt` local pywebview değişikliği (onay bekliyor; public dala baseline sürüm gitti).
- Arayüz taşıma envanteri: `docs/ARAYUZ_TASIMA_ENVANTERI.md` — 816 madde (TAM 0 · KISMİ 76 · EKSİK 652 · TEST BEKLİYOR 88; BOZUK modüller bölümsel listelenir). Talimattaki "714" referansı diskte bulunamadı; sayı zorlanmadı, koddan üretildi.
- Test sonucu: tam suite bu ortamda %27'de askıda kaldı (8 dk sert timeout; bilinen port/GUI/legacy sınıflar); görünen 344 testten 260 geçti, 72 başarısız (hepsi belgelenmiş çevresel), 3 atlandı. Odaklı yeni-modül seti (28 dosya): 177 geçti / 1 başarısız; başarısız `TESTLER/test_v487_ham_designs.py::test_gui_and_watcher_wired_to_one_working_root` idi (eski literal assertion), yapısal garantiye yükseltildi → 14/14 geçti.
- Yerel durum: `epic/template-intelligence-v1` @ `cea4e8b` ve `main` @ `153b60d` dokunulmadı; eski `main` ile değiştirme yapılmadı; Codex'ın yerel çalışması korundu.