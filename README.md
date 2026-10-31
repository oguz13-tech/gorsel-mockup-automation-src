# Görsel Üretim Merkezi — V4.10.1 Kaynak Kod ve Geliştirici Merkezi

> **Kaynak doğrulama:** Bu dalda 31 Ekim 2026'da oluşturulan V4.10.1 Windows ZIP'indeki **482/482 dosya** Git blob kimliğiyle birebir doğrulandı. **Canlı Windows kabulü hâlâ bekleniyor.** Burayı “tamamen hatasız üretim finali” olarak değerlendirmeyin.

## İlk adım

**[V4101_AI_DEV_HANDOFF.md](V4101_AI_DEV_HANDOFF.md)** dosyasını okuyun. İçerik: yedi kategori, başlangıç ve kurulum, önemli modüller, kaynak şablon/maske güvenliği, PETEK revizyon akışı, mağaza/Excel bağlantıları, test yolları ve bilinen açık hatalar.

| Kaynak | Amaç |
|---|---|
| [Teknik mimari](docs/V4101_ARCHITECTURE.md) | 7 kategori, Tk/Flask/JavaScript/API/üretim modülleri |
| [Bütün kaynak dosyaları](docs/V4101_SOURCE_FILE_INDEX.md) | V4.10.1 paketine giren dosyaların haritası |
| [Değişiklikler ve açık kalanlar](docs/V4101_CHANGELOG_AND_GAPS.md) | Tamamlanan, kısmi ve canlı kabul bekleyen işler |
| [Windows kabul adımları](docs/V4101_WINDOWS_ACCEPTANCE.md) | Kullanıcıdan beklenen adım adım testler |
| [Kaynak eşleşme kanıtı](docs/V4101_GITHUB_SYNC_PROOF.md) | 482/482 Git blob eşleşmesi, SHA-256 |
| [Test raporu](V4101_TEST_VE_KABUL_RAPORU.md) | 124 test PASS, ortam sınırlamaları |
| [Paket manifesti](SHA256_MANIFEST.json) | Kanonik kaynak dosya listesi ve her dosyanın SHA-256 değeri |
| [Otomatik kaynak denetimi](.github/workflows/v4101-source-validation.yml) | Read-only manifest/Python/Node kontrolü |
| [Ana eksik/güncelleme takibi](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/72) | Önceki sohbetlerdeki eksikler |
| [Taslak kaynak PR](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/73) | V4.10.1 değişikliklerinin gözden geçirilmesi |

## Güvenlik ve durum notu

- V4.10.1'in Windows ZIP dosyaları bu dalda dosya dosya yer alır; tek ZIP paketi ChatGPT üzerinden ayrıca teslim edilmiştir. **GitHub Release ZIP asset'i henüz yayınlanmadı.**
- Dal, eski V4.6 geliştirme dalından üretildi. ZIP'e dahil olmayan **129 eski/referans dosya** tarihi bağlam için korunur; bunları yeni kanonik motor diye çağırmayın. Kanonik sınır: `SHA256_MANIFEST.json` kayıtları + manifest dosyası.
- **Kullanıcının canlı şablonları, PETEK approved maskeleri, veritabanları, OneDrive ana çalışma klasörü veya özel API tokenları bu repo çalışma paketine yazılmamalıdır.**
- PETEK'te kullanıcının onayladığı **15 koyu dikey yarık, Orta yoğunluk ve pembe kenar temizliği** korunmalı.
- Gerçek Windows/Flask/4K GPU/mağaza bazlı Excel uçtan uca test geçmeden PR'ı ana dala merge etmeyin.
