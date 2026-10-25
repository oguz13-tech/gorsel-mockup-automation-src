# COPILOT — FAZ 3 ANA GÖREV: HAZIR MODELLE GERÇEK ÜRÜNÜ BUL, BASKI ALANINI AYIR, GEOMETRİYİ DOĞRULA
**Tarih:** 24 Ekim 2026. **Kullanıcı:** Ara iş yükü verme, güvenli biçimde kendi kendine yapabildiğin tüm işleri tamamla, gerçek sonuç sun.
**Proje:** `oguz13-tech/gorsel-mockup-automation-src`, `research/reference-first-object-geometry-20261024`.
**Bağlı geçmiş:** Issue #53 eski CV/94 envanter arşivi; Issue #54 referans-önce/ResNet18 ilk faz. **Bu görev yeni; tekrar çalıştırma listesi değil.**

## 0. SON DOĞRULANAN RAPOR — ÖNCE DEVAM ET, TEKRARLAMA
Issue #54 Copilot raporları (test dosyaları bu GitHub'dan doğrudan görülemedi):
- 170 gerçek yerel görüntü (96 cam: Cam Dikey 23 + Cam Yatay 23 + Cam Doğrama 23 + Ocak Arkası 27; 74 diğer: Wi-Fi 21 + Ahşap 23 + PETEK 30).
- Eski ilk SIFT/RANSAC T1=92 güçlü aday, T2=53 yalnız referans-sınıfı, T3=25 kanıt yok. **Bunlar gerçekte ürünün eşleştiğini veya köşe doğruluğunu ispatlamaz**; ürün üstü inlier / ROI / arka plan sızıntısı testini halen bekliyor.
- Torchvision ResNet18 ImageNet pretrained, **170/170 CPU embedding inference**, 512 boyut, 20.584 sn, `gallery/PHASE2_PRETRAINED.html` (170 kart, broken=0) raporlandı. Bu bir OBJECT DETECTOR/SEGMENTER DEĞİLDİR: nesnenin bbox/maske/köşesini sağlamaz, bu nedenle görev hedefi tamamlanmış değildir.
- OWLv2, Florence-2, Grounding DINO ve SAM gerçek inference sonucu **0**: 'yerelde checkpoint yok' diye BLOCKED kalmış. Araştırma dalında son Faz2 görev dosyası commit'i `a696d4990861fc70f535395497bfd6da1cebe96c`, yeni Copilot code commit'i henüz saptanmadı.
- Issue #53'ün kesilen eski `RESULTS.json`/`INDEX.html` galerisini **silmeden** kurtarmayı dene, geçersiz dosyaları başarı diye sunma.

## 1. EN ÖNEMLİ KURAL: ÜRÜNÜ TANIMAK ≠ DOĞRU ÜRÜN KONUMUNU BULMAK ≠ DÖRT KÖŞE BULMAK
`CATEGORY_CLASSIFICATION` = resmin hangi ürün sınıfından olduğu; klasör zaten bunu bilerek veriyor.
`PRODUCT_LOCALIZATION` = o **fiziksel ürünü fotoğrafta tam olarak gösteren** bbox/instance maskesi; ayrıca ürün yoksa `NO_TARGET`.
`PRINTABLE_SURFACE` = örneğin Wi-Fi kutusunda kutu gövdesi değil sağa kayan **MDF kapak**, ahşap çerçevede dış frame değil **iç yüzey**, PETEK'te havalandırma delikleri hariç gerçek panel.
`GEOMETRY` = onaylı kaynaktan aynı referansın dört köşelerini aktar veya **doğru ürün ROI** içindeki segmentasyon ve kenarlarla taslak dört köşe; PETEK dört köşe değildir.
`VERIFICATION` = yanlış nesne, sahte arka plan eşleşmesi, fotogerçek ürün değişimi, baskı taşması, belirsizlik ve otomatik reddetme.
- Bundan sonra **ResNet18 / CLIP / DINOv2 / whole-image embedding skorunu 'ürünü bulduk' diye raporlama**. Bunlar ancak aday referans sıralamada yardımcıdır; bağımsız görsel lokasyon kanıtı değildir.

## 2. GÜVENLİK + KESİNTİYE DAYANIKLI YEREL YÜRÜTME (P0)
- Sadece `C:\AI_WORK\GORSEL_REFERENCE_LAB_20261024` altında izolasyon (yeni `phase3` alt klasörü, bağımsız venv/weight cache); orijinal fotoğraflar / onaylı 4 köşeler / SQLite / OneDrive / V4.6 / PR #52 dokunulmaz. Onaylı SQL read-only, source SHA read-only. `snapshot_before_after.json` ile kanıtla.
- Eski Phase2 / Issue #53/#54 ledger, `MATCH_RESULTS.json`, `PHASE2_PRETRAINED_RESULTS.json`, `PHASE2_PRETRAINED.html`, yerel galeriler ve source SHA'ları **asla silme veya üzerine yıkıcı biçimde yazma**. Sahipliği bilinmeyen klasör ve çok kullanıcılı modellerin sanal ortamlarını değiştirme.
- Her `(image_sha, model_id, weights_sha, config_sha, task_type)` kayıt anahtarına göre append-only JSONL atomik checkpoint, resume, failed reason, status. Aynı işi yeniden çalıştırma. `RESUME_PHASE3.bat` hazırlanıp küçük kesinti testi yapılacak; `GALERI_AC.bat` tek tuş açılış sürecek. GPU tek tek yüklenir; 3060 VRAM dolunca daha küçük/CPU model. Hardware kaynak kullanımını günlüğe yaz.
- Yalnız açık lisans/erişim koşulları uygun **resmî hazır ağırlık** indirip lokal inference. Özel eğitim/fine-tuning YASAK. Ücretli API/third-party özel resim yüklemesi/yeni driver/WSL/görev silme/devreye alma onaysız YASAK. MODEL CHECKPOINT İNDİRME erişim engeli varsa gerçek HTTPS/HTTP/proxy hata kodu ve denenen resmî model/revision/weight linkini kaydet; yalnız "yerelde kurulu değildi" gerekçe değildir.
- GitHub public repoya özel fotoğraf, orijinal/baskılı gerçek görsel, thumbnail, özel SQLite, cache/weight, kullanıcı bilgisi veya path upload YASAK. Kaynak kodu, sentetik fixture, model kimlik/sürüm/weight SHA, anonim toplu sonuçlar/rapor serbest. PR #52 ve main değişmez.

## 3. GÖREV A — REFERANS VARYANTLARININ GERÇEK GÖRÜNTÜ KANITI
**İlk ana soru:** Gerçekte kategori başına kaç fiziksel ürün/sabit açı var? Kullanıcının 'en fazla ~10' fikrini otomatik gerçek analizle **doğrula veya reddet**, 10 gruba zorla bölme.
A1. SHA/EXIF/crop/resize/transforms; mevcut SIFT/ORB/RANSAC/ECC kanıtlarının **görüntüde ürüne ait alanında** bulunma şartı. Ürün ROI yoksa bunu `ROI_UNVERIFIED` say; arka planın SIFT inlier'larını ürün olarak kabul etme. Ürün maskesini doğrulamadan global image matching ve whole-image ResNet mesafesini T1 güçlü kanıt sayma.
A2. Her T1=92 adayı için: matching target/source ürün bbox/seg, inlier keypoint overlay (ürün üzeri vs background farklı renk), inlier ürün içi sayısı/yüzde, bounding hull spread, homografi geometric roundtrip, reprojection, double-reflection/fayans yanlış eşleşme, edge-support ve printable sınır uyuşması. T1'i `PRODUCT_VERIFIED`, `BACKGROUND_ONLY`, `AMBIGUOUS`, `FAILED` olarak yeniden değerlendir.
A3. T2=53 yeniden çizilmiş mi, yoksa sabit fiziksel geometri 2D transformu mu? Arka plan değişirken ürün aynı ve kenar korundu mu? Ref matching confidence ve pozitif/negatif açıklamalı çiftler. T3=25 üzerindeki 'ürün mevcut ama bulunamadı' ile 'ürün yok' ayrı.
A4. 7 kategori için `REFERENCE_VARIANTS_REPORT.md` ve `REFERENCE_GROUPS.json`: önerilen `variant_id`, canonical `ref_image_sha`, scene-family, angle/print mask farkları, görülen varyant sayısı (kanıtlı/tahmin/kararsız), örnek çiftlerin galeri linkleri. Alt kümelerden genelleme yapma. Geometri kaynak doğrulanmamışsa `DRAFT`.

## 4. GÖREV B — GERÇEKTEN OBJE BULAN HAZIR AI MODELİNİ ÇALIŞTIR (EN YÜKSEK ÖNCELİK)
*ResNet18 kullanılmış olması bu gereği karşılamaz.* Aşağıdaki ilk sıradan başlanır, resmî hazır checkpoint + lisans ve gerçek inference kanıtı gerekir.
B1. **OWLv2 image-guided object detection:** kendi aynı ürün ref crop'u → farklı arka planlı hedef görsel. Yalnız text değil, mümkünse gerçek image-guided route. En az başlangıçta her 7 kategoriden sahne/ışık/açı zorları (cam şeffaf/siyah/beyaz, Wi-Fi gövde/kapak, PETEK).
B2. **Florence-2 Base** text-based object detection / phrase grounding; promptları ref product ile uyuşan fiziksel tanımlardan üret. "glass table" cam yemek masasına sapabilir; wall glass print panel / stove backsplash etc kullan; prompt versiyonla.
B3. **Grounding DINO** open-vocabulary grounding; Tiny/Small gibi 3060'a uygun modelin hazır checkpoint'i + bbox overlay.
B4. **SAM 2.1 Tiny/Small** (gerçek source/weight) yalnız tespit motorundan gelen bbox ile prompted segmentation; tek başına otomatik object localization gibi sunma. Oracle/insan-doğru ROI ile otomatik ROI ayrı deney kimliği.
B5. Koşullar uygunsa **YOLOE visual prompting**, **PerSAM one-shot ref+mask**, **SAM3** ve **glass-specialist GEM/GlassWizard/L+GNet** pretrained. Yanlış model lisansı veya çok VRAM → gerçek blocker, diğerlerine geç.
B6. Hiçbir ağır model çalışamazsa önceliği `REFERENCE_VERIFIED + ürün maskeli patch registration`, klasik contour/CV ve kullanıcıya iş çıkarmadan fonskiyonel yerel galeriye kaydır; **ama yalnız generic classifier/embedding'i "AI detection achieved" diye raporlama**.

**Model catalog zorunlu alanları:** `name, architecture, source_url, checkpoint_url, license_code, license_weights, redistribution_limits, SHA256, hf_revision, pip_venv, download_tried, download_status, HTTP/error, import_load_success, inference_n, bbox_saved_n, mask_saved_n, categories, median_p95_ms, cpu_gpu, peak_vram_gb, blocked_reason, next_fallback`. İndirilmeyen model için başarı iddiası yok. Ağ erişimine ilişkin en küçük gerçek denemeyi ve logu sakla (ödeme/üçüncü taraf resim aktarımı yok). Resmî weights'lerin lisansını uydurma.

**İlk check:** En az bir **bbox üreten hazır nesne bulucu** ile her kategoriye ait temsilci örneklerde gerçek model çıktısının piksele çizilmiş görsellerini göster. Ardından uygun modelleri 96 cam + 74 diğer 170 görselin tamamında dene; GPU/memory takılırsa yöntem bazlı örnek sayısını şeffaf belirt. Tek başına 170 embedding çok hızlı olduğu için kabul şartını karşılamaz.

## 5. GÖREV C — DOĞRU ÜRÜN → GERÇEK BASKI ALANI → GEOMETRİ TRANSFERİ
C1. Her görüntüde `category_known` ile başla; `TARGET_PRESENT` ve `target_bbox` için ref-visual vs text grounding; doğru nesneyi bulmadan maske/quad çıkarma.
C2. `outer_object_mask`, `printable_surface_mask`, `visible_surface_mask`, `occluder_mask` ayrı sakla ve görsel doğrula; SAM2/segmenter ya da uygun klasik ROI mask. Geometrik köşeler yalnız ilgili doğru yüzeyin sınırlarında.
C3. **Reference geometry transfer decision tree:** same source+APPROVED+SHA → direct reuse; doğrulanmış 2D registration → homografi ile `TRANSFER_DRAFT`; AI-render yeniden çizim/T2 → *birebir quad transfer yok*, ROI prior + gerçek yeni sınır tespiti; başarısız/şeffaf görünmez → `REVIEW_REQUIRED`. SIFT inlier sayısı veya homografi reprojection tek başına onay değil.
C4. **Category-specific:** Cam Dikey ve Yatay gerçek cam sınırı vs duvar; Cam Doğrama tezgâhtaki cam levha/durum H yatay önceliği; Ocak Arkası panel vs dolap/fayans/tezgâh/davlumbaz; Wi-Fi sağa kayan **ince MDF kapak** vs beyaz kutu gövdesi; Ahşap Tablo dış çerçeve vs baskı iç alanı; PETEK özel kontur/kavis/havalandırma/slot (asla sırf dörtlü quad'a sıkıştırma).
C5. **ABLATION**: (1) ref registration-only, (2) image-guided detection-only, (3) text-guided detection-only, (4) oracle ROI→SAM2, (5) AUTO bbox→SAM2→RANSAC, (6) prior ref+AI+mask+edge. Aynı görüntülerde ayrı puan/kanıt.
C6. **Negatif test:** Arka planı aynı ama ürün değişmiş; aynı ürün ama arka plan farklı; panel hiç yok; ayna/fayans/cam pencere yanıltıcı; kötü render bozulmuş fiziksel ürün, kadraj dışı, kısmi örtü. `WRONG_OBJECT` ve `NO_RELIABLE_RESULT` açıkça göster; confidence/benzerlik yüzdelerini gerçek doğruluk sayma.
C7. 3:4 gerçek baskı görünümü; doğru kenar, mask bleed/taşma piksel, objenin önünde olması gereken nesne arkada kalmamalı; mahrem gerçek ürün görsellerini yalnız localde tut.

## 6. GÖREV D — ADİL GERÇEK SONUÇ, İNSAN QA ve ÇALIŞIR GALERİ
D1. `APPROVED + manually_verified + source SHA + identity` dışındaki koordinatlar `UNVERIFIED_GT`; legacy `ayarlar.json` kaynak doğrulama değildir. Golden olmayan örnekteIoU/köşe px 'accuracy PASS' verme. İki algoritmanın aynı sonucu vermesi ground truth değildir. Üretimde güvenli kabul yok; her şey `DRAFT`.
D2. 7 kategori ve scene/variant groups; yöntem başına gerçek `tested N`, doğru ürün GT varsa precision/recall, bbox/mask IoU, wrong object, false T1 accept, auto-vs-oracle delta, printable corner p50/p95/max, no-panel FP, REVEW_REQUIRED; bilinmiyorsa yalnız candidate count. En başarısız görüntüleri gizleme.
D3. 170/170 gerçek görüntü için yeni `gallery/PHASE3_INDEX.html` ve `GALERI_AC.bat` veya `PHASE3_GALERI_AC.bat`: orijinal/ref crop, keypoint ürün/arka plan overlay, objektif detection bbox, SAM mask, ref/transfer quad, GT onay durumu, final mockup, her yöntem önerisi, hata nedeni, en kötü örnekler ve kategori/angle/method filtresi.
D4. Galeri yerel browser `file://` salt-okunur olabilir; kullanıcı `DOĞRU/YANLIŞ/ŞÜPHELİ` geri bildirimini saklayacaksa tek-tık localhost lab-only backend + JSONL ile gerçek QA persistence test (safety). Kırık resim kontrolü 0, thumbnail/card sayısı, PETEK kontur preview ve 170 image present test logu. Eski phase1/2 HTML üzerinde yıkıcı işlem YOK.
D5. `RESUME_PHASE3.bat`, atomic checkpoint per image/model, index incremental, tests for interrupt/resume without wiping previous results, job limit/OOM. Tüm işlemler kullanıcıya ara görev vermeden, eşdeğer güvenli local testlerle ilerleyecek.

## 7. GÖREV E — GITHUB'DA GERÇEK KOD TESLİMİ ve SON KARAR
*Bu görevde sadece Issue #54 yorumu **yeterli değil***. `research/reference-first-object-geometry-20261024` dalına şu artefactları gerçek dosya olarak commit et:
- test runner/CLI modules, reference matcher with background-inlier rejection, bbox detector model adapters, mask/quad adapters, secure read-only data interface, checkpoint/resume, gallery writer, unit/integration tests, environment lock/license downloader inventory.
- `reports/PHASE3_SUMMARY.md`, `reports/PHASE3_MODEL_CATALOG.json`, `reports/REFERENCE_VARIANTS_AGGREGATE.json`, `reports/PHASE3_VALIDATION_MATRIX.json` **yalnız anonimize edilmiş** sonuçlar ve blockers, doğru kategori sayıları; örnek loglarda kişisel Windows yolları ve gerçek fotoğraf içerikleri yok.
- `docs/REPRODUCE_LOCAL_PHASE3.md`: iş kodunu özel kullanıcı fotoğrafları olmadan sentetik fixtures üzerinde bile sınayabilen test komutları; kullanıcı PC'sindeki 170 görüntü public repository'de bulunmadığından kamuya açık CI'nin bunları koşamadığı açıkça yazılacak.
- **Etkin source code diff** + test pass count + privacy scan + hashes. Gerçek uygulama modülleri yoksa 'bitti' denmeyecek. Public repo içinde Windows yerel kaynak fotoğrafları, SQLite, full path, pretrained gigabayt weights asla yok.
- Issue #54 içine son teslim linkleri veya bağlı yeni issue açıklaması: `PHASE3_STATUS=VERIFIED_LOCAL / PARTIAL_BLOCKED / INCOMPLETE`, kategoriye göre varyant sayıları, yeni bbox models `tested N`, T1 background leak düzeltmesi, HTML gallery local launcher path, eksik İnsan QA, PR #52 unchanged.

## GERÇEK BİTİŞ KRİTERLERİ (KAPATMA ÖNCESİ KONTROL)
- [ ] 170/170 input SHA + 7 kategori + eski outputs korunmuş; V4.6/PR #52 hiç değişmedi.
- [ ] Eski 92 T1 candidate ürün içi inlier & bbox koşuluyla tek tek yeniden doğrulandı, arka plan sahte eşleşmeleri ayıklandı.
- [ ] Her kategori için 'fiziksel ürün varyantı/angle' sayısı **kanıtlı / aday / bilinmiyor** ayrımıyla raporlandı; 10 limitini zorlamadı.
- [ ] En az bir **gerçek bbox/instance mask oluşturan pretrained object localization** modelini yerel Windows ortamında çalıştırıp örnek overlay, used weight SHA ve gerçek inference logu koydu, **veya** her model için spesifik teknik/lisans engelini kanıtladı. Generic embedding başarı yerine geçmedi.
- [ ] Doğru ROI / otomatik ROI ile maske ve geometri karşılaştırması, cam 96 + diğer 74; GT yoksa sayı uydurulmadı.
- [ ] 170 görüntü ve tüm kategori filtreleri görülen galeri, 0 broken source, durable review, restartable logs.
- [ ] Public GitHub'a gerçek kaynak kodu + testler + anonim çıktılar commit edildi; en az bir fiilî code commit; Issue #54 bağlantıları güncellendi.
- [ ] Eğitim ve production onayı yok; approved geometry/SQLite/V4.6 korunmuş.
**Yürütme:** Yerel VS Code Copilot ajanının bu metni açıp uygulaması gerekir; GitHub Issue tek başına kullanıcının bilgisayarında ajanı başlatamaz. Ara yetki/ücret/yeni driver gerektiren engelde bu kısmı atla, bağımsız işleri yap. Gerçekleşmediği halde 'saatlerce çalıştım', '170 / 170 bbox', 'MODEL_PASS' diye raporlama.
