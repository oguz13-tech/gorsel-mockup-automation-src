# MOR Premium VNext — güvenli Windows kurulum ve geri dönüş

**Durum:** Aday. `WINDOWS_NOT_VERIFIED`. Eski V4.10.2 ZIP + SHA ayrı korunur.

1. ZIP dosyasını `C:\AI_WORK\GORSEL_MOR_VNEXT_TEST` gibi **yeni boş klasöre** aç. **OneDrive/Masaüstü/aktif veri klasörünün üzerine kesinlikle açma.**
2. Önce `MOR_VNEXT_DOGRULA_WINDOWS.bat` çalıştır ve tüm manifest dosyaları için hata 0 sonucunu kontrol et.
3. `MOR_VNEXT_BASLAT_WINDOWS.bat` ile başlat. Çalışma klasörü seçimi istenirse mevcut ana veriyi yalnız test prosedürüne göre bağla; yeni canlı DB sürüm yükseltmesi otomatik yapılmaz.
4. Şablon İnceleme’de `Arayüzü Düzenle` aç: kayıt yapmadan **Vazgeç** ile kapat; test verileriyle renk/panel/sekmeyi dene. Üretim/maske kayıtları salt okunur gözlemlenir. HTTP/Windows UAT ayrıca yapılmalıdır.
5. UI görünümü bozulursa `%LOCALAPPDATA%\GorselMockup\UI_VNEXT\review_layout.json` dosyasını **yeniden adlandır** (silme gerekmiyor). Program güvenli varsayılan temaya döner; `.lastgood.json` son geçerli görünümün yedeğidir. `Son İyi Düzen` işlemi önceki `.backup.json` kayıtlı düzeni yükler; kalıcı olması için `Kaydet` gerekir.
6. Tam sürüm rollback gerektiğinde MOR adayını kapat, V4.10.2 kaynak ZIP'ini **başka boş kod klasörüne** çıkar ve kendi `V4102_BASLAT_WINDOWS.bat` dosyasıyla aç. Kullanıcı DB, çalışma havuzu ve onaylı maskeleri ZIP'le ezme.
7. F07 mağaza atama kaldırması yalnız üyelik JSON'unu değiştirir. Gerçek mağaza üyeliği geri alınacaksa işlemin `.backup_*.json` dosyasını **başka yeni atamalarla çakışma denetimi yapmadan** üzerine kopyalama; önce mağaza bazlı farkları kontrol et.

**Kritik:** Gerçek Windows'ta veri snapshot/restore testi yapılmadan canlı veri üzerinde onay, revizyon veya mağaza toplu kaldırma kabulü verilmez.
