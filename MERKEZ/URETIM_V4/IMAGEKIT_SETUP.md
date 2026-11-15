# ImageKit (yerel ayar)

ImageKit anahtarı kaynak koda veya GitHub'a yazılmaz. `runtime_root` altında
`ayarlar.local.json` oluşturun (bu dosya paylaşılmamalıdır) veya Windows yerel
ortamında `IMAGEKIT_PRIVATE_KEY` değişkenini tanımlayın:

```json
{
  "bulut_ayarlari": {
    "provider": "imagekit",
    "imagekit_private_key": "<ImageKit Private Key>",
    "imgbb_keys": []
  }
}
```

`provider` değeri `imgbb` olduğunda mevcut ImgBB/FreeImage akışı değişmeden
çalışır. ImageKit yüklemesi multipart olarak orijinal baytları gönderir; dönen
URL'ye `tr=orig-true` eklenir ve bağlantı Excel/ledger'a girmeden önce uzak
baytların SHA-256, piksel çözünürlüğü ve formatı kaynak dosyayla karşılaştırılır.
