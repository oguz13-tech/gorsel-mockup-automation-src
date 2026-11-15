# CODEX_ACTIVE dosya envanteri — 2026-11-02

## Kaynak ve çalışma modeli

- Aktif kaynak: `C:\GorselUretimMerkezi\CODEX_ACTIVE`
- Taban: önceki kanıtlı V4 PETEK adayı (`den\work\package`); başlangıç paketindeki V4 taban ve seçmeli V3 güvenlik mimarisi karşılaştırması referans alındı.
- Canlı klasörler: `%USERPROFILE%\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu` ve `%LOCALAPPDATA%\GorselMockup` okunmadı/yazılmadı.
- `ayarlar.json`, `koseler`, canlı SQLite, maske/profil ve üretim kayıtları bu çalışmada değiştirilmedi.
- Yerel Git snapshot: `baeed93` (`codex: secure isolated Windows candidate startup`).

## Ana bileşenler

| Alan | Sorumluluk |
|---|---|
| `MERKEZ/PETEK_V3` | PETEK maske, kaynak-geometri, görsel render ve QA |
| `MERKEZ/URETIM_V4` | yedi kategori batch, ledger, resume/recovery, Excel/mağaza |
| `MERKEZ/merkez.py` | koyu temalı ana Windows arayüzü |
| `SABLON_V2_MIMARI` | eski/legacy şablon ve dört köşe altyapısı |
| `PETEK_MASTER_REVISIONS` | yalnız inceleme/draft kaynakları; canlı aktive edilmez |
| `TESTLER`, `tests` | regresyon ve güvenlik testleri |
| `tools` | açık onay gerektiren bakım/onarım araçları |

## P0/P1 değişiklik alanları

- `MERKEZ/BASLAT.bat`: otomatik `install_petek_master_revisions.py` çağrısı kaldırıldı.
- `MERKEZ/merkez.py`: başlangıçta PETEK klasörlerini otomatik oluşturma kaldırıldı; kullanıcı tarafından görünür araç üzerinden yapılır.
- `tools/install_petek_master_revisions.py`: açık insan onayı token’ı zorunlu; `GORSEL_RUNTIME_ROOT` ile taşınabilir kaynak araması; OneDrive sabit yolu kaldırıldı.
- `TESTLER/test_codex_active_safety.py`: bu üç güvenlik kapısı için yeni testler.

## Bilerek değiştirilmemiş alanlar

- `PETEK_MASTER_REVISIONS` içindeki profiller/maskeler.
- Canlı kullanıcı verisi, dört köşe, maske, SQLite, Excel ve output klasörleri.
- Deneysel efektler ve otomatik master aktivasyonu.
- Windows GUI, Excel, GPU/4K ve gerçek canlı üretim durumu.

