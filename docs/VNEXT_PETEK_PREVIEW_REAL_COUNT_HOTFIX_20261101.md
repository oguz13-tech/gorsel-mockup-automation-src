# PETEK VNext — 13/14/15/16 gerçek ızgara önizleme hatası / acil düzeltme

**Tarih:** 01.11.2026 · **Durum:** Windows adayı · `WINDOWS_NOT_VERIFIED`

## Kesin kök neden
Eski `SABLON_V2_MIMARI/static/js/petek_editor_v477.js` içinde `data.slot_qa?.count!==15` kapısı bulunuyordu. `MERKEZ/PETEK_V3/petek_finish_v492.py` ve `petek_slot_geometry_vnext.py` gerçek fotoğraftan 13–16 fiziksel yarık sayısı döndürebildiği halde UI 15 dışında `after` görselini reddediyordu. Ekrandaki `Tam 15 ızgara önizlemesi üretilemedi` bunun doğrudan belirtisidir.

## Düzeltme
- UI `after` görseli mevcut ve `slot_qa.count` tamsayı 13–16 aralığında olduğunda gösterir.
- UI sonucun gerçek yarık sayısını gösterir; kaynak görüntüden ölçülen merkezler, genişlikler ve aralıklar değişmez.
- Gerçek geometrisi yetersiz kayıtlarda anlamlı uyarı korunur; eksik yarıklar 15'e tamamlanmaz.
- `index.html` script URL cache-busting değeri yenilendi ve eski 15 etiketi kaldırıldı.
- Sunucu/motor, kayıt, onay, maske, quad, ham arşiv veya mağaza motoru değiştirilmedi.

## Kanıt
- Gerçek Chromium DOM testi: 13/14/15/16 senaryolarında A/B tuşları çalışır; her birinde 1 POST, doğru `count`, `fifteen_slot_ab=true`, `orta` yoğunluğu.
- İlgili testler: `95 passed, 1 skipped, 1 deselected` (Linux/Xvfb/Chromium).
- Flask gerçek HTTP + Windows kullanıcı şablonları denenmedi: `WINDOWS_NOT_VERIFIED`.
- SHA256 manifesti ile temiz ZIP çıkarımı doğrulanır.

## Kurulum ve geri dönüş
`PETEK_ACIL_DOGRULA_WINDOWS.bat` ile kaynak bütünlüğünü kontrol et, ardından `PETEK_ACIL_BASLAT_WINDOWS.bat`. Her zaman yeni boş çalışma klasörüne çıkar. Eski çalışan ZIP saklanır; geri dönüş için bu adayın kullanılmasını bırakıp önceki çalışan sürüm açılır. Kullanıcı verilerini adayın üzerine kopyalama, otomatik migration yapma.
