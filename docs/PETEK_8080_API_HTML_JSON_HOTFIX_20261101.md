# PETEK /api önizleme HTML/JSON hata düzeltmesi

## Belirti
`Unexpected token '<', "<!doctype ..." is not valid JSON`.

## Teknik neden
Tarayıcı POST `/api/petek/preview-artwork` çağrısı için JSON beklerken HTML alıyor.
Olası kaynaklar: eski/yanlış Flask servisi 8080'i tutuyor (404), sunucu iç hatası (500), isteğin çok büyük olması (413). Bu hata yalnız başına bunları ayıramaz.

## Çözüm
- JSON olmayan yanıtlara HTTP durumunu ve çözüm yolunu açıklayan istemci hatası.
- Yeni, salt-okunur `/api/petek/service-status` kontrat kontrolü; büyük görüntü POST'undan önce sürüm uyuşmazlığını yakalar.
- PETEK için 404/405/413/500 JSON hata gövdesi (diğer sayfaları değiştirmez).
- Cache-busting JavaScript versiyonu.
- Salt okunur, PID/komut satırı raporlayan Windows port teşhisi. Bilinmeyen süreci sonlandırmaz.

## Güvenlik ve geri dönüş
Bu yama PETEK maske, 4 köşe, kaynak fotoğraf, SQLite, mağaza veya gerçekçilik algoritmalarını değiştirmez.
Eski ZIP ayrı klasörde korunmalı. Kullanıcıya yalnız yeni ZIP ile başlatma önerilir.
Flask HTTP/gerçek Windows 8080 kabulü için sahada test gerekir: `WINDOWS_NOT_VERIFIED`.
