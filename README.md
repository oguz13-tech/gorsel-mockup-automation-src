# Görsel Üretim Merkezi — GitHub kaynak senkronizasyonu

> **DURUM (2026-11-03):** Bu GitHub dalı bir **güvenli kaynak senkronizasyonu adayıdır**. Eski `main` dalı ve tarihsel PR'lar, Windows bilgisayarındaki güncel `CODEX_ACTIVE` kodunu **temsil etmek zorunda değildir**. Henüz tüm aktif kaynaklar GitHub'a aktarılmamıştır; `FINAL` veya gerçek Windows kabulü iddia edilmez.

## Önce buradan başla
- Güncel iş listesi: [Issue #82](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/82) (yalnızca 12 iş paketi).
- Tarihî belgeler, eski PR'lar ve 103 maddelik önceki plan **referanstır, uygulanacak güncel talimat değildir**.
- Kanonik yerel geliştirme klasörü: `C:\GorselUretimMerkezi\CODEX_ACTIVE`.
- Kamuya açık depoya gerçek kullanıcı fotoğrafları, onaylı maskeler, dört köşeler, canlı ayarlar, mağaza/Excel kayıtları, SQLite ve API anahtarları konulmaz.
- Başlatma, bağımlılık ve Windows kabul adımları yalnız **güncel yerel kaynak** eşleştirildikten sonra doğrulanabilir.

## Geliştirme ilkeleri
1. Mevcut yedi kategori/PETEK/üretim kodu, canlı veriler ve insan onayları korunur.
2. Testten geçmeyen değişikliğe başarılı veya `FINAL` denmez.
3. Yeni PETEK 409 düzeltmesi ve 2026-11-03 gölge motoru ayrı gerçek-render/Windows testleriyle doğrulanır.
4. Görsel kaliteyi azaltarak hız kazanılmaz; tekil üretim hatası tüm kuyruğu durdurmaz.
5. GitHub geçmişini zorla sıfırlama; güvenlik için eski açık sırlar varsa onları ayrı incele, gerektiğinde anahtarı iptal edip yenile.

## Kaynak güvenliği
`ayarlar.json` gibi canlı yapılandırma dosyaları public GitHub'da tutulmaz. Geçmişte izlenmiş bir dosyanın yeni commit'ten çıkarılması, eski commit'lerinden kaybolduğu anlamına **gelmez**.
