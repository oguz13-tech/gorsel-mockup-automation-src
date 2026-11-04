# V4.2.2 TEK Windows FABRİKA — KABUL MATRİSİ

**Kod mevcut** `CODE` ≠ **sentetik test raporu** `SYN` ≠ **kullanıcı Windows kabulü** `WIN`. Her hücre için delil gerekir. `PENDING` bitmiş değildir.

| ID | Alan | Koda dair rapor | Sentetik doğrulama | Gerçek Windows kabul | Sonraki kanıt |
|---|---|---|---|---|---|
| G1-01 | 6 kategori kayıtlı gerçek köşelerle toplu onay | CODE | SYN raporlandı | PENDING | Seçili 2+ farklı şablonda kaynak SHA/profil değişmeden onay |
| G1-02 | `Too small` manuel düzeltmesi | CODE | SYN raporlandı | PENDING | Küçük geçerli quad kabul, self-cross/outside red |
| G1-03 | 7 kategoride güvenli otomatik inbox importer | CODE | SYN raporlandı | PENDING | Exact duplicate, farklı SHA, PNG/JPEG stem çakışması, bozuk dosya |
| G1-04 | 7 kategorili isimlendirici, son numara | CODE | SYN raporlandı | PENDING | Numara sicili kalıcılığı / PETEK dahil / kayıp dosya |
| G1-05 | Ham orijinal göster/geri yükle, missing PNG | CODE | SYN raporlandı | PENDING | Ocak Arkası WORKING_PNG_NOT_FOUND_OR_UNSAFE, never overwrite |
| G1-06 | Eski Flask/Tk/araçlar sürüm köprüsü | CODE | Bazı testler geçti | PENDING | 8080/Tools/tüm bağımsız butonlar |
| G2-01 | Cam yansıma ve ışık dengesi | CODE | SYN raporlandı | PENDING | 4 cam kategoride gerçek golden A/B ve çevre piksel SHA |
| G2-02 | PETEK/Wifi/ahşap doğal ışık gölge | CODE | SYN/önceki kod raporlandı | PENDING | Gerçek odalar/maske/delik/kavis |
| G2-03 | Köşe radius 0 / küçük yuvarlama | CODE | SYN raporlandı | PENDING | Perspektif, no quad mutation, mask edge |
| G2-04 | Gerçek thumbnail, açık missing hata | CODE | GUI Xvfb raporlandı | PENDING | 7 kategori ekranı |
| G2-05 | Kısa Türkçe yardımlar | CODE | Kısmi | PENDING | Her buton/sekme PETEK dahil |
| G2-06 | F5 / race / loadTemplate tokencount | CODE | JS kontrol raporlandı | PENDING | Arka arkaya onay/kategori değişimi |
| G2-07 | Cam Doğrama yeni H; eski V korunur | CODE | SYN raporlandı | PENDING | Eski APPROVED V hash/profil sabit |
| G2-08 | Koyu Tk/Flask tema | CODE | Xvfb açılış raporlandı | PENDING | Windows kontrast/focus |
| G2-09 | PETEK ve V4 Excel `file:///` bağlantısı | CODE | SYN openpyxl raporlandı | PENDING | Yerel MS Excel fiziksel link açılışı |
| V421-01 | Batch başında bozuk/kayıp şablonu ayır | CODE | SYN raporlandı | PENDING | 1 bozuk / diğerleri devam |
| V421-02 | UI snapshot/UID çakışması | CODE | SYN raporlandı | PENDING | Uzun batch, farklı maskede yanlış baskı yok |
| V421-03 | Yarım `.venv` kurulum onarımı | CODE | Static/SYN | PENDING | Windows eksik bağımlılık sonrası toparlanma |
| V422-01 | Factory Doctor açıklama ve 3.11 tercih | CODE | 65 test raporlandı | PENDING | 3.11/3.14 ortamları Windows |
| P0-01 | Onaylı DB/köşe/orijinal SHA koruma | Koruma amaçlı kod | Birim test mevcut | PENDING | Before/after HASH + DB backup |
| P0-02 | 7 kategori görsel kalite golden dataset | Kısmen | Kısmi | PENDING | Gerçek 7 kategori kullanıcı onayı |
| P0-03 | 1000 batch, pause/resume, kill 2x | Kısmi | Tam test yok | PENDING | Gerçek dayanıklılık, receipt |
| P0-04 | GPU lock/AI CUDA doğru runtime | Doctor raporu var | Sentetik | PENDING | Python 3.11 / CUDA GPU gerçek çalışma |
| P0-05 | OneDrive SQLite güvenli yol | Risk tanımlanmış | Taşıma yapılmadı | PENDING | Onaylı backup/rollback planı |
| P0-06 | Public GitHub kaynak + özel Library 379 manifest | Handoff branch | Source SHA/ZIP CRC | PENDING | PR review ve GitHub CI |

**Kapatma kuralı:** #35 `GO` olamaz; yerel Windows kanıtı, doğal görüntü onayı, SHA koruma, rollback ve gerçek Excel hyperlink koşulları karşılanmalıdır. Kod incelemeyi gerçek üretim kabulü diye işaretleme.