# GitHub kaynak, paket ve devir senkronizasyon sözleşmesi

## Hedef GitHub deposu

`oguz13-tech/gorsel-mockup-automation-src` ve yeni sürüme özel çalışma dalı: `release/v4101-source-and-windows-audit-20261031` (mevcut kanonik dal `feature/v46-safe-consolidation-20261024`).

## İstenen gerçek senkronizasyon

1. ZIP içinden çıkan **bütün kanonik kaynak dosyaları** (MERKEZ, SABLON_V2_MIMARI, scripts, tests, BAGIMSIZ_ARACLAR, release yönergeleri) GitHub dosya ağacına aktarılmalı. Eski referanslar `LEGACY_...` dizinlerinde okunabilir kalmalı, ama ana kodla karışmamalı.
2. Tek ZIP'in tam SHA-256 değeri, iç manifesti, test çıktısı ve gerçek Windows kabul statüsü GitHub Release/Actions veya bir açık kaynak commitinde eşleştirilmeli.
3. `.github/workflows` ana kodun lint, Python sözdizimi, JS `node --check`, PETEK maske QA ve bütün testleri çalıştıran güvenli PR işi olmalı. Windows masaüstü kabulü yapılmadan otomatik 'FINAL' ibaresi yazılmamalı.
4. Görevlerin durumu, ilgili commit/test/kabul referansı ile ancak gerçekten kapanınca değiştirilmelidir; #69, #70, #72 gibi görevleri kullanıcı Windows kabulü yoksa kapatma.
5. Geliştirme devir alan yapay zekâ ilk `docs/V4101_ARCHITECTURE.md`, `docs/V4101_CHANGELOG_AND_GAPS.md`, `docs/V4101_WINDOWS_ACCEPTANCE.md`, `docs/V4101_GITHUB_SYNC_STATUS.md` ve `SHA256_MANIFEST.json` dosyalarını okuyup ilerlemeli.

## Doğrulama

- GitHub'da yalnız doküman veya issue oluşturmak **tam kaynak senkronizasyonu değildir**.
- ZIP'i GitHub Releases/Assets'e aktaramama veya bütün kaynak dosyaları commit edememe halinde **GITHUB_SOURCE_NOT_SYNCED** açık kalmalı.
- GitHub dalının **gerçek HEAD SHA'sı** ve kaynak dosyalarının hash değerleri ZIP manifestiyle karşılaştırılmadan "GitHub güncel" denmemeli.
