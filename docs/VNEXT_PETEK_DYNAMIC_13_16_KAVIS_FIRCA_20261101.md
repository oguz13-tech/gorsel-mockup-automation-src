# PETEK VNext — Dinamik 13/14/15/16 yarık, yalnız kavis taşma koruması, görünür fırça

## Kullanıcı kararı
Gerçek PETEK şablonunda bulunan yarık sayısı korunacak. Kaynakta 13/14/15/16 varsa aynı sayıda koyu perspektif uyumlu gölge uygulanacak. **15'e tamamlama yapılmayacak.**

## Kaynak kod
- `MERKEZ/PETEK_V3/petek_slot_geometry_vnext.py`: Orijinal fotoğraftan rektifiye yarık geometrisi (x/y/uzunluk/genişlik), 13..16 adaylı model, kaynak dışı çizgi ekleme yok, incelenmiş maske fallback.
- `MERKEZ/PETEK_V3/petek_finish_v492.py`: Parametrik ölçümlü yarık çizimi; korunan maske pikselleri değişmez; eski `draw_fifteen_slots` API çağrısı geriye uyumludur, ama sayı zorlanmaz.
- `MERKEZ/PETEK_V3/final_cleanup_v495.py`: Pembe kalıntı temizliğinde değişken uzunluktaki kaynaktan ölçülen merkezler.
- `SABLON_V2_MIMARI/static/js/petek_editor_v477.js`: `clipWoodPaintAtCurves`, kaynak fotoğraf pikseliyle eşleşen `updateBrushCursor`, dinamik aralık/yarık UI raporu.
- `SABLON_V2_MIMARI/static/css/petek_editor_v477.css` ve `templates/index.html`: kontrastlı halkalı fırça, anlık px göstergesi, dinamik A/B etiketleri.

## Güvenlik ve sınırlar
- `Ahşabı Boya` normal quad içinde, ancak kullanıcı tarafından çizilen üst/alt kavislerin **yalnız X aralıklarında** sınırlandırılır. Diğer bölümlerde ek maske kısıtlaması yoktur. Eğri noktaları yetersizse var olmayan bir kavis tahmin edilmez.
- `Ahşap boyasını sil` ve `Delikleri Koru` mevcut görevlerini sürdürür.
- Gerçek orijinal, onaylı maskeler, köşeler ve mağaza verisi çalışma sırasında kod düzenlemesinden etkilenmez; çizim taslak ve renderın RAM kopyasında kalır.
- Kaynak görüntü/maskeden güvenilir biçimde 13–16 yarık ölçülemiyorsa sessizce 15 üretilmez, kayıt bazlı hata raporu döner.

## Testler
- Linux + Xvfb + Chromium: **90 PASSED / 1 SKIPPED / 1 DESELECTED** (Flask HTTP live test excluded due to missing dependency).
- Fiziksel yarık sayıları 13/14/15/16, orijinal fotoğraf perspektifi ve eksik maske deliği, boya sadece kavis sınırına takılır, düz bölgeler boyanır, zoom/slider fırça çapı, önceki mağaza/şablon testleri.
- **WINDOWS_NOT_VERIFIED**: gerçek PETEK havuzunda fotoğraf/maske/4K, mağaza/Excel, Windows DPI, gerçek Flask HTTP, kullanıcı UAT.

## Kurulum ve rollback
Yeni ZIP'i ayrı boş `C:\AI_WORK\PETEK_DYNAMIC_TEST` klasörüne çıkarın. Önce `PETEK_VNEXT_DOGRULA_WINDOWS.bat`, ardından `PETEK_VNEXT_BASLAT_WINDOWS.bat` çalıştırın. Asıl sistemi üzerine yazmayın. Eski çalışan ZIP'i saklayın; gerektiğinde aday klasörünü kullanmayı bırakıp eski sürümü açın. Onaylı kayıtları gözünüz kapalı geri yüklemeyin.
