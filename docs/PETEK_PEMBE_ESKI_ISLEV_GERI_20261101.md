# PETEK — pembe onarım işlevinin kontrollü geri kazanımı

Eski maskenin DIŞINDAKİ sınırlı pembe saçak düzeltmesi 409 hotfix sonrasında
geçersiz kılınmıştı. Bu aday, 4 köşe/kavis/delik/maske kayıtlarını değiştirmeden
salt bellek içi onarım istisnasını geri getirir.

- Yalnız eski geometrik alt-sol pembe koridorunda, kaynak fotoğrafın gerçek
  yüksek doygunluklu magenta pikselleri düzeltilebilir.
- Diğer bütün baskı-maskesi-dışı pikseller, gerçek koyu yarıklar, kavis,
  beyaz gövde, duvar ve zemin fotoğrafla birebir aynı kalır.
- Önizleme ve üretim aynı doğrulama fonksiyonunu kullanır.
- A/B testi 'önce' gerçekten `lighting=off` ile efektsizdir.
- Belirgin profilde uzun pencere gölgeleri güçlendirildi.
- Kullanıcı verisine ve onaylara yazma işlemi yoktur.
- Sentetik testler Windows canlı kalite kabulü değildir.
