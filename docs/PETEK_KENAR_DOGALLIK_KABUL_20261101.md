# PETEK kenar doğallığı — izole aday

## Kaynak bazlı teşhis
- Sert görünümlü dikey gövde/baskı birleşimi, fotoğrafik referansla kenarda yumuşak ton geçişi olmamasıyla ilişkili.
- Önceki şablonlarda magenta kaynak renklerini alpha ile karıştırmak pembe sızıntısı yaratıyordu. Bu nedenle **alpha feather / seamlessClone uygulanmadı**.
- Yeni fonksiyon yalnız **baskının izinli pikselleri** içinde çalışır; orijinal beyaz gövdeden yalnız düşük doygunluklu/açık renkli örnekleri alır. Örnek yoksa renk uydurmaz.
- Basılı renkli çizim ve siyah yazıya dokunmaz; 13–16 delik ve kavislerin korunmuş piksellerine dokunmaz.
- Sol dikey birleşimde 0–42 px aralığında yumuşak ton harmonizasyonu ve gerçek dış konturda maks. %1,8 temas gölgesi.
- Önce/Sonra: 'off' modunda uygulanmaz, normal ve Belirgin modlarda aynı PETEK motorundan uygulanır.

## Değişiklikler
- Yeni: `MERKEZ/PETEK_V3/edge_harmony_vnext.py`
- Güncel: `MERKEZ/PETEK_V3/engine.py` (yalnız PETEK kompozit çağrısı)
- Yeni test: `tests/test_vnext_petek_edge_harmony_20261101.py`
- Paket doğrulayıcı, BAT ve bu belge.

## Kritik koruma
Pembe kaynak saçak temizliği, ızgara sayısı/ölçümü, `realism.py` gradyan ve yatay gölgeler,
onaylı maskeler, orijinal fotoğraflar, mağaza ve SQLite dosyaları değiştirilmedi.

## Sınır
Gerçek şablon ve kamera perspektifinde kenar tonunun gözle değerlendirilmesi gerekiyor.
Gerçek Windows testi: WINDOWS_NOT_VERIFIED. İsteğe bağlı pilot, mevcut sürümü silmeden.
