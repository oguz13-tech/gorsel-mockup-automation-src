# Windows geri dönüş yönergesi

Bu teslim paketi canlı SQLite, mağaza profilleri, PETEK profilleri, maskeleri
ve kullanıcı artwork dosyalarını içermez.

1. Programı kapatın ve açık üretim işlerinin tamamlanmasını bekleyin.
2. Mevcut program klasörünü silmeden veya üzerine yazmadan yeniden adlandırın.
3. Önceki çalışan klasörün `BASLAT.bat` dosyasını kullanın.
4. Runtime yedeğini yalnızca bilinçli bir operatör kararıyla geri yükleyin:
   - `v4_ortak_uretim.sqlite3`
   - `store_profiles_v47.json`
   - `PetekV3\profiles`
   - `PetekV3\masks`
5. Geri yükleme öncesi ve sonrası SHA256 manifestlerini karşılaştırın.

Bu paketteki PETEK master revizyonları `DRAFT_REVIEW_ONLY` durumundadır.
Kullanıcı görsel onayı, insan onayı ve açık Registry aktivasyonu olmadan
etkin revizyon olarak kullanılmaz. Eski onaylı maskeler değiştirilmez.
