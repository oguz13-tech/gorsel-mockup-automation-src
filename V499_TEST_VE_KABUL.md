# GÖRSEL ÜRETİM MERKEZİ — V4.9.9 WINDOWS ADAY

**Tarih:** 31 Ekim 2026  
**Kaynak:** Kullanıcının V4.9.8 ZIP'i üzerinden izole V4.9.9 kod düzeltmeleri.  
**Durum:** **WINDOWS_NOT_VERIFIED — gerçek Windows + Flask HTTP + canlı PETEK verisi kabulü bekliyor.**

## Gerçekten yapılan ve kodla test edilen değişiklikler

1. **PETEK tüm taslakları tek toplu onay:** GÖRÜNEN doğrulanmış DRAFT'lar otomatik seçilir. Her şablonun yanındaki tik kutuları zorunlu değildir. Kullanıcı yalnızca bir kez toplu onay sorusunu kabul eder. Sunucu fotoğraf kaynağı, UID, SHA, maskenin gerçek QA durumu ve DRAFT statüsünü her kayıt için tekrar denetler. Uygun olanlar onaylanır, hatalılar DRAFT kalır; tekil açıklamalar raporlanır. Program kullanıcıyı sekizli onay turlarıyla durdurmaz; performans için içeride sekizli HTTP taleplerini kullanabilir. İptal butonu, sıradaki grubun gönderilmesini durdurur.
2. **Toplu seçimde PETEK dosya adları artık kaybolmamalı:** Sol listede mevcut input'un yüzde 100 genişlik alıp şablon butonunu sıkıştırması engellendi; checkbox genişliği 18 px'e sabitlendi, dosya adı kalan alanı kullanır.
3. **Aktif kategoriye bağlı ok tuşları:** PETEK açıkken altı kategorinin genel ok tuşu işleyicisi etkisizleştirildi. PETEK listesinde ok tuşları kendi öğeleriyle gezinir; maske üzerinde kaydedilmemiş değişiklik varsa gezinme engellenir.
4. **PETEK Ahşap Boyasını Sil fırçası:** Maskenin boyanmış alanını siyaha geri döndürür; orijinal fotoğraf piksellerini silmez; Ctrl+Z geri alması korunur.
5. **Onaylı PETEK maskesi için güvenli 4 köşe/maskeyi yeniden düzenleme:** Onaylı kaydın kendisi salt-okunur kalır. İnsan onayıyla yeni revizyon DRAFT açılır, köşe ve maskeyi değiştirebilirsin. Onay verildiğinde yeni revizyon geçerli onaylı maske olarak atomik `active_revisions.json` kayıt işaretçisinde seçilir; önceki approved profil ve maskesi SHA ile aynı kalır. “Önceki Onaylı Sürüme Dön” yolu eklenmiştir. Aynı fotoğrafın eski ve yeni maskeleri için kaynak SHA kontrolü korunur. Başarı/başarısızlık/geri dönüş için izole Registry testi yapıldı.
6. **7 kategoride ortak Yeni/Mavi, Onaylı/Yeşil, Taslak/Sarı, Hatalı/Kırmızı tik kutulu görünüm filtresi:** Filtre yalnızca görünüme etki eder, kayıtları değiştirmez.
7. **Antrasit görünüm:** Tk koyu tema/ana dashboard ve PETEK web görünümünün arka planları antrasit palete yaklaştırıldı. Mor vurgu, okunaklı yazı ve durum renkleri korundu.
8. **Arayüzü Düzenle, sekmeler, renk/efekt, 4K kontrol düğmesi, modern üretim panelleri, test/not merkezi:** V4.9.8'den korunmuştur. V4.9.9'a özel kapsamlı canlı Windows UI testi bu ortamda mümkün olmadı.
9. **PETEK 15 koyu ızgara (varsayılan Orta) ve pembe kenar temizliği:** Bu iki motorun kaynak dosyaları değiştirilmedi. Kullanıcı V4.9.5'te ikisini de başarılı buldu.
10. **Test Merkezi**: Eski sekizli tik yönlendirmesi tek toplu onay kılavuzuyla değiştirildi; onaylı maske revizyonu, klavye ve liste görünümüne ayrı test kartları eklendi. Kayıtlar Windows `%LOCALAPPDATA%` altında saklanır.

## Çalıştırılan doğrulamalar

- İzole PETEK registry revizyonu/geri alma ve UI statik testleri: **5/5 geçti**.
- Seçili PETEK V3, bakım/güvenlik, koyu ızgara/kenar temizliği ve arayüz regresyonları: **54 geçti; 1 atlandı; 1 HTTP-Flask testi ortam bağımlılığı nedeniyle çalıştırılmadı**.
- Python sözdizimi: **281 Python dosyasında hata yok** (eski referans kopyaları hariç).
- JavaScript sözdizimi: derlenebilir JS dosyaları `node --check` ile denetlendi.
- ZIP ayrı çıkarılarak SHA-256 manifest ve ZIP CRC doğrulaması yapılır; sayı paket raporunda verilir.

## Ayrıntılı açık kabul sınırları

- **Flask bu test ortamında yüklü değil ve ağdan kurulamıyor:** Yeni `/api/petek/bulk-approve-confirmed`, yeni revizyon HTTP uçları ve tam browser etkileşimi gerçek Flask test istemcisi ile bu ortamda çalıştırılmadı. Bunlar Windows kullanıcı Test Merkezi'nde görülmeden koşulsuz final ilan edilemez.
- **Eski ve yeni maskelerin geçerli üretim seçimi** izole Registry testinde doğrulandı. Mevcut kullanıcı mağaza profil atamalarında, aktif devam eden üretim kuyruğunda ve yedi kategoride gerçek seri üretim için ayrıca kullanıcı kabulü gerekir.
- **Arayüz tamamen serbest piksel düzenleme değildir:** V4.9.8'deki güvenli sekme/kart sıralama ve kişiselleştirme korunuyor; bu sürümde her ekrana evrensel hata pop-up desteği baştan sona eklenmedi.
- Magenta LAB gerçek dosya değiştirme, Real-ESRGAN GPU ve bulut/Trendyol Excel erişimi bu oturumda çalıştırılmadı; bunu olmuş gibi saymıyoruz.
- Kullanıcının gerçek OneDrive SQLite, orijinal yedekler, onaylı şablon/maske verileri bu çalışma alanından değiştirilmedi.

## Kullanıcının yeni sürümde kontrol edeceği ana testler

1. **PETEK Toplu Seçim** aç → `GÖRÜNEN TÜM TASLAKLARI TEK ONAYLA` → tek onay → bütün uygun DRAFT kayıtları onaylansın; sekizli ekran ve tek tek tik yok. Hatalılar DRAFT kalıp rapor versin.
2. Toplu seçimde dosya adları ve durum çerçeveleri görünür, kaydırma düzgün; PETEK açıkken Sağ/Sol ok Wifi listesine gitmez.
3. Önceden onaylı PETEK maskesi → Yeniden Düzenle → dört köşeyi düzelt → taslak kaydet → onayla → güncel revizyon → eski onaylıya geri dön.
4. Ahşap Boyasını Sil fırçası yeşil alanı geri alır; fotoğraf değişmez.
5. Ana ekran ve Seri Üretim penceresi aynı anda çalışır; açılış hızlı kalır; 4K ve HTTPS kontrolleri hover sırasında okunur.
6. 15 slot + pembe temizlik zaten kullanıcının V4.9.5 kabulünde başarılıdır; bu motorlara dokunulmadı.

## Güvenli kurulum

**V4.9.8/V4.9.5 çalışan klasörleri silme.** ZIP'i ayrı, boş ve OneDrive dışındaki klasöre çıkar. `GORSEL_V46_CANDIDATE/V499_DOGRULA_WINDOWS.bat` ile manifesti kontrol et, `V499_BASLAT_WINDOWS.bat` ile başlat. Ana çalışma klasörü önceki gerçek veri kökü olmalı. Veriler yedeklenmeden ve görsel denetimi yapılmadan canlı seri üretime geçme.
