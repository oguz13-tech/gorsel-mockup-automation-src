# V4.10.1 — Kullanıcının yapacağı son Windows kabul kontrolleri

**Güvenli kurulum:** Eski çalışan sürümü silme. ZIP'i ayrı yeni klasöre aç; ana çalışma klasörünü aynı bırak. `V4101_DOGRULA_WINDOWS.bat` → `V4101_BASLAT_WINDOWS.bat`.

1. **PETEK listesi:** Şablonları İncele → PETEK → Toplu Seçim. Dosya adları bütün sarı/yeşil satırlarda açıkça okunmalı; kutular dosya adını silmemeli. Kompakt/Fotoğraflı geçişi dene; %100 ve %125 Windows DPI.
2. **Tiksiz sınırsız toplu onay:** 2 deneme taslağı seçmek zorunda kalmadan, tüm uygun ve görünür DRAFT kayıtları için tek onay ver. Eski sekizli onay ekranı gelmemeli. İşlem başlamadan önce canlı verinin harici yedeğini al; sonuç raporunda geçen/kalana bak.
3. **Onaylı maske yeniden dört köşe:** Onaylı PETEK → Yeni Revizyon → köşeleri düzelt → yeni otomatik maske → Taslak Kaydet → açık insan onayı → Etkinleştir → Eski Onaylıya Dön. Eski kaynak fotoğraf ve onaylı maskenin korunmasını doğrula.
4. **Klavye:** PETEK açıkken ←/→ Wi-Fi şablonlarına gitmemeli. Kaydedilmemiş değişiklikte şablon değiştirme uyarısı olmalı.
5. **Ahşabı Boya/Sil:** Boyayı Sil yalnızca yeni taslak maskeyi etkilemeli, orijinal görseli silmemeli. Ctrl+Z test et.
6. **7 kategori filtre:** Yeni/mavi, Taslak/sarı, Onaylı/yeşil, Hatalı/kırmızı; tik filtreleri ilgili listeyi gizleyip göstermeli; kayıt silinmemeli.
7. **Ana ekran kart taşı:** Kartları Taşı → bir tutamaçla yer değiştir → moddan çık → programı kapatıp yeniden aç → aynı düzen. Sonra Varsayılana Dön ve Geri Al dene.
8. **Hata yardım pop-up:** Eksik maske taslağında neden/çözüm mesajı ve 'Gerekli Adıma Git' işlevi; kritik olmayan toplu hatalarda modal yağmuru olmamalı.
9. **Mağazalar:** A mağazasına 2 mockup ata, B'de aynı kaynak görseller engellensin. Aynı ham tasarım iki ayrı mockup ile iki mağazada kullanılabilsin. Mağaza başına XLSX alanlarını doğrula.
10. **4K/performans:** Kurulu ESRGAN'da Kontrol Et sadece durum bildirsin, otomatik kurulum başlatmasın; 4K seçili gerçek GPU örneği. Seri Üretim hızlı açılmaya devam etsin; Şablon İnceleme/ana pencere kilitlenmesin.

**Kayıp veri koruması:** Orijinal yedek, PETEK maske, şablon kimlikleri, onaylı dört köşeler, mağaza Excel ve üretim ledger alanlarını sürüm başına SHA/DB kontrolüyle karşılaştır. Bunlardan biri beklenmedik değişirse durdur ve önceki ZIP'e dön.

**Rapor başlığı:** `V4101_WINDOWS_NOT_VERIFIED` otomatik test başarılarından ayrı kalacaktır.
