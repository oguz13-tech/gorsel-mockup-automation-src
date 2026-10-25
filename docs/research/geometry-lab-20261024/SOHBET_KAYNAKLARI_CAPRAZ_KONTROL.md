# SOHBETTEKİ DİĞER KAYNAKLAR — ÇAPRAZ KONTROL VE KAYIP ÖNLEME

Bu belge, kullanıcının sohbet içinde yazdığı veya yapıştırdığı fakat bu turda **ayrı ham dosya olarak bulunmayan** DeepSeek, Ghosting, Qwen-PPI-OET, Gemini ve Copilot katkılarını mümkün olduğunca ayrıntılı özetler. **Kelimesi kelimesine orijinal mesaj değildir.** Ana rapordaki 94 envanter kaydıyla beraber kullanılmalıdır.

## DeepSeek — birinci araştırma (önceki tur özeti)
- Ana öneri: kategoriye özel 4 keypoint YOLO pose; SAM2/3 ile maske; Grounding DINO ile ROI; AI tahmini + OpenCV kenar; GEM cam segmentasyonu; PTN adıyla perspektif düzeltme ağı.
- Bütçe önerisi: 300–500 çeşit onaylı örnek, tek modelle başlangıç ve ikili hibritlerin denenmesi.
- DeepSeek'in örneklem bazlı satranç tahtası ~%95 doğruluk, 192 görüntü, `pose loss` 12→24 gibi performans/veri ayrıntılarının birincil kaynağı gösterilmemişti; **kanıtlanmış sayı kabul edilmedi**.
- GEM için repo: https://github.com/isjinghao/GEM; bu cam yüzeyi segmentasyon tekniğidir, keypoint motoru değil.
- PTN: tam model/repo doğrulaması henüz yoktur; `KAYNAK_BELIRSIZ` diye saklanır; yok sayılmaz.
- Özgün görüntülerin DeepSeek'e yüklenmiş olabileceği ifade edildi, bu arşivde onun gördüğü fotoğraflar bağımsız şekilde doğrulanmadı.

## Ghosting — kullanıcı tarafından gönderilmiş bağımsız fizik teklifi
1. Yerel yüksek geçirgen filtre ve phase correlation/normalized cross-correlation ile camın ön/arka yüzey kaynaklı olası kaymış yansıma çiftlerini taramak.
2. Ocak, tezgâh, davlumbazı bağlamsal kısıt yaparak yüzey ROI/boyut öncülü üretmek.
3. Ghosting iç sinyali + sahne geometrisiyle dörtgenin optimum dört köşesini bulmak; güven yetersizse reddetmek.
- ÖNEMLİ: Yansıma camın ortasında olup fiziksel köşesinde olmayabilir. Ghosting cam için benzersiz veya her camda görünen bir imza değildir. Gerçek veya AI üretimi fotoğrafta bu sinyal yoksa onu icat etmeyiz.
- Görsel arayüzün katı 90° perspektif beklememesi gerekir. Camın dış köşeleri, baskı alanı ve görünür bölge ayrıca değerlendirilir.

## Qwen — PPI-OET ikinci teklif (sohbet metni)
1. **Perspective grid and plane estimation:** LSD/ELSD ile line segments, vanishing points, mutfak sahnesi yönlerinin tahmini.
2. **Normal/depth discontinuity:** Depth Anything V2 Small veya Omnidata ile monoküler sahne geometrisi ipuçları.
3. **Optical edge topology and intersection solver:** çizgi parçaları ve varsayılan panel/tezgâh konum öncülleriyle dörtgen adayları.
4. **Sub-pixel refinement:** 20×20 gibi mikro ROI ve faz korelasyonuyla yerel köşe düzeltmesi.
- **İddia düzeltmeleri:** iki VP tek başına 3B duvar/tezgâh düzlemi denklemine yetmez; tek RGB normal/depth map, 3–5 mm cam kalınlığını kesin ölçmez; fayans çizgileri de aynı vanishing-point yönünde olabilir; örtülü köşeler genel projektif durumda tekil ve milimetrik geri kazanılamaz; Depth Anything V2 normal değil depth haritası üretir; klasik photometric stereo farklı ışık altında birden fazla görüntü ister.
- Qwen'in ~1.2 GB, 15–20ms, 30–40ms toplam ve %99 fayans eleme tahminleri gerçek RTX3060 test sonuçları değildir.
- Özet: Bu hipotez deney dışı bırakılmaz ama `FIZIBILITE` etiketiyle, **doğru kenar sinyalini gerçekten üretiyor mu?** ölçülür.

## Gemini — öneri ve paylaştığı görsel durumları
- Ana tercih: YOLOv8 Pose özel dört nokta (TL, TR, BR, BL); YOLO instance segmentation, SAM2, GroundingDINO+SAM ve hibrit YOLO det+OpenCV karşılaştırması.
- Eğitim: Albumentations, kategoriye özgü çeşitlilik, panel olmayan zor negatifler, source-onaylı koordinatların YOLO formatına taşınması.
- İddia edilen 500–1000 örnek eğitim yeterliliği, RTX3060 30–50 görüntü/s ve yüksek başarı *gerçek test değil.* PETEK'in eğrileri/delikleri keypoint quad ile temsil edilmez.
- Gemini'nin **kendi analiz ettiği şeklinde anlattığı** dört örnek (görselleri bu araştırma dosyasıyla yeniden değerlendirmedik):
  - `image_51b1fc.png` — şeffaf cam / balıksırtı fayans; sol köşeler dolap/tezgâh sınırına kaymış iddiası.
  - `image_51b21a.png` — beyaz cam; tüm mutfak nişi seçilmiş iddiası.
  - `image_51b23b.png` — beyaz cam; geniş pencere/duvar boşluğu seçilmiş iddiası.
  - `image_51b27c.png` — şeffaf cam; gerçek dış sınıra karşı sahte dar dörtgen iddiası.
- Dosya adları araştırma referansıdır; ilgili piksel dosyaları bu araştırma ZIP'inde bulunmadığı için Gemini'nin görsel teşhisi bağımsız kanıt değildir.
- Gemini'nin sorduğu export konusu: mevcut kodda `template_profiles.surface_quad`, `outer_quad`, `source_asset_sha256`, `review_status='APPROVED'`, `manually_verified=1`, revizyon geçmişi bulunuyor; çalışır bir YOLO/COCO salt-okunur veri dışa aktarıcısı henüz doğrulanmış değil.

## Copilot — 20 başlığın eksiksiz kapsam denetimi
1. Keypoint: YOLO Pose, RTMPose, Keypoint R-CNN ve TL/TR/BR/BL.
2. Instance segmentation: YOLO Seg, Mask R-CNN, Detectron2, MMDetection, MMSeg.
3. SAM family: SAM2, SAM3/3.1, MobileSAM, FastSAM, edge-aware SAM.
4. Text-guided: Grounding DINO, Grounded-SAM, OWLv2, Florence-2 ve prompt alternatifi.
5. Hybrid AI+OpenCV ROI + Canny/LSD/Hough/kesişim.
6. Mask-to-quad: min area, Douglas–Peucker, convex hull, RANSAC 4 lines, spline/polygon.
7. Partial visibility completion: vanishing point/homography, kenar ve RANSAC.
8. Line/perspective: LSD/EDLines, Hough, RANSAC, Manhattan-world.
9. Color/light: LAB, HSV, glare, gradients, local contrast ve panel renkleri.
10. Reflection/tile suppression: texture, frequency, Gabor, reflection confidence.
11. Depth/normals/plane constraints.
12. Foundation feature similarity + prompt refinement: DINOv2, CLIP ve negatif SAM noktaları.
13. Dedicated Ocak Arkası detector ve panel var/yok hard-negative.
14. Cascade varlık → kimlik → geometri → kontrol → inceleme.
15. Candidate ranking: konum, alan, perspektif, edge/mask/doku destek ve reddetme.
16. Temporal/multiview: seri çekim-video izleme.
17. Active learning: belirsizlik seçimi, insan düzeltmesi, hard-negatives.
18. Category specialists: Wi-Fi, Cam Dikey/Yatay, Ahşap, Cam Doğrama, Ocak Arkası ve PETEK özel maske/kavis/delik.
19. Safe failure: DRAFT, REVIEW_REQUIRED, APPROVED korunumu.
20. Measured benchmark: IoU, mean/p95/max corner error, wrong object, absent-panel FP, misses, runtime, peak RTX3060 VRAM, synthetic versus real Golden ayrımı.

## Perplexity iki orijinal raporda bulunan ama unutulmaması gerekenler
- Aynı file -> SHA-checked human geometry; aynı şablonun dönüşümü -> verified registration; yeni sahne -> model.
- Kaynak JSON/PSD/SmartObject/SQLite geometry recovery; metadata kaydı.
- 4 farklı görev: nesne kimliği, fiziksel sınır, printable surface, compositing optics/occlusion.
- Confidence calibration, abstain, guided correction, ayrı hata sınıfları, çoklu candidates ve **"hiçbiri"** seçeneği.
- Her model için aynı gerçek Golden, aynı sahne aileleri, train/val/test/holdout; iki bağımsız insanın label disagreement ölçümü.
- PETEK'in quad'a sıkıştırılmaması; ayrı maske, üst/alt kavis, havalandırma/slot sayısı.

## Asistanın farklı veya güçlendirdiği hipotezler
- ORB/AKAZE hafif source registration referansı.
- Belirgin sınır olup olmadığını ölçen `UNOBSERVABLE_BOUNDARY` mekanizması.
- Bir modelin her köşesine ayrı belirsizlik; calibration ve olası conformal risk-control.
- Birden çok artwork'te aynı geometri özdeşliğini koruyan test/eğitim.
- Sentetik Blender render depth/normal/objectID/UV geometri ve known ground truth; gerçek testle asla karıştırılmamalı.
- Farklı fayans/dolap adversarial negatif testleri.
- Son baskının ürün/baskı maskesi dışına gerçek **taşma piksel alanı** (render-quality) metriği.
- Çoklu ağır model benchmark sonrası hafif ONNX/Windows worker; bu dağıtım stratejisi, model başarısından sonra değerlendirilecek.
- Çekim kontrol edilebiliyorsa döndürülebilir polarizasyon, çoklu ışık ve photometric stereo opsiyonu; tek fotoğrafa genellenmez.