# EPIC-3 / Gerçek Tasarım Görseliyle İzole Pilot — 2026-10-13

Bu kılavuz yalnız CAUTION/INSPECTION içindir. **Canlı üretime geçiş değildir**. Kullanıcı görseli/pazaryeri çıktısı otomatik onaylanmaz. Kilo kendi kendine bu testi başlatmayacak; G0 Doctor/Preflight raporu ve kullanıcı gerçek tasarım onayı sonrası ayrıca yetkilendirilecek.

## Amaç
- Giriş: gerçek H (yatay) ve/veya V (dikey) baskı dosyası (PNG/JPG/WEBP/BMP).
- Çıktı: **her uygun APPROVED+hash-valid şablon için** 1200×1600 JPG ve tek karşılaştırma sayfası; yalnız yeni OS TEMP klasörü.
- İçerik koruması: oryantasyon, kaynak onayı, SHA, fiziksel ratio, en az 500px kısa kenar, opak RGB, yanlış kaynak dizininde başlatmama.
- Gerçek render motoru homography, glass/non-glass, kalite ve 3:4 kontrolleri kullanır. Maskeyi doğrulayamadığı profil `BLOCKED` olur.
- Bulut, SEO, Excel, ticari artifact state, DB onayı/rename/kopyalama/restore ya da üretim klasörüne yazma YOK.

## Kaynak ve sürüm
- Güncel geliştirme dalı: `safety/epic3-archive-guardrails-20261010`. YALNIZ test edilmiş exact commit SHA ile koddan ayrı TEMP clone oluştur.
- Kod: `scripts/epic3_real_artwork_pilot.py`, temel izole render: `scripts/epic3_six_template_smoke.py`.
- Pilot *olmadan* kod kontrolü için `--execute` parametresini VERME. `PLAN_ONLY` yazar; dosya okuma/yazma ve render yapmaz.

## PowerShell örneği (YALNIZ EĞİTİM/ONAY SONRASI)

```powershell
$runtime = 'C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu'
$h = 'C:\ARTWORK\tasarim-yatay.png'
$v = 'C:\ARTWORK\tasarim-dikey.png'
python scripts\epic3_real_artwork_pilot.py --runtime-root "$runtime" --artwork-h "$h" --artwork-v "$v"
# Ancak ayrıca açık kullanıcı izni, exact tested SHA ve G0 kabulünden sonra:
python scripts\epic3_real_artwork_pilot.py --runtime-root "$runtime" --artwork-h "$h" --artwork-v "$v" --only 02_Cam_Tablo_Dikey --only 02_Cam_Tablo_Yatay --only 03_Ahsap_Tablo --only 05_Ocak_Arkasi --execute
```

Her kategori için farklı doğru fiziksel oranda baskı gerekiyorsa `--artwork-for 02_Cam_Tablo_Dikey=C:\ARTWORK\ozel-dikey.png` gibi tekrarlanan seçenek verilir. `--only` olmadan altı sabit deneme UID'si kullanılır. Yeni şablon otomatik aranmaz veya onaylanmaz.

## Kritik fiziksel oran kontrolü
- Normal render motoru küçük oran farklarında merkezden KIRPMA, orta oran farklarında BLEED üretebilir; pilot bunu özellikle önler.
- Pilot yalnız onaylı nominal fiziksel en-boy oranıyla farkı en fazla %0,5 olan gerçek tasarım dosyasını geçirir. Aksi halde `ARTWORK_RATIO_WOULD_CROP_OR_SYNTHESIZE` yazıp güvenli durur.
- Uyumlu H/V dosyalarınız yoksa ne ChatGPT ne Kilo oranı gizlice esnetir/kırpar; yeni doğru oranlı baskı master'ı hazırlanır ve insan görsel onayı alınır.
- Orijinal arşiv/çalışma şablonları/çıktılar **tasarım girdisi** olarak kullanılamaz.
- `04_Cam_Dograma` şu anda görsel ürün açısı açısından kalite beklemede: koddan PASS çıksa bile kullanıcı görsel onayı olmadan ticari üretime açılmaz.

## Sonuç ve kanıt
- Terminalde `ISOLATED_OUTPUT_ROOT`, `PILOT_RESULT`, `PILOT_REPORT_PATH`, `PILOT_EXIT_CODE` görünür.
- OS TEMP'de `real-artwork-pilot-report.json`, `CONTACT_SHEET_TEST_ONLY.jpg`, ayrıca başarılı kategori JPEG'leri bulunur.
- `PILOT_EXIT_CODE=0`: seçilen kategorilerin hepsi teknik QA geçmiştir ve kaynak hashler değişmemiştir. **Ürün gerçekçiliği ve maskeleme için insan onayı hâlâ gerekir.**
- `PILOT_EXIT_CODE=2`: bir veya daha fazla FAIL/BLOCKED veya giriş değişimi; otomatik düzeltme/approve/deploy YOK.
- Kilo yalnız exit, kategori, blokaj ve TEMP yolunu Issue #1'e raporlar. Gerçek artwork veya çıktılar Github'a yüklenmez. Kullanıcı JPG/CONTACT_SHEET'i ChatGPT'ye inceleme için yükleyebilir.

## Sonraki kapılar
- G0 read-only doctor/preflight; G1 kullanıcı gerçek baskı onaylı pilot; G2 kontrollü 4 kategori küçük seri; G3 full commerce factory; G4 açık kullanıcı izinli release.
- Otomatik maskeleme, cloud/Excel, UI staging/watcher, tam GT değerlendirmesi ve 492 şablonun tamamı başka kapsamlardır. G1 PASS bunların tamamlandığı iddiası değildir.