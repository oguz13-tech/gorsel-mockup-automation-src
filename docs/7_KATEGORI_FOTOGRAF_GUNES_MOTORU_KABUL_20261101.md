# 7 kategori fotoğraf-tabanlı güneş / gerçekçilik — test adayı

**Tarih:** 2026-11-01. **Ana kod tabanı:** `PETEK_2_GOLGE_DUVAR_ON_YUZ_WINDOWS_20261101.zip`. **Yeni tarif:** `SEVEN_CATEGORY_PHOTO_DAYLIGHT_V1_20261101`.

## Tamamlanan yazılım kapsamı

- 7 kategori üretim ekranı, `03 KALİTE` içinde tek seçici: `Kapalı / Doğal / Belirgin`. Arayüzde varsayılan `Belirgin`, ancak üstteki mevcut `Efektler KAPALI` bütün modları kapatır.
- Wi-Fi kutusu, dikey/yatay cam tablo, ahşap tablo, cam doğrama ve ocak arkası: mevcut fotoğraf-tabanlı aydınlık/renk motoru korunur; `Belirgin` seçilince PETEK'te kullanılan **aynı iki yataya yakın, fotoğraf-koordinatlı gölge alanı** ön baskıya uygulanır. Güvenle tespit edilmiş duvar varsa, iki gölge aynı koordinatlarla yan duvarda devam eder.
- Fotoğraf rengi: Baskıdaki açık ve düşük-doygunluklu yüzeylere yalnız gerçek kaynak fotoğraftan ölçülen yakın nötr renk tonuyla küçük uyum. Orijinal magenta kaynak markerı örnek olarak kullanılmaz. Doygun sanat eseri veya siyah yazılar beyaza boyanmaz.
- PETEK: kullanıcı tarafından kabul edilen son çalışan duvar/ön yüz iki gölge, pembe temizleme, dikey 13–16 ızgara geometrisi ve koruma fonksiyonları **dokunulmadan bırakıldı**. Ortak seçici PETEK'te yalnız eski `natural / strong / off` profillerini yönlendirir.
- Cam optiği: var olan cam yansıması ve kenar efektleri kaldırılmadı. Ahşap/MDF renk dokusu da var olan malzeme motoruna dayanıyor. Yeni AI ağırlıkları indirilmez.
- Onaylı özgün fotoğraflar, maskeler, quadrilateral koordinatlar, tasarımlar ve SQLite fiziksel olarak değiştirilmez. Güneş gölgesi yalnız oluşan çıktı kopyasına uygulanır.
- Onaylı maske dışındaki değişiklik, yalnız sınır-bağlı, düşük detaylı, nötr fotoğraf duvar piksellerinde; kesin eşleşen iki-bant karartmasıysa izinlidir. Korunmuş kabin yanları, zemin, gerçek oyuk ve dekor bölgelerinde fark görülürse işlem engellenir. Güvenilir duvar yoksa kullanıcıya `WALL_NOT_CONFIDENT` QA bilgisi verilir.
- A/B butonu artık yedi kategoriyi seçebilir. Kaydedilmiş üretim maske kayıtları A/B'de değiştirilmez.
- Yeni seçim üretim makbuzu/ledger SHA kimliğinde ayrı versiyonludur; mağaza çıktıları için `__GUNES_BELIRGIN` veya `__GUNES_DOGAL` dosya adı ayracı eklenir; eski mağaza çıktısı üzerine yazılmaz.

## Kaynak dosyalar

- **Yeni:** `MERKEZ/URETIM_V4/scene_daylight_vnext.py`
- **Bağlantılar:** `MERKEZ/URETIM_V4/unified_batch.py`, `MERKEZ/URETIM_V4/gui_v4.py`
- **Test:** `tests/test_vnext_seven_category_scene_daylight_20261101.py`
- **İnsan kabulü:** Önce bir şablon ve tek tasarım ile A/B; ardından her kategori için bir gerçek fotoğrafı müşteri gözünden değerlendirme.

## Kontroller / sınırlar

- Bu sürüm **PCT-Net, libcom, SAM2, Depth Anything, IC-Light veya Blender tabanlı 3B ters aydınlatma entegrasyonu değildir**. Bu projeler, modellerin lisansları/hardware/gerçek fotoğraf güvenliği doğrulanmadan otomatik entegre edilmedi.
- İki gölge vardır, ancak mevcut kadrajdan gerçek pencerenin 3B konumu çıkarılmaz. Tahmini gölge alanı fotogerçekçi olmayı garanti etmez.
- Her şablonda duvar algılanacağına veya her sahnede gölge duvarın iki tarafına devam edeceğine dair iddia yoktur.
- Pembe kalıntıların gerçek Windows görsellerinde düzeldiği kullanıcı tarafından onaylandı; yeni sürüm bu başarılı kodları değiştirmiyor.
- `WINDOWS_NOT_VERIFIED`: Linux sentetik/entegrasyon testleri ve ZIP SHA kontrolleri gerçek Windows kabulünün yerine geçmez.

## Test ve geri dönüş

- `PYTHONPATH=.:MERKEZ pytest -q` ile yeni 7-kategori testleri, PETEK iki gölge, PETEK pembe, önizleme uyumu, mağaza ön kontrolleri ve eski kategori render regresyonları koşuldu.
- Teslimde `SHA256_MANIFEST.json` ve 7 kategori doğrulama BAT'i ile yeniden bütünlük denetimi yapılır.
- **Geri dönüş:** ZIP'i yalnız yeni, boş klasöre çıkarın; önceki çalışan sürümü silmeyin. Yeni sürümü kapatıp önceki BAT ile tekrar çalıştırın. Kullanıcı kayıt/maskelerini bu paketle yerinden taşımayın.
