# Issue #79 — Mağaza–Mockup / Seri Üretim eşleşme P0 düzeltmesi

**Tarih:** 01.11.2026 · **Aday:** STORE_P0_ISSUE79_20261101 · **Windows:** `WINDOWS_NOT_VERIFIED`

## Kaynak ve ispat seviyeleri
- V4.10.2 release HEAD kaynak, VNext MOR/PETEK düzeltmeleri ve önceki salt-okunur mağaza teşhis sürümü tek dalda korunur. `main` dalı temel kabul edilmemiştir.
- `StoreProfiles.plan()` hatası seçilen mağazanın geçerli `category:uid@source_sha` kayıtlarıyla motorun gönderdiği `selected_uids` kesişmediğinde oluşur. Bu kod seviyesinde yeniden üretildi.
- `gui_v4.py` ekranı `selected_uids` kümesini şablon yenilemelerinde korur; mağaza ataması değiştiğinde kullanıcı seçimi otomatik güncellenmez. Bu da **kanıtlanan olası bir hata senaryosu**dur.
- **Ek gerçek güvenlik hatası bulundu:** En az bir UID mağazayla eşleşirken ikinci seçili UID mağazaya ait değilse eski `plan()` ikinci UID'yi sessizce çıkarıyordu. Artık hata vererek engelleniyor. Bu düzeltme motor dahil tüm çağrı noktalarını korur.
- `StoreProfiles(self.batch_engine.root)` hem mağaza penceresine hem üretim ön kontrolüne ve üretim motoruna aynı `store_profiles_v47.json` yolunu aktarır. Kod yapısında iki farklı kök yoktur. **Gerçek Windows kullanıcı bilgisayarındaki kayıt, dosya yolu veya çalışan oturumun gerçek seçili UID'si bu ortamdan okunamadı. Bu nedenle bireysel `wudie` olayının tam kök nedeni henüz `WINDOWS_NOT_VERIFIED` ve `RUNTIME_EVIDENCE_REQUIRED` olarak kalır.**

## Düzeltilen dosyalar
1. `MERKEZ/URETIM_V4/store_selection_diagnostic_vnext.py`: üretime gönderilen mağaza/UID, onaylı category/UID/SHA, dosya adı, tam mağaza anahtarı, sahip mağaza, değişmiş SHA ile başka kategori ayrımı, görünür/oturum seçimi ve okunan profilin SHA256 bilgisini karşılaştıran **salt-okunur** rapor.
2. `MERKEZ/URETIM_V4/gui_v4.py`: gerçek `start()` parametreleriyle ön kontrol, açıklamalı ve eylemli popup, **Bu Mağazanın Mockuplarını Göster** yalnız liste filtresi, **Bütün Mockupları Göster**, kullanıcı isterse **Mağazaya Atananları Üretime Seç**; kayıtlar sessizce değiştirilmez. Mağaza değişiminde dosyadan yeniden okunur.
3. `MERKEZ/URETIM_V4/store_profiles_v47.py`: seçilen hiçbir ekstra UID sessizce atlanamaz; fail-closed `STORE_SELECTED_UID_NOT_ASSIGNED`. Atama/SHA korunur.
4. `MERKEZ/URETIM_V4/store_assignment_ui_v410.py`: SOL yeni atama / SAĞ yalnız kaldırma seçimleri açık; solda 0 ise Ata düğmesi devre dışı; hedef UID+mağaza+kategori yönlendirmesi sadece uygun ve boşta şablonu işaretler, **son insan onayını şart koşar**.
5. `tests/test_vnext_store_preflight_p0.py`: 11 ayrı yeni regresyon testi; eskiler korunur.

## Kabul akışları (otomatik ve Windows)
- [x] Bir mağaza, gerçek atanmış UID -> plan üretim şablonunu içerir.
- [x] Başka UID seçilmiş -> detaylı `NO_COMMON_UID`, üretim durur.
- [x] Bir doğru + bir yanlış UID -> `STORE_SELECTED_UID_NOT_ASSIGNED`, yanlış UID sessizce düşmez.
- [x] İki mağaza, farklı mockup kaynağı, ortak baskı tasarımı senaryosu; kaynak kilidi korunur.
- [x] Kaynak SHA değiştiğinde eski atama otomatik değiştirilmez.
- [x] Profil kapat/aç tekrar okunur; disk SHA güncel raporlanır.
- [x] PETEK kategori UID eşleşmesi, diğer kategori UID ile çakışma ve çakışan kimlikler engellenir.
- [x] Sol 0 seçiliyken Ata kapalı; sağ mevcut atamalar hiçbir işlemde silinmez.
- [x] Hedef mağazaya yönlendirme yalnız boşta onaylı şablonu işaretler, dosyaya yazmaz.
- [x] Mağaza filtresi eski üretim seçimini sessizce değiştirmez.
- [ ] **Gerçek Windows:** `wudie` mağazasının mevcut üç ataması, üretimdeki gerçek UID/SHA, aynı profil dosyası ve üretim başarısı; `WINDOWS_NOT_VERIFIED`.
- [ ] **Gerçek Windows:** %100/%125/%150 DPI, Excel/4K/PETEK 13–16 yarık, hızlı açılma, güvenli kapatma end-to-end; `WINDOWS_NOT_VERIFIED`.

## `wudie` doğrulama adımı
1. Ana çalışan uygulamada atama **silme, yeniden atama veya yeniden onaylama yapma**.
2. Ayrı ZIP adayını aç; ilk çalışmada gerçek çalışma klasörünü otomatik bağlamadan önce güvenli testle başla.
3. `Seri Üretim > Mağazalar > wudie > Mağaza – Üretim Eşleşmesini Denetle (Salt Okunur)`.
4. Raporu **Raporu Kopyala** ile alın. `Motor planına gönderilen seçili UID`, `KAYIT/ATANMIŞ`, `SEÇİLİ MAĞAZADA DEĞİL`, `Profil dosyası/SHA` alanları teşhisi kesinleştirir.
5. `NO_COMMON_UID` ise isteğe bağlı **Mağazaya Atananları Üretime Seç** ile eski üretim seçimini bilinçli biçimde değiştir; **mağaza kayıtları değişmez**. `SOURCE_SHA_CHANGED` varsa **yeniden onayı otomatik yapma**.

## Güvenlik, rollback ve sürüm bağımsızlığı
- Bu patch hiçbir mağaza profili, mask, quad, orijinal fotoğraf, üretim SQLite veya barkod/Excel çıktısını otomatik değiştirmez.
- Yeni UI penceresi yalnız rapor/filtre/manuel yönlendirme yapar; başka mağazanın anahtarı atanamaz.
- Çalışan ZIP'e üzerine yazma. Eski sürümün orijinal JSON yedeklerine dokunma; bir önceki ZIP'i yeniden açmak yeterlidir. Veri taşıması yok.
- Çalışma klasörünü seçmeden önce programın açıkça gösterdiği kökü ve ayrı `store_profiles_v47.json` yolunu denetle. Farklıysa üretime girme.
- **`main` ve eski PR'lar değiştirilmedi; bu aday ayrı PR olarak kalır.**
