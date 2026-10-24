# V4.6 — COPILOT AGENT'E TEK SEFERLİK TAM KAPSAMLI FİNAL GELİŞTİRME EMRİ
**24 Ekim 2026 | Repo:** oguz13-tech/gorsel-mockup-automation-src | **PR:** #52 (DRAFT) | **Dal:** feature/v46-safe-consolidation-20261024
**Önce bunu uygula.** Bu emir, daha önceki PR ve issue'ları, 103 maddelik planı, V4.5 durum matrisini, V4.6 Windows testlerini ve son kullanıcı değişikliklerini birlikte kapsar. Yeni bir proje başlatma; çalışan mevcut sistemi bitir.

## A. AMAÇ, ÇALIŞMA ŞEKLİ VE TESLİM SÖZLEŞMESİ
Bir programcı asistanı gibi *gerçek* mühendislik yap: mevcut kodu ve son doğrulanmış kaynakları uzlaştır; kalan bütün işlevleri uygula, kendi otomatik testlerini oluştur/çalıştır, bulduğun hataları düzelt, tekrar test et, Windows'ta izole kurulum testi yap, sonunda **TEK kurulum adayı ZIP** + SHA256 manifest + test raporu + kullanıcı kılavuzu teslim et. Yalnız analiz veya yapılacaklar listesiyle DURMA. Gereksiz soru sorma; güvenli mühendislik tercihini kendin yap. Bütün sonuçları PR #52'ye küçük mantıklı commit'lerle aktar, PR **DRAFT** kalsın, MAIN'e merge etme.

Kullanıcı kodlama bilmez. İngilizce terminal komutu, karmaşık merge kararı, PID kapatma gibi şeylerde kullanıcıyı onay vermeye zorlama. Günlük teknik onayı kullanıcıdan istemek yerine yalnız çalışma kopyasında düşük riskli işleri bitir. Sistem/VS Code izinleri ayrı kalır: onları atlatmaya çalışma. Bir izin otomasyonunu engelliyorsa bunu nihai raporda BLOCKED/NEEDS_HOST_AUTH olarak kaydet ve diğer bağımsız işlere devam et. "Allow All / YOLO" önermeyi bırak. İnsanın görmesi zorunlu olan karar sadece son gerçek Windows ürünü/görsel kabulüdür.

**Asla sahte final iddiası yok:** Kodun varlığı, simülasyonun PASS olması ve kullanıcının gerçek Windows görsel onayı farklıdır. Otomatik test sonucu, Win11 izole test sonucu ve kullanıcı canlı kabulü ayrı sütunlara yazılır. Kullanıcının cihazında denenmeyen adımı 'canlı PASS' sayma. Gerçek dış servis/özel veri gerektiren işleri test-double ile test edip insan bağımlılığını açıkça göster.

## B. AŞILMAYACAK GÜVENLİK SINIRLARI
1. SADECE geliştirme kopyasını değiştir. Canlı kullanıcı kaynak kökü: \`%USERPROFILE%\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu\`; kurulu aday \`C:\GorselMockup_V46_ADAY\GORSEL_URETIM_MERKEZI_V46_4KOSE_TOPLU_YANSIMA_ESRGAN_WINDOWS_TEK_PAKET\`. Bu ikisinde **yazma/silme/taşıma/gerçek üretim/migration/recovery YASAK**. Kullanıcının mevcut V4.6 Copilot kaynak kopyasının konumunu açık VS Code workspace'inden doğrula; yalnız o klon veya ondan üretilmiş ayrık worktree ile çalış. Terminal ile dış dosyaya yazma yetkisi bulunması serbest kullanım anlamına gelmez.
2. Canlı 2 SQLite DB, onaylı insan dört köşeleri, PETEK maskeleri, orijinal/working/yedek görseller, eski/4K render, receipt/ledger/SKU geçmişi **immutable**. Asla otomatik APPROVED, otomatik restore, silme, overwrite, PR merge, \`git clean/reset --hard\`, \`taskkill /F\` veya sudo/admin hak yükseltmesi yapma. İsimleri aynı JPEG/PNG farklı SHA çatışmaları atlanmamalı.
3. GitHub PUBLIC repo: gerçek müşteri fotoğrafları, mockup kaynakları, DB, özel ZIP, kimlik/API key, gizli dosya, kişisel yol veya dosya içerikleri asla yükleme. Sentetik fixture ve anonim ölçüm tablosu serbest. Her push'tan önce branch, git status/diff ve secret/private-asset taraması. Push ancak PR #52'nin baş dalına; main, eski 22 PR, master, force-push, otomatik merge, release publish YOK.
4. Gerçek ImgBB/FreeImage upload ya da kullanıcıya ait fotoğrafı internete gönderme; sahte HTTP sunucusu/mock kullan. Gerçek kullanıcının mevcut dosyalarını bozmayan **kaynak kopyası** üzerinden örnek test yapabilirsin; özel test görsellerini public GitHub'a koyma.
5. Gerekiyorsa kullanıcı orijinal görüntülerini SALT-OKUNUR açıp, açık ve ayrı QA çalışma dizinine özel örnek kopyaları oluştur; hash kaydet; tüm görüntü manipülasyonlarını kopyada yap. SQLite'ın gerçek dosyasını açmak/yazmak yerine backup snapshot ya da üretilecek sentetik DB kullan. Orijinal dosya saklama yollarının içine çıktı üretme.
6. Kodu birleştirirken özelliği silme: eski araçlar, eski günlük akış, #9/#12/#13/#14/#26/#27/#28, 4 köşe tarihi ve onayları korunacak. Eksik yerel özel ZIP gerçekten yoksa 'entegre edildi' iddiasında bulunma; bu kanıt gerektiren ayrı satır olur.

## C. KAYNAĞIN DOĞRU OLDUĞUNU TESPİT ET — EN KRİTİK İLK İŞ
GitHub \`main\` eski; PR #52 V4.5 PR #48 HEAD \`35a04577294307b0c72452f0614776382e7965fd\` üzerinden başladı. Gerçek V4.6 Windows kaynakları GitHub'da tam olmayabilir. PR #52'ye Copilot tarafından yeni commit'ler de gelmiş olabilir; mevcut HEAD'i tekrar oku, önceki çalışmalarını ezme. VS Code yerel temiz V4.6 kopyasını **dosya hash + özellik farkı + test davranışı** ile PR #52'ye uzlaştır. *Körce eski V4.5'i yeni V4.6 üzerine kopyalama.* \`MERKEZ\`, \`SABLON_V2_MIMARI\`, \`PETEK_V3\`, \`TESTLER\`, başlatıcılar, 4K motor, Excel entegrasyonu, profesyonel araçlar gerçek dosyalarla eşleşsin.

\`docs/THREE_GROUP_103_TASK_PLAN.md\` ve \`docs/V45_103_MADDE_DURUM_MATRISI.md\` okunacak. #15–#24, #29–#36, #39–#44, #49–#51 ve eski açık PR'lar (özellikle #45–#48) EN AZ bir kez kapsam karşılaştırması için kullanılacak. Yeni kod yalnız çalışan modüllere uygulanacak. Dosya sayıları/tekil testler tarihsel sürüme aitse güncel canlı hakikatmiş gibi yazılmayacak.

## D. ÖNCEDEN DOĞRULANAN BAŞARILAR — GEREKSİZ TEKRAR ETME
- Windows V4.6 ana inceleme ekranı açıldı, toplu seçme ve "4 Köşesini Algıla (Taslak)" işlevsel; **otomatik geometrinin doğruluğu FAIL**. Onaylıyı değiştirmeden draft üretmek PASS.
- İnsan tarafından ayarlanan onaylı dört köşelerin kalıcılığı/gerçek render kullanımı PASS. İki SQLite yedek ve izole restore provası PASS.
- Real-ESRGAN resmi x4plus: NVIDIA GeForce RTX 3060 Laptop GPU, Vulkan 64x64 GPU_SMOKE_PASS; Cam Dikey gerçek 2880×3840 4K baskı görseli kalite PASS. Fast modeli eksik. Tekrar GPU kurulumu yapma.
- Geçmiş salt-okunur ledger: 708 template, 591 template_profiles satırı (aktif APPROVED sayısı **değil**); 111 receipt, 110 RENDERED, 1 REVIEW_REQUIRED; 75 verified, 35 missing, SHA mismatch 0, unsafe path 0. Kullanıcı bazı eski çıktı görsellerini alan açmak için sildi; nedenini 35 tekil dosyada kanıtsız kesinleştirme. Kayıtları silme/yeniden oluşturma.
- Dört cam kategorisi yansıma QA **FAIL** (haç / '+' sert simetrik yansıma, diğer kategorilerde eksik pencere/spot). Gerçekçi kullanım ve referans uyumu henüz sağlanmadı. Önceki PASS otomatik testleri görsel sonucu kanıtlamadı.
- PR #52'de 8080 geçişi modülü ve hedefli testler başlatıldı. Bu ancak gerçek V4.6 arayüzüne bağlanıp gerçek Windows testini geçerse kapatılır.

## E. İŞ PAKETLERİ — KOD + OTOMATİK TEST + GEÇERLİ KABUL
### E1 — Güvenli source entegrasyonu / sürüm
Bütün modülleri tek gerçek kaynak çizgisinde birleştir; PETEK ve altı diğer kategori birbirinin kayıtlarını bozmadan tek kullanıcı girişi üzerinden çalışsın. Dinamik kategori registry, menü bağlantıları, eski /tools ve bağımsız BAT'lar, testler, UI sürüm bilgisi, geri dönüş prosedürü dahil. Diğer dallardan kör merge yok. Yanlış veya eksik modülü açıkça BLOCKED kaydet.

### E2 — Dört köşe ve şablon editörü (Ocak üzeri cam panel dahil yüksek öncelik)
Çoklu seçimde köşeler karışmasın; küçük ama geçerli dörtgen kabul, self-intersect/çökmüş geometri ret; zoom/pan/undo/redo/fırça source coordinate; APPROVED tekrar açma, versiyonlama, önce/sonra kanıtı; yeni Cam Doğrama varsayılan fiziksel yönü H, geçmiş onaylı V korunur; Cam Doğrama öndeki nesne occlusion; orijinale dön/beyazlat/ham orijinal backup restore ancak SENTETİK veya izole kopyada; progress bar, listede kategoriler/adet, KONTROL_GEREKENLER içinden seçmeli tarama, işlem ortasında durup kısmi sonuç saklama, kopyalanabilir Türkçe mesaj. Kaynağı değiştiren restore mevcut onayı sessiz revalidate etmesin; source hash mismatch \`STALE_SOURCE_CHANGED\` ve REVIEW_REQUIRED.

**Ocak Üstü Cam Tablo / Ocak Arkası — ayrı süren zor problem:** Kullanıcı "ocak üstü cam tablo şablonlarının dört köşesini" otomatik doğru yakalamak istiyor. Kaynak isimlerinden hangi fotoğrafların gerçekten cam paneli, hangilerinin ocak arkası panel, hangilerinin Cam Doğrama olduğunu açıkça sınıflandır; kategori adlarını karıştırma. Bazı eski Ocak Arkası kaynakları tamamen siyah/bozuk ve panel görünmez; gerçek yüzey yoksa uydurma köşe çıkarma.

**Otonom geliştirme döngüsü:**
  1. APPROVED insan köşelerini yalnız source SHA'sı eşleşen fotolarla eşleştir; bunları ground-truth golden olarak kullan, asıl DB'ye dokunma. Özel test klasöründe kategori, yüzey siyah/beyaz/şeffaf/desenli, sert/yumuşak ışık, dar perspektif, yatay/çapraz panel, yansıma/occlusion, fotoğraf dışı siyah padding, panel yok/bozuk fotoğraf durumlarına böl. Veri azsa bunu açıkça belirt; sentetik variasyon üret ancak onları gerçek test diye sunma.
  2. Ground-truth'u train/tune ve daha önce görülmemiş holdout olarak ayır; test setinden parametre sızdırma. Ölç: homography-aware mask IoU, sıralanmış dört köşede mean/95p/max kaynak-piksel sapması ve görüntü diyagonaline oran, self-intersection sayısı, false-positive/no-panel, kontrol için REVIEW_REQUIRED oranı, algoritma çalışma süresi, CPU/RAM/GPU.
  3. Baseline mevcut TemplateAnalyzer; sırayla veya makul seçilmiş adaylarla: kaynak görüntü/crop-padded black exclusion, panel/cam bölgesi sınıflandırma, kontur/çizgi/Hough+perspektif, adaptive threshold/Canny/line intersections, segmentation/semantic/edge, RGB+alpha, gerektiğinde izin/VRAM/lisans uygun SAM/Grounded-SAM/OpenCV yeni sürümleri; tamamen yeni AI ağırlıkları indirip canlı makineyi değiştirme. Deneysel yöntemler izole ve opt-in.
  4. Her deneyde hypothesis → değişiklik → otomatik ölçüm → golden önce/sonra → başarısız örnekler → bir sonraki gerekçeli düzeltme. Aynı algoritmayı aynı görüntüde delilsiz sonsuza dek tekrarlama; bir fikir birkaç kez başarısızsa farklı yönteme geç. Başarılı adayın gerçek farklı mockuplarda transferini de ölç. Kalite kapısı olarak öneri: true-panel örneklerinin tümü geçerli dörtgen; IoU ≥0.98 (medyan) ve ≥0.95 (her bir kritik örnek), ortalama köşe hatası görüntü diyagonalinin ≤0.5%'i, kritik max ≤1%; false-positive "panel yok" sayısı 0. Bunları **öneri eşikleri** olarak raporla; ölçülmemiş PASS iddiası yok. Gerçek etiket azsa bu eşiklerde \`INSUFFICIENT_GOLDEN\`.
  5. Son çözüm tek çağrıda "Taslak Algıla"; confidence+neden; düşük güven \`KONTROL_GEREKENLER\`; asla otomatik APPROVED yapma. Kaynak dışı siyah alan değerlendirmeye alınmaz. SHA256+analyzer_version cache'i, aynı şablon yeni versiyonda tekrar etiketlenebilir, başka onaylı köşeler değişmez.
  6. Ocak panelinde başarı diğer altı kategorinin başarı kanıtı DEĞİLDİR. Wi-Fi kutusu, yatay/dikey cam, ahşap tablo, Cam Doğrama, PETEK ayrı kategori regression/golden görmeli. Gerçekçi "kusursuz" doğruluk kanıtı yoksa saklamadan \`HUMAN_REVIEW_REQUIRED\`.

### E3 — Cam efektleri ve yüksek kaliteli render
Cam Tablo Dikey/Yatay 60×90, Cam Doğrama 25×35 yatay/tezgâh ve Ocak Arkası gerçek mutfak camı. V4.5'te kaybolan pencere çıtaları/spotları ve V4.6'da çıkan sert simetrik haç efekti düzelt. *Gerçek fotoğraf referanslarına uygun* perspektif oturtulmuş pencere geometri/soft reflection, makul opacity ve glow, cam kenar/bevel, artwork detay koruma; ince cam kalınlığını bozmama. Efekt yalnız onaylı cam baskı alanında, öndeki nesneler mask üstüne korunur, maske dışı orijinal pikseller birebir. Açık/kapalı A/B; reçete/SHA kimliği ve create-only output farklı; açık/koyu baskı, her dört kategoride minimum 1 gerçek şablon × 2 farklı artwork görsel. Algoritma testi yanında görsel QA; 4/4 insan QA olmadan "gerçek final cam kalitesi" demek yasak.

### E4 — PETEK gerçek delik/kavis/maske/ışık
Sabit 13 yapay yarık geri dönmeyecek. Gerçek slot/delikler korunur; üst ve alt kavis tam bağımsız, işaretlenen noktaları izler, keybind Ctrl+Z/Y, nokta sürükle/sil, zoom/pan; full-resolution kaynak fırça, quad clip, kesintisiz coverage; ahşap dokusu karartısını delik sanıp maskeme, beyaz benek onarımı, sağ-alt artifakt/bant/halo QA; sahneye uygun ton/ışık/contact-shadow; 3:4 yatay/dikey tasarıma uyum, FILL/COVER/CONTAIN odak, çerçeve OFF/micro-bleed/5 mm/10 mm ancak bilinen fiziksel oranla. Mask=0 source pixel birebir. 34+ PETEK golden özel dosyalarda varsa izole A/B, yoksa sentetik FAIL/BLOCKED ayrımı.

### E5 — 4K / Real-ESRGAN ve görüntü bütünlüğü
Mevcut PASS motoru bozma. Dolu \`AI_Kalite_Artirici\` klasörüyle Windows x4plus kurulum hotfix'i kaynakta koru; sadece resmi dosyalar gerekli durumda güvenli kurulsun, model/EXE/hash/ZipSlip/yeniden kurulabilirlik ve GPU fallback testleri. Varsayılan 4K kapalı; kullanıcının açacağı 2880×3840 opsiyon, create-only normal PNG'yi bozmasın, 4K detay/çerçeve/yazı/artwork kalite metrikleri ve SHA; çıkış konumu kullanıcının bulacağı şekilde normal galeri yanında opsiyonel ve çakışmasız; eski 4K dosyası dokunulmaz. Gereksiz **AYRI \`4K_DOSYA_LINKLERI_*.xlsx\`** raporunun üretimini kaldır; **ticari pazaryeri Excel/HTTPS/SKU** asla kaldırma. Fast model yoksa sessiz kurulum vaat etme.

### E6 — Yedi kategoride tam ticari çıktı / bulut Excel
ImgBB/FreeImage HTTPS foto URL, PETEK dahil 7 kategoride doğru SKU → output SHA → Excel resim link satırı, marketplace kolonları, barkod, varyant/SEO, çoklu mağaza/pazaryeri profilleri, tasarım adları ve export; daha önce üretileni yeniden render etmeden izinli link güncelleme; duplicate/başarısız network/idempotency, çeşitli dosya türleri ve HTTPS açılabilirlik mock test; gerçek online test ayrı insana gerekli olarak raporlanır. Eski pazaryeri Excel formatlarını eksiltme; ayrı 4K yardımcı xlsx kaldırılması bu görevin dışında.

### E7 — Üretim motoru: yüksek hacim, SKU, SQLite ve bütünlük
Yedi kategori tek üretim girişi, dinamik geçerli APPROVED şablon keşfi; eski 10 özel pilot sınır değil. Kalıcı queue/status/pause/resume/stop, 1/10/100/200/1000 izole sentetik iş, geri açma/iki process/kilit/power/disk/crash testi, çıktı create-only/atomik/sha, yanlış yön/bozuk PNG/format/Unicode, 40MP/80MB/415MP güvenli proxy, büyük artwork tek bozuksa batch devam, aynı ad-farklı SHA ve .jpg/.jpeg/.png kimliği, 135/000135 numara ve duplicate SKU, store group, eski receipt idempotence. Foto/approved/mask değişince yeni reçete kimliği, eski dosya immutable; maliyet/disk/başarı paneli ve QA geri bildirimleri. SQLite canlı onaylı DB'yi değiştirmeden izole çalışma DB; offline backup, integrity_check, yalnız sentetik üzerinde restore tatbikatı, istenirse ileride kullanıcı onaylı migration. Missing 35 receipt gerçek dosyalarla path bazında kontrol edip \`MISSING_USER_REMOVED\` gibi yeni statüye kanıtsız geçirme; "daha önce çıktı vardı, şimdi yok" sayısını doğru göster.

### E8 — UI ve bütün profesyonel araçlar
Türkçe koyu tema, 5 aşama kullanışlı akış, fotoğraf/mockup ile baskı tasarımı net ayrım, 7 kategori/menü butonları gerçek işlevli, İnceleme Merkezi sol kategori/adet/dropdown, ayrı scan/restore/fırça/maske, kopyalanabilir hatalar, progress/bitiş özet, tararken başka iş, durdurulduğunda kısmi veri, listede seçilen toplu scan, kategori seçim, CAM DOĞRAMA varsayılan H, PETEK Excel ve üretim, dosya isimlendirme/format/filigran/3:4 blur-mozaik/SEO/linkleme bütün eski bağımsız araçlar. Zoom, DPI 900x720/1366x768, mouse ve klavye. 8080 old server'da aynı sürüme doğru yönlendirme, eski V4.x sunucusunda yalnız açık kullanıcı onayıyla iki aşamalı güvenli stop; diğer süreçler asla kill edilmez, PID reuse denetlenir.

### E9 — Platform / paket / geri dönüş / güvenlik
Python/OpenCV/NumPy/Pillow/Tk/Flask ve ihtiyaç duyulan CUDA/Vulkan gerçek sürümlerinin pin/doctor testleri; dış VDS yok, normal Windows çift tık launcher; Unicode/OneDrive/offline/disk dolu/8080 dolu Windows izolasyon testi; dosya/DB yedek envanteri ve RESTORE izole prova, taşınabilir root path; eski final çalışma alanlarına dokunulmadı raporu. 103 madde, eski #15–#24, #29–#36 ve #39–#51 içindeki bilinen gereksinimler kaybolmasın; deneysel SAM/SwinIR/HAT/SUPIR yalnız lisans/donanım ve somut golden kazanım varsa opt-in, mevcut üretimi bozarak default alma.

## F. TEST SİSTEMİ — MANUEL SON TEST DIŞINDA OTOMATİK KABUL
- Her değişiklik için bağımlı modüllerin unit + property + integration + regression testlerini yaz; \`pytest\` üzerinden gerçek komut/test sayıları/özet. Mock GUI gerekiyorsa Tk/Flask test client ve service subprocess smoke. Sadece kağıt üstünde test yazıp PASS deme.
- 103 ID'nin her biri için **tek ayrı kayıt**: \`ID | kaynak dosya | çözüm commit/SHA | UNIT | INTEGRATION | WINDOWS_ISOLATED | REAL_VISUAL | kanıt | blocker\`; önceki V4.5 durum matrisini güncelle, eski geçmişi koru.
- Test grupları: SHA/original immutable ve atomic output; manuel quad preserved; auto draft quad + false positive; Cam 4x2 visual, PETEK 34+ mümkünse; 4K quality; Excel/SKU/HTTPS; 1000 sentetik batch + iki-process + iki interruption; tüm araçlar; 8080 process allowlist; Windows fresh install/rollback.
- Kullanıcının fiziksel bilgisayarında ancak onun yapabileceği gerçek GUI/GPU/bulut kullanıcı onayı \`HUMAN_REQUIRED\` olarak ayrı durur. Otomasyon kendi testleri bitmeden tek final paket üretme. Test FAIL varsa ilgili kodu düzelt ve tekrar çalıştır. Deneysel corner tespitinde sınırsız model/token harcamak yerine sonuç metriğiyle kazanım/başarısızlık günlükle, başka yönteme geç; kaynak/izin/yetersiz gold blocker'ını açıkla. Kredi israfı için aynı repo ve dokümanı durmadan tekrar okutma.

## G. TEK FİNAL TESLİM
Geliştirme çalışma kopyasında **bir tek** \`V46_FINAL_CANDIDATE\` klasörü/ZIP üret; Windows launcher/bağımlılık kurulum seçenekleri/SDK? hayır kullanılmayan paketleri dahil etme; \`MANIFEST_SHA256.json\`, \`TEST_RESULTS.json\`, \`KABUL_103_MADDE.md\`, \`WINDOWS_KULLANIM.md\`, \`ROLLBACK.md\`, \`BLOCKERS.md\`, değişen kaynak dosyaları ve PR HEAD SHA. ZIP'ı çıkar → aynı içerik SHA doğrula → izole Windows ortamında kur → GUI/7 kategori smoke + synthetic 4K/fabrika/Excel ve önceki veriye müdahale olmadığına kanıt üret. Kullanıcı için GERÇEK Windows son kabulünde sadece 1 kısa kontrol rehberi ver: Cam dört kategori görüntüleri; Ocak panelinde taslak dört köşe; PETEK; pazaryeri Excel ve 4K; sistem çalışıyor mu. Kaynak ZIP sadece kanıtlı ise final link; çalışmamış modüller gerçek PASS değildir.

**NİHAİ BİTİŞ KURALI:** Her 103 ID ve eski issue kapsamı ya (1) TEST_EDILDI/PASS kanıtıyla tamam, ya (2) dış veri/insan testi nedeniyle HUMAN_REQUIRED, ya (3) gerçek BLOCKED ve alternatif/sonraki somut adım. Hiçbir madde sessizce kaybolamaz. Özellikle Ocak paneli otomatik 4 köşe düzeltmesi ölçümsüz PASS olamaz; ayrıca gerçek cam yansımasında insan görsel QA şarttır. Tamamlanmadan 'kusursuz bitmiş' iddiası olmaz. Tek final aday teslimi, açık blocker listesi ve açık PR ile sona er.

---
# EK A — ORİJİNAL 103 MADDELİ KANONİK GÖREV LİSTESİ (AYNEN KORUNUR)

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
Durum: KOD CHECKPOINT BAŞLADI. Yeni salt-okunur KONTROL_GEREKENLER envanteri + ayrı, kullanıcı onaylı 4-köşe TASLAK tekrar analizi + 3:4 uzatma + özel Golden QA kodlandı; canlı Windows/gerçek görsel kabulü bekliyor. Koruma hedefi: onaylı 4 köşe, kullanıcı maskeleri ve 6+PETEK orijinallerine sessiz müdahale yok. Deneysel SAM/AI yalnız özel test dalı.

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
Durum: GRUP 3 KOD CHECKPOINT / TEK BIRLESIK WINDOWS KABUL ADAYI oluşturuldu. Gerçek Windows ve kullanıcı kabulü henüz tamamlanmadı; final ticari GO kapalı. Ayrıntı docs/V44_GRUP3_19_GOREV_DURUMU.md.

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
