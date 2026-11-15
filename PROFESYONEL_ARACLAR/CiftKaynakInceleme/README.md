# Çift Kaynak Sistem İnceleme ZIP'i — Profesyonel Bağımsız Araç

**Araç adı:** Çift Kaynak İnceleme Paketi Hazırla

Bu araç `C:\GorselUretimMerkezi` kökündeki kaynak kodları ve `C:\GorselUretimMerkezi\CODEX_ACTIVE` alt ağacındaki kodları **birbirinden ayrı** olacak şekilde aynı ZIP içine koyar. `KOK/` ve `CODEX_ACTIVE/` önekleri korunur; iki ağaç birleştirilip üzerine yazılmaz.

**Tek tıkla nasıl kullanılır?**
1. Bu klasörü uygulamanın mevcut `Profesyonel Bağımsız Araçlar` altyapısında uygun yere ekleyin.
2. Menüde görünen **Çift Kaynak İnceleme Paketi Hazırla** aracını çalıştırın.
3. Program ZIP'i `C:\GorselUretimMerkezi\INCELEME_PAKETLERI\` içine tarihli adla kaydeder ve Windows Gezgini'nde ZIP'i seçili açar.
4. Aynı klasörde bir adet `.sha256.txt` doğrulama dosyası olur. İçerik envanteri ZIP içinde `PAKET_DOSYA_LISTESI.tsv` ve `INCELEME_NOTU.txt` dosyalarındadır.

**Uygulama menüsüne bağlama (Tkinter / CustomTkinter kullanılıyorsa):**

```python
from PROFESYONEL_ARACLAR.CiftKaynakInceleme.arac import baslat

# Mevcut menü butonunun command/callback işleyicisine:
command=lambda: baslat(parent=ana_pencere,
    tamamlandi=lambda basarili, bilgi: durum_goster(bilgi))
```

`ana_pencere` ve `durum_goster` uygulamanızda mevcut bileşenlere göre uyarlanmalıdır. Web tabanlı menü/Flask kullanılıyorsa mevcut yetkili araç çalıştırma uç noktasına bağlanmalıdır; bu örnek doğrudan bir HTTP uç noktası kurmaz.

**Menü entegrasyonu tamamlanmadan kullanım:** `CIFT_KAYNAK_INCELEME_HAZIRLA.bat` çift tıklanarak aynı işlem yapılabilir.

## Paketleme kapsamı ve güvenlik

- **Dahil:** `.py`, `.js`, `.ts`, `.html`, `.css`, `.ps1`, `.bat`, `.md`, `.sql` gibi izinli kaynak/metin dosyaları; izinli diğer dosyalar için PS1 içindeki liste geçerlidir.
- **Hariç:** `.git`, sanal ortamlar, loglar, veritabanları, maskeler, görseller, modeller, üretim çıktıları, kullanıcı dosyaları, şifre/token adlarıyla eşleşen dosyalar. 4 MB üzeri tekil dosyalar ve toplam 120 MB kaynak sınırı.
- **Amaç:** Kod/sistem mimarisi incelemesi. **Bu bir tam geri yüklenebilir sistem yedeği değildir.**
- **Gizlilik:** Kod dosyalarının içine gömülmüş anahtarlar otomatik olarak ayıklanamaz. ZIP'i başkasına yüklemeden önce gözden geçirin.
- **Koruma:** Kaynak iki klasördeki mevcut dosyalar değiştirilmez; otomatik düzeltme veya veri temizliği yapılmaz.
- **Doğrulama:** ZIP merkezi dizini okunabilirliği doğrulanır; tam arşiv içeriği Windows'ta ayrıca test edilmelidir.

## Kurulum sınırı

Bu ZIP içinde araç, tek tıklamalı çalıştırıcı ve Tkinter/CustomTkinter için asenkron bağlayıcı hazırlanmıştır. Mevcut uygulamanın *güncel menü kodu* dosyaları bu konuşmada verilmediğinden menü butonunu o uygulamaya doğrudan yazıp test etmek mümkün olmadı. Kod tabanına değişiklik yapmadan önce mevcut menü kayıt/bağlantı yönteminin incelenmesi gerekir. Yanlış tahmine dayanarak ana panel veya üretim kodları değiştirilmemiştir.
