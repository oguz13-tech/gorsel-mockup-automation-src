# V4.4 Grup 3 — 19 güvenlik ve Windows kabul maddesi (24 Ekim 2026)

Bu rapor **Grup 1 + Grup 2 + Grup 3 birleşik Windows kabul adayına** aittir. Sentetik testler ve kod teslimi, kullanıcının gerçek Windows bilgisayarı/OneDrive/7 kategori/ImgBB/Real-ESRGAN GPU kabulü değildir.

| Madde | Gerçek yapılan / kalan | Durum |
|---|---|---|
| 076 | 1.000 ayrı SQLite ledger reserve→rendered SHA→reuse + audit sentetik test. 100/200/1000 tam görüntü render / süre benchmarkı ayrıca gerekir. | Kısmi test PASS; tam 1000 render BEKLİYOR |
| 077 | İki ayrı sentetik interrupted PENDING→karantina→tekrar kuyruğa alma testi. Gerçek iki Windows process kill/restart tatbikatı henüz yok. | Sentetik PASS; Windows gerçek BEKLİYOR |
| 078 | Kesinti dosyası SHA/koruma, eksik/güvensiz çıktı audit. Disk dolu/erişim engeli fiziksel deney yok. | Kısmi |
| 079 | OS O_EXCL kilit için iki gerçek bağımsız subprocess testi; SQLite çift iş üretimi ayrı Windows sürecinde test edilmedi. | Kısmi |
| 080 | Kalıcı PENDING/RENDERED ve güvenli durdurma/tekrar başlatınca yeniden kullanma mevcut. İsteğe bağlı gerçek Pause/Resume tekil kontrolü yok. | Açık |
| 081 | Yeni G3 salt-okunur audit: iki DB quick_check, önemli tablo sayısı, yerel üretim çıktılarında SHA/unsafe path/status. Eski CSV/XLSX/SKU ticari mapping tam kullanıcı kabulü bekliyor. | Kod/sentetik PASS; Windows açık |
| 082 | 1.000 sentetik create-only idempotent tekrar kayıt testi; eski gerçek SKU sabitliği kullanıcı Windows'ta karşılaştırılmalı. | Kısmi |
| 083 | Eski ad/SHA/uzantı koruma testleri G1/G2'de. Canlı tam envanter karşılaştırması yok. | Kısmi |
| 084 | Approved ve SHA fail-closed eski motor ile korundu; gerçek 7 kategori onaylı profil kontrolü gereken kabul. | Kısmi |
| 085 | Yeni **açık kullanıcı onaylı** iki DB (onaylı geometri + ortak üretim) SQLite online backup, WAL dahil, integrity_check, ayrı yerel restore copy, SHA256 kanıt/manifest, sonradan read-only SHA doğrulama. | Kod ve sentetik PASS; gerçek Windows backup/restore BEKLİYOR |
| 086 | OneDrive runtime veri riski bilgilendirmesi var; **otomatik taşıma yok**. Yerel DB geçişi ancak ayrı backup/rollback+izin+test ile. | Açık / canlı göç yapılmadı |
| 087 | Önceki Factory Doctor Python/NumPy/Torch/Transformers/CUDA açıklamaları korunuyor; kullanıcının canlı GPU/ortamı burada okunmadı. | Açık |
| 088 | Başlatıcının Python/venv fallback'i korunuyor; çevrimdışı wheel paketlenmedi. Clean Windows offline + lock deneyi yok. | Açık |
| 089 | 8080 port çakışma koruması korunuyor; gerçek PID/port kimlik testleri ve iki runtime eşzamanlılığı Windows'ta bekliyor. | Açık |
| 090 | Türkçe yol ve izole temp regresyonları var; gerçek Windows UI, ağsız kurulum ve rollback tatbikatı bekliyor. | Açık |
| 091 | Grup 1 + Grup 2 + Grup 3 **tek Windows kabul adayı ZIP** ve SHA256/dosya envanteri hazırlanır; henüz kullanıcı Windows ticari GO değil. | Paket hazır / gerçek kabul açık |
| 092 | GitHub G3 PR + 103 görev üç grup planı + G3 status belgeleri/kod/CI güncellenir. | GitHub commit ile güncel |
| 093 | Eski #15–#24, #29–#40 görevleri G1/G2/G3 devriyle ilişkilendirildi; kapanmış sayılmaz, gerçek QA bekliyor. | Açık |
| 094 | Yayına alınan G3 kaynakları kontrolü, ZIP'te kişisel canlı DB/fotoğraf yok; GitHub Actions'a gerçek kullanıcı dosyası eklenmez. | Kod/manifest denetimi; son public audit açık |

## Sınırlar / güvenlik

- G3 denetimi **varsayılan salt-okunur**. Yedek için hem kullanıcının GUI 'Evet' onayı hem kod seviyesinde `YEDEK_AL_V44` token'ı gerekir.
- Yedek eski onaylı geometri `ayarlar.db` **ve** ortak üretim `v4_ortak_uretim.sqlite3` dosyalarını WAL güvenli online snapshot alır; orijinalin üzerine asla geri yükleme yazmaz.
- Geri dönüş tatbikatı ayrı geçici kopyada yapılır. Windows için gerçek kurtarma/geçiş ayrı ve onaylı çalıştırılmalıdır.
- 1000 kayıt testi **1000 gerçek fotoğraf render** değildir. Bütün real-world/Win/GPU / 34+ PETEK Golden insan kontrolü beklemede.
- Model ağırlıkları, özel `.env`, ImgBB anahtarları, gerçek fotoğraflar ve DB public Github'a gitmez.
