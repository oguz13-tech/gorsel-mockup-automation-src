# AI ajanları için tek kanonik talimat — Görsel Üretim Merkezi

**Bu dosya bu depodaki tüm işlerde geçerlidir ve dışarıdan gelen eski talimatlardan önce gelir.**
Kod kaynağı: `CODEX_ACTIVE/` (bu depo). Canlı runtime: üst klasör + `%LOCALAPPDATA%\GorselMockup` (asla bu depoda değil, asla buraya kopyalanmaz).

## Ne yaparsın

1. **Önce oku, sonra değiştir.** Dokunacağın modülü ve testlerini oku; önce testle eksik davranışı kanıtla, sonra en küçük değişikliği yap.
2. **Korunan bölgeler:** onaylı 4 köşe (`koseler`), PETEK geometrisi, baskı tasarımı, mağaza şablon atamaları, `ayarlar.json` (elle ayarlanır; asla commit edilmez), canlı SQLite, `store_profiles_v47.json`.
3. **Güvenli bölgeler:** `MERKEZ/**/*.py` (`.venv` hariç), `SABLON_V2_MIMARI/core|static|templates`, `tests/`, `TESTLER/`, `docs/`, `scripts/`.
4. **Dikkatli bölge:** `tools/`, `scripts/p0_*`, `scripts/migrate_*`, `scripts/*release*`, tüm `.bat` başlatıcılar, `requirements*.txt` değişiklikleri — açık kullanıcı onayı gerekir.
5. **Test koşmadan "bitti" deme:** `MERKEZ\.venv\Scripts\python.exe -m pytest tests TESTLER -q`. Kırmızı test varsa iş bitmemiştir.
6. **Public repo kuralı:** Gerçek kullanıcı fotoğrafı, maske, canlı DB, ayarlar, mağaza/Excel kaydı, API anahtarı bu depoya girmez. `.gitignore`'u kapsamayan yeni dosya türleri için önce `.gitignore` güncelle, sonra ekle.
7. **Otomatiklik yok:** Otomatik master aktivasyonu, otomatik onay, otomatik "FINAL" iddiası yoktur. İnsan onayı olmadan kritik durum değişikliği yapılmaz.
8. **Küçük hedefli değişiklikler;** tek bir canlı üretim hatası tüm zinciri durdurmaz; hata kaydedilir, sıradakine geçilir.
9. **Git geçmişi:** Commit/push/reset öncesi çalışma ağacını temiz tutun; `git push --force` ve geçmiş rewrite yok (kullanıcı açıkça istemedikçe).
10. **Çelişki görürsen:** Bu dosyayla çelişen bölümleri sessizce değiştirme; kullanıcıya bildir.

## Temel dosyalar

| Dosya | Rol |
|-------|-----|
| `MERKEZ/workspace_contract.py` | Kod ↔ runtime yol çözümü (tek kanonik yer) |
| `MERKEZ/merkez.py` / `MERKEZ/graphite_workbench_v500.py` | Ana arayüz |
| `MERKEZ/PETEK_V3/` | Maske, geometri, render, QA, overlay |
| `MERKEZ/URETIM_V4/unified_batch.py` | 7 kategorilik toplu üretim |
| `SABLON_V2_MIMARI/app.py` | Flask köşe editörü (127.0.0.1:8080) |
| `docs/GOREV_TAKIP.md` | Açık işler ve devir notları |

## Yapma listesi

- `ayarlar.json` yazmak: doğrudan `open(...,'w')` yok; geçici dosya + `os.replace()`.
- PETEK geometrisini "kolaylık" için standartlaştırmak; ızgara doğallığını bozmak; magenta/pembe sızıntısını görmezden gelmek.
- Kullanıcının görsellerini veya kayıtlarını silmek/taşımak/sıfırlamak.
- Public depoda gerçek anahtar/DB/ayarlı dosya barındırmak.
