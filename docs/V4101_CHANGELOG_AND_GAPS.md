# V4.10.1 değişiklikler, kanıt ve hâlâ açık iş listesi

## Bu pakette değiştirilenler

1. **PETEK Toplu Seçim dosya adları:** global `input width:100%` etkisini ezmek için CSS grid ve *sabit 17px checkbox* uygulandı; uzun dosya adları kalan genişlikte elipsis+tooltip ile görünüyor. **Chromium 400px ve 1280px** izole DOM/screenshot testi geçti. Kullanıcının gerçek Windows ekranı ayrıca bekliyor.
2. **Eski 8'li onay penceresi ve her-maske tik zorunluluğu:** ilgili dialog, kullanılmayan review fonksiyonları ve eski JS olay bağları kaldırıldı. Yeni bir defalık toplu onay düğmesi ve sunucu tarafı ayrı SHA/UID/maske doğrulaması korunuyor.
3. **Ortak durum/renk dili:** 7 kategoride yeni=mavi, onaylı=yeşil, taslak=sarı, hatalı=kırmızı CSS; ortak status filter JS. PETEK farklı işlemleri tutuyor; iş mantığı kodları bütünüyle birleştirilmiş değil.
4. **Antrasit tema ve okunurluk:** PETEK ve diğer altı kategorinin liste tipografisi/hover/koyu renkler iyileştirildi.
5. **Ana ekranda doğrudan kart taşıma:** `Kartları Taşı` modunda tutamaçtan başka kart üzerine bırakarak sıra UI JSON'una atomik kaydedilir. Düzenleme modunda kart eylemleri tetiklenmez. Mevcut sekme yöneticisi ve geri al/varsayılan düzen korunur.
6. **Renk seçiciler:** zemin/kart/düğme/başlık/kenarlık renkleri UI yapılandırmasına eklenmiştir; kontrast doğrulaması düşük okunabilir seçenekleri reddeder. Görünüm efektleri ve farklı pencere/kart ebatları yönünden bazı sınırlamalar sürer.
7. **Hata neden/çözüm:** Tk merkezde global `showerror` kılavuzu; Web altı kategori `showMessage` içinde gerekçe ve çözüm; PETEK'te ilgili adıma götüren modal. Toplu kuyruktaki dosya hatalarında tekrar tekrar popup göstermez.
8. **Test Merkezi:** yeni V4101 kabul kartları + sürüm/başlatıcı/manifest güncellemesi.

## Kullanıcı tarafından önceki sürümde doğrulanmış ve KORUNAN

- PETEK 15 koyu dikey yarık, varsayılan Orta yoğunluk.
- PETEK pembe/magenta kenar kalıntısı temizliği.
- Seri Üretim penceresinin hızlanması.
- Programı Kapat işlevi.

## YAPILMIŞ GİBİ RAPORLANMAMASI GEREKENLER

- **WINDOWS_NOT_VERIFIED:** Flask gerçek PETEK HTTP toplu onay akışı, gerçek üretim/GPU 4K, mevcut kullanıcının fotoğraflarında maskelerin revizyonu/geri alınması, 7 kategorinin tümündeki durum filtreleri gerçek Windows kabulü.
- **Kısmi UX:** Kartları sürükleme mevcut ana sayfada sıralama şeklindedir; istediğin serbest piksel koordinatı/istenen ebatta kart boyutlandırma yok. Üretim sekmeleri ayrı düzenleyici üzerinden düzenlenir. Farklı pencerelerin tamamında aynı antrasit tonu tek tek doğrulanmadı.
- **Kısmi UI:** 7 kategori aynı renk/filtre ve satır tipografisini kullanır; PETEK özel HTML/JS editörü altı genel kategoriyle tek bir kod bileşenine tamamen birleştirilmiş değildir.
- **Kısmi hata çözümü:** Tk `showerror` ve temel Web/PETEK hataları kapsanır; bütün bağımsız BAT araçları ve her Flask API hata kodu için bire bir otomatik düzeltme butonu yoktur. Riskli kurtarmalar hiçbir zaman otomatik yapılmaz.
- **Eski açık riskler:** Cam/ahşap yansımaları, 1000+ iş uzun testleri, XLSX/Trendyol link canlı doğrulaması, 80 MB/40MP stres, OneDrive senkron/kimlik ve güncel GitHub ile kaynak eşleşmesi ayrıca takip edilir. Önceki rapora ve GitHub #72'ye bak.

## GitHub dürüstlük kuralı

Bu dağıtım kaynağının ve ZIP'in SHA karşılığı GitHub'da yayınlanıp doğrulanmadıkça **GITHUB_SOURCE_NOT_SYNCED** yazılmalıdır. Yalnız issue açmak, kaynak kodu GitHub'a aktarmak değildir. `V4101_GITHUB_SYNC_STATUS.md` bu farkı ve çalışma talimatını açıkça belirtir.
