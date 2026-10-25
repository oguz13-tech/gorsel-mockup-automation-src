# ÖZEL GOLDEN DATASET: Gerçek görselleri internete yüklemeden kalite denetimi

## Amaç
Gerçek PETEK, Wi-Fi, Cam Tablo, Cam Doğrama, Ocak Arkası ve Ahşap mockuplarının sabit SHA ve görsel QA karşılaştırmasını kullanıcı bilgisayarında yapmak. Bu yordam **onay vermez** ve hiçbir kullanıcı dosyasını değiştirmez.

## Klasör örneği (tamamen özel)
```
C:\Gorsel_Golden_Ozel\
    manifest.json
    kaynak\petek_001.png
    uretim\petek_001_baski.png
    maskeler\petek_001.png
```

`manifest.json` örneği:
```json
{
  "cases": [
    {
      "id": "petek-001-a",
      "category": "06_Petek_Kapama",
      "source": "kaynak/petek_001.png",
      "render": "uretim/petek_001_baski.png",
      "mask": "maskeler/petek_001.png"
    },
    {
      "id": "cam-dikey-001",
      "category": "02_Cam_Tablo_Dikey",
      "source": "kaynak/cam_001.png",
      "render": "uretim/cam_001.png"
    }
  ]
}
```

- **Kaynak ve render aynı piksel ölçüsündeyse** maske siyah=korunmuş yüzey, beyaz=baskı alanı varsayımıyla kaynağın maskesi DIŞINDA herhangi bir RGB farkı olup olmadığını kontrol eder.
- **Ölçü farklıysa** baskı dışı orijinal piksel eşitliği hesaplanamaz; `NOT_COMPARABLE_DIFFERENT_IMAGE_SIZE` döner. Kullanıcı gerçek görselleri görsel olarak onaylamalıdır; QA PASS uydurulmaz.
- `flat_image_review_hint` bazı beyaz/siyah sade baskıları yanlışlıkla işaretleyebilir. Bu kalite kararı değil, inceleme ipucudur.
- Çıktı Excel pazaryeri kalite ve ürün doğruluğuna eşdeğer değildir.
- 34+ gerçek PETEK fotoğrafını kaynak + maske + baskı için seçip kullanıcı bilgisayarında A/B değerlendir. Eski kaynaklar internete/GitHub'a gönderilmesin.
- 100 MP üstü görseller kaynak açısından yüksek RAM tüketebileceğinden otomatik pixel-decode yapılmaz; daha küçük doğrulanmış test kopyası/insan incelemesi gerekir.

## Güvenlik
Dosyalar yerel okunur; arayüz hiçbir otomatik kaynak taşıma, maske değiştirme, onaylama veya bulut yüklemesi yapmaz. Rapor dış klasöre kullanıcı özellikle kaydetmek isterse oluşturulur; mevcut rapor üzerine yazılmaz.
