# F07 — Mağaza–Mockup toplu atama kaldırma (V4.10.2 sonrası aday)

**Temel kaynak:** V4.10.2 `release/v4102-approval-speed-and-ui-20261031`, HEAD `a7f9542523b16f8312c2c0fdb04f46811ecc8da9`. Bu F07 ara geliştirmesi **F00–F12 genel modernizasyon finali değildir**.

## Kullanım

1. `Seri Üretim > Mağaza Profilleri / Şablon Atama` bölümünden mağazayı seç.
2. Sağdaki **Seçilen Mağazanın Mevcut Atamaları** listesinde Ctrl/Shift ile birden fazla satır seç; veya **Tüm Atamaları Seç**, üstten kategori belirleyip **Bu Kategoriyi Seç** seçeneklerini kullan.
3. Seçili sayaçta tam sayı görünür. **Seçimi Temizle** hiçbir kayıt değiştirmez.
4. **SEÇİLİ ATAMALARI TOPLU KALDIR** ile bütün seçilen kayıtları ve mağazayı gösteren kaydırılabilir son kontrol ekranını aç.
5. **Vazgeç** işlemi iptal eder. Son onay verilirse yalnız seçili eşleştirmeler mağazanın `store_profiles_v47.json` listesinden kaldırılır. İşlem öncesi config otomatik yedeklenir; kaldırılan mockup başka mağazaya atanabilir.

**Önemli:** Mockup görsel dosyaları, çalışan/orijinal şablon havuzu, PETEK maskeleri, onaylı 4 köşe, SQLite, üretim defteri, daha önceki Excel ve çıktı fotoğrafları silinmez. Aynı HAM baskı tasarımının farklı mockuplarla farklı mağazalarda kullanılması serbesttir. Aynı mockup kaynak SHA'sının eşzamanlı iki mağazaya atanma yasağı devam eder.

## Güvenlik önlemleri

- Kaldırmada boş/tekrarlı anahtarlar ve mağazaya ait olmayan atamalar reddedilir.
- Son onay penceresi açıldığındaki mağaza üyelik listesi snapshot'ıyla tekrar kontrol edilir; dialog açıkken üyelik değişmişse işlem durur.
- Bir UI kaldırma işlemi süresince `busy` koruması çift tıklamayı engeller.
- Mevcut `StoreProfiles.save` atomik yazma ve her değişim öncesi geri dönüş JSON'u üretir.
- İşlem şablon dosyasına, fotoğraf numarasına ve mockup üretim motoruna dokunmaz.
- **Sınırlama:** Ayrı iki bağımsız süreç aynı config dosyasını tam aynı anda yazarsa süreçler arası dosya kilidi henüz yok. Bu F07 adayı tüm eşzamanlı yazma problemlerini çözdüğü iddiasını taşımaz.

## Test kanıtı (31.10.2026, izole Linux/Xvfb)

- `xvfb-run -a pytest -q tests/test_v4100_store_assignment.py tests/test_vnext_store_bulk_unassign.py` → **17 passed**.
- 970x600, 1280x720 ve 1366x768 pencere boylarında toplu kaldırma komutları ekranda ve tıklanabilir; gerçek Windows DPI doğrulaması ayrıca gereklidir.
- Genişletilmiş ilgili 8 test dosyası, `PYTHONPATH=.` ve tek Flask HTTP testi hariç → **62 passed, 1 skipped, 1 deselected**.
- Tüm `tests/` koleksiyonu paket dışı `V2_KONTROL_MERKEZI/app.py` eksikliği nedeniyle bloke. Flask HTTP testi `flask` modülü eksikliğinden çalıştırılamadı.
- Gerçek Windows GUI/DPI, canlı çok mağazalı veri ve mağaza/Excel uçtan uca kabul: **WINDOWS_NOT_VERIFIED**.

## Geri dönüş

Kod için bu aday dalını ve aday ZIP'i kullanmayı bırakıp değişmemiş V4.10.2 ZIP'ini izole klasöre geri aç. Atama kaydı yanlış kaldırıldıysa `store_profiles_v47.backup_*.json` otomatik yedeğinden manuel doğrulanmış restore yapılabilir veya mockup yeniden atanabilir. Üzerinde çalışılan gerçek `store_profiles_v47.json` dosyasına körlemesine eski JSON'u yazma; ara dönemde yapılan başka mağaza atamaları kaybolabilir.
