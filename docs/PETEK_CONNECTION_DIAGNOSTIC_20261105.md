# PETEK / 4 Köşe bağlantı teşhis ve güvenli yeniden bağlanma

## Kaynak incelemesi

- PETEK API, `SABLON_V2_MIMARI/core/petek_web_v477.py` içindeki Flask blueprint'tir.
- 4 Köşe/PETEK tarayıcı editörü `static/js/petek_editor_v477.js` içinden aynı-origin `/api/petek/...` yollarını çağırır.
- Ana Merkez, `MERKEZ/merkez.py` ve `MERKEZ/review_port_owner_v478.py` ile yalnız kimliği doğrulanmış kendi Flask sürecini 127.0.0.1:8080 üzerinde başlatır/devir alır. Bilinmeyen port sahibi kapatılmaz; sağlıklı ve çalışan süreç gereksiz yere durdurulmaz.

## Kesin gözlem

Bu inceleme sırasında 127.0.0.1:8080 dinliyordu ve `GET /api/petek/service-status` HTTP 200 ile beklenen `PETEK_PREVIEW_API_VNEXT_JSON_20261101` sözleşmesini döndürdü. Süreç, `CODEX_ACTIVE/SABLON_V2_MIMARI/app.py` kaynağından çalışıyordu. Bu nedenle bildirilen `Failed to fetch`, PETEK maske/4-köşe motoru hatası değil; tarayıcının sunucuya erişemediği an (sunucu sürecinin kapanması, WebView bağlantısının kopması veya yanlış/stale listener) sınıfındadır. Başarısız olan ilk istek, editörün liste açılışında yaptığı `/api/petek/templates` isteğidir; öncesinde artık salt-okunur `/api/petek/service-status` kontrolü vardır.

## Uygulanan düzeltme

1. Editör açılırken servis sözleşmesi kontrol edilir; başarısızsa kullanıcıya açık neden ve `Bağlantıyı yeniden dene` düğmesi gösterilir.
2. Editör açıkken 15 saniyede bir salt-okunur sağlık kontrolü yapılır. Kopma sessizce beklenmez.
3. Ağ/HTML/yanlış sözleşme hataları yerel Flask günlüğüne `PETEK_CONNECTION_DIAGNOSTIC` satırı olarak iletilir. Bu uç nokta kaynak, maske, onay veya DB değiştirmez.
4. Yeniden deneme başarılı olduğunda PETEK listesi yenilenir. Sunucu durmuşsa Ana Merkez'in mevcut güvenli başlatma akışı (PID/token/kök doğrulaması ve `ensure_canonical_8080`) kullanılmalıdır; bilinmeyen 8080 süreci otomatik kapatılmaz.

## Doğrulama

- Python derleme ve JavaScript sözdizimi kontrolü: PASS.
- Yeni bağlantı yaşam döngüsü testleri (`tests/test_petek_connection_lifecycle.py`): 2 PASS.
- Gerçek Windows WebView2 üzerinden sunucuyu durdurup yeniden başlatma testi bu oturumda yapılmadı: `WINDOWS_NOT_VERIFIED`. Canlı 8080 sağlık isteği bu oturumda HTTP 200 olarak gözlendi.

## 2026-11-05 kalıcı düzeltme

Hata raporundaki `8080_SAHIP_BILINMIYOR` kodunun kök nedeni 8080'in gerçekten
sahipsiz olması değildi. Bu Windows 11 kurulumunda
`Get-NetTCPConnection -State Listen`, gerçek Flask dinleyicisini `State` alanı
boş olacak şekilde döndürüyor; buna karşın dinleme uç noktasının
`RemotePort=0` değeri korunuyor. Eski sorgu `-State Listen` filtresi nedeniyle
dinleyiciyi yok sayıyor ve güvenli devir kodu yanlış hata üretiyordu.

`MERKEZ/review_port_owner_v478.py` artık yalnızca 8080'i sorgulayıp
`RemotePort=0` olan uç noktaları dinleyici adayı olarak topluyor. TIME_WAIT veya
aktif bağlantılar uzak porta sahip oldukları için dışarıda kalıyor; ardından
mevcut PID/SID/komut satırı/kod kökü/çalışma kökü doğrulamaları aynen uygulanıyor.
Bu davranış `TESTLER/test_v478_port_owner.py` içinde regresyon testiyle sabitlendi.

Doğrulama: `test_v478_port_owner.py` ve `test_petek_connection_lifecycle.py`
birlikte `10 passed`; Python derleme kontrolü PASS.
