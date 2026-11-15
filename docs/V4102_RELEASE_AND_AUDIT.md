# V4.10.2 — kaynak değişikliği ve performans denetimi

## Canlı kullanıcı sorunu
PETEK maskesi onaylanırken şablon havuzu 127+ fotoğraf içeriyorsa ekran işlem
sonunda bekliyordu. Bir başka kullanıcı isteği ise modern SaaS benzeri antrasit,
sekme/kart görünümünde, hover/disabled durumlarında okunabilir arayüzdür.

## Neden ve çözüm (kaynak)
- `SABLON_V2_MIMARI/static/js/petek_editor_v477.js` / `approve()`:
  Eskiden başarılı `/api/petek/approve` sonrası `await reload(s.uid)` tüm
  `/api/petek/templates` havuzunu (fotoğraf/maskelerin SHA ve QA denetimleri)
  yeniden tarıyor ve seçili fotoğrafın tam boyutunu tekrar yüklüyordu.
  Artık yalnızca **sunucudan başarı cevabı geldikten sonra** ilgili şablonun
  durumu, listede etiketi ve onay butonları yerel DOM'da güncellenir.
  `Listeyi Yenile` halen tam doğrulamayı manuel yapar.
- `SABLON_V2_MIMARI/core/petek_web_v477.py` / `approve()`:
  Onay öncesi fotoğraf dekodunu ve tüm profil listesini gezme kaldırıldı.
  Açıkça verilen UID regex, kaynak dosya yolu, güncel kaynak SHA ve onay SHA
  karşılaştırmaları korunur. `Registry.approve` yine **gerçek maske QA**, SHA,
  source/quad eşleşmesi ve insan onayı şartlarını denetler.
  Sunucu gecikmesi `approval_server_ms` olarak döner ve günlüklenir.
- `MERKEZ/PETEK_V3/registry.py` / `get()`:
  Fotoğrafı ölçü ve QA için iki defa değil, bir defa decode eder.
  Asıl fotoğraf ve maske hashleri her onayda yeniden doğrulanır.
- `static/css/v4102_ui_system.css`:
  Kullanıcının verdiği antrasit dashboard referanslarının görünüm ilkeleri;
  renk/kontrast/okunaklı metin ve klavye focus'u. Yalnız CSS, motora dokunmaz.

## Test durumu
- Saf Registry + JS regresyon: sentetik kaynak, gerçek maske, source-tamper,
  mask immutability, tek decode ve listede taramasız güncelleme.
- Seçili tarihsel testlerde Flask gerektiren HTTP testi mevcut ortamda yok;
  `WINDOWS_NOT_VERIFIED`. Flask API davranışı gerçek Windows'ta ayrıca ölçülmeli.
- Tam sistem genelinde gerçek 1000+ üretim ve mağaza XLSX son kabulü önceki
  #72 görevinde açık; bu sürüm onları tamamladığını iddia etmez.

## Yüksek riskli değişiklikler için korunacaklar
- PETEK 15 koyu ızgara / Orta yoğunluk / pembe temizliği motorlarına DOKUNULMADI.
- Onaylı profil/maskeler immutable, yeni revizyon ayrı ve eskiye dönülebilir.
- Çalışma klasörü, SQLite, mağaza kayıtları, OneDrive orijinal arşivler dağıtıma
  dahil değildir ve güncellenmez.
- Konsol ölçüleri `approval_server_ms` ve tarayıcıda saniye raporu; gerçek
  cihazda 5 farklı fotoğrafla karşılaştırılmalı. Hız için HASH atlanmaz.

## Kod haritası
- `MERKEZ/version_v47.py`, `MERKEZ/premium_dashboard_v489.py`: sürüm metni
- `MERKEZ/personal_hub_v493.py`: yeni test-kabul kartları
- `SABLON_V2_MIMARI/templates/index.html`, `static/css/v4102_ui_system.css`:
  modern antrasit inceleme bileşenleri
- `SABLON_V2_MIMARI/templates/tools.html`: araçlar sayfası
- `MERKEZ/PETEK_V3/registry.py`: güvenli imzalı kayıt katmanı
- `SABLON_V2_MIMARI/core/petek_web_v477.py`: Flask PETEK HTTP API
- `SABLON_V2_MIMARI/static/js/petek_editor_v477.js`: web onay ekranı

## Geliştiriciye devretme
Önce `README.md`, `docs/V4101_ARCHITECTURE.md`,
`docs/V4101_SOURCE_FILE_INDEX.md`, `docs/V4101_CHANGELOG_AND_GAPS.md` ve
`docs/V4102_RELEASE_AND_AUDIT.md` dosyalarını oku. Sonra
`python -m pytest -q` ile seçili testleri çalıştır, Flask HTTP akışını Windows
üzerinde gerçek kullanıcı verisine yazmadan izole test et. Yalnızca
**insan onaylı** maskeleri üretime al. GitHub #72 açık kabul matrisidir.
