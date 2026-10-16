# P0 Şablon Kaybı — Numara, Kimlik ve Dosya Güvenliği

**Durum: TASLAK / TEST BEKLİYOR. Canlı Windows sistemine uygulanmadı.**

## Somut kök nedenler

1. `sablon_oto_izleyici.py` adı belirsiz gelen dosyaya en düşük boş numarayı veriyordu; eski numara sicilde kaybolduğunda yeniden kullanılabiliyordu.
2. `reserve_number()` eski akışta **çıktılar ve DB kaydı sonrasında** çağrılıyordu; `INSERT OR IGNORE` sessiz başarısız olabiliyordu. Paralel watcher/UI GET işlemleri aynı hedefe çarpışabiliyordu.
3. `_write_png_atomic()` içindeki `os.replace` aynı isimdeki mevcut PNG'yi ezebiliyordu.
4. Başarılı import `.processing` dosyasını siliyordu; ham JPEG/PNG kaynak kaybolabiliyordu.
5. GET `/api/ayarlar`, açılış onarıcısı, PowerShell launcher ve ayrı watcher aynı havuzu otomatik ve farklı zamanlarda işleyebiliyordu.
6. Eski otomatik onarıcı, `ayarlar.json` kaydı yok diye çalışma havuzundaki dosyayı `YENI-BOS` içine TAŞIYORDU.
7. Beyazlatma yazma yordamı `wb` kullanıp aynı isimdeki dosyayı ezebiliyor, uzantı değişince eski dosyayı siliyordu.

## Güvenlik kuralı ve değişiklikler

- Numara sadece **artan** şekilde tahsis edilir; boşlukları doldurmaz.
- Numara **herhangi bir çıktı yazılmadan önce** SQLite `BEGIN IMMEDIATE` + kesin `INSERT` ile kalıcı rezerve edilir.
- `staging_intake.lock` global dosya kilidi iki eşzamanlı Python sürecini seri hale getirir; crash kilidi otomatik temizlenmez.
- Aynı isim/farklı içerik/farklı uzantı **asla aynı kimliği paylaşmaz**; yeni numara verilir, eski numara silinmez.
- PNG üretimi yalnızca `os.link` üzerinden atomic create-only; dosya sistemi desteklemiyorsa **işlem bloklanır**. Windows/OneDrive uyumu ayrıca test edilmelidir.
- Kaynağın birebir baytları `_GUVENLI_GELEN_HAM_GORSELLER` altında benzersiz klasörde saklanır; hata halinde otomatik yedek silinmez.
- Eski auto-healer salt okunur, 8999/vision GET yan etkisiz, launcher otomatik watcher başlatmaz.
- `MOCKUP_STAGING_IMPORT_APPROVED=I_REVIEWED_AND_APPROVED_STAGING_IMPORT` olmadan içe aktarma tamamen kapalı.
- `.processing` eski dosyaları otomatik silmek yerine kurtarma klasöründe saklanır.

## Test kabul eşiği

- 100/100 farklı ham girdi korunacak, 100/100 yeni ayrı UID alacak.
- `005` ve geçmiş numaralı var olan dosyaların SHA'sı değişmeyecek.
- Aynı numara farklı uzantı, kayıt dışı silinmiş numara, eşzamanlı iki job, yeniden başlatma ve yazma hatası bloklama testleri.
- Kaynak DB, orijinal arşiv ve üretim onayları değişmeden ayrı sentetik klasörde test.
- Kodu canlıya kopyalama veya `main`/`safety` içine merge **yasak**; izole Windows testinde `os.link` uyumu ve 100 dosya PASS kanıtı şart.

**Önemli:** Kullanıcının aynı klasöre aynı tam dosya adıyla Windows üzerinden kopyalama yaparken dosya gezgininde `Replace` seçmesi, Python'dan önce kayba neden olur. Bu durum için ayrı güvenli alma/drop arayüzü gerekir; watcher tek başına dışarıdan yapılan bu overwrite'ı durduramaz.
