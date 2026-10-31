# GÖRSEL ÜRETİM MERKEZİ V4.9.2 — TESLİM VE SINIRLAR

**Tarih:** 31 Ekim 2026  
**Kaynak:** Kullanıcıya sunulan V4.9.1 Windows adayı, ayrı kaynak kopyası.  
**Durum:** WINDOWS GÜVENLİ ADAY — WINDOWS_NOT_VERIFIED; GERÇEK ÜRETİM FİNAL ONAYI YOK.  

## BİTİRİLEN GELİŞTİRMELER

1. PETEK 15 dikey ızgara için **kaynak fotoğrafta kanıtlı dar ve koyu yarık tespiti**: maskenin koruduğu deliklerin gerçek koyu pikselleri esas alınır. Düzenli 10–16 yuva saptanmıyorsa veya dağılım güvenilir değilse çizgi oluşturmaz. Algılanan yarık kenarına yakın, yalnız **baskıya izin verilen maskeli pikseller** hafif/orta/güçlü oranda koyulaştırılır; maske=0 orijinal delik ve kavis pikselleri aynen kalır. Varsayılan KAPALI.
2. Alt sol PEMBE İZ için yalnız maskenin alt-sol çevresindeki çok küçük güçlü MAGENTA (referans) adaylarına izin verilir. 220 px üst sınırı ve yakın temiz kaynak piksel gereksinimi vardır; kaynak görsel diske yazılmaz. Yeterli kanıt yoksa işlem iptal edilir. Varsayılan KAPALI; köşe QA için insana A/B önizleme sunulur.
3. **PETEK Önce/Sonra Testi**: Gerçek onaylı PETEK şablonu + seçilen ham tasarımla bir A/B üretir; izlenen örnekte sıfır değişiklik varsa onay düğmesi çıkmaz. Üretimde yeni tarif kullanılması insanın A/B önizlemesini onaylamasına bağlıdır. Onaylı maske/geometri veya orijinal şablon güncellenmez. Kaydedilmiş eski çıktılar değiştirilmez.
4. **Çakışmaz PETEK yeni dosya kimliği:** mağazaya ait yeni PETEK denemesi `__PV492_orta_P1.png` benzeri tarif sonekiyle kaydedilir; LOCAL tarif kimliği de mod/düzeltmeye göre ayrılır. Kaynak, onay ve eski ledger korunur.
5. **Seri üretim seçim alanı:** kategori filtresi, şablon arama, ada/kategoriye göre sıralama, filtrelenenleri seç, tümünü seç, temizle, seçili/toplam sayacı. Bir kategori seçiliyken diğer kategoride yapılmış seçimler silinmez. Üretim ekranının tamamı kaydırılabilir, alt düğmeler gizli kalmaz.
6. **4K Durum / Kur / GPU Test**: arayüzden resmi Real-ESRGAN NCNN Windows kurulum BAT/PowerShell aracına ulaşılır. Mevcut resmi x4plus EXE ve `models/*.bin/.param` ön kontrolden geçer; eksikse resmi kaynak, sabit SHA256 ve gerçek Vulkan GPU testine dayalı kurulum yapılabilir. Model/EXE **ZIP'te hazır kurulu değildir**; internet ve Windows GPU gerekir; 4K varsayılan KAPALI. Otomatik 4K yerine düz resize yalanı söylenmez.
7. V4.9.1'deki görsel seçici dosya silinmesi, hata yalıtımı, güvenli bağımsız araç açılışı ve modern ana ekran düzeltmeleri korunmuştur. Diğer sekiz kritik motor SHA256 eşitliğiyle değişmeden kaldı.

## OTOMATİK / YEREL TESTLER
- Yeni V4.9.2 PETEK & filtre testleri: 7 PASS (korunan alanlar, 15 slot, geçersiz geometri, düşük güvenle atla, pembe temizleme, salt-okunur filtre).
- V4.9.1 güvenlik/üretim/mağaza/Excel/4K/PETEK regresyonlarıyla birlikte: **84 PASS, 0 FAIL** (seçili kapsam).
- Linux Xvfb ile canlı Tk UI: açılış, kategori değişikliği, çoklu seçim hafızası, filtre ve scroll smoke: PASS.
- Statik bağlantılar: 30 dashboard referansı, 50 web callback, 13 profesyonel araç, 0 kopuk.
- Tüm dağıtım Python sözdizimi ve JavaScript Node --check: paketleme öncesi PASS.
- ZIP CRC + SHA256 manifest: ayrı özet ve doğrulama BAT.

## BİLİNEN SINIRLAR — GERÇEK FİNAL YOK
- **Kullanıcının gerçek PETEK fotoğrafı+onaylı maskesi bu ortamda yok.** 15 gerçek yarık hizası ve alt-sol taşmadaki tam görsel düzeltme, sentetik test geçse de henüz gerçek şablonda kabul edilmedi; sistem düşük güven durumunda düzeltmeyi atlar. %100/0 hata vaadi yok.
- 4K EXE ve ağırlıklar bu dağıtımın içinde bulunmaz. Kullanıcının Windows PC'sinde kurulum, Vulkan ve çıktı boyutu testi bekleniyor.
- Gerçek OneDrive, şablon SQLite (WAL dahil), onaylı PETEK profilleri, mağaza/Trendyol dosyaları, ImgBB HTTPS linkleri ve 7 kategorili büyük parti yerinde test edilmedi.
- V4.9.1 tarihsel test takımında **650 PASS / 40 FAIL / 3 SKIP** vardı; bu köklü eski testlerin tamamı kapatılmadı. V4.9.2 yalnız seçili 84 testi geçti. Tüm tarihsel regresyon yeşil olmadığı için koşulsuz final değil.
- ESKI_GORUNUME_DON yalnız UI geri dönüşüdür; çalışan kodun tam geri dönüşü, korunan V4.8.8/V4.9.1 ZIP ve canlı veri yedeğiyle yapılır.

## GÜVENLİ KURULUM
1. V4.8.8 ve mevcut ana çalışma klasörünü koru. ZIP'i farklı boş klasöre çıkar.
2. `GORSEL_V46_CANDIDATE\V492_DOGRULA_WINDOWS.bat` çalıştır; hata 0 değilse açma.
3. `GORSEL_V46_CANDIDATE\BASLAT_V47_WINDOWS.bat` ile başlat (Python 3.11, ilk sefer internet).
4. Önce PETEK tek onaylı fotoğrafta `orta` koyu ızgara, önce/sonra; olumlu ise A/B penceresinden onayla.
5. 4K için `4K Durum / Kur / GPU Test` ile gerçek GPU kurulumunu ve test makbuzunu doğrula.
6. Yedi kategori/Excel/bulut normal üretime ancak canlı Windows şablon/maske QA ve yedek sonrası geç.
7. Eski magenta onaylı şablonları toplu değiştirme halen ayrı kullanıcı önizleme+onay işlemidir. Eski ana klasörü kesinlikle silme, üzerine ZIP çıkarma.

**KARAR:** YENİ WINDOWS ADAYI TESLİM EDİLDİ; KESİN CANLI ÜRETİM FINAL = NO-GO / WINDOWS_NOT_VERIFIED.
