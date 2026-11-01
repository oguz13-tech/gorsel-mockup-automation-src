# PETEK İzole Düzeltme Test Raporu

## Kapsam

Bu paket yalnız kaynak kodu, güvenli testleri ve toplu gerçek tasarım
önizleme UI düzeltmesini içerir. SQLite, kaynak fotoğraf, onaylı maske,
mağaza profili, üretim ledger'ı ve müşteri tasarımı paketlenmemiştir.

## Değişiklik

- `SABLON_V2_MIMARI/templates/index.html`: tüm PETEK kayıtları için tek
  ekranda kart tabanlı gerçek artwork önizleme alanı.
- `SABLON_V2_MIMARI/static/js/petek_editor_v477.js`: her template için
  bağımsız detail + preview çağrısı; tek hata diğer kartları durdurmaz.
  `diagnostic_preview` sonuçları açıkça güvenli teşhis olarak gösterilir.
- `SABLON_V2_MIMARI/static/css/petek_editor_v477.css`: kart/grid görünümü.
- Renderer, kaynak fotoğraf–maske güvenlik guard'ı, onay ve batch üretim
  kodu değiştirilmedi.

## Çalıştırılan testler

| Test | Sonuç |
|---|---|
| PETEK kontrat, 422 fallback, dinamik yarık, preview parity testleri | 23 passed |
| İzole toplu-preview UI kontratı | PASS |
| İzole JavaScript `node --check` | PASS |
| Preview browser/API contract suite | 2 skipped (Playwright/runtime bağımlılığı bu sandbox'ta yok) |
| Gerçek Windows runtime/API/ledger/mağaza verisi | ÇALIŞTIRILAMADI |

Gerçek runtime kanıtı bu sandbox oturumunda mevcut değildi:
`MOCKUP_RUNTIME_WORKSPACE` ve `PETEK_V3_LOCAL_STATE` ayarsızdı,
`%LOCALAPPDATA%\GorselMockup` yoktu ve 8080 süreç sorgusu CIM erişim
kısıtına takıldı. Bu nedenle gerçek 14/16 fotoğraf, `wudie` UID/SHA ve
ortak ticari output SHA için PASS iddiası yapılmamıştır.

## Güvenlik

- Fiziksel yarık guard'ı kapatılmadı.
- Geçici maskeler yalnız RAM'de kalır; onay veya üretim anlamına gelmez.
- Preview endpoint'i üretim ledger'ına yazmaz.
- Hatalı template kartı `KONTROL GEREKİYOR` olarak kalır.

## Geri dönüş

Canlı klasöre kurulum yapılmadı. İzole paketi kullanmayı bırakmak için
yalnızca ZIP'i kapatmak yeterlidir; canlı verilerde geri dönüş işlemi
yoktur.
