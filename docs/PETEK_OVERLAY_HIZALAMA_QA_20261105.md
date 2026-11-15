# PETEK overlay hizalama QA — 2026-11-05

Uygulanan değişiklik tek noktadadır: `MERKEZ/URETIM_V4/petek_overlay_variations_v1.py`.
PETEK render, mağaza seçimi, linkleme ve Excel akışı değiştirilmemiştir.

## Canlı havuz preflight

Kaynak: `C:\GorselUretimMerkezi\Overlay_Giydirme`

| Ölçü | Geçerli grup | Üst | Alt | Yan |
|---|---:|---|---|---|
| 76CM | 13 | grup PNG’si | uygulanmaz | uygulanmaz |
| 96CM | 7 | grup PNG’si | ortak `alt_overlay/altbilgi-overlay.png` | uygulanmaz |
| 116CM | 7 | grup PNG’si | ortak `alt_overlay/altbilgi-overlay.png` | uygulanmaz |
| 136CM | 8 | grup PNG’si | ortak `alt_overlay/altbilgi-overlay.png` | uygulanmaz |

Preflight sonucu `ready: true`.
`116CM/116grup1` yalnızca JPEG içerdiği için güvenli biçimde geçersiz grup olarak raporlandı. `96CM/96grup4` içindeki eski dikey PNG üst seçiminden dışlandı; yatay üst PNG korundu. Hiçbir kaynak PNG değiştirilmedi veya silinmedi.

## Otomatik yerleşim sözleşmesi

- PNG’nin yalnızca tamamen şeffaf dış bbox’ı kırpılır; iç şeffaflık korunur.
- Görünür içerik 1200 px genişliğe orantılı ölçeklenir.
- Üst: `x=0, y=0`.
- Alt: `x=0, y=1600-overlay_height`.
- Temiz PETEK çıktısı 1200×1600 olarak korunur; kaynak fotoğrafa üstten 200 px eklenmez ve fotoğraf 1200×1800 canvas’a taşınmaz. Böylece yapay beyaz spacer oluşmaz.
- Önceden üretilmiş 1200×1800 türevler silinmez; tekrar çalıştırmada boyutları doğrulanır, yeniden kullanılmaz ve yeni 1200×1600 dosya create-only/retry yolu ile oluşturulur.
- 76CM seçiminde alt adımı yoktur; yan adımı hiçbir seçimde ve render’da yoktur.

## Üretim doğrulaması

Sentetik temiz 1200×1600 PETEK kaynakla dört ölçü ayrı ayrı üretildi. Dört çıktı da 1200×1600 oldu:

- 76CM: üst `[0,0]`, doğal ölçek yüksekliği 400 px, alt yok.
- 96CM: üst `[0,0]`, 691 px; ortak alt `[0,1377]`, 423 px.
- 116CM: üst `[0,0]`, 209 px; ortak alt `[0,1377]`, 423 px.
- 136CM: üst `[0,0]`, 338 px; ortak alt `[0,1377]`, 423 px.

Kaynak SHA doğrulaması, create-only çıktı yazımı ve mevcut overlay cache’i korunmuştur. Gerçek üretim kuyruğuna canlı yayın/aktivasyon yapılmamıştır.
