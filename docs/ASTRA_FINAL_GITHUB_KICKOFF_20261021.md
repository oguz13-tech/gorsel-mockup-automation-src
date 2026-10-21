# ASTRA FINAL GITHUB KICKOFF — 2026-10-21

**Canonical live task:** https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/24

This document is a non-sensitive source-controlled snapshot of the user's final instruction to Astra. The live GitHub issue #24 and its linked subissues are authoritative for progress/checkboxes. No real user images, masks, databases, SKU ledgers, private workspace paths, or ZIP assets are committed here.

**Current delivery status:** Not commercially accepted. Real Windows seven-category acceptance, photo QA, recoverability, and stable final release still pending. Historical reports of Linux/Xvfb tests should be rerun with evidence, not asserted as new native Windows tests.

**Next maintainer first step:** Reconfirm PR #13/#14 HEAD, open issue #15, implement a small verified packaging/CI fix on a separate branch, push + create draft PR, comment on #15 and update next-task docs. Never merge or touch live installed user data without explicit approval.

---

# ASTRA PRO — FINAL RELEASE ORCHESTRATOR / START HERE

> **Bu ana issue, Astra'nın GitHub üzerinden okuyup uygulayacağı tek final görevdir.** Kullanıcının sözlü talimatı: **"Kotan yettiği kadarını tamamla; bitiremediğin işleri biz devralacağız."** Plan üretip durma; gerçek kod/test/commit/push ile ilerle. Her aşamayı kalıcı kaydet.

## 0) Projenin hedefi
Çalışan eski **altı kategori**yi ve profesyonel araçları koruyan, **PETEK Dolabı** ile toplam **yedi kategori** için tek Windows görsel üretim merkezi; orijinal ürün delikleri/kavisleri koruyan yüksek kaliteli PETEK maskeleme ve sahneye uygun doğal baskı; günlük seri üretim, SKU/Excel, güvenli veri/numaralandırma, durdur-devam ve yanılgısız final teslim.

**Yapma:** yeni rakip ikinci sistem, sentetik 13 sabit havalandırma yarığı, kullanıcı onayı olmadan merge/live migration/üzerine yazma/bulut yayını. Sıfırdan yeniden yazmak yerine çalışır mevcut parçaları test ederek birleştir.

## 1) Teknik kaynakların gerçeği — önce yeniden doğrula
- Repo: `oguz13-tech/gorsel-mockup-automation-src`.
- PR #9 (eski koruma), PR #12 (NumberGuard/FILL), PR #11 (eski 13-slot deneysel **varsayılan olamaz**).
- PR #13: `feature/petek-v3-source-preserving-factory-20261021`, gözlenen head `ca6314af44491136373a0c807df732403c37c71b`. Flask arayüzlü **aktif entegrasyon adayı**.
- PR #14: `checkpoint/astra-petek-v3-local-20261021`, gözlenen head `b936a6b8ad292fad239bc7183c38a0f4964c2d7a`. Astra Tk/paralel implementasyon **koruma checkpoint'i**, topluca merge etme.
- En son kullanıcıya verilen **ayrı, özel Windows V3.7 Tk paketi**: `GORSEL_MOCKUP_WINDOWS_V3_7_MANUEL_KAVIS_DUZELTME.zip`. İçinde `MERKEZ/PETEK_V3/{gui,engine,realism,curves,viewport,registry,batch}.py`, `MERKEZ/quad_interaction.py` ve Windows launcher var. **Paket GitHub'a commit edilmiş değildir.** Kullanıcı özel olarak Astra'ya sunmadıysa dosyayı gördüğünü/entegre ettiğini iddia etme; GitHub'daki işler ve PR13 release paket kusurundan başla.
- Eski 6 kategori: Wi-Fi Kutusu, Cam Tablo Dikey, Cam Tablo Yatay, Ahşap Tablo, Cam Doğrama, Ocak Arkası; PETEK yedinci.
- Bildirilen test geçmişi: özel V3.7'de Linux/Xvfb **48 otomatik test** geçmiş, fakat gerçek Windows final kabulü **yok**; önceki PR13 CI yeşil olsa bile kullanıcının Windows finali onaylanmış sayılmaz.
- Gerçek PETEK üretimi kullanıcıca test edildi, 34 örnek QA + son yeni örnekler. Sorunlar: alt-sağ kenar kusuru, maske/kavis zor işaretleme, doğal modda bile yapay parlaklık, kontrast/gölge eksikliği, bazı yatay/dikey tasarımlarda crop. Bu özel fotoğraflar GitHub'a yüklenmemeli.

## 2) **Bütün açık final görevleri** (yapılacak tek kaynak; öncelik sırası)
- [ ] **#15 P0 Kaynak uzlaştırma ve ilk commit/PR.** https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/15
- [ ] **#18 P0 Veri kaybı ve isimlendirme engeli.** https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/18
- [ ] **#16 P0 PETEK dörtgen, bağımsız elle çizilen kavis, zoom, Ctrl+Z, maske kilidi.** https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/16
- [ ] **#17 P0 PETEK kontrast/gölge/ışık, feather ve 0/5/10 mm çerçeve/bleed testleri.** https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/17
- [ ] **#19 P0 Yedi kategori + eski tüm araçlar tek Windows kaynak.** https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/19
- [ ] **#20 P0 Durable batch, SKU/Excel, kesinti/kurtarma, kalite ayrımı.** https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/20
- [ ] **#21 P0 Gerçek golden dataset ve Windows/Linux QA kapısı.** https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/21
- [ ] **#22 P1 Sade Türkçe arayüz; mockup ≠ tasarım.** https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/22
- [ ] **#23 P0 Windows final kurulum, snapshot, rollback, yedi kategori kabulü.** https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/23

## 3) ASTRA'YA VERİLEN SON OTOMATİK GÖREV METNİ
1. **GitHub kaynaklarını gerçekten tara:** `AGENTS.md`, açık PR'lar, ilgili branch HEAD, tüm 9 issue, docs ve CI; eksik/çakışan şeyleri açıkça işaretle.
2. **İlk küçük ve doğrulanabilir kod adımı olarak #15'te code+commit:** PR13 üstünden yeni dal, release paketinin test dosyası eksikliğini düzelt, paket testi çalıştır, push ve draft PR aç. Kod eksik özel Windows ZIP için kullanıcıdan başka kaynak gerekeceğini devirde belirt; çalışmayı bloklama.
3. **Sonra #18 veri güvenliği:** kilitli numaralandırma, immutable source/ledger, aynı ad farklı hash/uzantı testleri, rollback. Önce koruma, sonra üretim.
4. **Sonra imkanın kadar #16 → #17 → #19 → #20 → #21 → #22 → #23** sırayla ilerle; kritik güvenlik/entegrasyon testi yoksa sonraki aşamayı final sayma.
5. Her ayrı düzeltmede ilgili issue'ya **gerçek** check-in yaz: yapılan dosyalar, açık kalanlar, test komutu + sonuç, commit SHA, Windows kabul durumu. Asıl checkbox yalnız doğrulandığında işaretlensin. Hiçbir job'u sırf CI yeşil diye 'ticari final' yapma.
6. Her ~mantıksal parçadan sonra commit/push; Github'a `docs/WORK_HANDOFF_CURRENT.md`, `docs/NEXT_AGENT_TASK.md` ve `docs/FINAL_RELEASE_STATUS.md` güncelle. Kota biterse işin en son **atomik olarak kaydedilmiş** aşaması GitHub'dan hemen devralınabilsin.
7. Ağır işlemler için ilk etapta sentetik, izole iş alanı kullan. Gerçek fotoğraflar/şablonlar ve canlı DB'ler gizlidir; public PR/Issue/Actions artifact'a konmaz.
8. **Yapılması gereken açık onaylar:** merge; eski Windows kurulumuna replace; runtime/SQLite migration; pazaryeri yayını; orijinal dosyalara değişiklik. Bunlar için açık kullanıcı onayı olmadan işlem yok.

## 4) Teslim sözleşmesi ve 'kotam bitti' protokolü
- **Kota bitmeden mutlaka** commit + push; repo dışı lokal kod bırakma.
- Draft PR bağlantısı; güncel HEAD SHA; test listesi ve hangi ortamda yapıldığı; Windows native test sonucu; başarısız testleri gizleme.
- Durum tablosu: `ISSUE` | `DONE` | `IN PROGRESS` | `BLOCKED` | `NEXT`.
- Blokajda kullanıcıdan istenecek **tek somut girdi** (örn. özel V3.7 ZIP veya gerçek kaynak mockup); yoksa GitHub içindeki bağımsız sonraki görevle ilerle.
- Kalan görevleri **başka ajanın hiçbir konuşma bağlamı olmadan** devralacağı ayrıntıyla `docs/NEXT_AGENT_TASK.md` içine işle.
- Kullanıcıya "tam final" demek için: yedi kategori gerçek Windows accepted, özgün onaylar ve eski araçlar korunmuş, kesinti testi geçmiş, dosya kaybı garantileri doğrulanmış, görsel kalite karşılaştırmaları kullanıcıca kabul edilmiş ve geri alma denenmiş olmalı.

## 5) Test ve veri sınırları
- Dosya adları/uzantıları kimliği karıştırmasın. **Aynı isim farklı dosya asla ezilmeyecek.** Eski SKU ve onaylı SHA kayıtları korunacak.
- `mask==0` korunması, delik/gölge/zemin ve gerçek üst-alt kavis şart; başka kategoriye PETEK geometrisi bulaştırma.
- GitHub PR13/14 kodlarını körlemesine merge etme. Eski onaylı 4 köşeler ve yedeklere dokunma.
- Yeni beyaz 5/10 mm frame, micro-bleed ve contrast ayarları ölçülmüş A/B sonuçlardan önce evrensel açık default olmasın.

**Şimdi başlayacağın somut iş:** Issue #15'i aç, güncel PR HEAD'leri doğrula, ilk küçük packaging/CI kusurunu kodlayıp ayrı branch+draft PR oluştur, commit/push ve burada sonuç linklerini paylaş. Başarabilirsen sonraki issue'ya geç.
