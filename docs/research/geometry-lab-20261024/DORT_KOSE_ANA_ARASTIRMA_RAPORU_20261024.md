# DÖRT KÖŞE VE BASKI YÜZEYİ — BİRLEŞİK ARAŞTIRMA ANA RAPORU
**Tarih:** 24 Ekim 2026  |  **Kapsam:** Görsel Üretim Merkezi V4.6 / EPIC-3 / yedi ürün kategorisi

**Durum:** Araştırma tamamlandı; bu belge *deney tasarımı*dır. Hiçbir model kullanıcı şablonlarında bilimsel olarak üstün veya üretim-kabulü almış ilan edilmedi. Bu belge canlı kaynak, orijinal yedek, APPROVED köşe veya SQLite değiştirmez.

## 0. KAYIP ÖNLEME / KAYNAK ZİNCİRİ
Bu ZIP içinde **üç orijinal uzun araştırma dosyası byte-for-byte korunmuştur** (Perplexity ilk ve ikinci rapor, Qwen ilk rapor). Diğer katkılar mevcut sohbetten ayrıntılı içerik özetleriyle işlenmiştir; ilk DeepSeek tam ham mesajı, Qwen PPI-OET, Ghosting önerisi, Gemini ve Copilot 20 madde bu oturumda bağımsız orijinal dosya olarak yüklenmediği için **tam kelimesi kelimesine arşiv oldukları iddia edilmez.** Envanter bunlardaki teknik fikirleri korur. Anlık dosyalar ve SHA değerleri KAYNAK_ENVANTERI.json içindedir.

### Araştırma kökenleri / katkı dökümü
- **DeepSeek (önceki tur):** YOLOv8/YOLO11 Pose, 4 keypoint, SAM2/3, Grounding DINO, GEM, PTN, AI+CV hibrit, veri kalibrasyonu. Anlatılan satranç tahtası %95 ve 192 görüntü/pose-loss iddiaları birincil kanıt olmadan kabul edilmez.
- **Fizik tabanlı Ghosting:** iki cam yüzeyinden kaymış yansıma, yerel korelasyon, ocak+tezgâh+davlumbaz öncülü, dörtgen optimizasyonu. Yansıma camın sınırında olmak zorunda değildir; cam dışında da çift yansıma oluşabilir.
- **Perplexity 1 (orijinal ekli):** RTMPose, veri etiket standardı `outer_surface`/`printable_surface`/`visible_surface`, SAM2.1, Grounding DINO, robust RANSAC kenar hassaslaştırma, risk-kapsam, lisan/Windows, Golden/holdout, imzalı kaynak ve onay koruma.
- **Qwen 1 (orijinal ekli):** RT-DETR özel keypoint varsayımı, MMPose HRNet, MobileSAM/FastSAM, Active Contours/subpixel. Verilen `HybridCornerDetector` kodu çalışır uygulama değil; model yükleyici, refine ve geometri işlevleri eksik.
- **Qwen 2 (sohbet):** PPI-OET; vanishing point, monocular normal/depth, düzlem-kesişim topolojisi ve subpixel optimizasyon. Monoküler normal kalınlık ölçmez, vanishing points fayansları kesin elemez, 3–5 mm kalınlık tek RGB fotoğrafta garanti değildir.
- **Perplexity 2 (orijinal ekli):** kimlik bilinen şablonu tekrar çözmeme, kaynağından geometri kurtarma, doğrulanmış geometrik aktarım/LightGlue/ECC, parça-kenar öğrenme, çok adaylı karar, az müdahaleli UI, kontrollü 3B üretim, maliyet odaklı strateji.
- **Gemini (sohbet):** YOLOv8 Pose/Seg, Albumentations, panel var/yok, özel eğitim; 500–1000 örnek/30–50 FPS/kesin çözüm iddiaları test edilmeden kabul edilmez. PETEK dörtgen değildir.
- **Copilot (sohbet):** 20 maddelik kapsamlı aile: keypoint R-CNN, segmentation Detectron2/MMDetection, SAM, text/OWLv2/Florence-2, klasik ve optik CV, 3B, DINOv2/CLIP, cascade/ranking, multi-image, active learning, kategori ve güvenlik, benchmark.
- **Asistanın bu rapora ilaveleri:** kaynak/metadata tabanlı karar ağacının önceliklendirilmesi; ORB/AKAZE hafif eşleme baseline; farklı tasarımlara karşı öğrenme tutarlılığı; tek kenar ve köşe bazında epistemik belirsizlik; conformal risk-control fizibilitesi; adversarial tile negatifler; controlled capture polarizasyon; 3B/ObjectID/depth/normal render-pass; onaylı print-mask üzerinden final baskı taşması ölçümü; araştırma ensembleden ONNX küçük worker distillation. Her birinin kaynak listesi ve durumu ayrı tutulur.

## 1. GERÇEK MEVCUT DURUM (GITHUB PR #52, 24 EKİM 2026)
- Repo: https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/52 ; dal: `feature/v46-safe-consolidation-20261024`; son bilinen commit `27449cd`. PR açık/draft; ZIP paketleme raporlandı ancak gerçek Windows kabulü tamamlanmadı.
- Rapor: **708 şablon**, **591 `template_profiles` satırı** (aktif insan APPROVED sayısı bilinmiyor). Gizli müşteri varlıkları PUBLIC GitHub’a aktarılmaz.
- GitHub sentetik 7 kategori geometri değerlendirmesinde **gerçek Golden sample 0**. Ocak Arkası sentetik 0/3; Cam Doğrama IoU ~0.358. Bunlar gerçek dünya başarısı değildir.
- Windows aday paket, resmi Real-ESRGAN, 4 cam kategori yansıma, PETEK ve Excel/HTTPS gerçek kabul testlerinden bağımsız olarak düşünülür. AI laboratuvarı V4.6 kabulünü bloke etmez.

## 2. ZORUNLU ÖNCELİK SIRASI — KÖŞE PROBLEMİNİ DOĞRU TANIMLA
1. **Kimlik:** Aynı onaylı kaynak mı? SHA ve `template_uid`, kaynak boyutları, EXIF ve sürüm eşleşiyorsa kilitli geometriyi kullan. Onaylı dörtgeni yeniden tahmin etme.
2. **Doğrulanmış türev:** Farklı dosyanın aynı şablonun crop/resize/JPEG türevi olduğu *geometrik kanıtla* gösterilir, homografi/similarity transform hesaplanır; panel değişimi olmuşsa aktarma yok.
3. **Kaynak metadata:** Kaynak PSD, mask, render receipt, homografi kaydı, eski JSON/SQLite veya 3D engine passes kullan. Bilinen geometriyi yeniden icat etme.
4. **Yeni sahne:** Model/klasik/optik/3B yöntemlerini önce bağımsız dene. Çok aday üzerinden `correct object + boundary support + printable fit + uncertainty` ile seç veya reddet.
5. **Kısmi görünürlük:** `visible` ile `inferred` corner farklıdır. Maske/occluder çıktılarını dörtgenle karıştırma.
6. **Ret veya en az müdahale:** Panel yok, bilgi yok, uyumsuz SHA veya düşük güven -> REVIEW_REQUIRED / NO_RELIABLE_DETECTION. Asla sessiz APPROVED atama.

## 3. TEKNOLOJİ ENVANTERİ: 94 KAYIT, 8 İŞ AİLESİ
**Not:** 94 kayıt, 94 farklı bağımsız eğitim modeli demek değildir. Model aileleri, algoritmik alt yollar, hipotezler, yardımcı katmanlar ve test/kalite altyapısı bilinçli olarak ayrı izlenir; aynı çözümün farklı adları tek deneyle temsil edilebilir.

### A. Mevcut geometri (9 kayıt)
| ID | Yöntem veya teknoloji | Köken | İşlev / deney şartı |
|---|---|---|---|
| ID01 | Kaynak SHA256 ile APPROVED profil tekrar kullanımı | Perplexity-2 / mevcut GitHub | Aynı kaynağı sıfır yeni tahminle çöz; **risk:** Kimlik + kaynak hash + insan onayı birlikte doğrulanmalı |
| ID02 | Piksel hash / tam görsel eşleme | Perplexity-2 | Farklı encoder ile aynı pikselleri bul; **risk:** EXIF yönü ve renk profili dikkate alınmalı |
| ID03 | Perceptual hash / çoklu şablon türev arama | Perplexity-2 / asistan ekleme | Aynı kaynağın JPEG/renk türevlerini adaylaştır; **risk:** Yakın hash asla tek başına geometri aktarımı yetkisi vermez |
| ID04 | LightGlue yerel özellik eşleştirme | Perplexity-2 | Onaylı şablon ile türevi arasında geometrik eşleşme; **risk:** Tekrarlı fayansların sahte eşleşmeleri reddedilmeli |
| ID05 | OpenCV ECC image registration | Perplexity-2 | Eşleşen görüntüleri hassas hizalama; **risk:** Başlangıç dönüşümüne ve fotometrik benzerliğe duyarlı |
| ID06 | ORB/AKAZE/SIFT + RANSAC geometri aktarımı | Asistan ekleme | Ağır model olmadan türev eşleme referans tabanı; **risk:** SIFT patent durumu yerel sürümle kontrol, sahne 3B değişmişse homografi geçersiz |
| ID07 | PSD/SmartObject/vector path/alpha mask geometri kurtarma | Perplexity-2 | Kaynak dosyadaki bilinen dört köşeleri geri al; **risk:** Her PSD/JPEG bu metadata bilgilerini içermez |
| ID08 | Render JSON/SQLite/homografi receipt kurtarma | Perplexity-2 / mevcut sistem | Kaybolmuş profil ve dönüşümleri doğrulanmış kaynaktan geri al; **risk:** Canlı DB salt okunur |
| ID09 | İşlem sırasında geometri provenance metadata kaydı | Perplexity-2 / asistan ekleme | Gelecekte görselden tekrar geometri aramayı önle; **risk:** Kaynak/şablon sürüm/hash ile bağlanmalı |

### B. Geleneksel CV (15 kayıt)
| ID | Yöntem veya teknoloji | Köken | İşlev / deney şartı |
|---|---|---|---|
| ID10 | Canny edge detection | Copilot / tümü | Kenar adaylarını üret; **risk:** Derzleri panel kenarı sanabilir |
| ID11 | Contour + approxPolyDP | Copilot / önceki sistem | Dörtgen adayları çıkar; **risk:** Perspektif ve örtülmede yanıltabilir |
| ID12 | Hough / probabilistic Hough | Copilot / tümü | Uzun ve kısa çizgi adayları; **risk:** Mutfak çizgileri güçlü yanlış pozitif |
| ID13 | LSD / EDLines / ELSD | Copilot / Qwen-PPI | Yerel doğru parçaları; **risk:** Fayans çizgileri de çıkar |
| ID14 | Adaptive Threshold / CLAHE / gamma | Copilot / Gemini / Qwen | Düşük kontrast sınır iyileştirme; **risk:** Haleleri ve gürültüyü artırabilir |
| ID15 | LAB/HSV/brightness color scoring | Copilot | Beyaz/siyah/desenli panel farklarını puanla; **risk:** Şeffaf camda renk ipucu yetmeyebilir |
| ID16 | Gaussian/Bilateral/texture suppression | Copilot / Qwen | Arka plan dokusunu bastır; **risk:** Gerçek ince cam kenarı da kaybolabilir |
| ID17 | Gabor/frequency periodicity suppression | Copilot / Ghosting | Tekrarlanan fayans desenlerini cezalandır; **risk:** Benzer periyodik cam iç desenini de bastırabilir |
| ID18 | Convex hull / mask smoothing | Copilot / Qwen | Maskeden sınır adayı; **risk:** Maskeden gerçek gizli dış köşe garanti edilmez |
| ID19 | Min-area rectangle / minimum area quad | Copilot | Maske üzerinden başlangıç geometri; **risk:** minAreaRect perspektif dörtgen yerine döndürülmüş dikdörtgen döndürür |
| ID20 | Active Contours / Snakes | Qwen-1 | Kenar yakınında yerel sınır takibi; **risk:** Fayans konturuna sapabilir |
| ID21 | RANSAC doğrular + robust TLS + kesişim | Perplexity-1 / Copilot | Kenar parçalarından gerçek dörtgeni hassaslaştır; **risk:** Zayıf sınırda doğru uyumu güvenilmez |
| ID22 | ROI/black-padding exclusion | Mevcut GitHub / Copilot | Kaynak dışı siyah alanı analiz dışında tut; **risk:** Görüntü içindeki siyah cam dışlanmamalı |
| ID23 | Edge strength/orientation + local structural change | Copilot / asistan ekleme | Gerçek panel sınırında tutarlı doku değişimi ölç; **risk:** Sahnedeki gölge ve fayans da değişim yaratır |
| ID92 | SciPy nonlinear constrained quad optimization | Ghosting / Qwen-PPI / Perplexity-1 | Köşelerin toplam kenar+maske+prior maliyetini en aza indir; **risk:** Yanlış kenar sinyalini optimizasyon kesinleştirebilir |

### C. Köşe modelleri (9 kayıt)
| ID | Yöntem veya teknoloji | Köken | İşlev / deney şartı |
|---|---|---|---|
| ID24 | Ultralytics YOLOv8/v11/YOLO26 Pose | DeepSeek / Gemini / Qwen / Copilot / Perplexity-1 | Dört semantik köşeyi doğrudan öğren; **risk:** AGPL/Enterprise ticari lisans incelemesi |
| ID25 | MMPose RTMPose | Perplexity-1 / Qwen / Copilot | Lisans alternatifi özel dört anahtar nokta modeli; **risk:** Kod Apache; veri/weights/bağımlılık ayrı |
| ID26 | MMPose HRNet | Qwen / Copilot | Yüksek çözünürlüklü keypoint heatmap; **risk:** RTX3060 üzerinde VRAM/süre ölçülmeli |
| ID27 | Keypoint R-CNN | Copilot | Alternatif ROI-temelli keypoint; **risk:** Dört köşe veri adaptasyonu gerekli |
| ID28 | RT-DETR + özel keypoint head | Qwen | Transformer detector sonrası dört nokta; **risk:** Standart RT-DETR hazır 4 köşe modeli değildir |
| ID29 | Özel köşe heatmap / doğrudan regresyon | DeepSeek / Copilot | Yüzeyin dört köşe olasılığını öğren; **risk:** Görünmeyen köşelerin belirsizliğini ayrıca belirt |
| ID30 | Boundary+keypoint multi-task learner | Perplexity-1 / asistan ekleme | Köşe ve dört kenardan ortak geometri öğren; **risk:** Veri etiketlemesi daha fazla |
| ID31 | Per-edge heatmap + junction graph | Perplexity-2 / asistan genişletme | Görünür kenar parçalarından köşe kesişimleri; **risk:** Dörtgen topolojisi sağlam kısıtlanmalı |
| ID90 | YOLOX-Pose veya YOLOX keypoint adaptasyonu | Gemini | Ultralytics dışı dört nokta öğrenme opsiyonu; **risk:** Standart YOLOX keypoint checkpoint varmış gibi varsayma, lisansı ve proje kodunu teyit et |

### D. Segmentasyon (12 kayıt)
| ID | Yöntem veya teknoloji | Köken | İşlev / deney şartı |
|---|---|---|---|
| ID32 | YOLO instance segmentation | Gemini / Copilot | Cam/baskı yüzeyi maskesi; **risk:** Lisans ve arka plan kaçışı |
| ID33 | Mask R-CNN | Copilot | Instance mask baseline; **risk:** Köşeler ayrıca fit edilmeli |
| ID34 | Detectron2 / MMDetection / MMSegmentation | Copilot / Perplexity-1 | Çeşitli segmentasyon modelleri karşılaştır; **risk:** Framework ile model farklıdır; tüm kombinasyonlar ayrı zorunlu değil |
| ID35 | SAM 2 / SAM 2.1 Hiera Tiny-Small | Perplexity-1 / Qwen / Gemini / Copilot | ROI/nokta ile panel maskesi; **risk:** Şeffaf cam maskesinde hatalar; Windows/WSL deney |
| ID36 | SAM 3 / SAM 3.1 | Perplexity-1 / Copilot | Prompt destekli maske karşılaştırması; **risk:** Model lisansı/erişimi/VRAM belirsiz |
| ID37 | MobileSAM | Qwen / Copilot | Hafif prompt segmentasyon; **risk:** Köşe değil maskeler |
| ID38 | FastSAM | Qwen / Copilot | Hızlı segmentasyon adayı; **risk:** Lisans + sıfır-shot davranışını doğrula |
| ID39 | Edge-aware SAM fine-tuning | Copilot | Sınır hassasiyeti iyileştirme; **risk:** Köşeler yine ayrı doğrulanmalı |
| ID40 | GEM Glass-Segmentor | DeepSeek / önceki asistan | Cam yüzeyi için özel maske; **risk:** Windows Detectron2/MaskDINO, checkpoint/lisans doğrula |
| ID41 | GlassWizard (ICCV2025) | Perplexity-1 / önceki asistan | Diffusion priors ile cam segmentasyonu; **risk:** Çıktı hâlâ maske, runtime maliyeti |
| ID42 | Trans10K-v2 data/segmentation baseline | Perplexity-1 | Şeffaf nesne üzerine ön eğitim veri; **risk:** Sınıf taksonomisi ocak paneli değil |
| ID43 | VGGT_GLASS (ACMMM2026) | Önceki asistan / web kontrol | 3B-geometri-temelli cam yüzeyi maskeleme; **risk:** Yeni araştırma; ağırlık/Windows ticari şartlar |

### E. Açık kelime nesnesi (7 kayıt)
| ID | Yöntem veya teknoloji | Köken | İşlev / deney şartı |
|---|---|---|---|
| ID44 | Grounding DINO | DeepSeek / Qwen / Gemini / Copilot / Perplexity-1 | Metinle ürün adayı bbox; **risk:** Bbox gerçek dörtgen değildir |
| ID45 | Grounded-SAM | Copilot / Perplexity-1 | Text bbox + mask; **risk:** Prompt/negatif/algılama yanlışları zincirlenebilir |
| ID46 | OWLv2 | Copilot | Açık sözcüklü panel aday kutuları; **risk:** İfade hassasiyetini test et |
| ID47 | Florence-2 | Copilot | İstemle bölge/nesne anlama; **risk:** Benchmark ve lisans şartları incelensin |
| ID48 | DINOv2 feature similarity | Copilot | Panel ROI aday sıralaması; **risk:** Özellikler baskı içeriğine aşırı bağlanabilir |
| ID49 | CLIP feature similarity | Copilot | Kategori/nesne adayı sıralama; **risk:** Tek başına kesin sınır sağlamaz |
| ID50 | Dedicated panel present/absent classifier | Copilot / Perplexity-1 | Panel yoksa yanlış dörtgen üretme; **risk:** Zor negatif çeşitliliği gerek |

### F. Fizik ve optik (12 kayıt)
| ID | Yöntem veya teknoloji | Köken | İşlev / deney şartı |
|---|---|---|---|
| ID51 | Ghosting shifted double-reflection | Bağımsız öneri | Cam yüzeyindeki çift yansıma ipuçları; **risk:** Her camda görünmez, cam için eşsiz imza değildir |
| ID52 | Phase correlation / NCC micro-windows | Ghosting / Qwen-PPI | Kaymış yansıma ve yerel eşleşme ölç; **risk:** Fayans tekrarları yanlış korelasyon üretebilir |
| ID53 | Reflection prior / Fresnel / glare | Ghosting / Copilot | Optik sınır olasılığı; **risk:** Yansıma konumu doğrudan fiziksel kenar değildir |
| ID54 | PPI-OET plane intersection + edge topology | Qwen bağımsız öneri | 3B/geometrik yapıdan dörtgen hipotezi; **risk:** Qwenin zorunluluk ve %99 iddiaları doğrulanmadı |
| ID55 | Depth Anything V2 Small | Qwen / önceki asistan | Görselden göreli derinlik öncülü; **risk:** Doğrudan surface normal yok; 3–5 mm cam kalınlığı güvenilir değil |
| ID56 | Omnidata normals | Qwen / önceki asistan | Tek görüntü normal yönleri; **risk:** Paralel panel/duvar aynı normal olabilir |
| ID57 | TransNormal transparent normal prediction | Önceki asistan | Şeffaf yüzey normal tahmini; **risk:** Alan uyumu ve kaynak doğrulama |
| ID58 | Vanishing point / Manhattan world | Qwen-PPI / Copilot | Sahne yönlerini yardımcı kısıtla; **risk:** Fayans aynı perspektife uyabilir, eleme garantisi yok |
| ID59 | Ocak-davlumbaz-tezgâh semantik konumu | Ghosting / Copilot | Panel adayını bağlama göre puanla; **risk:** Ürün her zaman tam ortalı / davlumbaz altında değil |
| ID60 | Controlled multi-photo/polarization/photo setup | Perplexity-2 / asistan ekleme | Çekim kontrollüyse cam kenarını belirginleştir; **risk:** Hazır internet/mockup fotoğraflarında uygulanamaz |
| ID61 | Controlled 3D render normal-depth-objectID passes | Perplexity-2 / asistan ekleme | Geometri belli yeni şablon üret; **risk:** Gerçekçilik/üretim maliyeti ayrı |
| ID94 | Photometric stereo multi-light controlled capture | Qwen-PPI / asistan düzeltme | Aynı sabit kamerada farklı ışıkla yüzey yönü ipucu; **risk:** Tek normal RGB fotoğraftan klasik photometric stereo yapılamaz |

### G. Kısmi örtülme (6 kayıt)
| ID | Yöntem veya teknoloji | Köken | İşlev / deney şartı |
|---|---|---|---|
| ID62 | Line extrapolation + RANSAC hidden corners | Copilot / Perplexity-1 | Görünür segmentlerden saklı köşe çıkar; **risk:** Üç nokta perspektif dördüncüyü tekil belirlemez |
| ID63 | Foreground occluder segmentation | Perplexity-1 / asistan ekleme | Tencere/kol/mobilya baskı üstüne taşınmasın; **risk:** Dört köşe ile görünür baskı maskesi farklı |
| ID64 | Visibility-aware keypoint head | Perplexity-1 / Copilot | Görünürlük ile tahmin belirsizliğini ayır; **risk:** Inferred ≠ measured |
| ID65 | PETEK curve/slot dense UV mapping | Copilot / asistan ekleme | Kavis/deliklere özel maske veya deformable warp; **risk:** PETEK tek dörtgen değildir |
| ID89 | PTN / perspective correction network iddiası | DeepSeek | Perspektif ve kayıp köşeyi tahmin eden özel ağ hipotezi; **risk:** Birincil yayın/çalışır açık repo kanıtlanmadan hazır teknoloji sayma |
| ID93 | Line-junction / wireframe neural representation | Asistan ekleme | Dört kenarı ve dört birleşim noktasını topolojik grafikte birlikte tahmin; **risk:** Hazır mimarinin bu kategoriye taşınması için etiket gerekir |

### H. Karar/QA (24 kayıt)
| ID | Yöntem veya teknoloji | Köken | İşlev / deney şartı |
|---|---|---|---|
| ID66 | Cascade / candidate ranking | Copilot / Perplexity-2 | En iyi fiziksel hipotezi seç veya reddet; **risk:** Model confidence karşılaştırılabilir değil |
| ID67 | Category/material-aware expert router | Kullanıcı / Copilot / asistan | Görsele göre en uygun motoru kullan; **risk:** Kapalı testte eğitilmemeli |
| ID68 | Isotonic/logistic calibration | Perplexity-1 | Başarı olasılığını gerçekle kalibre et; **risk:** Ayrı calibration split gerekli |
| ID69 | Conformal risk control / abstention | Asistan ekleme | Yanlış otomatik kabul riskini istatistiksel sınırla; **risk:** Varsayım/kalibrasyon ve örnek sayısı gerektirir |
| ID70 | Test-time augmentation inverse consistency | Perplexity-2 / asistan genişletme | Küçük görüntü dönüşümlerinde köşe kararlılığı; **risk:** Kararlılık doğru olduğunun tek başına kanıtı değil |
| ID71 | Uncertainty per-edge and per-corner | Perplexity-1 / asistan genişletme | Belirsiz kenar ve örtülmüş köşe raporu; **risk:** Tek global % confidence yeterli değil |
| ID72 | Hard negatives + active learning | Copilot / Qwen / Perplexity-1 | Fayans/dolap/pencere hatalarından eğitim; **risk:** Etiket ve test sızıntısı önlenmeli |
| ID73 | Error taxonomy + adaptive human nudge | Perplexity-2 | Bir tıklama/tek kenar düzeltme; **risk:** İnsan süresi ve güven ayrı ölçülecek |
| ID74 | Risk coverage curve + expected cost | Perplexity-2 | Yanlış kabul/müdahale dengesini seç; **risk:** %100 otomasyon hedef değil |
| ID75 | Synthetic Blender/domain randomization | Perplexity-2 / asistan ekleme | Bilinen köşelerle farklı cam malzeme/ışık üret; **risk:** Sentetik başarı gerçek performans demek değil |
| ID76 | Artwork invariance paired training | Perplexity-2 / asistan genişletme | Aynı panelde tasarım değişse geometri değişmesin; **risk:** Üretken düzenleme fiziksel paneli değiştirmişse eşlenemez |
| ID77 | Counterfactual tile adversarial test suite | Asistan ekleme | Aynı geometrili farklı fayans/dolap baskısı ile hata stress testi; **risk:** Gerçek test kümelerinin yerini tutmaz |
| ID78 | Photometric edge-vs-print-area observability | Asistan ekleme | Sınır ölçülebilir mi, belirsiz mi raporla; **risk:** Tekil fotoğrafta bilgi yoksa ölçüm icat edilmez |
| ID79 | Final render overprint pixel loss | Asistan ekleme | Dörtgen IoU yüksek olsa da baskı dışına taşmayı ölç; **risk:** Referans baskı maskesi/occluder gerekir |
| ID80 | Knowledge distillation ONNX deployment | Asistan ekleme | Araştırma çoklu ağır modelleri küçük Windows workerına indirgeme; **risk:** Lisans/ONNX/CUDA test şart |
| ID81 | Out-of-distribution and panel-absent abstain | Copilot / Perplexity-1 | Yeni sahne veya panelsiz görüntüde güvenli ret; **risk:** Güven skoru yalnız model softmax değil |
| ID82 | Multi-view video optical flow glass mask | Copilot / yeni akademik doğrulama | Video varsa cam tespiti ek ipucu; **risk:** Tek fotoğrafta çalışmaz |
| ID83 | Blind human label disagreement audit | Perplexity-1 / Perplexity-2 | İnsanlar aynı köşelerde anlaşabiliyor mu; **risk:** Referans gold ölçümün hata tabanı |
| ID84 | Box-to-region & controlled ROI human test | Perplexity-2 | Model nesneyi mi kenarı mı yanlış buluyor ayır; **risk:** Kullanıcı ROI referansını değerlendirmede sakla |
| ID85 | A/B single-model refiner ablation | Perplexity-1 / asistan | İyileştirme gerçek köşe hatasını düşürüyor mu; **risk:** Orijinal ham tahmin de ölç |
| ID86 | Golden group-wise split leakage controls | Perplexity-1 / Perplexity-2 | Aynı sahne farklı tasarımla train/teste girmesin; **risk:** SHA yanında sahne/template grup id |
| ID87 | Geometry-to-compositing provenance contract | Perplexity-1 / asistan | Outer/printable/visible yüzeyi ayrı sakla; **risk:** Yansıma ve maske ayrı |
| ID88 | Manual approved immutable write-protection | Tüm kaynaklar / GitHub | İnsan onaylı onarım/read-only deney; **risk:** Bağımsız DB düzeyi yetki/transaction ve checksum |
| ID91 | f-BRS interactive segmentation refinement | Perplexity-2 | Belirsiz yüzeyi tek tıklamalarla düzeltme; **risk:** Cam ve dört köşe başarısı garanti değil |

## 4. ASİSTANDAN AYRI EKLENEN HIPOTEZLERİN NET DENEY TANIMI
1. **Hafif image-registration baseline:** ORB/AKAZE (ve lisans kontrolünden sonra SIFT) + RANSAC; kaynak türevlerinde LightGlue olmadan ne kadarı kurtarılıyor? Aynı veri ve kabul şartlarıyla karşılaştır.
2. **Bilgi/yetersiz kanıt dedektörü:** Kenar-çevre patch gradyan, kesişim devamlılığı, ışık/gradyan değişimi ve panelin dışına destek haritaları. `UNOBSERVABLE_BOUNDARY` gerekçe kodu.
3. **Çift hedef eğitim:** `printable_surface` dört köşesi ve 4 ayrı kenar güveni + occlusion görünürlük; farklı görevlerin hata analizi ayrı.
4. **Tasarım değişmezliği:** Aynı ana şablona çok farklı artwork bindirildiğinde model köşeleri değiştirmemeli. Poz/ürün şekli AI tarafından değiştirilmişse bu deney negatif sayılmamalı; grup ayrımı sabit.
5. **Çıkış hedefi olarak gerçek taşma:** Son `warpPerspective + print mask + occluder` sonucunun onaylı fiziksel baskı sınırı dışına çıkması piksel alanıyla ölçülür. Köşe IoU yüksek olup taşma üreten sistem kaybeder.
6. **Kontrollü kaynak üretimi:** Mümkünse Blender/benzeri sahnelerde panel UV köşesi, render mask, depth, normal, object ID, kamera pozu her sahneyle eşzamanlı saklanır. Optik deneye fiziksel cam kalınlığı ve Fresnel etkisi eklenir. Burada aynı anda elde edilen geometri insan anotasyonuna gerek bırakmaz; fotogerçekçilik ayrıca değerlendirilir.
7. **Conformal / kalibre ret:** Her modelin %confidence değeri farklıdır. Ayrı kalibrasyonda yanlış kabul riskine göre eşik, risk–coverage eğrisi ve değişen sahne dağılımında ret mekanizması test edilir; hiçbir matematiksel garanti veri dağılımına bakılmadan iddia edilmez.
8. **Hard negative generator:** Fayans, dolap/pencere kenarı, yanlış büyük niş, duvara benzer şeffaf cam vs üzerinden varyasyon ve karşı-örnek testleri; gerçek test verisi yerine geçmez.
9. **Geometri kontrollü fotoğraf üretimi:** Ürün panelinin nesne sınırı baskıdan önce kilitlenir; üretken model yalnız çevreyi değiştirir. Her yeni varyantta kaynak ve sınır değişimi kontrol edilir. Bu, mevcut eski zor fotoğrafları çözmez; yeni şablonlar için alternatif boru hattıdır.
10. **Küçük dağıtım işçisi:** Araştırma için ağır modeller kullanılabilir; kazanan fonksiyon ONNX Runtime/ayrı worker ile test edilir; aynı modelin CPU/GPU/VRAM ve Windows offline paketleme doğrulanır.

## 5. DENEY MİMARİSİ VE KABUL KAPILARI
**Faz 0 – Kilitle ve envanter:** Hedef 7 kategorinin sahne ve kaynak listesi; APPROVED sayımı; kaynak SHA eşleştirme. `template_profiles` sadece `is_active=1 AND manually_verified=1 AND review_status='APPROVED' AND source SHA match`. `outer_quad`, `surface_quad`, `visible mask`, `printable mask` birbiriyle karıştırılmaz. Ayrı READ-ONLY snapshot, kaynak dosyalara sıfır yazma.

**Faz 1 – Golden dataset:** Birbirinden bağımsız şablon/sahne ailesi grupları; negatif camsız mutfaklar; transparan, beyaz, siyah, desenli; az/çok kontrast; kısmi örtülme; fayans, renk, farklı kameralar; üç grup train/validation/**kilitli holdout**. Kendi verisinde aktif APPROVED azsa `INSUFFICIENT_GOLDEN` raporlanır. Önceden onaylı ama insan-hatalı örneklerin altın veri sanılması engellenir.

**Faz 2 – Mevcut sistem baseline:** Canlı kod snapshot aynı verilerde koşulmadan yeni teknolojilerin etkisi ölçülmez. Sentetik ve gerçek ayrı. Sadece salt okunur deney. En az köşe hatası, görsel-piksel/max/P90/P95, panel-relative hata, IoU, false positive, false negative, yanlış nesne, baskı taşma, kabul edilenlerde hata, hız, peak VRAM/RAM, cold/warm, fallback ve insan düzeltme süresi.

**Faz 3 – Ön eleme:** 94 adayın **hepsi envantere girer**, fakat her biri için applicability/licence/weights/runtime/data-fit/ROI target açıkça işaretlenir. Aynı teknolojik ailede eşdeğer seçeneklere 1 veya 2 temsilci seçilip kontrol edilir. Model yüklenemiyorsa `BLOCKED_DEPENDENCY/WEIGHTS/LICENSE/HARDWARE`; test edilmediyse `NOT_RUN`; hiçbirini sessiz silme.

**Faz 4 – Tekil gerçek testler:** Önce düşük maliyetli OpenCV/registration ve hazır segmentasyon/detector fizibilitesi. Eğitilebilir dört köşe modelleri için insan-onaylı etiket şartı, sabit veri bölmeleri; özel training kontrollü. Qwen Ghosting/PPI-OET kısmi fiziği önce sinyal var/yok fizibilitesinde test edilir.

**Faz 5 – Kazananların hibritleri:** Sınıf/doku/konum/cam görünürlüğüne göre farklı model çalıştır; ablation ON/OFF yap; refiner yanlış tahmini düzeltmeyebilir, eski sonuç da ölçülür. İki farklı quad ortalanmaz. En iyi aday yeterli kanıt sağlamıyorsa ret.

**Faz 6 – Adaptif router:** Bilinen SHA → doğrulanmış dönüşüm → proven source geometry → kategori uzmanları → ölçülü güven/ret. 7 kategori uzmanları birebir aynı değildir; PETEK ayrı maske/kavis/slot sözleşmesi.

**Faz 7 – Windows entegrasyonu:** Önce shadow mode öneri; mevcut APPROVED ve üretimi değiştirme; 100–1000 batch ayrı devam. Onay ve gerçek QA kapıları sağlandıktan sonra yalnız opsiyonel motor, hızlı rollback, manifests ve lisans denetimi.

### Deney sonucunun durum sözcükleri
`NOT_TESTED`, `FEASIBILITY_PASS`, `BENCHMARK_FAIL`, `BLOCKED_LICENSE`, `BLOCKED_WEIGHTS`, `BLOCKED_ENV`, `INSUFFICIENT_GOLDEN`, `READY_FOR_SHADOW`, `SHADOW_PASS`, `HUMAN_REVIEW_REQUIRED`, `PRODUCTION_ACCEPTED` (en son ve yalnız kanıtla).

## 6. İLK TESTLERDE SORULACAK 7 KARAR SORUSU
1. Ocak Arkası probleminin kaçında yanlış nesne ROI, kaçında doğru ROI yanlış köşe var?
2. Tüm tekrar gelen şablonların yüzde kaçı onaylı veya doğrulanabilir türev? AI iş yükünün gerçek hacmi ne?
3. Onaylı `surface_quad` fiziksel camın dışı mı, basılacak alan mı? Kategoriye göre sözleşme doğru mu?
4. Onaylı verinin kaç tanesi bağımsız gerçek sahne; kaç tanesi varyant/aynı fotoğraf?
5. Klasik kenar + kategori öncülü ve RTMPose gibi özel model, aynı kör testte ne kadar iyileşme sağlıyor?
6. Ghosting/normal/depth literatür fikri, gerçek cam fotoğraflarında doğru köşeye *ek kanıt* sağlıyor mu, yoksa gürültü mü?
7. Kullanıcı son kabulde 3:4 rendera bakınca baskı taşması ve optik yansıma artefaktı kalıyor mu?

## 7. KAYNAK DOĞRULAMALARI / LİSANS UYARILARI
- Depth Anything V2: https://github.com/DepthAnything/Depth-Anything-V2 — **Small Apache-2.0**, **Base/Large/Giant CC-BY-NC-4.0**. Model normal haritası üretmez; normal için ayrı model gerekir.
- GEM: https://github.com/isjinghao/GEM — gerçek cam segmentasyonu araştırması, Detectron2/MaskDINO karmaşıklığı; repo ve weights özel kontrol.
- GlassWizard ICCV 2025: https://openaccess.thecvf.com/content/ICCV2025/html/Li_GlassWizard_Harvesting_Diffusion_Priors_for_Glass_Surface_Detection_ICCV_2025_paper.html
- VGGT_GLASS 2026: https://github.com/YT3DVision/VGGT_GLASS — cam segmentasyonu için 3B geometri öncülü; RTX3060 üzerinde ölçülmemiş.
- LightGlue: https://github.com/cvg/LightGlue — kendi kodu/weights Apache-2.0, seçilen keypoint extractor ayrıca kontrol edilir.
- SAM2: https://github.com/facebookresearch/sam2 — kod/checkpoints Apache-2.0, Windows/CUDA derleme ve WSL maliyeti.
- Ultralytics: https://github.com/ultralytics/ultralytics — AGPL-3.0 veya Enterprise koşulları; kapalı ticari üretim için hukuk/uyum değerlendirmesi.
- Conformal risk control (ICLR 2024): https://research.google/pubs/conformal-risk-control/ — yöntemin varlığı doğrulandı, kullanıcının dört köşe problemine doğrudan garanti iddiası YOK.
- Transparent multi-view modeling: https://openaccess.thecvf.com/content/CVPR2024/html/Deng_Differentiable_Neural_Surface_Refinement_for_Modeling_Transparent_Objects_CVPR_2024_paper.html — çoklu görüntü verisi gerektirir; tek fotoğraf yerine geçmez.
- Video glass (AAAI 2026): https://ojs.aaai.org/index.php/AAAI/article/view/37700 — video/optical flow yaklaşımı; tek fotoğraflı pipeline’da optional.
- Tüm lisans/weights/bellek iddiaları model ve checkpoint bazında ayrıca doğrulanacaktır. Bu metin hukuki görüş değildir.

## 8. GÖZ ARDI EDİLMEYECEK KRİTİK ÇÜRÜTMELER
- Şeffaf veya siyah cam fotoğrafında güvenilir sınır kanıtı yoksa *gerçek ölçüm mümkün olmayabilir*; algoritma tahminini ölçüm diye satma.
- `Ghosting` yalnız cama özel değildir ve her panelde yoktur; fotoğraf üretiminde optik olarak hiç modellenmemiş olabilir.
- `PPI-OET` altında normal map camın 3–5 mm derinliğini tek RGB fotoğrafta kesin ölçmez; fayanslar da duvarla aynı VP’ye uyabilir.
- Özel eğitim için 500–1000 veri miktarı garanti değildir; `591 profile` sayısı `591 confirmed training sample` değildir.
- Keypoint modelinin yüksek confidence değeri doğru dört köşe olasılığı değildir; kalibrasyon ve yanıltıcı negatifler zorunlu.
- Pixel IoU 0.98 görünüp baskı kenardan taşabilir; en kötü köşe ve taşma metrikleri gerekir.
- Çok model kurmak yerine veri+ölçüt hazırlamak ilk gerçek kod aşamasıdır.
- Kamu repo PR veya GitHub Actions içine müşteri fotoğrafı/SQLite/orijinal şablon yükleme YASAK.

## 9. NE ZAMAN BİTTİ DİYECEĞİZ?
Her kategori için: (i) bağımsız gerçek Golden örnekleri; (ii) önceden tanımlı baskı toleransı; (iii) yanlış nesne ve panel-yok hataları; (iv) maliyet/VRAM/Windows; (v) source immutability 0 değişim; (vi) risk–coverage; (vii) ayrı gerçek görsel render kabulü. `NO_GO` gerekirse kabul edilecek; insan incelemesi kusur değil güvenlik katmanı.

## 10. KULLANICI İÇİN ÖNERİLEN SIRADAKİ İŞ
**İlk Copilot işi yalnız FAZ 0 + FAZ 1 + baseline olacaktır.** 94 araştırma kaydının kayıt ve teknik fizibilite kontrolünü yapabilir; fakat veriyi saymadan ağırlıkları indirip tüm modelleri kurmayacak. Sonra veri raporu ve baseline sonucu görülerek modellerin izolasyonlu deneyleri başlatılır. Final V4.6 ZIP/PR #52 ve #35 bağımsız kabul hattında kalır.