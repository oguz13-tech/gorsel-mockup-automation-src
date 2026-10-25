# COPILOT / VS CODE — ISSUE #54 FAZ-2 UZUN OTONOM GERÇEK DENEME ve TAM TESLİMAT
**Kullanıcının açık yürütme emri:** "Sonraki aşamaya hemen geçir. Kapsamlı iş ver, uzun süre çalışsın; ben bilgisayardan ayrılıyorum. Bütün işlemleri Copilot yapsın, sadece nihai sonucu görmek istiyorum."  
**Tarih:** 2026-10-24  
**Tek kanonik görev:** https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/54  
**Bu metin statü güncellemesi, öneri veya TODO listesi değil; yerel Windows VS Code Copilot ajanına fiili uygulama/test/kanıt üretme emridir.**  
**Yürütme gereği:** İşler tamamlanmadan "bitti" deme; alt aşama sonunda checkpoint yaz, takılı kalırsan kaynak sorunu raporla ve güvenli bağımsız testlere devam et. Kullanıcının bilgisayarındaki gerçek verilere erişebilen YEREL ajan çalıştırır; GitHub'a yazılan görev tek başına VS Code ajanı başlatmaz.

## DEĞİŞMEZ SINIRLAR
1. Canlı V4.6 / PR #52 / ana repo çalışma kopyası, OneDrive orijinal havuzu, SQLite/template_profiles/APPROVED, manuel köşeler, asıl maskeler ve müşteri fotoğrafları **değiştirilemez**. Salt-okunur ve kopya üzerinden çalış; başlangıç/sonra checksum, gerçek DB için read-only SQLite URI. Kimlik SHA ve revizyon ile doğrula.
2. Sadece `C:\AI_WORK\GORSEL_REFERENCE_LAB_20261024` ve kendi alt kaynaklarını kullan, önceki çıktı üzerinde kayıp olmadan sürümle; gerekiyorsa `phase2` adında ayrı klasör aç. Bağımsız virtualenv, model cache, data manifest. V4.6'nın Python, Torch, CUDA, WSL, driver, Windows package veya sistem PATH ayarlarını değiştirme.
3. **Yeni model eğitmek / fine-tuning YASAK.** Yalnız uygun resmî hazır ağırlıklarla inference. Ücretli API, satın alma, ücretli cloud, yeni OS/driver/WSL kurma, lisansı belirsiz veri/özel görselin üçüncü tarafa gönderilmesi yok. Kamuya açık GitHub'a özel fotoğraf/SQLite/müşteri yolları/yerel image pixels ekleme yok.
4. İnsan onayı yokken yalnız DRAFT/REVIEW_REQUIRED. Legacy ayarlar.json `LEGACY_MANUAL_REFERENCE_UNVERIFIED`, gerçek Golden değildir. '92 T1' başarı yüzdesi değildir. Sıfır yanlış ve 170/170 başarı iddiası üretme.
5. **En değerli kullanıcı hipotezi:** Gerçek ürün kategori başına yaklaşık en fazla 10 temel açı/boyut varyantıyla AI tarafından arka plan değiştirilerek çoğaltılmış olabilir. Gerçek örneklerle kanıtla veya çürüt; kümeleri 10'a zorlamadan T1 piksel korundu / T2 aynı ürün ama AI yeniden çizdi / T3 farklı-belirsiz sınıfını raporla.
6. Kullanıcıya yeni komut, manuel kurulum, prompt yapıştırma, resim yükleme, bir sonraki faz onayı için ara adım çıkarma. Yalnız gerçek güvenlik/ücret/kişisel veri onayı gerekli ise o çalışmayı BLOCKED olarak işaretle ve diğerlerine devam et. Üretim merge/release/APPROVED değişikliği yapma.

## DURUM KABULÜ / YENİDEN İŞLEM YAPMAMA
- Issue #53 eski lab: 170 fotoğraf, 10 klasik yöntem ailesi, 1700 deney; eski uzun koşu kesildi ve eski `RESULTS.json`/`INDEX.html` eksik olabilir. `reports/EXPANDED_BENCHMARK_SUMMARY.md`, `METHOD_LEDGER_94.json` korunduğu raporlandı. **Sırf toparlamak için eski 1700 koşuyu baştan koşturma.**
- Issue #54 ilk referans aşaması: 170 yerel görüntü (Cam Dikey 23, Cam Yatay 23, Cam Doğrama 23, Ocak Arkası 27 = 96 cam; Wi-Fi 21, Ahşap 23, PETEK 30 = 74 diğer); `T1=92/T2=53/T3=25` SIFT/RANSAC adayları; henüz insan onaylı GT, doğrulanmış ürün-ROI inlier analizi ve model testleri yok.
- YEREL raporlanmış kanıtlar: `C:\AI_WORK\GORSEL_REFERENCE_LAB_20261024\reports\MATCH_RESULTS.json`, `REFERENCE_INVENTORY.json`, `EVALUATION_SUMMARY.md`, `MODEL_CATALOG_AND_LICENSES.json`, `OLD_RUN_CHECKPOINT.json`, `PRIVACY_AND_APPROVED_INTEGRITY.json` ve `gallery\INDEX.html` / `GALERI_AC.bat`. Her biri gerçek dosya mı, içerik sayısı doğru mu kontrol et. Sadece sağlam kaydı yeniden kullan; hiçbiri yoksa BLOCKED_FILE ve gerçek geri kazanım denemesi.
- GitHub araştırma dalı: `research/reference-first-object-geometry-20261024`. Kullanıcıya özel veri hariç gerçek kodun GitHub'da bulunması şimdiye kadar doğrulanmadı; **bu turda gerçek uygulama kodu ve otomatik testleri commit et**.

## FAZ 0 — 170 GÖRSELİN SAFETY CHECKPOINT ve TEKRAR BAŞLATILABİLİR JOB MOTORU
A. Giriş/çıkışları atomic temp→rename ile kaydet, satır bazlı append-only JSONL/SQLite lab-only, `run_id`, `dataset_sha`, `method_id`, `weights_sha`, `preprocess_version`, `config_sha`, `git_sha`, `prompt_version`, `source/target_hash`, `status`, `duration`, `peak_vram`, `error_stack` sakla.
B. Windows yeniden açıldığında veya ajan token/çalışma kesildiğinde `RESUME_PHASE2.bat` ile yalnız tamamlanmamış deneyi yeniden çalıştır. Yarım kalmış işlerden tüm galeriyi ve sonuçları silip sıfırdan yapma. Her deneyden sonra gerçek kaydı fsync/commit; galeri jeneratörü önce eski INDEX'i korur, tam yeni galeri doğrulandıktan sonra atomik değiştirir.
C. P0 validation: 170 kaynak SHA, exact source path local-only, 7 kategori sayıları, hard-links değil çalışma kopyası, okuma yetkileri, canlı V4.6 SHA/APPROVED karşılaştırması, mevcut kayıt korunma testi, OUT_OF_MEMORY/job kill testiyle resumability doğrula.
D. Çıkış: `CHECKPOINT_PHASE2.json`, `RUN_INDEX.json`, `RESUME_PHASE2.bat`, test edilen retry/partial-work durability logu. Hasarlı eski galeri varsa kayıtlı overlay'lardan kurtar, olmayanı hayal etme. Çalışan PC'yi uykuda/kapalıyken kendiliğinden çalışıyor gibi raporlama.

## FAZ 1 — ANA BULUŞUN GERÇEKLİK DENETİMİ: ÜRÜN AYNI MI, YOKSA ARKA PLAN?
1. Her kategoride temel referans/angle/variant adayları, crop konumları, ürünün dış ROI/maskesi, printable alanı ve kaynak/üretim metadata'sını çıkart. Metadata her görüntüde yoksa kanıt eksikliği olarak işaretle, gerçekte doğrulanmayan 10 sınıfı zorla oluşturma.
2. Aynı fotoğraf/türev ile yeniden çizilmiş fiziksel nesneyi ayır: canonical pixel hash after EXIF, exact coordinate transform, registered product-only crops, SSIM/LPIPS benzerlik (tek başına kanıt değil), SIFT/ORB/AKAZE/SuperPoint+LightGlue (mevcutsa resmî ağırlık), RANSAC homografi, ECC, normalized template matching, görüntü üzerinde kontur/maske/kenar geometrisi. Sonuçları **tam görüntü** ve **ürün ROI** üzerinde ayrı çalıştır.
3. **Yanlış T1 ayıklama en kritik deney:** RANSAC inlier keypoints'lerin kaç tanesi ürün ROI'sinde, kaçı fayans/arka planda? Dağılımı (en azından görüntü üzerinde inlier heatmap ve bbox), homografi transferiyle panel sınır uyumu, forward-backward consistency, reflected/perspective tilt, yüzey düzlemi, inlier'ların dört kenarı destekleme yüzdesi. Arka plan kolay eşleşiyorsa `BACKGROUND_MATCH_REJECT`, `UNKNOWN_PRODUCT`; eski T1'i kesin aktarım sayma.
4. Arka plan çeşitleri değiştirilince ürün matching robustness: solda aynı ürün/farklı arka plan, sağda benzer arka plan/farklı ürün, yanlış nesne/dolap/fayans, beyaz/siyah/şeffaf cam, tezgâh örtülmesi. Doğru ROI yoksa otomatik maskeyle pseudo ROI belirt, insan onayını taklit etme.
5. Sonuç per-kategori: `product_variant_count_estimated`, `verified_count`, `ambiguous_count`, unique scene families, güvenli transfer source IDs, T1/T2/T3 yeniden değerlendirmesi, eski-yeni sınıflandırma confusion matrix. Tahmini kategori başına <10/10/>10 hipotez sonucu. Kategoriye özel zorlukların kısa raporu.
6. Yalnız onaylı geometri kaynağı+doğrulanmış transfer birlikte var ise `VERIFIED_TRANSFER_CANDIDATE`; legacy/manual-unverified köşeleri yeni kaynak onayı yapma.

## FAZ 2 — HAZIR PRETRAINED MODELİN KURULUMU (EĞİTİM YOK; GERÇEK DENEME ŞART)
Eski raporda 'checkpoint yerelde yok' diye her şeyi BLOCKED yazmak artık kabul edilmiyor. Resmî izinli açık ağırlığı **izole lab cache'e indirip gerçekten çalıştır**. Bir model çalışmasa diğerine geç; mümkünse 170 fotoğrafa, değilse aşamalı tarama: her kategoride kolay-orta-zor+negatif temsil eden denge seti; güçlüleri ilk 96 cam, ardından 74 diğer üzerinde ölçeklendir.
Önce environment/hardware gerçek tespit: VRAM ve CUDA runtime, PyTorch driver compatibility, Python, torchaudio/torchvision uyumu, HF Transformers cache. Var olan core Python'a dokunma, paket çatışırsa model başına venv/isolated worker. Normal kullanıcı PC'sini aşırı zorlayacak paralel GPU modelleri açma; modelleri sırayla yükle boşalt. Büyük SAM3 Windows/VRAM uygun değilse BLOCKED_OOM/BLOCKED_ENV ve daha küçüklere devam.

**Aynı benchmark içinde model yolları:**
- **OWLv2** image-guided (ürün referans crop→hedef ROI) ve text-conditioned; model preflight, image processor prompt gerçek logu.
- **Florence-2 Base** ve gerekiyorsa Large (uyum varsa), phrase-grounding/object detection gerçek yanıt; uygun metin prompts.
- **Grounding DINO Tiny/Swint** resmî checkpoint, ürünün fiziksel tarifleri ve pozitif/negatif prompt kıyas.
- **YOLOE Small visual prompt** (hazır ağırlık varsa) ve text prompt; kullanım/lisans doğrulaması yapılmadan ticari release, dağıtım veya lisans kabulu verme.
- **SAM 2.1 Tiny/Small**, mevcut bbox prompts ile maske; 2 farklı ROI kaynağı: oracle/known ROI (yalnız test üst sınırı) ve modelden otomatik ROI. **SAM2 kendi başına referans ürünü otomatik seçiyor sanma.**
- **PerSAM** pretrained demo ve varsa görsel referans + mask; one-shot test.
- **SAM3** uygun erişim/VRAM/Windows koşulu doğrulanırsa (isteğe bağlı ağır), çalışamıyorsa gerekçe ve küçük alternatifi.
- **Cam uzmanları:** GEM, GlassWizard, L+GNet, başka resmî cam ağırlığı olan çalışan segmenter. Repo/model linki, lisans, gerçek ağırlık URL'si ve SHA, model çıktısı; erişimi/çıkarım kodu yoksa `BLOCKED_MODEL_NO_WEIGHTS`, eğitim gerekiyorsa `DEFERRED_TRAINING`, sahte checkpoint üretme.
- **Ensemble olmadan baseline**: CPU SIFT/AKAZE/ECC, OpenCV, genel segmentasyonu her modelden bağımsız kıyas.

Her model için:
`MODEL_ID`, `REPO_URL`, `WEIGHT_URL`, `LICENSE_CODE`, `LICENSE_WEIGHTS`, `download_attempted`, `download_succeeded`, `sha256`, `inference_command`, `cold_start_sec`, `median_and_p95_runtime`, `peak_vram`, `sample_count`, `success_count`, `wrong_object_count`, `fail_reason` ve kaydedilmiş örnek overlay dosyası. Kullanım şartları gereği indirmek yasaksa indirme. Hiç model kullanılabilir değilse nedenini model model gerçek hata ile açıkla, diğer fazlar bitir.

**Önemli ayrı sınav:** Ürünü yalnız adına göre aramak yerine, **aynı ürünün örnek fotoğrafını** hedefe vermek temel hipotez; image prompt olan/olmayan modeller karşılaştırılsın. Örn. model 'glass table' deyince yemek masası buluyorsa açıkça kaydet. İngilizce kategori prompts farklı fiziksel ifadeler ve negations, prompt metni/artifact sürümüyle kayda geçsin.

## FAZ 3 — DOĞRU ÜRÜNDEN BASKI YÜZEYİNE, SONRA GEOMETRİYE (ABLATION)
A. `REFERENCE_IDENTICAL` → locked existing coordinates, no AI; `REFERENCE_VERIFIED_REGISTRATION` → geometry transform and validation; `REFERENCE_SIMILAR_REPAINTED` → yalnız identity+rough ROI prior, panel quad **otomatik transfer yasak**; `REFERENCE_UNKNOWN` → open-vocabulary AI ROI candidates.
B. İki koşu: **AUTO_FULL_IMAGE** (tam otomatik obje bulucu) ve **ORACLE_PRODUCT_ROI** (yalnız referans çalışması, canlı başarı sayılmaz). Kategori/nesne tespiti, ROI, outer surface, printable surface, visible mask, occluder mask birbirinden ayrı artefact.
C. Denenecek pipeline varyantları: SIFT→transfer; OWLv2 image→SAM2→mask-to-quad; Florence→SAM2→edge refine; GroundingDINO→SAM2→RANSAC; YOLOE visual→mask; PerSAM→ROI/segmentation; glass segmenter→ROI→edge; SAM2 doğru ROI + SciPy; candidate ranking→reject; fizik/ghosting/depth yalnız zar zor çözülenler için, referansı olmayan üretim kabulü değil.
D. Cam Dikey/Yatay: glass outer vs printable surface ayrı; Cam Doğrama: tezgâh/doğrama camı ve masa kenarı ayır; Ocak Arkası: ocak/davlumbaz/gereçler üstünde basılacak gerçek panel, dolap/fayans yanlış obje negatif; Wi-Fi: gövde ve sağa kayan **ince MDF baskı kapağı** birbirinden ayrı, kapağın açık/kapalı durumu; Ahşap: dış frame vs iç print rect; PETEK: kontur + kavis + hava deliği/vent + slot maske, minAreaRect quad zorlaması yok.
E. 3:4 mockup final render: panel dışına taşan baskı, fiziksel nesneye sığmayan artwork, perspektif uçlarına taşan/kapatan overlay, ön nesne üstüne boya, kenar boşlukları; edge/corner IoU yanında **final ticari mockup kalitesi** ölç. Sadece güvenli **kopya** output, üretimdeki Excel/HTTPS işine karışma.
F. Her pipeline için tekil bileşeni çıkarıp hatanın artıp azaldığını göster (ablation); false positive object, false transfer ve mask taşması asla gizlenmez. Güvensiz motor confidence'ı doğruluk zannetme; `REVIEW_REQUIRED/NO_TARGET` üret. Otomatik APPROVED yok.

## FAZ 4 — REFERANS ANNOTASYON / ADİL DEĞERLENDİRME
- Yerel onaylı gerçek referans aramasını kaynak hash+identity+APPROVED+manually_verified+orientation şartı ile salt-okunur tekrar dene. Yoksa `UNKNOWN_GT`; insan 4 köşesi uydurma. Kendi üretilen iki tahminin birbiriyle örtüşmesi gerçek Ground Truth değildir. Legacy JSON/ayarlar içindeki koordinatlar `UNVERIFIED` olarak ayrı gösterilir.
- Tüm 170 resmi galeriye koy; gerçek metrikleri **yalnız gerçek GT olan alt kümede** hesapla. Kategori ve ürün/scene-family bazlı split ve leakage kontrolü; aynı ana ürünün arka plan kopyaları train/validation/holdout'a farklı bağımsız görüntülermiş gibi dağıtılmasın.
- Yöntemlerin ürün localization precision/recall, wrong-object, false transfer accepted, missed panel, no-panel false accept, mask IoU, four corner mean/p50/p95/max (gerçek GT varsa), review coverage, final render overflow, peak GPU + CPU wall time, repeatability and abstention. T1 thresholds için false acceptance penalty. Benzer çekim aileleri üzerinde sahte yüksek skor üretme.
- Kısmi etiket: altın yoksa görsel kalite için kullanıcı inceleme beklerken kendi başına yöntem seçiminde *weak-proxy* ve güven kalibrasyonunu sadece tanısal tut; gerçek başarı PASS verme.
- Hatalı önceki sonuçları gizleme: T1 ürün-dışı RANSAC keypoint, yanlış cam, görünmeyen geometri, tasarım bozulması ve PETEK yanlış quad örnekleri `WORST_CASES` galerisi.

## FAZ 5 — YEREL İNSAN GÖRSEL QA GALERİSİ ve OTOMATİK TESLİM
A. En önemli hedef `C:\AI_WORK\GORSEL_REFERENCE_LAB_20261024\gallery\INDEX.html`, `GALERI_AC.bat`: 7 kategori filtre, unique product variant / reference family filtre, gerçek angle grubu sayısı, T1/T2/T3, model adı ve sonuç, otomatik vs oracle ROI, doğru/belirsiz/yanlış objeler, yansıma vs dolap/fayans, en kötü örnekler.
B. Her resim: orijinal; reference crop; refs/cluster; inlier ürün üstü renk işaretleme vs background; tüm obje aday bbox; printable mask; GT varsa köşeler; predicted corners + yakın plan; final 3:4 mockup; diğer yöntem karşılaştırma overlay; sınıflandırma ve karar nedeni; GT yoksa `GT YOK` belirgin. PETEK için slot/kavis/vent maskesi.
C. Kullanıcı `DOĞRU / YANLIŞ / ŞÜPHELİ` + açıklama işaretleyebilsin; **offline file:// HTML uygulamalarının tarayıcı güvenlik limiti nedeniyle kalıcı JSON yazma ayrı başlatıcı/localhost API gerektiriyorsa `GALERI_AC.bat` tek tık localhost başlatır, kendi küçük lab-only JSONL store'una kaydeder**. Kalıcı veri yazımını gerçekte test et. Offline internet gerektirmez; normal açılan INDEX de salt-okunur galeri sunar.
D. **Resumable gallery**: method/image composite güncellendiğinde incremental küçük HTML/JSON index; parça sonuçları üzerine yıkıcı `rmtree` yok. 170 fotoğraf (dosyalar özel local), açılan thumbnail/link kontrol 0 broken, 7 kategori hepsi, Windows test logu, slow gallery için pagination/lazy loading.
E. Bir `CALISMA_TAMAMLANDI.md` hazırlayarak tek ekranda kullanıcıya anlat: görüntüler gerçek mi, kaç referans geometrisi var, kaç tane gerçekten otomatik eşleşiyor, hangi model gerçekten indirildi/test edildi, GPU süreleri, mask/köşe başarısı ve hangi sıradaki model/hata çözülmedi; GALERI_AC.bat tam dosya yolu. Ek kullanıcı sorusu yerine çıktıyı sonlandır.

## FAZ 6 — TEST / REPRODUCIBILITY / GITHUB TESLİM
- Dosya okuma kodu ve tamamlanmış test runners, model adapters (gizli checkpoint içermez), requirements LOCK/ENV versions, stable image/test config, manifest ve anti-data-leak scan, integration tests & unit tests yeni research branch'e commit et. İlgili PR #52, canlı DB ve main **değişmeden** kalmalı. Birim testleri: EXIF/orientation, exact hashes, RANSAC background false positive, four-point order, PETEK quad prohibited, zero-GT no false PASS, no-target reject, interrupted atomic-gallery recovery, save user QA.
- Gizli 170 görselin piksel verisi veya thumbnail'ı, müşteri bilgisi, SQLite, path'ten private kullanıcı adı, token, model cache, gigabyte weights public GitHub'da YOK. PUBLIC yalnız yöntem kodu, sahte/sentetik anonim unit-test fixtures, model weight download instructions, anonim metrik raporu, anonim test ledger; secret scan + diff listesi.
- Issue #54'e zaman damgalı ara **somut** iş checkpoint'leri: faz0 data proof, faz1 category variant count, faz2 model install/inference matrix, faz3 winning/no-win ablation, faz4 real GT vs proxy, faz5 170 image gallery, faz6 code commit+hash; yalnız metin yorumlarını kanıt yerine koyma. En az bir **gerçek yeni kaynak kodu commit** ve dosya listesi olmadan "teslim" deme.
- Nihai kapanış: `DELIVERY_STATUS.json`: `DONE_VERIFIED` / `PARTIAL_BLOCKED` / `FAILED`; `BLOCKED` alt işleri, gerçek işlenen adet, 7 kategori, 170/170 galeri durumları, koruma checksum, GitHub links, kullanıcıya tek ekran açma. Bir model takılmışsa gereksiz günler harcama, diğer modelleri otomatik sürdür; aynı üç kez teknik hata sonrası `BLOCKED` olarak kaydet.
- **Ajan uzun çalışacak:** her yöntem ve resimden sonra kalıcı ara kayıt; iş listesini bağımlılığa göre sırala, disk/GPU alanı yetmiyorsa güvenli kalite kaybı olmayan smaller model fallback; kontrol edilmeyen ödemeli API/driver kurulum yok. Gece uzun koşu yapılabilir ancak bilgisayar açık ve uyanık değilse süreç ilerlemez; bunu gizleme. İş sonunda kullanıcıya sadece gerçek sonuçları raporla.

## SON KABUL MATRİSİ
[ ] 170 dataset source SHA+7 kategori bütünlük; V4.6 unchanged.
[ ] Geçmiş #53/#54 raporları/safe evidence korundu; eski 92/53/25 ürün üstü RANSAC sonrası yeniden değerlendirildi.
[ ] Her kategoride GERÇEK tahmini/kanıtlı product-variant count, T1/T2/T3, background leakage false matches, örnek crop overlay.
[ ] En az bir **gerçek pretrained object localization yöntemi** indirilmiş ve inference çalışmış, veya model bazlı gerçek logla neden hiçbiri çalışamadı belgelenmiş; 'yerelde ağırlık yok' tek başına mazeret değil.
[ ] Doğru ROI→mask→geometri ile en az iki uygulanabilir hibrit model karşılaştırması; PETEK ayrı.
[ ] 96 cam + 74 diğer sonuçları, metric GT distinction, false accept, final mockups.
[ ] 170/170 görsel, 0 broken references, 7-category/filterable Windows HTML galeri, tek tık launcher + durable user QA.
[ ] Tests/restore/restart/ablation logs and privacy scan; report and actual code commits; Issue #54 updated.
[ ] No custom model training; no automatic APPROVED, merge/deploy, no touch to PR #52/production.

**BAŞLATMA CÜMLESİ (yerel Copilot VS Code):** "Issue #54'teki `COPILOT_PHASE2_UZUN_OTONOM_GERCEK_TESTLER.md` belgesini kanonik emir olarak oku ve faz0→6'yı gerçek kodlama/testle başlat; tüm ara checkpoint'leri koruyarak mümkün olan işleri tek oturumda devam ettir, insandan görev isteme; iş tamamen yapılana kadar durum raporuyla yetinme."
