# GÖRSEL ÜRETİM MERKEZİ V4.10.0 — GÜVENLİ ADAY

**31 Ekim 2026 — `WINDOWS_NOT_VERIFIED`.** Önceki V4.9.9 paketi korunarak yeni mağaza şablon eşleştirme ekranı geliştirildi. Bu sürüm gerçek Windows verileriyle çalıştırılıp kullanıcı tarafından kabul edilmeden koşulsuz final değildir.

## Kullanıcının isteği ve uygulanan gerçek değişiklikler

1. **Önce mağaza → sonra kategori:** 7 kategoriden birini seçmeden şablon atama listesi açılmaz. Mağaza seçimi, isimli bir Combobox; kullanıcı yeni mağazayı ayrıca oluşturabilir.
2. **Onaylı şablon listesi ve küçük fotoğrafları:** Seçilen kategoride 36'lık sayfalar, resim küçük önizlemesi, dosya/şablon kimliği, mevcut mağaza sahibi ve durumu. Sağ alanda seçilen görselin daha büyük önizlemesi, sağ üstte seçili mağazanın mevcut bütün eşleşmeleri.
3. **Anlaşılır sahiplik:** Mavi = kullanılabilir; yeşil = zaten bu mağazada; kırmızı = başka mağazada / daha önce kullanıldı (ve sahibi); turuncu = önceki onay/SHA değişmiş, kontrol gerekiyor. Başka mağazaya ait kaynak SHA eşleşirse farklı dosya adına rağmen engellenir.
4. **Kolay seçim:** Her satıra tek tıklama ile işaretleme, Ctrl tuşu gerekmez. Sayfa veya kategorideki uygunları seç ve seçimi temizle. Birden çok sayfada seçim korunur.
5. **Son onay:** Mağaza, kategori, tam seçili şablon sayısı ve seçilen BÜTÜN dosya adları ayrı kaydırılabilir son onay penceresinde gösterilir. Açık bir kez kullanıcı onayı olmadan yazma yapılmaz.
6. **Atama ayrımı:** Mağaza atama ekranı ana üretim ekranının seçimlerini **kullanmaz**. Seri Üretim ilk açılışında hiçbir şablon otomatik seçilmez. Üretimin `store_plan` hesabı filtrelenmiş görüntü listesi yerine **bütün onaylı şablon listesini** kullanır (görünür filtre atanan başka kategoriyi yanlışlıkla kaybettirmez).
7. **Baskı tasarımı tekrar kullanımı:** Aynı ham tasarım numarası (örn. 18472), A/B/M5 mağazalarının hepsinde farklı onaylı mockup fotoğrafları ile kullanılabilir. Korunan benzersiz kaynak **mockup SHA**'dır; ham baskı tasarım SHA'sına mağazalar arası yasak uygulanmaz. pHash/benzerlik taraması etkinleştirilmedi.
8. **Veri güvenliği:** Eski mağaza JSON dosyasını ve onaylı PETEK/maskeleri silmez/taşımaz. Var olan mağaza yöneticisinin atomik yazma ve geri dönüş yedekleme mekanizması korunur. Onay/SHA değişmiş eski atamalar görünür ve otomatik yeniden kullanılmaz. Atama kaldırmak da ayrı açık onay gerektirir.
9. **Yapmam Gereken Testler:** Yeni `STORE-ASSIGN-EXPLICIT-V4100` test kartı kişisel Test Merkezi veritabanına eklenir; önceki onaylanmış testler yeniden açılmaz.

## Gerçek test sonuçları

- Kaynak kod testleri: **72 geçti**, Flask gerektiren **1 test ortamdan dolayı çalıştırılamadı/dışarıda bırakıldı**.
- Eşleştirme özeli 10 test (Tk GUI dahil) geçti; eski PETEK, 4K, Windows kapatma, üretim güvenliği ve mağaza/Excel regresyonları dahil edildi.
- 286 Python dosyası derleme kontrolünden geçti; 7 JS dosyası Node sözdizimi kontrolünden geçti.
- Şu 6 çekirdek kaynak dosya SHA düzeyinde V4.9.9 ile **aynı**: PETEK 15 ızgara, PETEK pembe temizliği, PETEK cutout/maske, unified batch üretimi, StoreProfiles veri modeli, bulut Excel.
- Manifest SHA-256 ve ZIP CRC ayrıca paketlenmiş arşivde doğrulanır.

## Hâlâ doğrulanmamış kabul sınırı

Kullanıcının gerçek Windows / OneDrive ana klasörü ve gerçek mağaza atamaları burada bulunmadığından: Windows canlı arayüzü, yüzlerce gerçek küçük resim yükleme performansı, Flask HTTP, PETEK gerçek üretim, 4K GPU, HTTPS bağlantı/Trendyol XLSX ve eski mağaza profil kayıtlarının gerçek veriyle kabulü **WINDOWS_NOT_VERIFIED**.

## Kurulum ve kullanıcı testi

Eski çalışan V4.9.9/4.9.5 klasörünü silme; ZIP'i yeni boş OneDrive dışı klasöre çıkar. `GORSEL_V46_CANDIDATE/V4100_DOGRULA_WINDOWS.bat` ile bütünlüğü denetle, sonra `V4100_BASLAT_WINDOWS.bat` ile çalıştır. `Seri Üretim > Mağaza Profilleri / Şablon Atama` bölümüne gir. İki mağazayı farklı mockup kaynaklarıyla eşleştir; önce küçük sayıyla onayla ve Test Merkezi'nde `STORE-ASSIGN-EXPLICIT-V4100` görevini tamamla.

**Not:** ZIP'deki eski V499 belgesi tarihsel rapordur; güncel V4100 raporu bu dosyadır.
