# Public-safe kaynak kapsamı / tam kaynak arşivi ayrımı

- `main` tespit anında GitHub ağaç sayısı **101 dosya**; V4.2.2 ZIP ise **379 dosya**. Önceki PR #37 yalnız V4 plan dokümantasyonudur.
- `handoff/v422-complete-20261023` dalına son ZIP'ten **293 adet `.py`, `.bat`, `.ps1`, `.js`, `.css`, `.html`, `.yml`** kaynak dosyası kopyalanmıştır. GitHub'a canlı kullanıcı fotoğrafları / DB / WAL / maske / geçmişte elle işlenmiş `ayarlar.json` yeniden gönderilmemiştir.
- Tam 379 dosyalık manifest `docs/V422_FULL_PACKAGE_FILE_MANIFEST.csv` içindedir; her üye için boyut ve SHA256 içerir; farklar tespit edilebilir.
- Tam özel ZIP ChatGPT Library `/Gorsel-Uretim-Merkezi/V4.2.2/` altında. Yeni ajan arşivi Library'den okuyabilir; public repo kapsamını tam yerel teslim sayma.
- Yeni paketi **eski programın veya canlı kullanıcı çalışma klasörünün üzerine çıkartma**. ZIP çalışma kodu/araçlar içindir, canlı veritabanı/baskı dosyaları için değildir.
- İleride eksik konfigürasyon/data dosyası için yetki ve güvenlik taramasından geçmeden public push yapma. Ana dal merge yok; draft PR ile kod incelemesi.