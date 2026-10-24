# TEK KOMUT — 94 Adaylı Adaptif Görsel Geometri ve 7 Kategori Test Laboratuvarı
Tarih: 24.10.2026 | Kapsam: TAM | Durum: GÖREV HAZIR — AJAN ÇALIŞTIRMASI AYRI TETİKLENECEK

## 0. Çalışma ilkesi ve kaynakların bütünlüğü
Bu görev TEK COPILOT KOMUTUDUR. Planı parçalara bölüp her faz için kullanıcıdan yeniden görev isteme; izinli ve test edilebilir aşamaları aynı oturumda ardışık yürüt. Kullanıcıya *yalnız gerçek görsel kalite ve nihai otomatik kabul* kararlarını bırak. Eksik kanıtı PASS yapma, zorunlu durumu BLOCKED olarak yaz. Bilimsel yöntemlerle kanıt topla; öncelik ticari kullanımda yanlış baskıyı engellemektir, yüksek görünen tekil demo başarısı değildir.

ZORUNLU araştırma kaynakları (atlama, bütününü oku):
- docs/research/geometry-lab-20261024/TEKNOLOJI_ENVANTERI_94_ADAY.json — **ID01–ID94** tamamı korunacak ve tekil takip edilecek; kayıtların bir kısmı model değil teknik/deney/güvenlik katmanıdır.
- docs/research/geometry-lab-20261024/DORT_KOSE_ANA_ARASTIRMA_RAPORU_20261024.md
- docs/research/geometry-lab-20261024/SOHBET_KAYNAKLARI_CAPRAZ_KONTROL.md
- docs/research/geometry-lab-20261024/ORIJINAL_ARASTIRMALAR/P1_PERPLEXITY_ILK_RAPOR.txt
- docs/research/geometry-lab-20261024/ORIJINAL_ARASTIRMALAR/P2_PERPLEXITY_YENI_RAPOR.txt
- docs/research/geometry-lab-20261024/ORIJINAL_ARASTIRMALAR/Q1_QWEN_ILK_RAPOR.md
- DeepSeek, Ghosting, Qwen-PPI-OET, Gemini ve Copilot'un 20 grup önerisinin çapraz kontrol özetleri.

Kaynaklara eklenecek fakat sessizce silinmeyecek farklı öneriler: çok ölçekli/tile+ROI yöntem, çizgi/kenar heatmap'leri, belirsizlik/aleatoric-epistemic ayrımı, test-zamanı augmentation kararlılığı, SHAP değil gerekçeli kanıt kayıtları, ORB/AKAZE/SIFT eşleme, perspektif bozulma karşılaştırması, data leakage / near-duplicate kümeleri, köşe-baskı taşması metrikleri, conformal/selective prediction, gerçek/sentetik domain shift, kontrollü 3B veya üretken arka plan geometri kaydı. Her ilavenin envanterde ayrı kimliği ve lisans/kanıt notu olsun.

## 1. Paralel V4.6 görevi ASLA DURMASIN
Mevcut teslimat hattı: PR #52, branch feature/v46-safe-consolidation-20261024, Issue #35 final kabul. 24.10 tarihli güncel kök neden raporu RELEASE=NO-GO; gerçek Windows GUI, Golden, PETEK, GPU, HTTPS/pazaryeri ve büyük batch kabulü eksik olabilir. Onları bu araştırma bahanesiyle durdurma, yeniden etiketleme, source head'lerini sıfırlama veya aynı workspace'de çatışmalı geliştirme yapma.
Bu araştırma için **ayrı Windows çalışma klasörü, ayrı Git branch, ayrı sanal ortam/worker, ayrı SQLite kopyası, ayrı çıktı havuzu ve iş kuyruğu** kullan. PR #52, çalışan V4.6 launcher/ZIP ve OneDrive runtime'a yazma. Commitleri yalnız araştırma dalına veya buradan açılan ayrı deney PR'ına yap. MAIN MERGE, otomatik release, üretime deploy, canlı DB migration yok. Var olan agent'ın çalıştığı dosyaların üstüne yazma ve onu sonlandırma. Ajan/iş paralelliği sağlanamıyorsa durdurmak yerine çatışmasız işleri sırala ve sebebini raporla.

## 2. Kesin veri ve yetki güvenliği
Mevcut 708 şablon / 591 profil satırı geçmiş envanter bilgisidir, doğrulanmış APPROVED sayısı değildir. Kaynağı salt okunur envanterle denetle:
- İnsan onayı = review_status APPROVED, manually_verified=1, is_active=1 ve doğru template_uid + kategori + source_sha256 + piksel yönü + sürüm doğrulaması. Onaylı koordinat/maskeye yeni modelin ASLA yazma yetkisi olmasın; otomatik öneriler ayrı geometry_proposals ve izole laboratuvar veri tabanına.
- Altın veri hedefleri ayrı: physical outer_quad, printable surface_quad, visible mask, occluder mask, visibility (visible/occluded/inferable/unlabelable), TL-TR-BR-BL.
- SHA256 önce/sonra, backup+restore dry run, read-only SQLite snapshot, disk boşluğu, izin/aynı isim çakışma, error logging. Canlı SQLite/şablon/maske, üretimler, kullanıcı fotoğrafları, hesap anahtarları, gerçek mağaza Excel ve kişisel yollar PUBLIC GitHub'a, CI artifact'a veya harici model API'lerine GÖNDERİLMEYECEK.
- Özel görüntülerin model eğitimine kullanım hakkını doğrula. Yerel offline inference öncelikli. Lisansı belirsiz ağırlıkları kurulu ticari motora taşımadan önce BLOCKED_LICENSE belirt.
- Kullanıcı ayrı izole lab kurulumu, Python/venv/WSL (gerekirse), GPU/CPU benchmark ve model indirmeleri için izin veriyor; yalnız güvenilir resmî kaynak, lisans ve SHA doğrulamasından sonra. Sistemi veya canlı kurulumları silen/yazan komutlar bu izin kapsamına GİRMEZ. Ücretli servis, özel checkpoint lisansı, kullanıcının özel verisini dışarı aktarma ve güvenlik korumasını kaldırma için ayrıca açık onay gerekir.

## 3. Tek komutla gerçekleşecek sıralama: ÖNCE DÖRT CAM, SONRA YEDİ KATEGORİ
Aşama A: güvenli preflight, kaynak arşiv 94/94 bütünlük, gerçek approved sayımı, golden manifest, boş/lisans engelleri ve mevcut baseline ölçümü.
Aşama B: **4 cam kategorisi önce**, her biri kendi alt gruplarıyla:
1. Cam Tablo Dikey — 60x90 dik; cam kalınlığı, gerçek maske/baskı alanı, yansıma.
2. Cam Tablo Yatay — 60x90 yatay; güçlü perspektif ve baskı kenarı.
3. Cam Doğrama — 25x35; yeni varsayılan fiziksel H, eski APPROVED V korunur; yatay/çapraz açı, ön plandaki nesne ve occlusion.
4. Ocak Arkası — şeffaf, siyah, beyaz, desenli; fayans/derz/dolap/davlumbaz, hayalet yansıma, ocak var/yok ve düşük kontrast zor örnekler.
İlk cam turundan sonra insanın bakabileceği **ARA CAM SONUÇ GALERİSİNİ oluştur**, aynı tek göreve devam et; görsel QA kararını otomatik PASS sayma.
Aşama C: diğer kategorilere geç:
5. Wi-Fi Kutusu — dış 40x30 cm, 12 cm İÇ derinlik, ince sağa kayan MDF kapak; dış kutu ile baskı yüzeyi ayrımı.
6. Ahşap Tablo — 50x70; çerçevenin dışı ile tasarımın basıldığı İÇ alan ayrımı.
7. PETEK — dört köşeye zorlanmaz; kapak konturu, üst/alt bağımsız kavisler, gerçek havalandırma delikleri, occlusion ve deliklerin baskıyla kapanmaması için maske geometrisi.
Aşama D: kazanan tekil ve hibrit motorları bütün 7 kategoride yeniden test; ayrı sahne aileleriyle kör holdout; hata/yanlış kabul, görsel kalite, hız, VRAM, maliyet ve güvenli ret. Yalnız deney adayı olarak adaptif category/surface router üret. Canlı üretime bağlama.

## 4. Testte GERÇEK ve çeşit çeşit şablon zorunluluğu
Her kategoride gerçek onaylı ve görseli doğrulanmış **farklı sahne/şablon ailelerinden** mümkün olduğunca çok örnek seç; önerilen pilot hedef her cam kategorisinde 20+ farklı gerçek sahne, diğer kategorilerde 12+ farklı gerçek sahne; veri yoksa **gerçekte bulunan tüm uygun örnekleri** ölç ve INSUFFICIENT_GOLDEN yaz, örnek uydurma. İzinli onaylı örnek sayısı yetersizse otomatik etiketsiz fotoğrafla başarısızlığı ölç ama onu ground truth sanma; kullanıcının sonradan incelemesi için sıraya koy.
Zorunlu varyasyon matrisi: siyah/beyaz/şeffaf/desenli; parlak/mat; net/yansımalı; sert/yumuşak/gün/akşam ışığı; açık-koyu mutfak; fayans/derz/kabin/pencere karmaşası; hafif/şiddetli perspektif; yakın/uzak/küçük panel; yatay/dikey/çapraz; cam kenarı görünür/kısmen kapalı/görünmez; önde tencere/nesne; siyah/şeffaf dış padding; bozuk kaynak; ürün bulunmayan zor negatif; aynı mutfağın çok tasarımlı türevleri. Her alt grup sayısını raporla. PETEK'te değişken delik sayısı, üst-alt kavis, öndeki nesne, beyaz benek, çıktı maskesi ve ışık.
Train/val/test rastgele dosya bazında değil **source template + scene family** bazında ayrılır; yakın benzerlik/perceptual hash ile sızıntıyı denetle. Augmentation yeni bağımsız gerçek sahne değildir. Çok tasarımlı aynı şablonlar aynı kümede; holdout kullanıcı onayı verilmeden parametre ayarına GİRMEZ. İlk pilot için sabit seed ve önceden belirlenmiş seçim; keyfi en kolay görüntüleri seçip başarı iddia etme. Test raporunda seçilenleri ve dışlananları nedenleriyle göster. Kritik az veri varsa iki bağımsız insan köşe uyuşması ölçümü veya MANUAL_QA_REQUIRED.
Testleri yalnız tek kez şans eseri başarılı göstermeme: en az 3 kontrollü seed / yeniden başlatma tekrarları (deterministik algoritmalarda aynı giriş-hash/sürüm determinism), farklı orijinal çözünürlük, yeniden ölçekleme ve aynı şablonun farklı sanat baskılarıyla geometri tutarlılığı. Holdout sonuçlarında cherry-picking yasak.

## 5. 94/94 aday için görünür uygulama ve deney matrisi
Tek bir METHOD_LEDGER.json / CSV / HTML oluştur: ID, grup, kaynak, teknik, tür (model/yardımcı/sistem kararı/metrik), gereklilik, resmi kaynak, gerçek checkpoint, ticari lisans+dependency, GPU/CPU/VRAM, kategori, kullanılan test görüntüsü ID/scene group, koşu seed'i, model/hash, ölçülebilir çıktı, status, failure reason, süre, galerideki karşılaştırma kartı, maliyet ve deney kanıtı. Hiçbir ID kaybolmasın. Tüm uygulanabilir teknikleri dene, ancak aynı yöntemin beş adını ayrı zafer diye sayma; aile/ablation matrisi ekle. Sonuç durumları en az: NOT_STARTED / FEASIBILITY_PASS / TESTED_PASS / TESTED_FAIL / BLOCKED_LICENSE / BLOCKED_MODEL / BLOCKED_DATA / BLOCKED_ENV / NOT_APPLICABLE; her başarısız/girilemeyen deney için neyin eksik olduğunu açık yaz. 'Test edildi' demek için gerçek yürütme/log/örnek sonuç zorunlu.
Başlangıç aileleri:
- APPROVED tekrar kullanım, SHA+pixel hash, kaynak metadata/PSD/JSON/homografi, ORB/AKAZE/SIFT+RANSAC, LightGlue+ECC doğrulanmış geometri aktarımı.
- Canny, Hough, LSD/EDLines/ELSD, contours, approxPolyDP, convex hull, min-area quad, gradyan/LAB/HSV, CLAHE, bilateral, Gabor, frequency texture suppression, RANSAC çizgi uydurma.
- Ghosting, reflection prior, local autocorrelation/phase correlation (optik katkı ayrı; faz korelasyonu subpixel corner kanıtı değildir), perspektif/vanishing/Manhattan, normal/depth/plane fitting PPI-OET; fizik iddiaları doğrulanmamış varsayım olarak test edilir.
- YOLO Pose/Seg, RTMPose/HRNet, Keypoint R-CNN, Mask R-CNN/Detectron2/MMDetection/MMSegmentation, RT-DETR + özel keypoint kafa, küçük özel panel detector, görünürlük keypoint; pretrained ağırlığın Ocak Arkası 4 köşeyi doğrudan bildiğini varsayma.
- SAM 2/3/3.1, MobileSAM, FastSAM, GEM, GlassWizard, Grounding DINO/Grounded-SAM, OWLv2, Florence-2, CLIP/DINOv2, Trans10K-v2, VGGT_GLASS/TransNormal ve mümkün diğer cam odaklı yaklaşımlar (müsait checkpoint/lisans olmadan PASS YOK).
- AI→ROI→Canny/RANSAC/line intersection, joint mask+edge+corner, partial edge completion, boundary uncertainty, hard negatives, candidate ranking, cascade, ensemble disagreement, active learning, adaptive routing.
YOLO/Ultralytics AGPL/Enterprise, SAM3 özel lisans, checkpoint ve model-specific kullanım hakları, Depth Anything V2 Small vs büyük ağırlık lisans ayrımı; lisansı doğrulamadan kurumsal kullanım PASS değil. RT-DETR standart bbox ağının pose çıkışı hazır değildir. Qwen PPI-OET normal haritasının mm cam çıkıntısını kesin gösterdiği iddiası ve gizli köşeleri kesin bulma iddiası FİZİKSEL GARANTİ DEĞİLDİR.
Kurulum: model bazında kilitli Python/CUDA/PyTorch/ONNX venv; RTX3060 Laptop için nvidia-smi gerçek VRAM ve driver; disk limit, VRAM OOM kurtarma; offline test; WSL yalnız ihtiyaç olduğunda. Hazır 4K Real-ESRGAN/Vulkan ile bağımlılık çakıştırma. Modelleri birbirine rağmen aynı aktif Python'a pip install etme. Kısıtlar test doğruluğunu gizlemesin; gerçek engeller raporlansın.

## 6. Sonuç metrikleri — 'doğru nesne' ve 'doğru baskı' ayrı
Aynı görüntüde aynı target tanımıyla kıyasla; TL/TR/BR/BL kaynak piksellerinde ortalama, medyan, P90/P95, MAX köşe hata; görüntü ve panel diyagonaline normalize hata; homography warp reprojection ve quad IoU; printable mask IoU ve visible mask IoU ayrı; yanlış nesne, panel yokken false positive, missed panel, küçük alan filtresinin gerçek küçük paneli reddi, occluded/inferred corner ayrı; son baskının ürün dışına taşan piksel sayısı/alanı; öndeki nesnelerin bozulması, dışarıdaki piksel eşitliği; tasarım değişmezliği; farklı çözünürlük ve seed kararlılığı; model kalibrasyonu, selective risk–coverage, AUTO_ACCEPT oranı ve onun hataları, REVIEW_REQUIRED sayısı; P50/P95 süre, soğuk model yüklemesi, GPU VRAM/RAM ve toplam iş maliyeti. IoU tek başına kalite değildir; düşük yanlış kabul öncelikli.
Dört köşe başarı skoru asla sadece confidence>0.85 veya en yüksek softmax demek değil; doğrulanmış ayrı kalibrasyon. Farklı modellerin skorlarını doğrudan birbirleriyle karşılaştırma. Tam görünmeyen köşe işaretini 'observed' gibi gösterme. Panel yoksa null-corners sonucu normal ve bazen doğru karardır. Altın veri yoksa ACCEPTANCE=INSUFFICIENT_GOLDEN.

## 7. KULLANICININ GÖZÜYLE DEĞERLENDİREBİLECEĞİ ZORUNLU GÖRSEL GALERİ
Her koşudan sonra yalnız sayısal CSV DEĞİL, tüm test edilen modellerin kıyaslandığı **yerel, offline açılabilir HTML karşılaştırma galerisi** hazırla (INDEX.html; dış servise bağımlı değil). Kullanıcı çift tıklayıp açabilsin; tercihen merkez arayüzünde 'Algoritma Karşılaştırma / Test Görselleri' bağlantısı yalnız deney modunda açılabilsin, mevcut çalışan arayüzü değiştirmeden.
Her farklı gerçek test örneği için:
A. Orijinal şablonun tam görüntüsü (altın referans yoksa açıkça);
B. İnsan-onaylı doğru dört köşe ve ayrı printable/outer/visible sınırlar;
C. Mevcut OpenCV baseline üst üste bindirme;
D. Test edilen **her model/yöntemin** ayrı overlay sonucu + 4 TL/TR/BR/BL işaret, özgün image hash, metode ID, sahne kategorisi/yüzey tipi, speed/VRAM, IoU, köşe hatası, AUTO/REVIEW/NO_DETECTION, yanlış nesne ve neden;
E. En iyi aday/hibrit ve final baskı tasarımının ürün üzerine gerçek kompozisyon sonucu; okluzyon/yansıma/maskeyi ayrı gözle gör;
F. Yan yana fark büyütme/zoom, köşe yakın plan 4 crop, kenar kırpma, hata heatmap veya difference-mask (kanıt, salt dekorasyon değil);
G. Şablon başına tüm yöntemler için karşılaştırma panosu ve global worst-case / yanlış nesne / düşük kontrast / başarısızları **otomatik filtreleyen** görünüm.
Filtreler: kategori (7), şeffaf/siyah/beyaz/desenli, ışık, perspektif, occlusion, algoritma/versiyon/seed, PASS/FAIL/REVIEW, real/synthetic, holdout/val. Kaynak, GT, tahmin ve 3:4 son baskı basit anlaşılır Türkçe açıklamalarla. Her kategori için camlarda hem ara galeri hem final galeri; yedi kategori final. İnsan örnekleri rastgele değil tümünü görebilmeli; kapak sayfasında özet, tam galeride tüm örnek ID'leri. Seçilmiş 'güzel' sonuçlar kadar hata örnekleri de göster.
'Gözümle karar' için kullanıcı işaretlesin: DOĞRU / YANLIŞ / ŞÜPHELİ, yanlışsa neden, not ve hangi köşe/maske hatalı; onayları sadece izole human_visual_reviews.json içine kaydet, production APPROVED'e otomatik yazma. Görseller özel olduğundan galeri **yerel diskte**, GitHub'a/publik CI artifact'a koyma. Kullanıcıya tam yerel klasör yolu, INDEX.html, galeriyi açan Windows BAT, ekran örneği ve istenirse kişisel paylaşım için seçilmiş güvenli paket hazırla. Görsel galeriyi gerçekten üretmeden bitti deme.
Görsellerde eski referans yanlışsa baseline karşılaştırmasını buna göre açıkça uyar. Görevin insan QA etabında CANDIDATE_READY_FOR_HUMAN_QA durumuna gelmesi mümkündür; insan kararını uydurma.

## 8. Üretim mimarisi deneyi ve rapor
Önce varsa onaylı doğru geometriyi kullan; kaynak metadata'dan geometri veya doğrulanmış türev aktarımı ikinci; yeni sahnelerde önce hedef panel var/yok + doğru nesne, sonra köşe/maske/sınır; seçicinin düşük kanıtta 'yok/inceleme' deme hakkı olacak. Her kategoride bazı modeller kazansın, PETEK mask-only olabilir. Kullanıcı görmek için kategori algoritma kazanan raporu + sorun sınıfı çözüm raporu + adayların kombinasyon kazanımı öncesi/sonrası karşılaştırması. Adayların ortalaması rastgele alınmaz; bağımsız kanıtla doğrulanır. Üretime otomatik yükseltme yok; ayrı GO/HUMAN_QA kararı gerekir.
Zorunlu kalıcı belgeler: METHOD_LEDGER_94.json/csv, source/GOLDEN read-only envanteri (gizli satırlar içermez), dataset splits ve source SHA + scene_group_id manifest (public değil), gerçek/sentetik ayrı test sonuçları, model/checkpoint lisans-env hash, deneme logları, hata atlası, skor/başarı matrisi, kategori yedi ayrı rapor, cam ara galeri ve yedi kategori final HTML galerisi, source hash karşılaştırma ve APPROVED değişmezlik testi, git private-scan, örnek görsel inceleme formu, son RELEASE=EXPERIMENT_ONLY / PENDING_HUMAN_QA. Her tablodaki raporu görüntü ve kullanıcı kararıyla bağla.

## 9. STOP/GO ve doğruluk denetimi
Tek komutta laboratuvarı **kur, uygulanabilir 94 kaydı değerlendir, tüm çalıştırılabilir teknik aileleri test et, görselleri gösterilebilir şekilde üret, yedi kategori kapsamına geç ve final adayları bilimsel olarak sıralamaya kadar devam et.** Bir bağımlılık engelinde kalan bağımsız deneyleri sürdür. İzin/lisans/erişim eksiği olduğunda yalnız o deney BLOCKED; diğer yöntemlere devam. Sonuç yoksa başarı uydurma. Kullanıcının cihazı üzerindeki VS Code Copilot izinleri ve GUI tıklamaları bu Issue ile teknik olarak kendiliğinden verilmiş olmaz; erişim gerekiyorsa gereken en dar izni açık yaz.
GÖREVİN BİTTİ SAYILMASI için: 94/94 ledger; dört cam ve diğer üç kategori/PETEK gerçek farklı şablon sayısı; tüm çalıştırılabilir seçeneklerin somut sonucu veya dürüst BLOCKED; **tüm yöntemlerin sonuçlarını görebileceği offline HTML galerisi**; yanlış/iyi örnekler; bağımsız holdout; veriye sıfır zarar kanıtı; kullanıcının gözle kalite onayı için hazırlanmış arayüz; mevcut V4.6 PR #52 hiç durdurulmamış/değiştirilmemiş. Onaysız main merge yok.

## Tetikleme sınırı
Bu görev metni GitHub'da hazırlanıp ISSUE olarak kaydedilir; yerel VS Code Copilot ajanının otomatik çalıştırıldığını göstermeye tek başına yetmez. Tetikleme sırasında kullanıcı Copilot'a ISSUE URL'sini/tek komutu vererek agent modunu başlatır; gerekli yazılım izinlerini VS Code arayüzünde kullanıcı verir.