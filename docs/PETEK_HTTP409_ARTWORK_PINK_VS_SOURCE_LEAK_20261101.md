# PETEK HTTP 409 — kanıta dayalı pembe temizleme düzeltmesi

## Doğrulanan kök neden
`MERKEZ/PETEK_V3/petek_visual_pipeline_vnext.py` çağrısı,
`final_cleanup_v495.cleanup_petek_magenta` sonucunda sıfırdan fazla
`remaining_pixels` olduğunda `PETEK_PINK_CLEANUP_INCOMPLETE_REVIEW` fırlatıyordu.
Eski temizleyici ise fotoğrafta şablondan sızmış magenta ile BASKININ KENDİ
pembe/mor renklerini karşılaştırmıyor, yalnız çıkış fotoğrafındaki rengin
HSV değerlerine bakıyordu. Geniş ama meşru pembe tasarımın sınırdaki rengi
dahi HTTP 409'a yol açabiliyordu. Bu davranış gerçek kodla yeniden üretildi.

## Düzeltme
Ortak PETEK render hattı, sanat eserinin dışa yansıtılmış, ilk kez basılmış
ve henüz ek güneş/malzeme/yarık efektleri uygulanmamış halini **RAM'de**
referans olarak tutar. Son temizleyici yalnızca:
1. baskı referansında pembe olmayan,
2. son efektlerden sonra magentaya dönmüş,
3. orijinal kaynağın magenta işareti taşıdığı,
4. onaylı baskı MASKESİ İÇİNDE ve dar kenar/yarık dudak bölgesindeki
pikselleri gerçek baskı referansından geri yükler.

Meşru pembe baskı rengi korunur. Orijinal PETEK fotoğrafı/maske/4 köşe,
deliklerin içi, üst-alt kavisler, SQLite, mağaza profilleri değişmez.
Bağımsız eski çağrıları korumak için `printed_reference` verilmeyen
`cleanup_petek_magenta` eski davranışını muhafaza eder.

## Gözlem ve kabul
- Sentetik canlı hata yeniden üretildi: önceden HTTP409; sonrasında başarılı.
- Aynı tam görsel işleminde 15 gerçek yarık / Belirgin ışık / pembe baskı başarılı.
- Magenta kirletme enjeksiyonunda gerçek yeni sızıntı baskıdan onarıldı.
- Salt-okunur dosya/maske korunması ve eski V4.9.5 testleri çalıştırıldı.
- Windows 8080 gerçek cihaz ve kullanıcının PETEK fotoğrafı: WINDOWS_NOT_VERIFIED.

## Güvenli kurulum/geri dönüş
1. Programın mevcut 4 Köşe/Şablon Servisini arayüzden durdurun;
   tarayıcı adresine eski sunucu cevap veriyorsa sürümü değiştirmeden
   PID'i teşhis edin, körlemesine `taskkill` kullanmayın.
2. Yeni ZIP'i C:\\AI_WORK\\PETEK_PINK409_TEST adlı yeni boş klasöre açın.
3. PETEK_PINK409_DOGRULA_WINDOWS.bat sonra PETEK_PINK409_BASLAT_WINDOWS.bat.
4. Şablon İnceleme Merkezi'ni açın, service-status'da `code_root` yeni sürümü
   gösterene kadar önizlemeye devam etmeyin. Ctrl+F5 ile sayfayı yenileyin.
5. Bir pembe baskı, bir saf beyaz baskı ve bir 15 yarıklı PETEK görseliyle
   hem A/B hem seri üretim çıktısını karşılaştırın.
6. Geri dönüş: eski klasörü aynı şekilde açın, yeni sürümden çıkın ve
   inceleme sunucusunu eski sürümden başlatın. Hiçbir veri migrasyonu yok.
