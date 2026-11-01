# PETEK / Doğal Beyaz + Uzun Pencere Gölgesi (VNext TEST ADAYI)

## Ne değişti
- `MERKEZ/PETEK_V3/realism.py` için magenta (#FF00FF) orijinal yüzeyden hiçbir beyaz/renk referansı alınmaz. Öncelik orijinal, fiziksel, düşük doygunluklu açık gövde bölgeleri; kanıt yoksa nötr mat varsayılan.
- Beyaz baskı çevre beyazına sınırlandırılır; `alpha=255` / opaklık korunur, magenta alttan geçirilmez.
- Düşük çözünürlükte yumuşak pencere çıtası (uzun eğimli gölge) ve yaprak gölgeleri üretilir; yalnız onaylı baskı maskesinde uygulanır. Ağır cam parlaması yerine mat yüzey amaçlanır.
- Kenar harmonizasyonunda kaynak magenta ile renk karıştırılmaz. Korunan delikler, ızgaralar ve kavisler birebir kalır.
- Mevcut `petek_slot_geometry_vnext.py` uç konsensusu korunur: 13/14/15/16 gerçek delik, perspektifli düz eksen, yanlış uzunluk varsa tekil iş incelenir.
- A/B önizleme üretim öncesinde isteğe bağlıdır; şablon insan onayı ve kaynak/maske SHA güvenliği devam eder.

## Dışarıdan gelen PIL kodunu neden aynen kullanmadık?
- Alpha %90 yapmak alttaki orijinal magentayı görünebilir kılar. Bu pakette alpha asla değiştirilmez.
- `np_img[white,2] *= 0.95` uint8 üzerinde dtype/casting hatası verir.
- Kodda Multiply, GaussianBlur, Mesh warp, grain gerçek uygulama değil, yalnız yorum satırıdır.
- Genel tüm-beyaz-piksel seçimi orijinal beyaz kasayı da değiştirir; bu yüzden yalnız maskeli baskı RGB çıktısında işlem yapılır.
- Mevcut dört köşe/homografi zaten gerekli perspektifi uygular; ek mesh warp geometriyi bozabilir.

## Gerçek kullanım koşulu
DİKKAT: **WINDOWS_NOT_VERIFIED**. Gerçek Windows + kullanıcı şablonları ve mağaza verileriyle test edilmedi. Sadece izole yeni klasörde dene; mevcut V4.10.2, SQLite, mağaza JSON, orijinal arşiv, onaylı maskeler ve 4 köşeleri değiştirme.

## Sonraki görsel kabulü
Önce son adaydan 2–3 PETEK önizlemesi al. Kontrol: beyaz/sol kasa uyumu, pembe/purple sızıntısı 0, yumuşak uzun pencere/yaprak gölgesi görünürlüğü, gerçek delik sayısı ve boy konsensusu, maske dışı fotoğrafın aynen korunması. Hatalı şablon için güvenlik kilidini kaldırma; yalnız o işin inceleme uyarısı raporlanır.
