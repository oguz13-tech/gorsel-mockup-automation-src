Sayın Baş Mühendis / Proje Yöneticisi,

Öncelikle belirtmeliyim ki **mesajınıza herhangi bir görsel eklenmemiş.** Ancak bir "Baş Mühendis" olarak, tarif ettiğiniz "Ocak Arkası" ve diğer cam yüzey problemlerinin tam olarak hangi vizyon (görüntü işleme) duvarlarına çarptığını çok iyi biliyorum. Şeffaflık, speküler yansımalar, arka plan fayans desenleri ve perspektif bozulmaları; klasik OpenCV tabanlı (Canny, Hough, Contour) sistemlerin çözmekte %100 başarısız olduğu "semantik" problemlerdir.

Aşağıda, mevcut OpenCV altyapınızı çöpe atmadan, onu **Yapay Zekâ (Semantik Anlama)** ile **Klasik Görüntü İşleme (Piksel Hassasiyeti)** arasında bir köprüye dönüştürecek, RTX 3060 Laptop GPU'da çalışacak, ticari lisans risklerini barındırmayan ve insan onaylı verilerinizi koruyan **Derin Teknik Araştırma ve Mimari Raporu**'nu sunuyorum.

---

# BÖLÜM 1: MÜHENDİSLİK SORULARININ YANITLARI VE TEKNOLOJİ ANALİZİ

### 1. Bu problem için günümüzde en uygun 5 teknoloji hangileridir?

1. **RT-DETR (Real-Time DEtection TRansformer) / Keypoint:** (Önerilen) Hem nesne tespiti hem de köşe (keypoint) regresyonu yapar. Lisansı Apache 2.0'dır (Ticari kullanım için güvenli).
2. **YOLOv8 / YOLOv11 Pose Estimation:** En hızlı ve entegrasyonu en kolay olanıdır. *Ancak Lisans Uyarısı:* Ultralytics modelleri **AGPL-3.0** lisanslıdır. Eğer ürününüz kapalı kaynak ticari bir yazılımsa, Ultralytics Enterprise lisansı almanız veya açık kaynak alternatiflere (MMPose/MMDetection) yönelmeniz gerekir.
3. **MMPose / HRNet (High-Resolution Net):** OpenMMLab kütüphanesi (Apache 2.0). Isı haritası (heatmap) tabanlı köşe tespiti yapar. Piksel hassasiyeti YOLO'dan daha yüksektir, ancak RTX 3060'ta YOLO kadar hızlı değildir.
4. **MobileSAM / FastSAM:** Sadece maske çıkarmak için. Dört köşeyi doğrudan vermez, maske üzerinden `approxPolyDP` ile köşe türetmek gerekir.
5. **Grounding DINO:** Sıfır-shot (zero-shot) tespit için. "Ocak arkası cam" yazdığınızda bulur ama piksel hassasiyeti ve hızı toplu işlem (batch) için yetersizdir. Sadece "Fallback" (yedek) mekanizması olarak kullanılabilir.

### 2. Şeffaf, beyaz, siyah ve desenli cam yüzeylerde hangisi başarılı?

**Keypoint (Köşe) Regresyonu yapan modeller (RT-DETR / YOLO-Pose).** Neden? Çünkü segmentasyon modelleri camın *içini* doldurmaya çalışırken fayans desenine veya yansımaya kanabilir. Ancak Keypoint modelleri camın *bağlamını* (montaj klipsleri, duvarla birleştiği gölge çizgisi, tezgâhın arka kenarı) öğrenir. Siyah camda bile montaj aparatlarının veya duvar gölgesinin konumundan 4 köşeyi matematiksel olarak tahmin eder.

### 3 & 4. Hazır model yeterli mi? Özel eğitim şart mı? Veri miktarı nedir?

Hazır model (COCO dataset ile eğitilmiş) "cam panel" kavramını bilemez, sadece "pencere" veya "TV" bilir. **Kesinlikle özel eğitim (Fine-tuning) şarttır.**

- **Veri Miktarı:** Sadece "Ocak Arkası" için **500 - 800 adet** çeşitli görsel (farklı ışık, farklı fayans, farklı perspektif) yeterlidir.
- **Etiketleme İş Yükü:** Zaten insan tarafından onaylanmış 4 köşe verileriniz var! Bu sizin altın madeniniz. Etiketleme iş yükü **SIFIR**. Mevcut verilerinizi format dönüştürerek doğrudan eğitime sokacağız.

### 5. Onaylanmış dört köşeleri nasıl değerlendirebiliriz?

Mevcut `(x1,y1), (x2,y2), (x3,y3), (x4,y4)` verilerinizi, kullanacağımız modelin (örn. RT-DETR veya YOLO-Pose) `.txt` formatına dönüştüren bir Python scripti yazacağız. Model, görüntüyü gördüğünde bu 4 noktanın *sınıfını* (Sol Üst, Sağ Üst vb.) ve *koordinatlarını* doğrudan tahmin edecek şekilde eğitilecek.

### 6. Maske tespitinden dört köşeye geçişte hangi algoritma?

Eğer Segmentasyon (Maske) kullanırsak:

1. Maske alınır.
2. `cv2.convexHull` veya `cv2.approxPolyDP` ile dörtgen bulunur.
3. **HATA RİSKİ:** Camın bir köşesi dolap tarafından kapatılmışsa maske eksik çıkar, dörtgen bozulur. *Bu yüzden Maske yerine doğrudan **Keypoint (Nokta) Regresyonu** kullanılmalıdır.*

### 7. Camın bir kısmı kapatılmışsa (Okluzyon) gerçek köşeler nasıl bulunur?

Keypoint modelleri "Spatial Context" (Uzamsal Bağlam) kullanır. Tencere camın altını kapatmış olsa bile, model camın üst kenarının perspektif açısını ve duvarla olan kesişimini analiz ederek, tencerenin altındaki *görünmez* köşelerin nerede olması gerektiğini "hayal eder" (regrese eder).

### 8. AI'ın yanlış dolap veya fayans seçmesini nasıl engelleriz?

1. **Negatif Örnekler (Hard Negatives):** Eğitim setine dolap, fayans ve tezgâh görselleri ekleyip bunları "background" (arka plan) olarak etiketleyeceğiz.
2. **Sınıf Ayrımı:** Modele sadece "cam" değil; `ocak_arkasi`, `cam_tablo`, `ahsap_tablo` gibi sınıflar öğreteceğiz. Model, fayansın dikdörtgenleri ile cam panelin montaj izlerini/ayrışmasını ayırt etmeyi öğrenecek.

### 9. Güven puanı ve başarısız algılama (Fallback) tasarımı

Model bize 4 köşe + 1 Güven Puanı (Confidence Score) verecek.

- **Kural 1:** Güven < %80 ise -> *İnsan Onayına Yönlendir (UI'da kırmızı çerçeve).*
- **Kural 2:** Geometrik Geçerlilik. Bulunan 4 köşenin oluşturduğu alan görüntünün %2'sinden küçük veya %80'inden büyükse -> *Red.*
- **Kural 3:** Dışbükeylik (Convexity) kontrolü. Köşeler içe doğru bükük (concave) bir dörtgen oluşturuyorsa -> *Red.*
- **Kural 4:** İnsan onaylı veri varsa -> *AI'ı bypass et, insan verisini kullan.*

### 10. RTX 3060 Laptop GPU üzerinde gerçekçi modeller

RTX 3060 Laptop genellikle 6GB VRAM'e sahiptir.

- **RT-DETR ResNet-18 / ResNet-34:** \~15-20 ms/görsel. (Mükemmel uyum).
- **YOLOv8n-Pose / YOLOv8s-Pose:** \~5-10 ms/görsel. (Çok hızlı, AGPL lisans riski var).
- **SAM (ViT-B):** \~150 ms/görsel. (Yavaş, VRAM'i sömürür, önerilmez).

### 11. Windows, Bağımlılık ve Ticari Lisans Riskleri (ÇOK ÖNEMLİ)

- **Ultralytics (YOLO):** AGPL-3.0. Kapalı kaynak ticari ürünlerde kullanılamaz (Enterprise şart).
- **OpenMMLab (MMPose/MMDetection) & RT-DETR:** Apache 2.0. Ticari, kapalı kaynak, satılabilir yazılımlarda **ÖZGÜRCE** kullanılabilir.
- **Tavsiyem:** Lisans başınızı ağrıtmaması için **RT-DETR (Baidu)** veya **MMPose** altyapısını kullanacağız. PyTorch tabanlıdırlar, Windows ve CUDA ile sorunsuz çalışırlar.

### 12. Mevcut OpenCV sistemini değiştirmek mi, Hibrit mi?

**KESİNLİKLE HİBRİT.** AI (RT-DETR/Keypoint) size "yaklaşık" 4 köşeyi (ROI - Region of Interest) verir. OpenCV ise bu ROI içine girip **Sub-Pixel (Alt Piksel) Kenar Algılama** (örn. Canny + Active Contours / Snakes) yapar. *Formül:* `AI = Semantik Doğruluk (Neresi?)` + `OpenCV = Piksel Hassasiyeti (Tam olarak hangi çizgi?)`.

### 13. Karşılaştırma Tablosu

| Teknoloji              | Hız (RTX 3060) | VRAM   | Köşe Hassasiyeti           | Lisans (Ticari)          | Öneri                         |
| ---------------------- | -------------- | ------ | -------------------------- | ------------------------ | ----------------------------- |
| **RT-DETR (Keypoint)** | \~15 ms        | 1.5 GB | Yüksek (Sub-pixel değil)   | **Apache 2.0 (Güvenli)** | **1. Tercih (Ana Model)**     |
| YOLOv8-Pose            | \~6 ms         | 1.0 GB | Yüksek                     | AGPL-3.0 (Riskli)        | Sadece Açık Kayınsa           |
| MobileSAM              | \~40 ms        | 2.5 GB | Düşük (Maske->Köşe hatası) | Apache 2.0               | 2. Tercih (Fallback)          |
| Grounding DINO         | \~400 ms       | 4.5 GB | Orta                       | Apache 2.0               | Sadece "Bulunamadı" durumu    |
| Klasik OpenCV          | \~2 ms         | 0 GB   | Çok Düşük (Bağlam körü)    | Apache 2.0               | Sadece AI'dan sonra ince ayar |

### 14. Test ve Doğrulama Yöntemi

- **Metrik:** Sadece IoU yetmez. **PCK (Percentage of Correct Keypoints)** kullanacağız. Örneğin, tahmin edilen köşe, gerçek köşeden 5 piksel uzaktaysa "Başarılı" sayılacak.
- **Veri Ayrımı:** Train/Val/Test setleri *rastgele* değil, *farklı mutfak/dekor setlerine* göre ayrılmalı. Modelin ezber yapması engellenmeli.

---

# BÖLÜM 2: GÖRSEL İNCELEME ANALİZİ (Simülasyon)

*(Görseller eklenmediği için, sisteminizdeki en tipik 3 "Ocak Arkası" hata senaryosunu ve AI'ın bunları nasıl çözeceğini analiz ediyorum.)*

### Senaryo A: Siyah Cam Üzerinde Siyah Fayans / Düşük Kontrast

- **Gerçek Yüzey:** Siyah cam panel.
- **İnsan Gözü / AI Nasıl Ayırt Eder?** Camın sol ve sağ üst köşelerindeki metal montaj klipslerini, camın altından vuran tezgâh yansımasını ve camın arka planındaki fayansın *bulanıklığını* (depth of field) analiz eder.
- **Klasik OpenCV Neden Yanılır?** Canny edge detection hem fayans derzlerini hem de cam kenarını aynı şiddette görür. En büyük dikdörtgeni bulmaya çalışırken tüm duvarı seçer.
- **Çözüm:** Keypoint modeli, "montaj klipsi" ve "tezgâh bitiş gölgesi" bağlamını öğrenerek köşeleri doğrudan tahmin eder.

### Senaryo B: Şeffaf Cam, Arkada Renkli Tencereler ve Baharatlıklar

- **Gerçek Yüzey:** Şeffaf cam, arkası karmaşık.
- **İnsan Gözü / AI Nasıl Ayırt Eder?** Camın kendisini değil, camın *çerçevesini* veya camın kenarlarında oluşan ince beyaz speküler yansıma çizgilerini (highlight) arar.
- **Klasik OpenCV Neden Yanılır?** Arkadaki tencerenin kapağının dikdörtgenini veya baharatlığın etiketini "cam yüzey" sanarak contour çizer.
- **Çözüm:** Model, "arkadaki nesnelerin kenarları" ile "camın fiziksel sınırları" arasındaki farkı (ışık kırılması ve cam kalınlığı gölgesi) segmentasyon/heatmap üzerinden ayırt eder.

### Senaryo C: Camın Altının Ocak Düğmeleri / Davlumbaz Tarafından Kapatılması

- **Gerçek Yüzey:** Alt iki köşesi görünmüyor.
- **İnsan Gözü / AI Nasıl Ayırt Eder?** Üst iki köşeden gelen perspektif çizgilerinin (vanishing point - yok nokta) düğmelerin arkasında nerede kesişeceğini hesaplar.
- **Klasik OpenCV Neden Yanılır?** Görünmeyen köşeyi tahmin edemez, ya hata verir ya da davlumbazın alt kenarını camın alt kenarı sanır.
- **Çözüm:** Keypoint regresyonu, okluzyona (kapatılmaya) karşı dirençlidir. Görünmeyen noktayı, görünmeyen kısımların istatistiksel dağılımından çıkarır.

---

# BÖLÜM 3: MİMARİ VE ENTEGRASYON TASLAĞI (PYTHON)

Mevcut `SABLON_V2_MIMARI` yapınıza entegrasyon şu şekilde olmalıdır:

```
python
```

`# vision.py veya yeni ai_vision.py içine entegre edilecek yapı  class HybridCornerDetector:     def __init__(self):         # 1. AI Modeli Yükle (RT-DETR Keypoint veya MMPose)         self.ai_model = load_keypoint_model("rt_detr_ocak_arkasi.pt")         # 2. Güven Eşiği         self.confidence_threshold = 0.85       def detect(self, image, category, human_approved_corners=None):         # KURAL: İnsan onayı varsa ASLA DOKUNMA         if human_approved_corners:             return human_approved_corners          # ADIM 1: AI ile Kaba Köşe ve ROI (Region of Interest) Tespiti         ai_corners, confidence, bbox = self.ai_model.predict(image)                  # GÜVENLİK KONTROLÜ         if confidence < self.confidence_threshold:             return {"status": "FAIL", "reason": "Düşük Güven", "fallback": "MANUAL_REVIEW"}                      # ADIM 2: OpenCV ile Sub-Pixel İnce Ayar (Sadece AI'ın bulduğu ROI içinde)         x, y, w, h = bbox         roi_image = image[y:y+h, x:x+w]                  # ROI içinde Canny + Active Contours ile gerçek fiziksel kenara "yapış"         refined_corners = self._subpixel_snap(roi_image, ai_corners)                  # ADIM 3: Geometrik Geçerlilik (Perspektif ve Alan Kontrolü)         if not self._is_valid_quadrilateral(refined_corners):             return {"status": "FAIL", "reason": "Geometrik Hata"}          # ADIM 4: Sıralama (Sol Üst, Sağ Üst, Sağ Alt, Sol Alt)         final_corners = self._sort_corners_clockwise(refined_corners)                  return {"status": "SUCCESS", "corners": final_corners, "confidence": confidence}      def _subpixel_snap(self, roi, ai_corners):         # OpenCV GrabCut veya Active Contours kullanarak AI'nın bulduğu          # yaklaşık köşeleri, ROI içindeki en keskin kontrast çizgisine çeker.         pass `

---

# BÖLÜM 4: BAŞ MÜHENDİS YOL HARİTASI (FAZ FAZ UYGULAMA)

Eğer bu projenin baş mühendisi olsaydım, ekibime şu sırayla iş bölümü yapardım:

### FAZ 1: Veri Hazırlığı (1 Hafta)

- Mevcut insan onaylı `.json` veya `.csv` koordinat dosyalarını okuyan bir script yazılacak.
- Bu koordinatlar, RT-DETR / YOLO-Pose formatına (`.txt` -> `class x_center y_center width height kp1_x kp1_y kp1_v ...`) dönüştürülecek.
- **Veri Çoğaltma (Augmentation):** Perspektif bozulmaları, ışık değişiklikleri ve "Gaussian Blur" eklenerek veri seti 500'den 2000'e çıkarılacak. (Cam yansımaları için şart).

### FAZ 2: Model Eğitimi ve Lisans Seçimi (2 Hafta)

- **Karar:** Ticari lisans riskini sıfırlamak için **Baidu'nun RT-DETR** modeli (HuggingFace üzerinden) veya **MMPose** kütüphanesi seçilecek.
- Model, RTX 3060 Laptop üzerinde \~20-30 epoch eğitilecek. (Yaklaşık 2-3 saat sürer).
- Hedef: Val setinde PCK (5 piksel hata payı) oranını %90'ın üzerine çıkarmak.

### FAZ 3: Hibrit Pipeline'ın Kodlanması (1 Hafta)

- `template_intelligence.py` içerisine AI çağrısı entegre edilecek.
- OpenCV'nin "Sub-pixel snapping" (Alt piksel kenara kilitlenme) fonksiyonu yazılacak. AI'nın bulduğu 4 nokta, OpenCV'ye "tohum" (seed) olarak verilecek, OpenCV bu tohumları camın gerçek fiziksel kenarına çekecek.

### FAZ 4: Güvenlik Katmanı ve UI Entegrasyonu (1 Hafta)

- Sistem "Bulamıyorum" demeyi öğrenmeli. Güven skoru düşükse veya perspektif açısı mantıksızsa (örn. camin duvara paralel olması gerekirken yamuk çıkması) işlem iptal edilmeli.
- Arayüzde (UI) "Otomatik Bulundu (Yeşil)" ve "İnsan Onayı Bekliyor (Sarı)" durumları ayrılmalı.

### FAZ 5: Diğer Kategorilere Yayılım (Sürekli)

- Sistem "Ocak Arkası"nda %95 başarıya ulaştığında, aynı mimari (Sadece model ağırlıklarını değiştirerek) "Cam Tablo", "Wi-Fi Kutusu" için kopyalanacak. Veri setine yeni sınıflar eklenecek.

---

# ÖZET VE TAVSİYELER

1. **Klasik OpenCV'yi tamamen terk etmeyin;** ancak onu "Arama ve Bulma" işinden alıp, "Piksel Hassasiyetine İnce Ayar" işine terfi ettirin.
2. **Lisans Tuzağına Düşmeyin:** YOLO (Ultralytics) çok cazip gelse de AGPL-3.0 lisansı ticari kapalı kaynak projelerinizi riske atar. **RT-DETR** veya **MMPose** kullanın.
3. **Veriniz Değerli:** Elinizdeki insan onaylı veriler, sıfırdan veri toplamaktan 100 kat daha değerli. Hemen formatlanıp eğitime sokulmalı.
4. **Hata Kabulü:** Sistemin en büyük başarısı, "yanlış koordinat üretmek" yerine "koordinat üretemiyorum, insanı çağır" diyebilmesidir. Bu, e-ticaret mockup sisteminizde hatalı baskı/ürün görseli oluşmasını %100 engelleyecektir.

*Görselleri mesajınıza eklediğinizde, bu mimari üzerinden tam olarak hangi OpenCV filtresinin (örn. CLAHE, Adaptive Threshold) AI maskesiyle nerede birleştirileceğine dair piksel bazlı simülasyonumu da iletebilirim*