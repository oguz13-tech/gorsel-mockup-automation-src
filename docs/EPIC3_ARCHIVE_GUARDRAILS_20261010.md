# EPIC-3 — Arşiv Güvenliği ve Klasör Farkları Kapanış Kararı

Karar tarihi: 2026-10-10. Kapsam: sadece güvenlik kuralları ve bunların testleri. **Bu belge tek başına kodun dağıtıma alındığı anlamına gelmez.** Değişikliklerin onaylı entegrasyon öncesinde bağımsız dalda test edilmesi şarttır.

## 1. Onaylanmış karar ve sabit envanter

Kullanıcının Windows üzerinde 2026-10-10 07:27:43 anında ürettiği envanter:
- `2_SABLON_HAVUZU_ORIJINAL_YEDEK`: 794 resim dosyası;
- `2_SABLON_HAVUZU`: 621 resim dosyası;
- aynı kategori + uzantıdan bağımsız / Windows case-insensitive stem: 172 `SADECE_YEDEK` kimliği, 614 `HER_IKISINDE`, 4 `COKLU_KIMLIK`, 2 `SADECE_HAVUZ`;
- 172 yalnız-yedek kimliğinin 173 fiziksel dosyası mevcut olabilir: `03_Ahsap_Tablo/AhsapTablo_011` hem .png hem .jpeg;
- 172'nin kategori dağılımı: WiFi 19, Cam Dikey 43, Cam Yatay 50, Ahşap 26, Cam Doğrama 25, Ocak 8, Yüklenecekler 1;
- 139 kimlik standart-dışı kaynak isimlidir, 33 kimlik standart numaralıdır.

**Politika:** Arşiv ile çalışan havuzun sayıları eşitlenmeyecek. 172 kimlik otomatik olarak içe alınmayacak, geri yüklenmeyecek, silinmeyecek. `SILINEN_SABLONLAR_COP_KUTUSU` ve `_COP_KUTUSU` sadece denetim/geçmiş kaynağıdır; geri yükleme talep edilmedi. Bilerek silindi iddiası pozitif kanıt olmadıkça kesin neden değildir. Bu araştırma nedeniyle çalışan görüntü üretim akışı engellenmemelidir; ancak fail-closed güvenlik kontrolleri asla devre dışı bırakılmamalıdır.

Not: GitHub Issue #1'deki önceki 120, 377, 379, '169 never imported' sayıları birbiriyle tutarsız ve geçmiş eylem kanıtı değildir. Ham SHA eşleşmesinin bulunmaması, resmin hiç aktarılmadığını ispatlamaz; işlenmiş görsellerin hash'i farklı olabilir.

## 2. Kullanılacak mevcut altyapı

Yeniden icat etmeyin. Önce mevcut implementation'ı inceleyin:
- `SABLON_V2_MIMARI/core/template_identity.py`: kategori+stem kimliği, çoklu uzantı/numara kaydı, tarihçe kontrolleri;
- `SABLON_V2_MIMARI/core/path_registry.py`: canlı workspace ve `WORKING_POOL`, `ORIGINAL_ARCHIVE`, `STAGING_INBOX`, `RECOVERABLE_TRASH` yolları;
- `SABLON_V2_MIMARI/tools_runner.py`: bağımsız araçların canlı havuz ve arşivde işlem yapmasını yasaklayan `ensure_not_live_template_path`, iki-aşamalı rename rollback'i.

Önce değişiklik gerekmediğini testlerle gösterebiliyorsanız kod eklemeyin. Mevcut DB/metadata okuyan kontrol yordamlarının bile salt-okunur taramada örtülü tablo oluşturabileceğini inceleyin; `mode=ro` ile gerçekten yazmasız denetim olmalı.

## 3. Değiştirilemez koruma sözleşmesi

1. **Orijinal arşiv koruması.** Source PNG/JPEG üzerinde in-place whiteout/transparency/crop/rename/overwrite/asıl dosyaya kaydetme yasak. Aynı dosya yoluna/kimliğe kopyalamak da yasak. Girdi dosyasını önce hashle; kopyalama gerekiyorsa ayrı hedefe geçici dosya + fsync/atomic replace only when target absent + source/target hashes verification; hata varsa rollback ve girdi korunmalı. Arşiv silme ve toplu eşitleme yasak.
2. **Tekil kimlik/numara.** Kimlik: kategori + normalize edilmiş uzantısız isim (Windows case-insensitive/Unicode normalize değerlendirmesi). `.png` / `.jpg` / `.jpeg` / `.webp` arasında aynı stem çakışma; aynı kategori tarihçe/çöp/recovery/DB/staging geçmişi de tekrar numara kullanımına engel. Farklı kategori bağımsız. Uyarı görünür ve açık: `AYNI İSİM, FARKLI UZANTI`. Çakışmada hiçbir dosya taşınmaz/silinmez/yeniden adlandırılmaz; gelen dosya staging'de kalır.
3. **Silme ve çöp kutusu.** Kullanıcıdan açık, dosya/kimlik bazlı onay olmadan aktif havuzdan çöp kutusuna taşıma yok; kalıcı silme yok. İşlemden önce işlem kimliği, kategori, tam kaynak/hedef yol, zaman, actor, reason, SHA256 ve status içeren güvenilir JSONL/event journal; taşıma sonrası doğrulama; kısmi hatada rollback. Arşiv kopyası olduğu kabulüyle silme yapılmaz. Çöp ve karantina otomatik geri alınmaz.
4. **Manuel geri alma.** Bu projede önceki silinmiş görselleri geri yükleme kararı YOK. Gelecekte kullanıcı açıkça talep ederse önce sadece önizleme ve tekil dosya incelemesi; hedefte stem/uzantı çakışırsa fail-closed. Asla bulk restore. Onaylı dosyanın kaynak hash, boyut, format ve semantiği doğrulanmadan işlem yok.
5. **Staging / watcher / renamer / folder scan.** Hepsi aynı ortak kimlik ve journal kontratından geçmeli; glob/uzantı farkından dolayı ikinci dosyaya sessiz izin yok; yarışan eşzamanlı iki girişte birisi kontrolü atlayamaz. Girdi korunur, kritik hata kullanıcıya ve loga yazılır. Girişte otomatik kabul/auto-approve yok.
6. **DB / profil sağlığı.** Silinmiş/yeniden adlandırılmış kaynak kimliğiyle stale profile veya eski `koseler` yeni görsele bağlanamaz. Source hash değişimi review-required/stale; otomatik APPROVED yok. `template_profiles` ile `templates` sayısının farklı oluşunu 'bozulma' veya 'hiç analiz edilmemiş' diye kanıtsız değerlendirme; veritabanı lifecycle sözleşmesine göre yorumla.
7. **Raporlama.** Sadece `review_needed`, `source_missing`, `collision`, `mutated_original`, `historical_only` gibi denetlenebilir güvenlik uyarıları; eski 172 diff için otomatik restore/copy tavsiyesi yok. Tüm koruma testleri pass etmedikçe güvenli denilmez.

## 4. Dar kapsam ve CI kabul matrisi

Sadece ayrı bu dalda değişiklik yapın, gerçek çalışma dosyalarında işlem yapmayın. Testlerde temp workspace, temp SQLite ve sentetik PNG/JPEG kullanın. En az:
- (T1) arşiv dosyasının SHA/mtime değişmiyor; iptal/hata durumunda;
- (T2) aynı kategori + aynı stem .png/.jpeg: BLOCK, gelen korunur; same-ext BLOCK;
- (T3) farklı kategori: ALLOW;
- (T4) silinmiş/trash/DB/tarihçe kullanılmış stem: BLOCK, önerilen numara varsa güvenli;
- (T5) iki watcher yarışması: biri kabul diğeri BLOCK, source korunur;
- (T6) crash sonrası journal/recovery idempotent; kısmi işlem rollback;
- (T7) sahte target mevcut: overwrite yok, orijinal değişmiyor;
- (T8) staging klasörü taraması ilerleme ve sonuç özetinde reddedilenler + neden gösterilir;
- (T9) kaynak değişikliği approved geometriyi otomatik geçerli kılmaz;
- (T10) geçmişte kaldırılmış dosya otomatik geri yüklenmez; toplu arşiv eşitleme yok;
- (T11) sadece-read audit SQLite gerçekten hiçbir tablo/data oluşturmaz; diff raporu yoksa çalışmayı bozmaz;
- (T12) Windows casefold, Unicode normalize ve tüm desteklenen görsel uzantılarında kimlik testleri.

Kabul kanıtları: değiştirilmiş dosya listesi, tam git SHA, gerçek komut ve exit-code, test adları PASS/FAIL, before/after source hash, kullanıcıya açık bir demo, mevcut regresyonların sonuçları, GitHub Actions exact-head run linki (varsa), geriye alma planı ve canlı sisteme hiç dokunulmadığının kanıtı.

## 5. Yasaklar ve sürümleme

- Katiyen 172'yi toplu restore/import etmeyin; arşivi working ile eşitlemeyin.
- Kaynak görsel, canlı DB, arşiv, staging, çöp veya recovery içeriklerini bu görevde MUTASYONA UĞRATMAYIN.
- Ana `feature/epic-3-geometry-accuracy` dalına doğrudan push YOK. `PR #4` draft/open/unmerged, auto-approval OFF.
- Sadece kod ve testlerin bu bağımsız güvenlik dalına commit/push'u serbest; merge veya runtime deployment açık insan onayına bağlı.
- Denetim çıktıları/raporlar çalışma dataset'inin içine yazılmaz.
- Kullanıcı ticari görsel üretimine dönmek istiyor: güvenlik kabulünden sonra minimum 6 onaylı şablonla gerçek 3:4 üretim testine geçilecek.

## 6. Bitiş ölçütü

Bu belge ve Github görevlendirmesi `POLICY RECORDED` demektir. `IMPLEMENTED` yalnızca tüm kod kapıları ve sentetik testler, `DEPLOYED` yalnızca kullanıcı tarafından onaylanmış güvenli canlı geçiş kanıtıyla ilan edilir. `EPIC-3 GRUP 4` eski envanter farkını **NO ACTION / HISTORICAL ARCHIVE** olarak kapat; ayrı güvenlik geliştirme işini test kanıtı gelene kadar açık tut.
