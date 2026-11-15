# PETEK master revizyon runtime kurulumu

`BASLAT.bat` başlamadan önce `tools/install_petek_master_revisions.py` çalışır.

Kurulum:

- Dört kaynak fotoğrafını UID ve SHA256 ile bulur.
- Yeni master maskelerini `PetekV3/masks` altına ekler.
- Yeni onaylı revizyon profillerini eski profillerin yanına ekler.
- `active_revisions.json` içindeki yalnız dört PETEK etkinliğini günceller.
- Önceden mevcut dosyaları `PetekV3/backups/master_revision_YYYYMMDD_HHMMSS` altına kopyalar.
- Kaynak bulunamaz veya SHA uyuşmazsa programı başlatmaz.

Eski profil, maske, SQLite ve üretim kayıtları silinmez. Eski ledger kayıtları
da yeniden yazılmaz; aktif revizyon yeni üretim kimliğinde kullanılır.

Kurulum ikinci kez çalıştırıldığında etkinlik aynıysa hiçbir dosya değiştirmez.
