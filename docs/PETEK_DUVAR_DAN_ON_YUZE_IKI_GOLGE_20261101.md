# PETEK 2 yatay gölge — duvardan ön yüze ve diğer duvara

## Talep ve fiziksel hedef
Gölge sahnenin kadrajından başlayıp duvarı, PETEK'in baskılı ön panelini
hafif yatay açıyla keser; yeterli duvar varsa ürünün diğer tarafına devam eder.
Tam olarak **iki** yumuşak pencere/perde gölge bandı kullanılır.

## Kod
- `MERKEZ/PETEK_V3/realism.py`: fotoğraf koordinatlarında ortak iki bantlı
  ışık alanı; yalnız baskı maskesindeki piksellere uygulanan kol.
- `MERKEZ/PETEK_V3/wall_window_shadows_vnext.py`: aynı alanı, fotoğrafın
  kenarına bağlı, renk/doku bakımından güvenilir duvarlarda uygular. Dolap yan
  paneli, gerçek siyah yarık, dekor, zemin ve korunmuş magenta işaretler
  bu kolun kapsamı dışındadır. Güvenilir duvar yoksa `WALL_NOT_CONFIDENT`
  durumuyla **yalnız duvar kolunu** atlar.
- `MERKEZ/PETEK_V3/petek_visual_pipeline_vnext.py`: duvar gölgesi yalnız
  RAM'deki son çıktı kopyasına eklenir; özgün fotoğraf/maske/quad değişmez.
  Korunmuş dış bölgedeki tüm değişiklikler kaynak fotoğraftan bağımsız
  yeniden hesaplanan duvar gölgesiyle piksel piksel doğrulanır.
- `SABLON_V2_MIMARI/core/petek_web_v477.py`: A/B önizlemesinde SONRA
  kareyi aynı kontrolle denetler ve `wall_shadow_qa` raporunu döndürür.

## Değiştirilmeyen davranışlar
Pembe magenta temizlik kodu, 13–16 fiziksel ızgara ve üst/alt kavis
motoru, onaylı maskeler, şablonlar, çalışma klasörü, SQLite ve mağaza
atamaları değiştirilmedi. A/B testi zorunlu hâle getirilmedi.

## Saha kabulü
Önce aynı PETEK şablonuyla A/B görüntüsünü, ardından tek gerçek seri
üretimi karşılaştırın. Iki gölgenin duvar ve ön panel üzerinde aynı
hizada olması gerekir. Görünür duvarın fotoğrafından güvenli yüzey
algılanamazsa dış duvar gölgesi uygulanmayabilir; zorla boyama yoktur.
Windows gerçek ortam kabulü: `WINDOWS_NOT_VERIFIED`.
