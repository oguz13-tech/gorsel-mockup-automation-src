# COPILOT DENEY GÖREVİ — İLK FAZ TASLAĞI / ONAY İÇİN

**Bu belge yalnız hazır taslaktır; Copilot'a gönderilmiş değildir ve hiçbir GitHub değişikliği yapılmamıştır.**

## Amaç
Görsel Üretim Merkezi V4.6 uygulamasının Ocak Arkası, Cam Doğrama, diğer beş kategori (PETEK özel maske) için, 94 araştırma kaydını kapsayan tekrar üretilebilir ve gizli verileri koruyan bir karşılaştırma laboratuvarının temelini oluştur. **İlk görev kapsamı: yalnız ENVANTER, GOLDEN KÜME TASARIMI, MEVCUT BASELINE, KODSUZ FİZİBİLİTE/KAYNAK KONTROLÜ.** Yeni AI modellerini henüz kurma veya eğitim başlatma.

## Sınırlar
1. Çalışan V4.6 final adayı/PR #52, #35 kabul hattı ve yedi kategori üretimini bozma. Ayrı branch + izole worker + bağımsız venv.
2. `C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu` içinde **hiçbir yazma**; SQLite ve onaylı geometri salt okunur snapshot; görüntü SHA, APPROVED durum, `manually_verified`, template_uid ve image version doğrula.
3. Canlı source görüntülerini, SQLite, müşteri fotoğrafını, API secrets ve çıktılarını PUBLIC GitHub'a/CI'ye gönderme.
4. Geçmiş 591 profil satırını gerçek APPROVED sayısı diye raporlama; yalnız doğrulanan eşleşmeleri say.
5. Altın veriler görünür dört köşe / çıkarımsal köşe / printable_surface / outer_surface / visible_surface / mask ayrımına tabi.
6. Tüm 94 aday değerlendirme envanterinde bulunacak; gereksiz kopya testlerinden kaçınmak için aile bazında grupla. Her adaya `NOT_TESTED`, `FEASIBILITY_PASS`, `BLOCKED_*` vb. gerekçeli durum ver; sessiz eleme yok.
7. Gerçek Golden ayrılmadan veya baselines raporlanmadan model eğitimi, lisanslı ağırlık kurulumu veya final üretim motoru değişikliği YOK.

## Çıktılar
A. 7 kategoriye göre gerçek doğru onaylı/aktif/SHA eşleşen kayıtların ve varyant/sahne ailesi sayısı (özel görüntüleri yayımlamadan).
B. `source_image_hash`, `scene_group_id`, `template_id`, `approved_revision`, `quad target`, `visibility`, `mask`, `copyright/source` alanlarını içeren sadece izole veri seti manifest sözleşmesi.
C. Mevcut OpenCV/template_intelligence baseline (sentetik ve gerçek ayrı) ve hatalı örnek tipleri; küçük ROI, zor fayans, transparency, hard negatives.
D. 94 aday JSON için kayıt/teknik mümkünlük tablosu, resmi link, checkpoint lisans, VRAM, Python/Windows/WSL, eksik etiket, expected output bbox/mask/keypoint/registration/proposal, test maliyeti.
E. Test protokolü, metrikler ve kategoriye özel karşılaştırma; PETEK maske/kavis/yarık ayrımı.
F. Onaylı DB ve kaynak SHA değişmezlik kanıtı, git diffinde özel dosya olmadığının taraması.
G. Ayrı gerçek ölçüm yoksa `INSUFFICIENT_GOLDEN`, kapalı görüntüye erişim yoksa `BLOCKED_PRIVATE_DATA_ACCESS`.

## Karar kapısı
Faz 0/1 verileri ve baseline raporuna göre hangi model ailelerinin nasıl çalıştırılacağına **sonraki ayrı görevde** karar verilecek. Rastgele model indirme, ana Windows Python ortamını değiştirme veya Github main merge yok.