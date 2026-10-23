# V4.4 — Grup 1 + Grup 2 + Grup 3 Tek Windows Kabul Adayı

## Kurulum (mevcut canlı kullanıcı dosyalarını değiştirmeden)

1. Mevcut programda dört köşe işini kaydedin ve eski GUI/8080 pencerelerini kapatın. Hiçbir eski klasör/ZIP'i silmeyin.
2. ZIP'i **ayrı yeni bir yere** açın: `C:\GorselMockup_V44_ADAY`. `C:\AI_WORK`, önceki V4.2.2/V4.3 ve OneDrive ana çalışma klasörünün ÜZERİNE açmayın.
3. **`BASLAT_V44_TEK_MERKEZ_WINDOWS.bat`** dosyasına çift tıklayın. Eski `BIRLESIK_V42_BASLAT_WINDOWS.bat` geriye dönük uyumluluk için tutuldu. Her ikisi aynı güncel G1+G2+G3 programını açar.
4. Ana çalışma klasörü olarak eski onayları içeren gerçek `GörselÜretme-ve-Mockup Otomasyonu` kökünü seçin. **Şablon görsellerini, `ayarlar.db` dosyasını veya `.db-wal` dosyasını yeni kurulum klasörüne kopyalamayın.**
5. **Gelişmiş Araçlar** menüsünden `G3 Salt-Okunur Veri / SHA Denetimi`ne basın. Kayıtlar, SHA veya tablo sayısı hatalıysa üretime geçmeyin.
6. **G3 Onaylı İki DB Yedeği + Geri Yükleme Provası** yalnız kullanıcının açık onayıyla çalışır. İki SQLite snapshot ve test geri yükleme kanıtı varsayılan olarak `%LOCALAPPDATA%\GorselMockup\G3_GUVENLI_YEDEK\...` altına ayrı kaydedilir. OneDrive'daki kaynak SQLite'lar değişmez.
7. Bir onaylı şablon+bir tasarımla küçük test, sonra yedi kategori gerçek çıktı/Excel/HTTPS link/cam A-B/4K onay testleri, ardından 100/200/1000 yük/kesinti testi yapılmalıdır. **Canlı kullanıcı üretimi bu paketle henüz burada test edilmedi.**

## Bağımsız denetim

- `G3_GUVENLIK_KONTROLU_WINDOWS.bat` yalnız rapor verir, disk/DB üzerinde değişiklik yapmaz. GUI'deki onaylı yedek seçeneği dışında otomatik backup/migration yok.
- Kod üzerinden açıkça yedek denenmek istenirse: `python MERKEZ/G3_GUVENLIK_KONTROLU.py --backup --confirm YEDEK_AL_V44`. Önce eski veritabanı kapalı ve yeterli disk boş alanı olduğundan emin olun.
- Yedek raporu `G3_YEDEK_KANIT.json`. `backup_manifest_verify()` kayıtlı SQLite SHA ve sayıları salt-okunur tekrar doğrular.

## Geri dönüş

- Yeni programı kapat, 8080 ve olası batch süreçlerinin tamamen durduğunu doğrula.
- Eski çalışan V4.2.2/V4.3 **kod klasörünü** yeniden aç. Bu işlem eski DB veya orijinal görseller üzerinde overwrite gerektirmez.
- Eski programın DB şemasını yeni sürüm yazmışsa otomatik olarak downgrade etme; uzman yönetiminde tutarlı onaylı backup ve recovery yapılır.
- SQLite DB dosyası ve `-wal`/`-shm` WAL dosyalarını çalışan sistem açıkken elle taşıma, silme veya kopyalama. Tam restore yalnız tüm programlar kapalı ve bir kontrol edilmiş yedeğin hash'i teyit edilerek yapılmalıdır.

## Bilerek açık kalan dış bağımlılıklar

- Real-ESRGAN NCNN/Vulkan gerçek exe ve ağırlıkları ayrı güvenli kaynaktan kurulmalı; ZIP içinde yok.
- ImgBB/FreeImage anahtarı yoksa bulut Excel upload yapılamaz, yerel `file:///` linkleri gerçek HTTPS değildir.
- Offline bağımlılık wheel paketi, Windows gerçek 1000 render testi, kullanıcı 34+ PETEK Golden QA, eski hatalı Wi-Fi listesi ve tam ticari Excel/SEO mapping henüz kabul edilmedi.

**Ticari GO sadece gerçek Windows QA ve kullanıcı kabulünden sonra.**
