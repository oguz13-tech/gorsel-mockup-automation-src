# Görsel Üretim Merkezi — Teknik mimari / V4.10.1

**Kaynak:** `GORSEL_V46_CANDIDATE/` altındaki Python, Flask/Web ve JavaScript dosyaları. Bu paket bir **Windows kabul adayıdır**, çalışma klasörü ve eski gerçek maskeler pakete dahil değildir.

## Çalıştırma

1. `V4101_DOGRULA_WINDOWS.bat` — dağıtım içeriği manifest SHA-256 ve boyut doğrulaması, veri yazmaz.
2. `V4101_BASLAT_WINDOWS.bat` → `BASLAT_V47_WINDOWS.bat` → `MERKEZ/merkez.py` — ana Tk merkez.
3. Ana menüden **Şablon İnceleme** → `SABLON_V2_MIMARI` yerel Flask + HTML/JS; **Seri Üretim** → `MERKEZ/URETIM_V4/gui_v4.py`.

## Dosya haritası

- `MERKEZ/merkez.py` — yedi kategori Windows giriş noktası, güvenli inceleme sunucusu ve pencere yönetimi.
- `MERKEZ/premium_dashboard_v489.py` — antrasit Tk ana sayfa, kartlar, açık düzenleme modunda sürükleme.
- `MERKEZ/ui_layout_v498.py` — yalnız UI ayarları (`%LOCALAPPDATA%/GorselMockup/UI_V498/layout.json`), güvenli atomik kaydetme, sekmeler, renk/efekt, geri al. Onaylı şablon SQL/PNG dosyaları burada değişmez.
- `MERKEZ/personal_hub_v493.py` — notlar, yapılacaklar, kalıcı kullanıcı test kabul kayıtları.
- `MERKEZ/error_advisor_v498.py` — Tk hata neden/çözüm pop-up kataloğu, kritik hatalarda; toplu dosya hata akışları günlükte birikir.
- `MERKEZ/dark_theme_v42.py` — ortak antrasit ttk stilleri/hover.
- `SABLON_V2_MIMARI/templates/index.html` — yedi kategorinin Şablon İnceleme UI ve PETEK bölümü.
- `SABLON_V2_MIMARI/static/js/main.js` — 6 kategorinin inceleme, toplu seçim ve köşe işlemleri; aktif PETEK varken kısayollar pasif.
- `SABLON_V2_MIMARI/static/js/review_v46.js` — altı kategoride 4 köşe taslakları/toplu algılama.
- `SABLON_V2_MIMARI/static/js/petek_editor_v477.js` — PETEK yedinci kategori editörü; 15 yarık/maske, 4 köşe revizyonu, toplu taslak onaylama, maskede boyama/silme.
- `SABLON_V2_MIMARI/static/js/v499_status_filter.js` — salt-görsel dört durumlu filtre (Yeni, Taslak, Onaylı, Hatalı).
- `SABLON_V2_MIMARI/static/css/v4101_unified.css` — yedi kategoride durum rengi/tipografi, PETEK boş satır düzeltmesi; şablon kayıtlarına dokunmaz.
- `SABLON_V2_MIMARI/core/petek_web_v477.py` — güvenli PETEK Flask HTTP uçları: `bulk-propose`, `bulk-save-new-drafts`, `bulk-approve-confirmed`, `new-revision`, `activate-approved-revision`, `restore-approved-revision`.
- `MERKEZ/PETEK_V3/registry.py` — PETEK maske/quad kaynak SHA ve onay/aktif revizyon kayıtları. **Kaynak doğrulama olmadan aktif onaylıyı değiştirme.**
- `MERKEZ/PETEK_V3/engine.py`, `petek_finish_v492.py`, `final_cleanup_v495.py`, `grille_guard_v482.py` — kullanıcı tarafından başarılı kabul edilen 15 koyu yarık ve pembe temizlik render motorları; V4.10.1'de değiştirilmedi.
- `MERKEZ/URETIM_V4/unified_batch.py` — seri üretim iş kuyruğu, üretilen görseller.
- `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` + `store_assignment_v410.py` — Mağaza→Kategori→Onaylı fotoğraflar→manuel seçim→tek açık atama onayı. Aynı ham baskı farklı mağazalarda farklı mockuplarla kullanılabilir; aynı kaynak mockup fotoğrafı iki mağazaya atanamaz.
- `MERKEZ/URETIM_V4/on_demand_4k_v495.py` + `upscale4k_v44.py` — 4K seçilince kurulum kontrol/önbellek; normal çıktı yolu bağımsız.
- `MERKEZ/URETIM_V4/cloud_excel_v43.py`, `store_excel_v485.py`, `marketplace_excel_v45.py` — HTTP görüntü linkleri/mağaza bazlı XLSX.
- `SABLON_V2_MIMARI/core/template_identity.py`, `workspace_consistency.py`, `safe_working_revision.py` — isim/uzantı/kimlik ve orijinal koruma.
- `tests/`, `TESTLER/` — Python/arayüz/maske/mağaza regresyonları.
- `LEGACY_TOOLS_REFERENCE/`, `LEGACY_REFERANS_KOD/` — geri dönüş ve karşılaştırma için eski araç referansları; yeni merkez için kanonik kaynak değildir.

## Veri saklama ve güvenlik sözleşmesi

- **Asla** çalışma klasörünün veya `2_SABLON_HAVUZU_ORIJINAL_YEDEK` içeriğinin üzerine ZIP açma.
- Onaylanan PETEK: eski immutable approved UID korunur; düzenlemede yeni DRAFT revizyonu, açık insan onayı ve yeni etkin UID kullanılır; eski sürüme dönüş desteklenir.
- PETEK toplu DRAFT onayı kullanıcıdan **tek genel onay** alır; arka uçta SHA/UID/maske kontrollü kayıt bazında geçerli olanları onaylar, geçersizler DRAFT kalır. 8'li sunucu işlemi bir UI kısıtı değildir.
- Ham baskı tasarımı kimliği mockup fotoğrafı kimliğinden ayrıdır. Tek mockup dosyasını mağazalar arasında paylaşma engeli ham tasarımı yeniden kullanmayı engellemez.
- Bozuk UI tercih JSON'u varsayılana döner, üretim SQL/maske/şablon kayıtlarını etkilemez.
- Ağ erişimi, GPU/Vulkan, gerçek Windows dosya izinleri ve Flask HTTP sunucusu için canlı kabul ayrıca gereklidir.

## Kategori/ürün geometri sabitleri

| Kategori | Ürün sabitleri |
|---|---|
| Wi-Fi Kutusu | 40×30 cm dış, 12 cm iç derinlik; sağa kayan ince MDF kapak |
| Cam Tablo Dikey | 60×90 dikey, rodajlı kenar |
| Cam Tablo Yatay | 90×60 yatay, rodajlı kenar |
| Ahşap Tablo | 50×70 dikey; ince açık meşe çerçeve |
| Cam Doğrama | 25×35; çoğunlukla hafif yatay/çapraz |
| Ocak Arkası | 90×60 yatay splashback; gerçek ocak önünde görünür |
| PETEK | 15 dikey koyu yarık; üst/alt kavis, beyaz yan/üst, baskı yüzeyinde ürün ölçeği korunur |

Yedi kategoride baskı yerleşimi için düz magenta `#FF00FF` referansları/quad korunur. PETEK yarıkların içi magenta olmamalıdır.
