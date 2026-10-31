# PETEK VNext — Fotoğraftaki 15 gerçek ızgaraya ölçümlü yerleştirme ve UID seçim koruması

**01.11.2026 / KISMİ GELİŞTİRME ADAYI / WINDOWS_NOT_VERIFIED**

## Gerçek sorun
Önceki üretim katmanı, orijinal maskede yeterli güvenilir delik verisi yoksa panelin üzerine sabit 15 eşit aralıklı ve sabit boylu koyu izgaralar ekleyebiliyordu. Bu, at grafikli ürün örneğinde baskı desenini kesen ikinci/yanlış yarık sırası oluşturuyordu. Fotoğraftaki perspektifte soldan sağa delik aralıkları fiziksel piksel olarak eşit değildir. Ayrı olarak PETEK sol listesinde dosya tıklanınca gizli select UID'si eski dosyada kalabiliyor; taslak kaydı/yenilemede seçim sıçrayabiliyordu.

## Uygulanan yeni yöntem
1. Kullanıcının dört köşeli panelini homografiyle 900×690 geçici düzleme dönüştür (orijinal dosyaya dokunmaz).
2. **Orijinal kaynaktan** dikey koyu fiziksel yarık kanıtlarını yatay morfolojik black-hat ile bul. İnsan onaylı maskenin korunan 0 piksellerini ayrı sinyal olarak tut.
3. Öncelikle gerçek görüntüdeki 15 merkez noktasını ölç; güçlü görsel kanıt yoksa sadece maskenin 15 fiziksel yarığını kullan. Kısmi gözlemlerde en fazla 2 noktayı yakınlarındaki gerçek kaynak kontrastıyla doğrulanmış aralık verisiyle tamamla. Eşit dağıtımlı kör üretim yok.
4. Her yarık için ayrı üst-alt uç, genişlik ve olası ince eğimi ölç. Koyu gölge/lip yalnız o yarığa projeksiyonla hizalanır.
5. Maske==0 korunan yarık pikselleri, beyaz yanlar, üst-alt kavis, zemin, orijinal fotoğraf, onaylı maske, onaylı dört köşe ve kayıtlar değiştirilmez. İşlem sadece çıktı PNG'sinin RAM kopyası üzerinde.
6. Artık QA/önizlemede 15 merkez, 14 ölçülmüş mesafe, 15 başlangıç-bitiş, 15 genişlik, kaynak/maske kanıt sayıları ve varsa interpolasyon sayısı gösterilebilir.
7. Gerçek delik bilgisi kayıpta tek şablon hata raporunda `PETEK_IZGARA_KONUMU_BELIRSIZ` olarak incelemeye ayrılır; varsayımsal 15 çizgi basılmaz. Seri üretimde üst motor zaten tekil hatayı kaydedip diğer işlere devam eder.
8. Sol listeden fotoğraf tıklanınca gizli native seçici aynı UID'ye eşlenir. Taslak kaydı yalnız o kaydı yerinde günceller; onay sonrası liste yeniden yüklenmez; filtre mevcut kaydı gizlerse ok tuşu ilk kayda atlamaz.

## Örnek görüntüde yerel doğrulama
Kullanıcının sağladığı maskeli önizleme **sadece yerel kontrol** için kullanıldı; GitHub veya dağıtım ZIP'ine eklenmedi. Dört köşe yaklaşık [[53,27],[547,16],[547,374],[52,484]]. Persfektif düzeltilmiş görüntüde 15 kaynak merkezi: [85,138,190,242,294,346,397,449,502,554,606,659,711,765,818]. Görüntüde orta yatay kesitte kaynak koordinatlarında yarık merkezleri yaklaşık 111 ile 511 px, komşu aralıklar solda 34.8px, sağda 24.1px. Yeni motor bu ölçümleri birebir geri projelendirdi. Bu tek örnek genel doğruluk yüzdesi değildir.

## Otomatik test
- İlgili 13 test dosyasında Linux/Xvfb/Chromium **83 PASS, 1 SKIP, 1 DESELECT** (Flask HTTP bağımlılığı eksik olduğundan). Sentetik geometri odaklı testler 24 PASS, 1 DESELECT. Tarayıcı taslak/onay UID testi PASS.
- **WINDOWS_NOT_VERIFIED:** gerçek PETEK fotoğraf havuzu, 15 yarık A/B, farklı DPI, 4K/Excel/seri üretim ve gerçek Windows çalışması.

## Güvenli kurulum / geri dönüş
Mevcut çalışan sürümü kullanmaya devam edin. Aday ZIP'i `C:\AI_WORK\PETEK_VNEXT_TEST` gibi yeni/boş klasöre çıkarın. İçeride `GORSEL_V4102_WINDOWS\GORSEL_V46_CANDIDATE` klasöründeki `PETEK_VNEXT_DOGRULA_WINDOWS.bat` ardından `PETEK_VNEXT_BASLAT_WINDOWS.bat` çalıştırılır. Gerçek veri havuzuna otomatik bağlama yapmayın; önce izole örneklerle test edin. Geri dönüş için aday klasörü kullanmayı durdurup değişmemiş V4.10.2 veya MOR VNext ZIP'ini ayrı klasörden açın. Orijinal/SQLite/mağaza JSON/maske verilerine otomatik migration yapılmaz. Meta AI Sahne DNA ile bağlantı kurulmaz.
