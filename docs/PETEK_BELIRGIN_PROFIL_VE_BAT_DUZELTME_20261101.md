# PETEK Doğallık Belirgin — Windows BAT düzeltme sürümü (TEST ADAYI)

## Doğrulanmış hata
Eski `PETEK_DOGAL_BEYAZ_DOGRULA.bat` dosyasında `scripts\v4102_verify_package.py`
oluşturulurken Python stringindeki `\v` yerine ASCII 0x0B (vertical tab)
yazılmış. Windows `Invalid argument` sonucu veriyor; bu **paket doğrulama BAT** kusurudur,
veri bozulması ispatı değildir.

## Düzeltme
- BAT dosyasındaki doğrulayıcı yolu gerçek ASCII backslash ile yazıldı; bütün BAT'ler kontrol edildi.
- `PETEK_BELIRGIN_DOGRULA_WINDOWS.bat` ve `PETEK_BELIRGIN_BASLAT_WINDOWS.bat` eklendi.
- PETEK Doğallık için `Doğal` ve `Belirgin` seçimleri eklendi; **varsayılan Belirgin**.
- Belirgin yalnız PETEK baskısında önceki `strong` mat-ışık modunu kullanır;
  diğer 6 kategoriye bu seçenek uygulanmaz. Genel efektler kapatılırsa Belirgin de uygulanmaz.
- Değişiklikler yalnız render/arayüz kodudur: onaylı maske, 4 köşe, kaynak
  fotoğraflar, mağaza atamaları ve SQLite'ya dokunulmaz.
- Pembe temizliği ve gerçek 13–16 ızgara ölçüm motoru korunmuştur.

## Belirgin profil hedefi ve limitleri
- PETEK baskısında uzun yumuşak pencere çıtası/yaprak gölgeleri ve hafif sıcak
  aydınlık hissi; beyazlar kaynak orijinal yan gövdeden örneklenir.
- Magenta kaynak renk referansı olamaz; alfa %100 kalır.
- Delik içlerine ışık eklenmez; maskenin dışı kaynakla bit düzeyinde aynıdır.
- Çizgi/izgara geometrisini serbest biçimde eğip bükmez, üst-alt uç konsensusu korunur.
- Bu efekt hâlâ **deterministik bir gölge modeli**; gerçek pencere konumunu
  otomatik saptadığı veya her sahnede fotogerçekçilik sağladığı iddia edilmez.

## Test/geri dönüş
- `PETEK_BELIRGIN_DOGRULA_WINDOWS.bat` SHA256 kontrolünü çalıştırır.
- İlk testi YENİ ve BOŞ bir klasörde yap; eski çalışan sistemi ezme.
- Kendi mağaza/PETEK verilerini test paketi üzerine KOPYALAMA veya TAŞIMA.
- İstenmeyen sonuçta yalnız bu test klasörünü silip eski çalışan kurulumdan
  devam et. Veritabanı taşıması gerektiren hiçbir işlem eklenmedi.
- Gerçek Windows ortamı ve gerçek PETEK örnekleri ile canlı üretim testi: WINDOWS_NOT_VERIFIED.
