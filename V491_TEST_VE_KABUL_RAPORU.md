# GÖRSEL ÜRETİM MERKEZİ V4.9.1 — DÜZELTME VE GÜVENLİ KABUL RAPORU

**Tarih:** 31 Ekim 2026  
**Kaynak:** Kullanıcının V4.9.0 aday ZIP'inden ayrı yeni çalışma kopyası.  
**Dağıtım kanalı:** GÜVENLİ ADAY, **WINDOWS_NOT_VERIFIED**.  
**Final canlı üretim kararı:** **NO-GO**; kullanıcının gerçek Windows/OneDrive/mağaza/4K ortamında uçtan uca kabul henüz yapılmadı.

## 1. Doğrulanmış hatalar ve çözümler
1. **P0 mevcut görsel silinmesi:** `orientation_sort_v489.py` içinde var olmayan hedefi yaratamama halinde önceden bulunan aynı isimli dosyanın silinmesi giderildi. Yalnızca bu işlemde başarılı biçimde yaratılmış dosyalar temizlenir. Hardlink desteklenmediğinde exclusive-create/no-clobber kopya yapılır; SHA256 doğrulaması korunur. Var olan `a.png` byte kontrolü ve `a__002.png` yeni dosya testi PASS.
2. **P1 büyük/bozuk görsel parti sonlandırması:** Pillow `DecompressionBombError` dahil görsel başına Exception yalıtımı eklendi. Kalan görseller işleniyor ve CSV raporu oluşuyor. PASS.
3. **P1 DB hazır değilken Profesyonel Araçlar engeli:** `/api/session/csrf`, `/api/tools/launch/` ve `/api/tools/status/` DB migrasyon kapısından ayrıldı. Kritik: Loopback host/origin + CSRF korunuyor. Fabrika DB API'leri hâlâ şema yoksa 503 ile kapanıyor. Flask test PASS.
4. **P2 yanlış 'araç açıldı' mesajı:** HTTP 202 STARTING + çocuğun gerçek Tk kökünü oluşturmasından sonra canlı marker/heartbeat + durum sorgulama yapıldı. Hemen hata koduyla kapanan araç artık başarı bildirimi üretemiyor. Flask ve Tk Xvfb test PASS.
5. **Profesyonel Araçlar eksik kartı:** `stage` motoru bulunduğu hâlde ekranda olmayan `Güvenli Yeni Şablon Ekle` kartı eklendi; otomatik onay yapılmaz.
6. **Bağımsız BAT'lerde yanlış Python:** 10 adet bağımsız BAT ile ana BAT ortak `KUR_ORTAM_V491_WINDOWS.bat` üzerinden Python 3.11 ve pinli bağımlılıkların kontrolüne bağlandı. Eski yanlış `python`/farklı Python kullanımı kaldırıldı.
7. **Eski bilgisayara bağlı .venv dağıtımı:** ZIP içine başka Windows bilgisayarından taşınan `.venv` alınmadı. Yeni kurulum kendine ait venv oluşturur; varsa bozuk ortamı silmeden ayrı adla korur. Python 3.11 kurulu olmalı, ilk kurulumda internet gerekebilir.
8. **Kaynak içinde test sonucu oluşan DB:** `ayarlar.db` ve `.db-wal/.db-shm` dosyaları ZIP'ten hariç tutuldu. Canlı kullanıcı DB ve orijinal arşiv paketlenmedi.

## 2. Kontrol sonuçları
- **Hedefli ve ilgili üretim regresyonları:** **97 PASS / 0 FAIL**. Kapsam: görsel seçici, çakışma, EXIF, bozuk veri, PETEK web, mağaza/Excel sentetik senaryolar, HAM tasarımlar, magenta geometri, araç CSRF/heartbeat, eski arayüze dönüş denetimi.
- **Gerçek Tk Xvfb GUI smoke:** V4.9.1 ana ekran açılışı, kritik kontrollerin varlığı PASS.
- **GUI çocuk hazırlık heartbeat testi:** READY marker oluşturuldu ve zamanla güncellendi PASS.
- **Statik bağlantılar:** 30 dashboard alanı, 50 web onclick çağrısı ve 13 araç haritası; hata 0.
- **Syntax:** Paket içerisindeki tüm Python kaynakları AST parse; JavaScript kaynakları Node `--check` ile kontrol edilecek ve paketleme scripti hata halinde ZIP üretmeyecek.
- **Önceki V4.9.0 ile 9 kritik motor:** SHA256 bazında değişmedi. (Ayrı dosyada listelendi.)
- **Geniş, tarihsel regresyon:** izolasyonlu koşulda test collection safhasında 1 eski `V2_KONTROL_MERKEZI/app.py` yokluğu; bu test hariç geniş çalışma **650 PASS, 40 FAIL, 3 SKIP** ve `--maxfail=40` nedeniyle durdu. Başarısızlıklar arasında eksik tarihi başlatıcılar, eski sabit ekran metinleri, izole ortamda açık 8080 güvenlik koruması, paket içinde git deposu bekleyen testler var. Tarihsel tüm testlerin PASS olduğu iddia edilmiyor. Bu testlerin tamamı yeni özelliklerde gerçek çalışma hatası anlamına gelmez; ancak **tam regresyon kapısı henüz yeşil değil**.

## 3. Açık riskler ve neden 'LIVE_GO' değil
- Bilgisayardaki gerçek OneDrive verisi, SQLite (WAL dahil), onaylı köşeler, PETEK maskeler, kullanıcı onayı ve geri yükleme gerçek Windows'ta test edilmedi.
- Eski magenta şablonlarını güvenle değiştirme aracı korunuyor; ancak çalışma görsellerinin gerçekten dönüştürülmesi yapılmadı. Kullanıcı eşleştirme önizlemesini ve açık onayı vermeli; yeni görseller otomatik APPROVED sayılmamalı.
- Mağaza bazlı gerçek Trendyol XLSX, ImgBB/FreeImage HTTPS bağlantısı, 4K GPU/Real-ESRGAN ve 7 kategoride gerçek tasarım çıktısı bu ortamda canlı doğrulanamaz.
- Opsiyonel ön-plan AI (Torch/Transformers + model ağırlıkları) temel Python kilidine dahil değil. Gerekli görülen şablonlarda bu bağımlılığın eksikliği üretim ön kontrolünde hata üretir; bunun yerine sahte başarı yazılmaz.
- Güncel UI ana penceresi modernleştirildi; yerel Windows dosya diyaloglarının ve tüm eski diyalogların birebir aynı tasarımda görünmesi garanti edilmiyor.
- Paket ayrı klasöre kurulmalı; ilk kurulum Python 3.11 ve temel paketleri indirmek için internet gerektirebilir.
- Kullanıcı PC'sinde her bir düğmenin gerçek tıklanması ve bütün işlerin kesintisiz üretimi henüz kanıtlanmış değildir. Hatasızlık garantisi verilmez.

## 4. Güvenli Windows kurulumu / geri dönüş
1. Çalışan V4.8.8'i koru; yeni ZIP'i **eski uygulamanın ve OneDrive çalışma klasörünün üzerine çıkarma**.
2. Örnek ayrı klasör `C:\AI_WORK\GORSEL_MERKEZ_V491_ADAY`. ZIP'i burada aç.
3. `GORSEL_V46_CANDIDATE\V491_DOGRULA_WINDOWS.bat` çalıştır; manifest PASS olmadan devam etme.
4. `BASLAT_V47_WINDOWS.bat` çalıştır; ilk kullanımda Python 3.11/bağımlılık kontrolü kendiliğinden yapılır.
5. Doğru eski ana veri klasörünü seç; ham veriler ve SQLite yedeği olmadıkça gerçek şablonlara işlem uygulama.
6. İlk deneme: ayrı geçici klasörde **KOPYALA** moduyla 3 kategori, bozuk görsel ve aynı adlı görsel testi yap.
7. Şablon ve PETEK, magenta değiştirme, mağaza XLSX ve gerçek seri üretime ancak ayrı dosya snapshot ile insan kabulünden sonra geç.
8. Sorun olursa uygulamayı kapat; `ESKI_GORUNUME_DON_WINDOWS.bat` sadece görsel eski arayüze döner. Kod geri dönüşü için hiç değiştirilmemiş V4.8.8 kurulumunu kullan. Ana veri klasörünü silme/taşıma.

## 5. Kabul matrisi
| Kontrol | Durum |
|---|---|
| Paket SHA256 / ZIP CRC / manifest | PASS (ayrı checksum raporu) |
| Yeni kritik işlevin hedefli regresyonu | 97 PASS |
| Sadece gerçek Windows açılışı, 7 kategori ve PETEK görsel QA | WINDOWS_NOT_VERIFIED |
| Gerçek veri korunması — önce/sonra byte karşılaştırması | WINDOWS_NOT_VERIFIED |
| Magenta replacement onaylı gerçek kaynakta | WINDOWS_NOT_VERIFIED |
| Bulut/Trendyol/4K üretim | WINDOWS_NOT_VERIFIED |
| Tüm eski regresyon | NOT_GREEN |
| Final LIVE_GO | **NO-GO (beklemede)** |

**Özet:** Kod seviyesinde keşfedilen P0 veri kaybı ve başlatma sorunları giderildi, güvenlik regresyonları geçti ve tek ZIP oluşturuldu; bunlar gerçek Windows uçtan uca final kabulünün yerine geçmez.
