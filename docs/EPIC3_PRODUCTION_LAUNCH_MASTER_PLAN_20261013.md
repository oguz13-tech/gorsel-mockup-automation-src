# EPIC-3 — Üretime Geçiş Ana Planı / 13 Ekim 2026

STATUS: ACTIVE. Bu plan bir çalışma sözleşmesidir; test PASS veya canlı deployment kanıtı değildir.
OWNERS: ChatGPT = mimari/kod/CI/release; Kilo = açık yetkili salt okunur Windows test ve rapor; kullanıcı = görsel onay ve canlıya geçiş izni.
TRACKING: oguz13-tech/gorsel-mockup-ai-bridge Issue #1. Source: oguz13-tech/gorsel-mockup-automation-src.

## 0. Sabit güvenlik ve kaynak kuralları
- Canlı OneDrive runtime DB, working/original archive, staging, trash/recovery, onay ve gerçek üretim çıktısına **bu plan nedeniyle yazılmaz**. Kod işlemleri yalnız GitHub güvenlik dalında; testler sentetik/izole TEMP alanında.
- Kilo kaynak kodu değiştirme, commit/push/merge, auto-approve, migration, file move/delete/restore veya ticari üretim yapmaz. Yeni yetki yalnız açık görev + doğru sürümle verilir.
- Auto-approval OFF. H/V zorlama, tasarımı kırpma veya en-boy esnetme yok. Kaynak SHA doğrulanır, şüpheli geometri/maske fail-closed, eski manuel köşe/kimlik değerleri bozulmaz.
- Arşiv-only 172 geçmiş template kimliği **kapatılmış envanterdir**; otomatik restore veya aktif havuzla eşitleme yapılmaz. Önceden silinmiş numara tekrar kullanılmaz.
- Başlangıç: feature/epic-3-geometry-accuracy PR #4 draft/open/unmerged; safety/epic3-archive-guardrails-20261010 güvenlik dalı, başlangıç SHA 2ec8482347fdc6c67a5f016a6958e92b7a55a938; main merge yok.

## 1. Kanıtlanan ve kanıtlanmayan durum
- 6 kategoride 46 APPROVED+source hash valid: WiFi 31, CamDikey 1, CamYatay 1, Ahşap 1, CamDoğrama 1, OcakArkası 11 (Kilo readonly kanıt).
- Gerçek 6 onaylı template + **sentetik** H/V artwork ile 6/6 render 1200x1600 ve TEMP izolasyon doğrulandı. Bu ticari gerçek artwork ve foreground AI testi değildir.
- WiFi 31 onaylı / 175 fiziksel / 3 preview sayfası; CamDoğrama 1 onaylı / 78 fiziksel / 6 preview sayfası; Kilo son rapor tamamlandı, görsel seçim eksik.
- Son güvenlik Actions run 38086997078: 5/5 job PASS; 222 regresyon + Windows güvenlik ve sentetik izole render. Canlı normal factory full flow PASS kanıtı henüz yok.
- Golden GT geçmişinin bazı legacy dört köşeleri hatalı; ~0.974 median IoU bağımsız fiziksel doğruluk garantisi değil. Şüpheli WiFi 015/016/018–020/026–035/044/057–066 ayrı gözden geçirme.

## 2. Üretim hedefleri ayrı tutulacak
- S0 İLK GERÇEK JPG: verified approved template + gerçek kullanıcı H/V artwork, 1200x1600, kaynak read-only, TEMP output, görsel kontrol. Bulut/Excel/SEO/satış yüklemesi YOK.
- S1 KÜÇÜK SERİ: öncelikli 4 kategori, en az 2 gerçek tasarım, partiler, skip/error/contact sheet ve görüntü QA, nonoverwrite.
- S2 TAM NORMAL FABRİKA: manifest, H/V master, preflight/doctor, mask/AI, bulut upload, SEO, Excel, artifact state, restart ve rollback; kullanıcı ayrı izin verir.
- S3 TAM OTONOM: tüm uygun şablonların gözden geçirilmesi, güvenilir GT, auto corner iyileşmesi, occlusion, çoklu mağaza ve performans.

## 3. P0 / G0 KILO TOPLU READ-ONLY HAZIRLIK — ŞİMDİ
- [ ] L01 Exact pinned SHA temiz bağımsız TEMP clone, Python/Windows/venv; kaynak ve runtime root karışmaz.
- [ ] L02 Runtime SQLite ve gerçek manifest SHA256 before/after; sadece read-only; gizli API anahtarlarını LOG'a koyma.
- [ ] L03 Factory Doctor --fast çıkış kodu, errors/warnings code ve runtime sürüm uyumu.
- [ ] L04 pc_master_factory.py --preflight çıkış kodu + ready/errors/warnings, manifest item/missing H/V, 6 category usable/stale/invalid/orientation, cloud *counts* yalnız, optional AI missing, occlusion AI-needed sayısı, outputs writable.
- [ ] L05 Manifest yoksa / API eksikse / mask bloke ise olgusal blocker; Kilo sahte H/V, key, onay veya dosya oluşturup düzeltmeye çalışmaz.
- [ ] L06 Tek Issue #1 raporu: SHA, komut+exit, literal hata, DB_SHA_SAME, MANIFEST_SHA_SAME, gerçek asset varlığı/dosya adetleri. Konum gizliliği gerektiğinde paylaşma.

## 4. P0 / G1 CHATGPT KOD — PARALEL
- [ ] C01 İzole gerçek artwork smoke: mevcut scripts/epic3_six_template_smoke.py tabanını genişlet; --execute yokken I/O yok; --artwork-h/--artwork-v isteğe bağlı, iki dosya için gerçek H/V ve aspect. Synthetic default 6/6 korunmalı.
- [ ] C02 Gerçek H/V artwork read-only; oryantasyon ve fiziksel yüzey oranı; no forced stretch/crop; incompatible source BLOCKED; format/dim guard; no imported normal factory state/upload/Excel writes.
- [ ] C03 Source DB+templates/artwork immutable, OS TEMP 1200x1600 JPG, SHA output manifest; report synthetic/test vs real clearly; block foreground/legacy plan without verified masking.
- [ ] C04 Synthetic fixture tests: no-execute, H/V selection, incorrect orientation/aspect, missing source, corrupted source, source hash unchanged, TEMP-only output, no cloud/Excel, unique output, blocked masks. Linux+Windows CI.
- [ ] C05 Ayrı epic3-geometry-fix dalındaki OcakArkası white panel fix diff ve testlerini safety dalı ile karşılaştır; güvenli seçici entegrasyon veya gerekçeli defer; tests/test_surface_mode_detection.py CI kapsamına eklensin.
- [ ] C06 scripts/epic3_validation_bundle.py EXPECTED_BRANCH feature/... sabit; güvenlik dalı ve release candidate için doğru branch+SHA gate'i doğrulamayı zayıflatmadan düzelt.
- [ ] C07 Full factory preflight ile isolated smoke arasındaki fark belgeli; S0 başarılı ise S2 PASSED denmez.

## 5. P1 / G2 GÖRSEL İNSAN DEĞERLENDİRMESİ + PİLOT
- [ ] V01 Kullanıcı 9 preview JPEG'i (Wi-Fi üç / Cam Doğrama altı) tek zip veya sayfalar halinde gönderir; asistan kategoriye uygun doğru adayları seçer.
- [ ] V02 Cam Doğrama cam kesme/doğrama tahtası dik çerçeve gibi değil, yatay/çapraz açı; 78 aday manuel seçilir; onaysıza otomatik APPROVED yok.
- [ ] V03 Wi-Fi dış ölçü 40x30 cm, 12 cm iç derinlik, sürgülü MDF kapakla beyaz gövde gerçekliği; uygun approved şablonlar.
- [ ] V04 OcakArkası, CamTablo Dikey/Yatay ve Ahşap öncelikli S1 pilot; cam ve mask gerçek testleri ayrı kabul.
- [ ] V05 Kullanıcı gerçek H/V tasarım sağlar; 1 metinli ve mümkünse nesne örtülmeli sahne; 1200x1600 JPG görsel kalite/matte/perspektif/font kabulü.
- [ ] V06 Hatalı/occluded/yanlış kimlikli ürün satışa çıkarılmaz. Kullanıcı onayı olmadan gerçek aktif profil değiştirme YOK.

## 6. P2 / G3 KONTROLLÜ ÜRETİM KABULÜ
- [ ] R01 Release candidate exact SHA; tüm önemli test dosyaları (özellikle surface mode), Linux+Windows and report; değiştirilen kod için regresyon PASS.
- [ ] R02 UI/8080 route ve review; approve persistance, orientation, hash stale, 4 köşe, foreground review, batch scan progress+popup/resume, health; staging watcher ekleme+tek analiz.
- [ ] R03 Bağımsız 8 araç launch/rename/trash tombstone/recursive PNG; iki Flask başlatıcısı ve input root tutarlılığı; mümkünse tek tercih edilen ana UI.
- [ ] R04 Full normal factory preflight.READY, H/V manifest, output permissions, cloud credentials sadece varlık kontrolü; opsiyonel AI veya trusted mask; render→artifact state→upload→SEO/Excel→rerun/collision/partial failure.
- [ ] R05 OneDrive SQLite WAL syncrisk bildirimi; kod/runtime ayrı, yedek/sürüm hash, rollback prova, sonrasında kullanıcı açık izinli deployment. PR #4 draft/merge kararı ayrı.

## 7. P3 / G4 TAM OTONOM BACKLOG
- [ ] Tüm 492 template kategori/GT doğrulaması; yanlış legacy quad karantina; altı kategoride gerçek surface IoU.
- [ ] Grounding-DINO/SAM object-mask + brush + auto detection; cam/doğrama/ocak vb foreground compositing QA.
- [ ] 4K Real-ESRGAN güçlendirme, hesaplama ve çıktı kalite dengesi, disk/performance.
- [ ] Kaggle girişleri, H/V manifest otomasyonu; toplu seri üretim; ürün/marketplace SEO; bulut ImgBB/FreeImage key management/retry; çoklu mağaza K1..K11.
- [ ] Staging progress, summary popup, numaralama, trash/recovery, iş kuyruğu, güvenli onarma ve JARVIS V3 entegrasyonu.
- [ ] Secrets redaction/credentials/Git history audit; legacy launchers and two UI/data path consolidation; QA release documentation.

## 8. Ölçülebilir release kapıları
| Gate | Kanıt | Durum |
|---|---|---|
| G0 | Kilo exact SHA Doctor+preflight+DB/manifest unchanged, blocker matrix | PENDING |
| G1 | Gerçek H/V approved source + 1200x1600 yalnız TEMP, QA + 1 human approved preview | PENDING |
| G2 | 4 kategori / ≥2 desen / dosya collision-safety / insan görsel QA | PENDING |
| G3 | Normal factory preflight READY + upload/Excel + UI/staging/mask Windows gerçek test | PENDING |
| G4 | CI+Windows RC SHA + backups/rollback + explicit user release approval | PENDING |

## 9. Zaman beklentisi (koşullu tahmin)
- S0 ilk gerçek JPG: 2–5 saat mühendislik/deneme eforu, gerçek H/V dosyalarının hazır olması ve Windows blokajının bulunmamasına bağlı.
- S1 küçük seri: 1–2 iş günü; S2 altı kategori/tam üretim 3–7 iş günü; S3 tam otonom 2–4+ hafta.
- Bunlar SLA değil. Kodu GitHub'da yazmak, kullanıcının yerel kurulumunu ve makinesindeki verileri değiştirmez.

## 10. Çalışma disiplinimiz
- Issue #1 = 1 toplu Kilo görevi + 1 kanıt raporu; geçmiş 172 dosya incelemesini tekrar etme.
- Her paket OWNER/EXACT_SHA/COMMAND/EXIT/INPUT_HASH/OUTPUT/RESULT/BLOCKERS/NEXT taşır; sonucun kanıtı yoksa PASS değil.
- Kod C01..C07 güvenlik dalında test edilir; yeni release candidate ayrıca açıkça belgelenecek; otomatik merge/approval/live write yok.
- **Sıradaki gerçek başlama eylemi:** P0 Kilo doctor+preflight; ChatGPT G1 isolated H/V gerçek artwork pilot kodu; kullanıcının görsel onayı.
