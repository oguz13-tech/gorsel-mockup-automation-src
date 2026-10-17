# P0 / İki görev — Windows kabul ve güvenli kurulum planı

**KARAR: DRAFT — CANLI UYGULAMA YASAK.** Bu dosya bir kurulum aracı veya onay belgesi değildir.

## Kaynak ve ayrım

- Ana güvenlik tabanı: PR #5 `c0345be4227b52752e61a2a03a61cd5f56c1db02`.
- Bağımsız düzeltme dalı: `fix/p0-independent-audit-20261017`; PR #6 -> PR #5.
- Yerel kullanıcı kod deposu `C:\AI_WORK\gorsel-mockup-automation-src`, veri çalışma alanı OneDrive Masaüstü içindeki `GörselÜretme-ve-Mockup Otomasyonu`. İkisini asla eşitleme/kopyalama.
- `main`, `safety`, PR #4, PR #5, canlı JSON/SQLite/yedekler değiştirilmedi.

## Kod ile kapsanan P0

- A: numara blok doğrulayıcı, geçmiş en yüksek numaranın altındaki boşlukları reddeder.
- B: araç isimlendiricisi, watcher ile ortak global kilit ve atomik DB numara claim'i kullanır. Başarısız fiziksel adlandırmada numara yanabilir; tekrar tahsis yok.
- C: çalışma PNG'si değişiklikleri versiyonlu SHA arşivli ve geri alınabilir; orijinal/raw immutable. 8999 / legacy vision HTTP önizleme, ayarlar, orijinale dön, toplu revizyon ve trash restore kapıları yeniden düzenlendi. 8080 orijinale dön ve trash restore create-only güvenli revizyon kullanır.
- D: legacy temizlik motoru sadece rapor verir, legacy toplu yenileme BAT engellenmiştir.
- E: güvenli olmayan eski PNG migrasyonu fail-closed; profesyonel araçların kaynak-koruyan dönüştürücüsü korunmuştur.
- Preview `-beyazlatilmis-onizleme` adı watcher'ın mevcut filtrelerinde zaten hariçtir.
- Yeni testler: `test_p0_independent_release_safety.py`, `test_p0_review_endpoints.py`, `test_p0_isolated_factory_render.py`, `test_p0_app_8080.py`.

## Geçiş için gerekli TEST / KAPI

1. **GitHub CI**: PR #6 HEAD'i için Windows ve Ubuntu her ikisi de PASS; hata sonucu gizleme.
2. **Bağımsız kod inceleme**: Argon çıktısını diff + exact SHA ile karşılaştır. Onun patch'ini körlemesine merge etme.
3. **Windows izole kabul**: Ayrı boş checkout + yalnız TEMP/fake-runtime üzerinde 8999/8080 kritik işlemleri, 100 collision, NTFS/OneDrive kilitleri, hata/rollback ve 1200x1600 üretim. `APPROVED` geometriler canlı sisteme yazılmaz.
4. **Salt-okunur preflight**: Bu dalın checkout'undan `P0_RELEASE_ON_KONTROL.bat` çalıştırılarak `%TEMP%\P0_RELEASE_PRECHECK_*.json` elde edilir. Bu işlem asla kurulum yapmaz. Türkçe yol Python 3 UTF-8 içinde bulunur.
5. **Onay öncesi** ayrık diske veri bütünlüğü/snapshot + SQLite Backup API **tutarlı kopyası**, doğru HEAD ile kod klonu snapshot, SHA manifest, geri-alma planı. OneDrive doğrudan DB dosyası `copy` işlemi canlı WAL varken güvenli snapshot sayılmaz.
6. **Kullanıcının ayrı açık kurulum izni**: ancak tüm PASS sonrasında; sadece onaylı kod release sürümünü ayrı kod klonuna uygulama. Kaynak görseller, yedekler ve DB hiçbir zaman ZIP extract veya `git clean/reset` hedefi değil.
7. **Tek canlı kurban testi** için ayrıca kullanıcı onayı, watcher opt-in ve benzersiz dosya giriş klasörü; sonrasında kontrollü küçük batch.
8. **Geri dönüş**: hizmetleri durdur, önce kod checkout'unu önceki tam commit'e döndür, işlem manifestlerini ve working snapshot SHA'larını karşılaştır; gerçek DB ve dosya restore ancak kullanıcı izni + doğrulanmış arşivle. Otomatik toplu `unlink`, `move`, `replace` yok.

## Kesin sınırlar / çözülmemiş iş

- CI PASS gerçek OneDrive üzerinde release onayı DEĞİL.
- Cam Doğrama occlusion/maske kanıtı olmadan ticari üretime açılamaz.
- R1 / 11 benzersiz gerçek onaylı şablon ve insan görsel QA hâlâ ayrı kabul aşaması.
- Tam 6 kategori, cloud, SEO ve ticari Excel süreçleri burada otomatik onay almaz.
- OS Explorer'da aynı isimle manuel Replace olayını Python müdahalesi öncesinde önlemek mümkün değildir; ileride benzersiz receipt klasörü kullanılmalı.
- PR #6 merge veya dağıtım ancak Argon karşılaştırması ve ayrı kullanıcının açık onayıyla.

**Not:** Projenin end-user paketlenmiş final sürümü henüz bu dokümanla ilan edilmemektedir.
