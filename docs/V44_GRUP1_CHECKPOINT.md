# Görsel Üretim Merkezi — V4.4 Grup 1 ilk kod checkpoint'i

23 Ekim 2026. Grup 1 **BAŞLADI**; bu **tam Windows final kabulü değildir**.

## Gerçek durum
- Kullanıcı Windows V4.2.2 ile 7 kategoride çoklu tasarım üretiminin genel görsel kalitesini başarılı buldu.
- V4.3 önceki geliştirme dalında bulut HTTPS Excel, cam A/B, yeni onaylı dört köşe revizyonu ve iş sınırı kaldırma kodlandı. Gerçek Windows A/B, ImgBB ve kullanıcı DB kabulü açık.
- Grup 1'in yeni V4.4 adayında eski 10 onaylı şablon düğmesi kaldırıldı (tarihî kod silinmedi); 7 kategori üretim ön plana alındı; bakım ve eski PETEK ayrı üretim araçları kapalı Gelişmiş alanda erişilebilir bırakıldı; ana merkez SHA denetimi hiçbir SQLite klasörü/dosyası oluşturmayan salt-okunur sorguya alındı. Gelişmiş menü SHA denetimi salt-okunur gerçek işleve bağlı.
- GUI'de varsayılan kapalı, gerçek Real-ESRGAN NCNN-Vulkan programı ve model dosyaları mevcutsa çalışan **4K 2880×3840** seçeneği eklendi. Kullanıcının asıl fotoğrafı, tasarımı, 1200×1600 çıktısı, SQLite, dört köşesi değişmiyor. 4K ayrı create-only yol, SHA receipt ve SKU eşleştirmeli ayrı yerel Excel hyperlink ile kaydediliyor.
- **Yürütülebilir binary/model dosyaları pakette bulunmuyor**, otomatik indirme yok. Kullanıcının ayrı kurması ve gerçek Vulkan çalıştırması gerekiyor; bunun için `docs/REAL_ESRGAN_WINDOWS_4K.md`.
- Yeni UI üretimden önce Real-ESRGAN ön kontrolü yapıyor. Geçemiyorsa 4K işaretini kaldırma yönlendirmesiyle normal üretim yapılabilir; sahte AI kalite yaratılmaz.

## Testler (sentetik Linux / sanal ekran)
- Seçilmiş yedi-kategori, GUI, Group2, V4.3 ve eski araç regresyon: 49 PASS.
- Ek hotfix, son güvenlik, Factory Doctor: 56 PASS; bir eski UI testi yeni karara güncellendi, thread snapshot test sınırı düzeltildi.
- **Toplam 107 benzersiz seçilmiş test PASS**. Ayrıca `python -m compileall -q .` PASS (eski string escape uyarıları var).
- Fake-engine mock testi: normal PNG korunur, ayrı 4K PNG 2880x3840, SHA receipt ve Excel hyperlink, idempotent tekrar, kaynak SHA uyuşmazlığında fail-closed, motor hata kodunda orijinal korunumu.
- **Gerçek Real-ESRGAN GPU çalıştırması ve yüksek hacimli 4K üretim yapılmadı.** Windows ticari kalite kabulü eksik. Tüm suite tek komutta çalıştırılmadı.

## Kesin açık kalan Grup 1 işler
- #19–#27: dört cam kategorisi gerçek kullanıcı A/B onayı.
- #28–#34: gerçek ImgBB/FreeImage ağ, tıklanabilir HTTPS Excel, SKU/SEO/mağaza kolonları, tekrar upload olmaması.
- #35–#37: Windows canlı SQLite yedek sonrası approved 4 köşe revizyonunun tekrar üretime yansıması.
- #38–#40: 415MP JPEG ve yüksek PNG/WebP gerçek güvenli yükleme, çoklu işi bozmama.
- #12–#16: resmi Real-ESRGAN binary/model kurulumu, Windows GPU tile, benchmark, 4K model/SHA Excel kabulü.
- #18, #101–#103: kalan e-ticaret raporu, ekran açıklamaları ve operasyon paneli.

## Sonraki gruplar
- Grup 2 #41–75 ve #95–100: şablon/4-köşe/PETEK/eski araçlar/golden.
- Grup 3 #76–94: dayanıklılık, 1000 batch, gerçek Windows, DB backup, rollback ve tek sürüm.
- 103 maddelik ayrıntılı plan: `docs/THREE_GROUP_103_TASK_PLAN.md`.

## Güvenlik
- Mevcut C:\GorselMockup_V422 ve V43 üzerine ZIP çıkarmayın. Canlı DB/WAL/SHM, orijinaller ve onaylı geometri dokunulmaz. Windows kabulü tamamlanmadan bu checkpoint'i nihai üretim olarak kurmayın.
- GitHub `main` ve tarihî PR'lar merge edilmez; kalıcı diff ayrı taslak dalda tutulur.
