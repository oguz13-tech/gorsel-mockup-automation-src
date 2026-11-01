# Mağaza–Üretim Seçimi Sorununun Teşhisi (VNext 01.11.2026)

**Kapsam:** Kullanıcı `wudie` mağazasında tüm eşleştirmeleri kaldırıp yalnız tek şablon atadıktan sonra da `Seçili şablonlar mağazanın özel grubunda yok` uyarısı aldı.

## Koddan doğrulanan neden ve hipotez

- `MERKEZ/URETIM_V4/store_profiles_v47.py::plan()` mağazanın `store_profiles_v47.json` dosyasındaki `category:uid@source_sha` anahtarlarını, onaylı fotoğrafların mevcut kaynak anahtarlarıyla doğrular ve en sonunda **Seri Üretim'de seçili UID** kümesiyle kesişimi alır. Kesişim sıfırsa hata verir.
- `MERKEZ/URETIM_V4/gui_v4.py` üretim seçimlerini bağımsız `selected_uids` alanında, filtreler değişse de korur. `reload_stores()` sadece mağaza seçeneklerini/sayılarını yeniler, üretime seçilen UID listesini otomatik değiştirmez. Böylece **mağazada 1 geçerli atama + üretimde 1 farklı şablon** durumunda aynı hata tekrar üretilebilir.
- Diğer ihtimaller: seçilen mağaza ya da şablonun farklı profil kökünden yüklenmesi, eski SHA/onayın değişmiş olması, kategori/UID çakışması. Bunlar gerçek Windows verisi görülmeden kesin olarak ayırt edilemez; yeni teşhis paneli read-only olarak ayırır.

## Eklendi

1. **Mağaza – Üretim Eşleşmesini Denetle (Salt Okunur):** Seçili mağazaları, profili okunan gerçek dosya yolunu, üretimde seçili UID'leri, kaydedilmiş `kategori:UID`/SHA ön eklerini, kesişim sayısını, eski SHA/APPROVED durumunu ve uygun düzeltmeyi gösterir. Hiçbir dosyaya yazmaz; rapor kopyalanabilir.
2. **Mağazaya Atananları Üretime Seç:** Kullanıcı açıkça tıkladığında önceki üretim seçimlerini temizler, seçili mağazaların geçerli onaylı üyelik UID'lerini *yeni üretim seçimi olarak* gösterir. **Yeni atama yapmaz, silmez, mağaza JSON'a yazmaz, üretimi başlatmaz.**
3. Kaynak SHA stale/eksik veya UID çakışması varsa otomatik seçim yerine teşhis paneli açılır. Böylece yanlış mockup'a üretim yapılmaz.
4. Eski mağaza izolasyonu ve insan onayı korunur. Başlatma sırasında bir uyumsuzluk olursa uygulama ayrıntılı teşhis düğmesini işaret eder.

## Test kanıtı

- `xvfb-run -a env PYTHONPATH=. pytest -q tests/test_vnext_store_selection_diagnosis.py tests/test_v4100_store_assignment.py tests/test_vnext_store_bulk_unassign.py` → **24 PASS** (Linux/Xvfb).
- Genişletilmiş PETEK/MOR/mağaza grubu → **73 PASS, 1 SKIP** (Linux/Xvfb).
- Senaryolar: tek atama + eski üretim UID'si hata verir; doğru UID seçildiğinde plan geçer; SHA stale tanısı; iki mağaza, kullanıcı temizle/yeniden ata senaryosu; UI filtre geri çağrısının yeni seçimi yanlışlıkla silmemesi; kayıt hash'i değişmeden teşhis.
- **WINDOWS_NOT_VERIFIED:** gerçek Windows veri havuzu, canlı `wudie` profili, gerçek üretim, Excel/4K/Flask HTTP. Bu sürümün üretime hazır olduğu iddia edilmez.

## Güvenlik / geri dönüş

- Gerçek kullanıcı `store_profiles_v47.json`, onaylı maskeler/quad, arşiv, SQLite, Excel veya üretim kayıtları bu çalışma esnasında açılmadı/değiştirilmedi.
- Uygulama ayrı klasöre çıkarılır; önceki PETEK ve MOR ZIP'leri olduğu gibi bırakılır. Geri dönüş eski klasörden başlatmaktır.
- Teşhis raporu kullanıcının PC'sinde gösterilir, otomatik hiçbir yere gönderilmez. Sorun devam ediyorsa sadece tanı sonucu (gerekirse özel dosya yolları gizlenerek) incelenir.
