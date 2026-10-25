# 94 yöntem için kanıta dayalı teknik eleme — 25 Ekim 2026

**KAPSAM:** Orijinal ID01–ID94 envanterindeki her kayıt okundu. Bu bir **mimari/öncelik kararıdır**; 94 yöntemin 94'ü laboratuvarda test edildi iddiası değildir. Envanter 8 kategori içerir; sadece 10 klasik yöntem ailesi eskiden 170 fotoğraf/1.700 deney kaydı olarak çalıştırıldı; sonrasında OWLv2 metin aday kutuları, Grounding DINO ve SAM2 merkez nokta maskelerinden 170'er görsel raporlandı. Hiçbir mevcut rapor 170 görüntüde gerçek APPROVED kaynak-SHA GT ile global doğru ürün/printable-surface accuracy sağlamıyor. Araştırma sadece PR #55 research dalında; PR #52 production kodu değiştirilmedi.

## BUGÜNKÜ TEK PRATİK KARAR
1. **APPROVED+SHA eşleşiyorsa AI sıfır:** kayıtlı quad / PETEK eğri-slot mask / occlusion / render bilgisi doğrudan yeniden kullanılır. Photoshop Smart Object gibi ürün yerleşimi bir kez ayarlanıp saklanır.
2. **Türevi sahici aynı ürün geometrisiyse:** product-ROI içi SIFT/ORB+RANSAC/homografi, inlier dağılımı ve fotoğraf türev kimliğiyle *sadece doğrulanmış* quad transfer; yeniden çizilmiş fiziksel ürün olduğunda asla otomatik transfer yok.
3. **Yeni ve onaysızsa:** gerekli olduğunda **OWLv2 image-guided (referanslı nesne bbox)** → **mevcut SAM2.1 bbox/tık maskesi** → category-aware printable surface / kısa çizgi hassaslaştırma / occlusion → DRAFT → tek tık veya 4-köşe insan onayı → SHA bağlı immutable kayıt. OWLv2 modelin 'query_images' moduyla gerçek inference daha önce doğrulanmadı. Tek tık/box ile doğrudan SAM2 de opsiyon; merkez nokta 170 koşusuyla karıştırma.
4. **PETEK ayrı:** kavis/slot/vent maske; quad'a zorlama. Yüksek belirsizlik → kısa insan düzeltmesi, otomatik APPROVED yok.
5. **Hedef test:** 7 kategori 1-3 zor gerçek foto + 7 mevcut APPROVED render; tüketici onayı öncesi onlarca yeni ağır model/170×10 referans kıyası yok. Sıfır GT varsa "doğru" başarı yüzdesi yok. İşe yararsa dar genişletme.

## REPO DENETİMİNDE SOMUT BULGU
`SABLON_V2_MIMARI/core/vision.py` fonksiyonu `detect_document_corners` üçüncü aşamayı “ORB Feature Matching + Homography” diye isimlendiriyor ama kodu HSV parlaklık bölgesi ve contour kullanıyor; hiç ORB/homografi yok. Birinci aşama en büyük dörtgeni seçiyor; alan %5 altında olan gerçek ürünü elemek mümkün. Hough aşaması global en üst/alt/sol/sağ çizgilerini dörtgen seçiyor. Yalnız nesnenin doğru ROI'siyle sınırlandırılmadan bu algoritmalar fayans/dolap seçecek. `core/template_intelligence.py` ayrıca çok sayıda full-scene renk/kenar adayını skorlayıp quad seçiyor; kimlik/reference-first adımı yoksa benzer yanlış riski sürer. Önce yanlış **arama alanını** düzelt; yeni 94'lük detector turnuvası yapma.

## HAZIR KODLAR / GÜVENİLİR LİNKLER
- OWLv2 image guided resmi HF API: https://huggingface.co/docs/transformers/model_doc/owlv2
- Meta SAM2 (box/positive-negative points): https://github.com/facebookresearch/sam2
- Grounded SAM2 detector→box→SAM kodu: https://github.com/IDEA-Research/Grounded-SAM-2
- YOLOE gerçek `refer_image + visual_prompts`, plus mask: https://docs.ultralytics.com/models/yoloe (**AGPL/Enterprise ticari lisans analizi şart**; yeni kurulum şimdi öncelikli değil)
- GEM cam segmentasyonu: https://github.com/isjinghao/GEM (MaskDINO/Detectron2 gerekir; eğitimin benchmark IoU'su bizim cam panel IoU değil)
- Meta SAM3, visual exemplar: https://github.com/facebookresearch/sam3 (güncel Python 3.12/Torch 2.7+/CUDA 12.6+; ağır; şimdi kurulum yok)
- VGGT_GLASS 2026: https://github.com/YT3DVision/VGGT_GLASS (kurulum/weights ve domain aktarımı maliyetli)
- Photoshop SmartObject replace contents: https://helpx.adobe.com/photoshop/desktop/create-manage-layers/smart-objects/replace-the-contents-of-a-smart-object.html
- Canva Magic Grab clicks/brush: https://www.canva.com/en_gb/help/using-magic-grab/
- BRIA RMBG2.0 CC BY-NC 4.0 ağırlıkları: https://github.com/Bria-AI/RMBG-2.0 ; generic foreground/background ≠ targeted printable surface. Ticari lisans olmadan ürün sistemine sokma.

**Not:** Bir repo var diye Windows V4.6'da çalışıyor sayılmadı. Model skorları doğru printable ROI/perspektif doğruluğu değildir. Şeffaf panelin görünmeyen fiziksel kenarı tek fotoğrafta bilinemeyebilir. Kullanıcı onaylı geometri korunacak. Bu rapor gerçek çalıştırma talimatı gibi davranmamalı; #52 final çalışma akışını durdurmaz.

## 94/94 tekil seçim matrisi
- **ÇEKİRDEK:** hazır mimaride kullanılan/kullanılacak olan kimlik, yeniden kullanım, tespit+maske, ROI sınırlı hassaslaştırma, insan düzeltmesi ve güvenlik işlevi. 24 ayrı model indirme/çalıştırma **değildir**.
- **ŞARTLI:** ilk çekirdek akış belirli gerçek hata örneğini çözemezse küçük hedefli seçenek; şimdilik ağır kurulum yok.
- **ERTELE:** kısa vadede fazladan model/eğitim/karmaşık fizik varsayımı; üretimi geciktirmemeli.

| ID | 94 envanterindeki yöntem (aslı) | Karar | Sebep / rol |
|---|---|---|---|
| ID01 | Kaynak SHA256 ile APPROVED profil tekrar kullanımı | **ÇEKİRDEK** | Kaynağa bağlı insan-onaylı dört köşe doğrudan render: inference yok. |
| ID02 | Piksel hash / tam görsel eşleme | **ÇEKİRDEK** | Yalnız gerçek aynı görüntü/normalize türev kimliği güvenle belirlenir. |
| ID03 | Perceptual hash / çoklu şablon türev arama | ŞARTLI | Aday türev bulma; tek başına quad aktarma yetkisi yok. |
| ID04 | LightGlue yerel özellik eşleştirme | ŞARTLI | Onaylı ürün ROI eşleştirmesinde SIFT başarısız ve ürün ROI kanıtı varsa. |
| ID05 | OpenCV ECC image registration | ŞARTLI | Kanıtlanmış aynı düzlem dönüşümünü hassaslaştırmak için; kendi başına ROI seçmez. |
| ID06 | ORB/AKAZE/SIFT + RANSAC geometri aktarımı | **ÇEKİRDEK** | Yalnız referansın **ürün içi** inlier'ları doğrulandığında güvenli geometri transferi. |
| ID07 | PSD/SmartObject/vector path/alpha mask geometri kurtarma | ŞARTLI | PSD/alpha/vector gerçek metaveri mevcutsa kullanıcıya zaten verilmiş geometrinin yeniden kullanımı. |
| ID08 | Render JSON/SQLite/homografi receipt kurtarma | ŞARTLI | Eksik geometriyi sadece mevcut onaylı kayıt/receipt içinden salt-okunur kurtarma. |
| ID09 | İşlem sırasında geometri provenance metadata kaydı | **ÇEKİRDEK** | Bir defa bulunan/onaylanan geometriyi SHA/ürün-yüzey-occlusion ile sakla. |
| ID10 | Canny edge detection | **ÇEKİRDEK** | Yalnız doğru ROI içinde çizgi öncülü, tam görüntüde 'en büyük dikdörtgen' değil. |
| ID11 | Contour + approxPolyDP | **ÇEKİRDEK** | Yalnız ROI içindeki panel maskesinden 4 köşe adayı. |
| ID12 | Hough / probabilistic Hough | ERTELE | Tüm görüntüde özgür arama fayans/dolap false-positive üretir; doğru ROI içinde yardımcı olabilir. |
| ID13 | LSD / EDLines / ELSD | **ÇEKİRDEK** | Yalnız doğru ROI içinde fiziksel kenar segmenti. |
| ID14 | Adaptive Threshold / CLAHE / gamma | ŞARTLI | Tüm görüntüde özgür arama fayans/dolap false-positive üretir; doğru ROI içinde yardımcı olabilir. |
| ID15 | LAB/HSV/brightness color scoring | ŞARTLI | Tüm görüntüde özgür arama fayans/dolap false-positive üretir; doğru ROI içinde yardımcı olabilir. |
| ID16 | Gaussian/Bilateral/texture suppression | ŞARTLI | Tüm görüntüde özgür arama fayans/dolap false-positive üretir; doğru ROI içinde yardımcı olabilir. |
| ID17 | Gabor/frequency periodicity suppression | ERTELE | Tüm görüntüde özgür arama fayans/dolap false-positive üretir; doğru ROI içinde yardımcı olabilir. |
| ID18 | Convex hull / mask smoothing | ŞARTLI | Tüm görüntüde özgür arama fayans/dolap false-positive üretir; doğru ROI içinde yardımcı olabilir. |
| ID19 | Min-area rectangle / minimum area quad | ERTELE | Tüm görüntüde özgür arama fayans/dolap false-positive üretir; doğru ROI içinde yardımcı olabilir. |
| ID20 | Active Contours / Snakes | ERTELE | Tüm görüntüde özgür arama fayans/dolap false-positive üretir; doğru ROI içinde yardımcı olabilir. |
| ID21 | RANSAC doğrular + robust TLS + kesişim | **ÇEKİRDEK** | Doğrulanmış kenar segmenti üzerinde RANSAC + kesişim ile hassaslaştırma. |
| ID22 | ROI/black-padding exclusion | **ÇEKİRDEK** | Görsel dışı siyah pad'i maskeyle çıkar; gerçek siyah paneli çıkarma. |
| ID23 | Edge strength/orientation + local structural change | ŞARTLI | Tüm görüntüde özgür arama fayans/dolap false-positive üretir; doğru ROI içinde yardımcı olabilir. |
| ID24 | Ultralytics YOLOv8/v11/YOLO26 Pose | ERTELE | Kullanıcının gerçek source-SHA onaylı keypoint eğitim/holdout'u olmadan hazır dört köşe model değildir; şimdi train etme. |
| ID25 | MMPose RTMPose | ERTELE | Kullanıcının gerçek source-SHA onaylı keypoint eğitim/holdout'u olmadan hazır dört köşe model değildir; şimdi train etme. |
| ID26 | MMPose HRNet | ERTELE | Kullanıcının gerçek source-SHA onaylı keypoint eğitim/holdout'u olmadan hazır dört köşe model değildir; şimdi train etme. |
| ID27 | Keypoint R-CNN | ERTELE | Kullanıcının gerçek source-SHA onaylı keypoint eğitim/holdout'u olmadan hazır dört köşe model değildir; şimdi train etme. |
| ID28 | RT-DETR + özel keypoint head | ERTELE | Kullanıcının gerçek source-SHA onaylı keypoint eğitim/holdout'u olmadan hazır dört köşe model değildir; şimdi train etme. |
| ID29 | Özel köşe heatmap / doğrudan regresyon | ERTELE | Kullanıcının gerçek source-SHA onaylı keypoint eğitim/holdout'u olmadan hazır dört köşe model değildir; şimdi train etme. |
| ID30 | Boundary+keypoint multi-task learner | ERTELE | Kullanıcının gerçek source-SHA onaylı keypoint eğitim/holdout'u olmadan hazır dört köşe model değildir; şimdi train etme. |
| ID31 | Per-edge heatmap + junction graph | ERTELE | Kullanıcının gerçek source-SHA onaylı keypoint eğitim/holdout'u olmadan hazır dört köşe model değildir; şimdi train etme. |
| ID32 | YOLO instance segmentation | ERTELE | Maske ≠ baskı yüzeyi veya perspektif dört köşe; yeni ağır checkpoint yerine SAM2 ile başla. |
| ID33 | Mask R-CNN | ERTELE | Maske ≠ baskı yüzeyi veya perspektif dört köşe; yeni ağır checkpoint yerine SAM2 ile başla. |
| ID34 | Detectron2 / MMDetection / MMSegmentation | ERTELE | Maske ≠ baskı yüzeyi veya perspektif dört köşe; yeni ağır checkpoint yerine SAM2 ile başla. |
| ID35 | SAM 2 / SAM 2.1 Hiera Tiny-Small | **ÇEKİRDEK** | Mevcut SAM2.1'i bbox / pozitif-negatif tıkla maske üretmek için kullan; center-only değil. |
| ID36 | SAM 3 / SAM 3.1 | ŞARTLI | SAM3/3.1 ancak mevcut OWLv2+SAM2 somut zor örnekte başarısızsa, izolasyon/lisans/VRAM kararıyla. |
| ID37 | MobileSAM | ERTELE | Maske ≠ baskı yüzeyi veya perspektif dört köşe; yeni ağır checkpoint yerine SAM2 ile başla. |
| ID38 | FastSAM | ERTELE | Maske ≠ baskı yüzeyi veya perspektif dört köşe; yeni ağır checkpoint yerine SAM2 ile başla. |
| ID39 | Edge-aware SAM fine-tuning | ERTELE | Maske ≠ baskı yüzeyi veya perspektif dört köşe; yeni ağır checkpoint yerine SAM2 ile başla. |
| ID40 | GEM Glass-Segmentor | ŞARTLI | GEM cam segmenter sadece sahici cam başarısızlığında, ağır MaskDINO/Detectron2 ve checkpoint uygunluğuyla. |
| ID41 | GlassWizard (ICCV2025) | ŞARTLI | GlassWizard pahalı diffusion, hazır runner/weights doğrulanmadan kurma. |
| ID42 | Trans10K-v2 data/segmentation baseline | ERTELE | Maske ≠ baskı yüzeyi veya perspektif dört köşe; yeni ağır checkpoint yerine SAM2 ile başla. |
| ID43 | VGGT_GLASS (ACMMM2026) | ŞARTLI | VGGT_GLASS araştırma sınıfı derinlik/3B kurulum; şimdilik geciktirir. |
| ID44 | Grounding DINO | ŞARTLI | Metin/görsel detektörü sadece ROI adayı üretir; yüzey doğruluğunu garantilemez. |
| ID45 | Grounded-SAM | ŞARTLI | Metin/görsel detektörü sadece ROI adayı üretir; yüzey doğruluğunu garantilemez. |
| ID46 | OWLv2 | **ÇEKİRDEK** | Elimizdeki OWLv2'yi gerçek image-guided detection ref crop ile kullan; tek hedef/tek referans, gerekirse az sayıda ref seç. |
| ID47 | Florence-2 | ERTELE | Metin/görsel detektörü sadece ROI adayı üretir; yüzey doğruluğunu garantilemez. |
| ID48 | DINOv2 feature similarity | ŞARTLI | Metin/görsel detektörü sadece ROI adayı üretir; yüzey doğruluğunu garantilemez. |
| ID49 | CLIP feature similarity | ŞARTLI | Metin/görsel detektörü sadece ROI adayı üretir; yüzey doğruluğunu garantilemez. |
| ID50 | Dedicated panel present/absent classifier | ŞARTLI | Metin/görsel detektörü sadece ROI adayı üretir; yüzey doğruluğunu garantilemez. |
| ID51 | Ghosting shifted double-reflection | ERTELE | Tek RGB görselde gerçek cam sınırı/kadraj optiği çoğu zaman belirsiz; düşük bilgi kazancına ağır fizik çözümü ekleme. |
| ID52 | Phase correlation / NCC micro-windows | ERTELE | Tek RGB görselde gerçek cam sınırı/kadraj optiği çoğu zaman belirsiz; düşük bilgi kazancına ağır fizik çözümü ekleme. |
| ID53 | Reflection prior / Fresnel / glare | ŞARTLI | Tek RGB görselde gerçek cam sınırı/kadraj optiği çoğu zaman belirsiz; düşük bilgi kazancına ağır fizik çözümü ekleme. |
| ID54 | PPI-OET plane intersection + edge topology | ERTELE | Tek RGB görselde gerçek cam sınırı/kadraj optiği çoğu zaman belirsiz; düşük bilgi kazancına ağır fizik çözümü ekleme. |
| ID55 | Depth Anything V2 Small | ERTELE | Tek RGB görselde gerçek cam sınırı/kadraj optiği çoğu zaman belirsiz; düşük bilgi kazancına ağır fizik çözümü ekleme. |
| ID56 | Omnidata normals | ERTELE | Tek RGB görselde gerçek cam sınırı/kadraj optiği çoğu zaman belirsiz; düşük bilgi kazancına ağır fizik çözümü ekleme. |
| ID57 | TransNormal transparent normal prediction | ERTELE | Tek RGB görselde gerçek cam sınırı/kadraj optiği çoğu zaman belirsiz; düşük bilgi kazancına ağır fizik çözümü ekleme. |
| ID58 | Vanishing point / Manhattan world | ŞARTLI | Tek RGB görselde gerçek cam sınırı/kadraj optiği çoğu zaman belirsiz; düşük bilgi kazancına ağır fizik çözümü ekleme. |
| ID59 | Ocak-davlumbaz-tezgâh semantik konumu | **ÇEKİRDEK** | Ocak-arkası panel için ocak/davlumbaz/tezgâh konumsal negatif ve pozitif prior. |
| ID60 | Controlled multi-photo/polarization/photo setup | ERTELE | Tek RGB görselde gerçek cam sınırı/kadraj optiği çoğu zaman belirsiz; düşük bilgi kazancına ağır fizik çözümü ekleme. |
| ID61 | Controlled 3D render normal-depth-objectID passes | ERTELE | Tek RGB görselde gerçek cam sınırı/kadraj optiği çoğu zaman belirsiz; düşük bilgi kazancına ağır fizik çözümü ekleme. |
| ID62 | Line extrapolation + RANSAC hidden corners | ŞARTLI | Görünmeyen köşeyi tek görüntüden kesin bilmeyiz; yalnız kanıtlı kenar ve kullanıcı onayına bağlı. |
| ID63 | Foreground occluder segmentation | **ÇEKİRDEK** | Foreground occluder ayrı maske; baskı maske dışına ve öndeki nesne üstüne taşmasın. |
| ID64 | Visibility-aware keypoint head | ŞARTLI | Görünür yüzey ile gerçek baskı düzlemi ayrı; insan/onaylı geometri gerektiğinde korunur. |
| ID65 | PETEK curve/slot dense UV mapping | **ÇEKİRDEK** | PETEK'e quad zorlamadan kavis/delik/slot maske ve geometri yolu. |
| ID66 | Cascade / candidate ranking | **ÇEKİRDEK** | Az sayıda aday, fiziksel/ROI/negatif kurallarla sırala ve emin değilse abstain. |
| ID67 | Category/material-aware expert router | **ÇEKİRDEK** | Kategorinin fiziksel biçimi, oryantasyonu, printable yüzeyi ve bilinen pozisyonu ayrı değerlendir. |
| ID68 | Isotonic/logistic calibration | ERTELE | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID69 | Conformal risk control / abstention | ŞARTLI | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID70 | Test-time augmentation inverse consistency | ŞARTLI | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID71 | Uncertainty per-edge and per-corner | ŞARTLI | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID72 | Hard negatives + active learning | ŞARTLI | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID73 | Error taxonomy + adaptive human nudge | **ÇEKİRDEK** | Kullanıcının tek tık/kutu ve tek kenar düzeltmesine izin ver; 4 köşe düzeltmeyi koru. |
| ID74 | Risk coverage curve + expected cost | ŞARTLI | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID75 | Synthetic Blender/domain randomization | ERTELE | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID76 | Artwork invariance paired training | ERTELE | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID77 | Counterfactual tile adversarial test suite | ERTELE | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID78 | Photometric edge-vs-print-area observability | **ÇEKİRDEK** | Kenarı fotoğrafta göremiyorsan doğruluk uydurma: abstain. |
| ID79 | Final render overprint pixel loss | **ÇEKİRDEK** | Gerçek baskı maskesi dışında piksel değişti mi renderla kontrol et. |
| ID80 | Knowledge distillation ONNX deployment | ERTELE | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID81 | Out-of-distribution and panel-absent abstain | **ÇEKİRDEK** | Hedef yok/yanlış nesne ise otomatik onaydan kaçın. |
| ID82 | Multi-view video optical flow glass mask | ERTELE | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID83 | Blind human label disagreement audit | ŞARTLI | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID84 | Box-to-region & controlled ROI human test | ŞARTLI | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID85 | A/B single-model refiner ablation | ERTELE | İzole gerçek insan GT olmadan güven skoru/başarı iddiası yok; basit abstain ve görsel doğrulama önce gelir. |
| ID86 | Golden group-wise split leakage controls | **ÇEKİRDEK** | Kopya ve aynı sahne ailesi test/ref setlerine sızmasın. |
| ID87 | Geometry-to-compositing provenance contract | **ÇEKİRDEK** | OUTER, PRINTABLE, VISIBLE ve OCCLUDER birbirinden ayrı maskeler/koordinatlar. |
| ID88 | Manual approved immutable write-protection | **ÇEKİRDEK** | Onaylı source SHA ve immutable insan 4-köşe koruması zorunlu. |
| ID89 | PTN / perspective correction network iddiası | ERTELE | Görünür yüzey ile gerçek baskı düzlemi ayrı; insan/onaylı geometri gerektiğinde korunur. |
| ID90 | YOLOX-Pose veya YOLOX keypoint adaptasyonu | ERTELE | Kullanıcının gerçek source-SHA onaylı keypoint eğitim/holdout'u olmadan hazır dört köşe model değildir; şimdi train etme. |
| ID91 | f-BRS interactive segmentation refinement | ŞARTLI | Tek tıklık maske düzeltme, mevcut SAM2 yetmezse ve entegrasyon hafifse. |
| ID92 | SciPy nonlinear constrained quad optimization | **ÇEKİRDEK** | Yalnız doğru panel ROI ve sınır kanıtıyla sınırlı optimizasyon, global sahne değil. |
| ID93 | Line-junction / wireframe neural representation | ŞARTLI | Görünür yüzey ile gerçek baskı düzlemi ayrı; insan/onaylı geometri gerektiğinde korunur. |
| ID94 | Photometric stereo multi-light controlled capture | ERTELE | Tek RGB görselde gerçek cam sınırı/kadraj optiği çoğu zaman belirsiz; düşük bilgi kazancına ağır fizik çözümü ekleme. |

### Teknik kararın yanlış anlaşılmasını önleyen notlar
- Gerçekten çalıştırılacak iki mevcut AI modülü: **OWLv2 sadece gerektiğinde referanslı nesne lokalizasyonu** ve **SAM2.1 hedefi belli nesnede bbox/tık prompt maske**. Diğerleri ucuz CV, veri bağı, maske ve QA korumasıdır.
- SAM2 ile şeffaf camın gerçek fiziksel kenarı bulunamazsa manuel dört köşe tek güvenli seçenek olabilir. Çok fazla sözde inlier gerçek ürün demek değildir.
- Eski 170 merkez-nokta SAM2 maskesi hedefe ait görsel kanıt değildir; 94 satırının orijinal `empirically_tested_on_user_real_images=false` bayrakları yeni laboratuvar sonucu statüsü değildir.
- `NO_GO` devam eder; bu dosya bir Windows release kabulü veya motor entegrasyonu değildir.
