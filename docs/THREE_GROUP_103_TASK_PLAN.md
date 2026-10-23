# GÖRSEL ÜRETİM MERKEZİ — 103 MADDELİ 3 GRUP PLANI

Kanonik temel: V4.3 ZIP / GitHub PR #41; 7 kategori çoklu gerçek Windows üretimi kullanıcıca başarılı bulundu. Eski V4.2.2 çalışan sürümü korunur.

**Kritik:** Kod var ≠ kullanıcı Windows testi PASS. Görev kutuları ancak test kanıtıyla kapatılır.
# İş grupları ve tüm madde kimlikleri

## Grup 1 — Kullanıcı arayüzü, yedi kategori üretim, optik, Excel, 4K ve e-ticaret çıktıları
Durum: BAŞLADI. V4.3 cam/Excel/quad özellikleri korunur; V4.4 aday arayüz sadeleştirme ve opsiyonel Real-ESRGAN kodları eklendi. Gerçek GPU/Windows ve bulut testleri bekliyor.

- [ ] **001** — Eski 10 şablonlu ana düğmeyi kaldır; kaynak referansını koru
- [ ] **002** — Yedi kategori tek ana üretim girişi
- [ ] **003** — Eski PETEK ayrı üretimi yedek gelişmiş alana taşı
- [ ] **004** — Eski inceleme sunucusu durdurmayı gelişmiş alana taşı
- [ ] **005** — İnceleme/kurulum/kayıt/çıktı teknik düğmelerini grupla
- [ ] **006** — Gelişmiş alan içinde kurtarma, kayıt denetimi, eski araçlara erişim
- [ ] **007** — Üretim sonrası isteğe bağlı 4K AI yükseltme
- [ ] **008** — Yedi kategori batch sonrası Real-ESRGAN motor bağlantısı
- [ ] **009** — Varsayılan 4K kapalı ve kullanıcı onaylı
- [ ] **010** — 4K asıl görsellerden ayrı klasör ve kimlik
- [ ] **011** — 3:4 hedef 2880×3840 ve format kararı
- [ ] **012** — Exe, model, Vulkan/GPU, tile ve RAM ön kontrolleri
- [ ] **013** — 4K başarısız olsa bile normal render korunması
- [ ] **014** — Model bazlı A/B yazı, çerçeve, delik ve renk doğruluğu
- [ ] **015** — 4K çıktıların SKU ve Excel'e bağlanması
- [ ] **016** — Çıktı reçetesinde 4K model, efekt, sürüm ve çıktı SHA
- [ ] **017** — Merkez ve yardımcı pencerelerde tek sürüm kaynağı
- [ ] **018** — Her seçenek için ne yapar/ne değiştirir/nereye yazar açıklamaları
- [ ] **019** — Cam Dikey gerçek açık/kapalı kalite testi
- [ ] **020** — Cam Yatay gerçek açık/kapalı kalite testi
- [ ] **021** — Cam Doğrama occlusion ve cam yansıma testi
- [ ] **022** — Ocak Arkası mutfak ışığı ve cam yansıma testi
- [ ] **023** — Beyaz/açık baskıda cam optik görünürlük
- [ ] **024** — Koyu baskıda aşırı parıltı olmaması
- [ ] **025** — Maske dışı kaynak piksellerin birebir korunması
- [ ] **026** — Cam efektleri açık/kapalı çıktı ve reçete farkı
- [ ] **027** — A/B gerçek baskılı önizlemenin Windows kabulü
- [ ] **028** — ImgBB/FreeImage gerçek HTTPS görsel linki
- [ ] **029** — Excel ürün/SKU doğru Resim Linki eşleme
- [ ] **030** — Excel linklerinin internette açılması
- [ ] **031** — PETEK dahil 7 kategoride bulut URL kontrolü
- [ ] **032** — Eski renderları yeniden üretmeden linkleme
- [ ] **033** — Upload tekrar/başarısızlık/idempotency geri dönüşü
- [ ] **034** — Eski Excel ticari kolonları/SEO boşluklarının kapanışı
- [ ] **035** — Onaylı köşeyi tekrar kaydet-APPROVED-üretim testi (Seçenek B)
- [ ] **036** — Önceki/yeni quad transaction denetimi ve eski SKU korunması
- [ ] **037** — Cam köşe yuvarlatma şablon editörü entegrasyonu
- [ ] **038** — 415 MP büyük JPEG güvenli proxy ile Windows testi
- [ ] **039** — Büyük PNG/WebP/alpha/bit-depth güvenli işlem desteği
- [ ] **040** — Tek bozuk tasarım tüm batch'i durdurmasın
- [ ] **101** — SEO metin/barkod/varyant ortak ticari Excel bütünlüğü
- [ ] **102** — Çoklu mağaza/pazaryeri export profilleri
- [ ] **103** — Üretim başarı hızı/başarısızlık/disk operasyon paneli

## Grup 2 — Dört köşe, şablon yaşam döngüsü, PETEK, kalite ve bütün eski araçlar
Durum: SIRADA. Koruma hedefi: onaylı 4 köşe, kullanıcı maskeleri ve 6+PETEK orijinallerine sessiz müdahale yok. Deneysel SAM/AI yalnız özel test dalı.

- [ ] **041** — Çoklu onayda her şablonun kendi köşesini koru
- [ ] **042** — Geçerli küçük dörtgeni kabul, bozuk self-intersect'i ret
- [ ] **043** — Onaylı geometri, yön, maske yeniden açılınca aynı olsun
- [ ] **044** — Onaylı revizyon diğer şablonlara dokunmasın
- [ ] **045** — Yeni Cam Doğrama H, eski onaylı V korunumu
- [ ] **046** — Şablon değişiminde eski önizleme/f5 yarışı ortadan kalksın
- [ ] **047** — Klasör tarama ilerleme/sayaç/özet/bitir
- [ ] **048** — Tarama sırasında edit, durdurma sonrası kısmi kalıcılık
- [ ] **049** — KONTROL_GEREKENLER içinden seçmeli tekrar tarama
- [ ] **050** — Kategori/şablon adetleri ve onay durumları
- [ ] **051** — Kopyalanabilir anlaşılır Türkçe hata/uyarı
- [ ] **052** — Beyazlat/Orijinale Dön/Ham Orijinal restore işlevleri
- [ ] **053** — Ocak Arkası missing WORKING PNG restore gerçek Windows
- [ ] **054** — Çalışma-orijinal havuz sayıları read-only fark raporu
- [ ] **055** — Hatalı Wi-Fi 26–35, 44, 57–66 yeniden kontrol
- [ ] **056** — Cam/şeffaf yüzey öncelikli otomatik köşe tespiti
- [ ] **057** — Resim dışındaki siyah alanı geometri algısına katmama
- [ ] **058** — Maske/fırça/zoom/undo onay koruma regresyonu
- [ ] **059** — 7 kategori kalıcı numaralandırma son/sıradaki sayı
- [ ] **060** — Aynı ad/uzantı/135 leading-zero geçmiş tutarlılığı
- [ ] **061** — Bağımsız araçların tamamı için smoke ve bağlantı
- [ ] **062** — Yataydan 3:4 blur/mozaik/kategorize aracı
- [ ] **063** — PETEK gerçek havalandırma delikleri sabit sayı değil
- [ ] **064** — Üst-alt bağımsız PETEK kavis düzenleme
- [ ] **065** — PETEK fırça sınır clip ve Ctrl+Z
- [ ] **066** — PETEK benek onarımı delik/ahşap koruma
- [ ] **067** — PETEK ışık/gölge/beyaz bant/sağ-alt QA
- [ ] **068** — PETEK kapalı/microbleed/5mm/10mm A/B
- [ ] **069** — 34+ PETEK Golden Dataset ve önce/sonra
- [ ] **070** — Wi-Fi 40×30, 12 iç derinlik, MDF kapak sahne ölçeği
- [ ] **071** — Dikey/Yatay Cam Tablo 60×90 yüzey kenarı
- [ ] **072** — Cam Doğrama 25×35 yatay/tezgah/occlusion
- [ ] **073** — Ocak Arkası panel mutfak/doku/cam kalınlığı
- [ ] **074** — Ahşap Tablo 50×70 çerçeve ve mat doku
- [ ] **075** — H/V master cover/contain/bleed kaynak esnetmeme
- [ ] **095** — Real-ESRGAN karşı SwinIR/HAT A/B benchmark
- [ ] **096** — SUPIR lisans/halüsinasyon nedeniyle deneysel araştırma
- [ ] **097** — SAM/Grounded-SAM/OpenCV deneysel golden kıyas
- [ ] **098** — Canva benzeri akıllı maskeleme alternatifini benchmark
- [ ] **099** — Görsel kalite skoru/tekrar sahne/sınıflandırma
- [ ] **100** — Lifestyle şablon otomasyonu üst pipeline araştırması

## Grup 3 — Kalıcı kuyruk, veri güvenliği, Windows dayanıklılığı ve nihai kabul
Durum: SIRADA. Bütün kabul şartları kanıtla PASS yapılana kadar ticari GO kapalı. Ana sürüm birleştirme yalnız sonra.

- [ ] **076** — 100/200/1000 gerçekçi/sentetik iş batch testi
- [ ] **077** — İki kez kill/restart/kesinti toparlama
- [ ] **078** — Elektrik/disk/izin/eksik dosya dayanıklılığı
- [ ] **079** — İki Windows süreç SKU/SQLite kilit çakışmazlığı
- [ ] **080** — Başlat/duraklat/güvenli durdur/devam kalıcı durumlar
- [ ] **081** — Kaynak/maske/quad/recete/SKU/Excel SHA audit
- [ ] **082** — Eski SKU overwrite olmadan idempotent üretim
- [ ] **083** — Aynı ad farklı SHA ve JPG/PNG çakışma güvenliği
- [ ] **084** — APPROVED dışı/yanlış yön/yanlış SHA fail-closed
- [ ] **085** — SQLite online backup/integrity_check/restore provası
- [ ] **086** — OneDrive dışı SQLite geçişi yalnız yedek/onayla
- [ ] **087** — Factory Doctor Python/NumPy/Torch/CUDA gerçek ortam testi
- [ ] **088** — Sabit bağımlılık Python/OpenCV/NumPy temiz setup
- [ ] **089** — Flask 8080 port/PID/DB çakışma testleri
- [ ] **090** — Offline/Unicode/izin/rollback Windows testleri
- [ ] **091** — Tek final Windows ZIP ve manifest/SHA/rollback belgeleri
- [ ] **092** — GitHub kanonik docs/PR/CI/Windows kanıt güncellemesi
- [ ] **093** — Tarihî #15–#24 ve #29–#40 kanıt uzlaştırma
- [ ] **094** — GitHub public kaynak gizlilik/anahtar/fotoğraf denetimi

## Sıra ve kesin kurallar
1. Grup 1 kod/regresyon + gerçek Windows UI/Excel/4K kabulü.
2. Grup 2 aynı kaynak dalı üzerinde veya yeni güvenli dalda şablon/PETEK/araç kapanışı.
3. Grup 3 yüksek hacim/kesinti/SQLite/tek Windows kurulum ve gerçek kabul.
4. Üç grubun kabulünden sonra tek kanonik Windows ZIP; varsa EXE ayrıca gerçekten test edilir.
5. Her aşamada commit, PR, SHA manifesti, test kanıtı ve sonraki ajan devir notu.
6. Canlı DB, onaylı köşeler/maskeler/orijinal görseller GitHub’a gönderilmez, izinsiz overwrite edilmez.
7. 4K AI çıktısı ayrı create-only dosya; bulut görselleri ancak ayrı açık onayla.
8. İşlevi olmayan butonla sahte başarı bildirimi yasak.
