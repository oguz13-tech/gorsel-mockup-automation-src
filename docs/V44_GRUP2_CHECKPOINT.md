# V4.4 — GRUP 2 GÜVENLİ KOD CHECKPOINT / GERÇEK WINDOWS KABULÜ BEKLİYOR

**Tarih:** 24 Ekim 2026. Önceki temel: V4.4 Grup 1 ZIP, GitHub PR #45. Bu belge tamamlanmış final Windows sürümü veya gerçek fotoğraf QA onayı değildir.

## Yeni eklenenler
1. **KONTROL_GEREKENLER seçilebilir klasör envanteri** `SABLON_V2_MIMARI/core/group2_quality.py::inventory_review_folder`: runtime içinde açık seçilmiş klasördeki görselleri SHA256 ve isim çakışmalarıyla listeler. Sadece rapor; analiz/aktarım/APPROVED yok. Kullanıcı İnceleme Merkezi içinden `/tools` üzerinden çalıştırabilir. **Seçilen klasördeki görselleri otomatik 4-köşe motoruna göndermek bu checkpoint'te yok; manuel rescan ayrıca G2 kabulüne açık.**
2. **3:4 dikey uzatma:** bağımsız `SABLON_V2_MIMARI/tools_runner.py::extend_to_portrait_3x4` ile blur/mosaic/frosted arka plan, kırpılmayan ön görsel, 1200×1600 PNG, create-only çıktı, aktif çalışma/orijinal/yedek klasörlerinde değişiklik engeli. Baskı master büyütme değildir.
3. **Özel Golden Dataset okuma QA:** `evaluate_private_golden_manifest`: kullanıcıya ait özel klasörde kaynak/render/isteğe bağlı maskelerin SHA, 3:4 boyut, eşit ebat + maske için baskı dışı RGB değişimi, düz görsel uyarısı. Resimler GitHub'a veya buluta gitmez, otomatik onay 0'dır. Ebatlar farklıysa piksel eşitliği hakkında PASS vermez. 100MP üstü QA decoding kilidi bulunur. 34 gerçek PETEK örneği bu ortamda bulunmadığından gerçek Golden Dataset henüz tamamlanmadı.
4. **Profesyonel Araçlar** ekranında yukarıdaki üç araca ayrı Türkçe açıklama ve başlatıcı, backend whitelist; mevcut tüm araçlar korunur.
5. Yeni sentetik testler `TESTLER/test_v44_group2_safe_tools.py` ile 10 PASS; tam mevcut `TESTLER` havuzunda **180 PASS, 2 SKIP** (Linux + Xvfb). Real Windows testinin yerine geçmez.

## Mevcut kodda olduğu doğrulanan eski G2 yetenekleri — yeniden yazılmadı
- Kalıcı kategori bazlı 4-köşe taraması, progress/stop, dört köşe algoritmasına dokunmadan insan onayını koruma; UI kategori/şablon adetleri ve sağlık raporları.
- Manuel geometri küçük geçerli dörtgen için manual doğrulama, kaynak SHA kontrolü ve APPPROVED; başka onaylı profili sessiz değiştirmeme.
- Ocak Arkası eksik WORKING PNG geri yükleme güvenli yeni dosya / SHA / audit desteği.
- PETEK üst-alt bağımsız kavis, görünür fırça sınırı, maske tamlığı, delik koruma, Ctrl+Z ve gerçek maskeler.
- Yedi kategori kalıcı numara, aynı ad/uzantı kimlik kontrolleri, kategori bazlı fiziksel yön.
- Eski bağımsız format/recursive PNG/filigran/4K/link/SEO araçları korunur.

## Kapanışta hâlâ BEKLEYEN Grup 2 işler
- **Gerçek Windows 4-köşe editörü:** APPROVED tekrar aç, küçük yüzey, Cam Doğrama H/V, onay revizyonu, iki şablon arasında gezinme, F5/önizleme yarışı, Excel/SKU'ya yeni geometri; güvenli DB yedeği ile. (41–46, 52–53)
- **Gerçek kullanıcı şablon envanteri:** eski Wi-Fi 26–35/44/57–66, Ocak Arkası siyah, çalışma/orijinal havuz farkları. Kodda kontrol araçları var; gerçek fotoğraf/SHA olmadan bu QA PASS sayılamaz. (47–57)
- **KONTROL_GEREKENLER'de seçilen klasörden gerçekten 4-köşe yeniden analiz akışı:** bu checkpoint *yalnız güvenli envanteri* ekler, otomatik import/onay yapmaz. (49)
- **PETEK gerçek 34+ fotoğraf Golden Dataset**, değişken yarık, kavis, gölge, sağ-alt artefakt, 5/10mm çerçeve A/B insan onayı; 7 kategori fiziksel ürün görüntüsü gerçek kullanıcı kontrolü. (63–75)
- **SwinIR/HAT vs Real-ESRGAN** özel örnek benchmarkı, SAM/OpenCV5/Grounded-SAM, Canva benzeri maske ve lifestyle otomasyon araştırması kod entegrasyonu değil; gerçek golden/izin/lisans/donanım kararı bekler. (95–100)

## Kullanım (sadece izole test kurulumu)
- Profesyonel Araçlar → 3:4 Dikey Uzatma; kaynak klasör değişmez, ayrı isimli PNG dosyalar.
- Profesyonel Araçlar → KONTROL_GEREKENLER Seçmeli İnceleme; onaylı şablon veya SQLite değişmez.
- Profesyonel Araçlar → Golden Dataset. Örnek JSON `docs/G2_OZEL_GOLDEN_DATASET.md` içinde.

## Sıradaki otomasyon görevi
Grup 2 taslak PR üzerinde CI ve gerçek Windows koşullarını belirle. Özel gerçek örnekler yalnız kullanıcı bilgisayarında işlensin, GitHub'a yüklenmesin. Tam G2 kabulü tamamlanmadan Grup 3'ü "güvenli final" ilan etme. `main` / canlı DB / dört köşe / master / mask / eski ZIP'e yazma yasak.
