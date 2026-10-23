# V4.4 G3 — Kota sonrası tam devir, 24 Ekim 2026

## Başlangıç

- Grup 1 kaynak: PR #45, Grup 2: PR #46, Grup 3: branch `feature/v44-group3-release-safety-20261024` (yeni DRAFT PR eklenecek).
- Son birleşik kabul adayı: `GORSEL_URETIM_MERKEZI_V44_GRUP1_GRUP2_GRUP3_TEK_WINDOWS_KABUL_ADAYI.zip`, SHA-256 değeri ZIP dışındaki `V44_3GRUP_SHA256.txt` dosyasında, **402 dosya** (401 + iç manifest), ZIP CRC/extraction PASS.
- Değişen kaynaklar: `MERKEZ/URETIM_V4/final_guard_v44.py`, `MERKEZ/G3_GUVENLIK_KONTROLU.py`, `MERKEZ/merkez.py`, `MERKEZ/URETIM_V4/gui_v4.py`, iki Windows BAT, `TESTLER/test_v44_group3_release_safety.py`, `.github/workflows/v44-group3-gate.yml`, `docs/*` durum/release belgeleri. Grup 1/2 önceki üretim motorları korunur.
- Yeni G3 modülünde: salt-okunur iki-DB schema/quick_check, 7 kategori output root/SHA; açık onaylı WAL-aware online SQLite backup/iki DB, restore copy doğrulaması, manifest SHA, bulut klasörüne yedek engeli, orijinal DB'ye yazmama.
- `docs/V44_GRUP3_19_GOREV_DURUMU.md` 076–094'ü satır satır açık kod/sentetik/Windows ayrımıyla işaretler.

## Tamamlanan test

- İzole Linux+Xvfb tam suite: **193 PASS / 2 SKIP**.
- Temiz ZIP extraction: Python compileall PASS, yeni G1+G2+G3 odaklı **31 PASS**.
- G3 testleri: WAL içeren SQLite backup, izole restore, SHA bozulma tespiti, iki-process O_EXCL, 1000 sentetik ledger artifact (gerçek image render DEĞİL), iki sentetik kesinti ve karantina.
- GitHub Windows+Ubuntu G3 CI son durumunu PR Checks'ten doğrula; burada henüz gerçek kullanıcı Windows testi yapılmadı.

## Kritik açıklar / kesinlikle final GO DEĞİL

1. Kullanıcının canlı Windows / OneDrive `ayarlar.db`'si bu ortamdan açılmadı, DB backup/restore ve 7 kategori 1000 gerçek render testi yapılmadı.
2. Real-ESRGAN Vulkan `.exe`/model zip'e dahil değil, GPU gerçek test yok; ImgBB/FreeImage gerçek HTTPS Excel linki de anahtarsız test edilmedi.
3. 34+ PETEK Golden fotoğraf QA, hatalı Wi-Fi 26–35/44/57–66, Cam Doğrama occlusion, Cam gerçek A/B ve approved 4 köşe yeni üretim Windows kabulü bekliyor.
4. Tam pause/resume, offline dependency wheels, kilitli production Python/env, OneDrive dışına canlı onaylı SQLite kontrollü migration çözümü uygulanmadı.
5. GitHub `main` merge yok; gerçek kullanıcı DB/görüntüler yüklenmemeli. Kontrol ZIP'i bile gerçek Windows testini geçmeden üretim GO diye adlandırılmamalı.

## Bir sonraki ajanın ilk adımları

- GitHub PR #45 → #46 → G3 PR, `docs/THREE_GROUP_103_TASK_PLAN.md`, `docs/V44_GRUP2_41_ITEM_STATUS.md`, `docs/V44_GRUP3_19_GOREV_DURUMU.md` ve `docs/V44_BIRLESIK_WINDOWS_KURULUM_VE_GERI_DONUS.md` oku.
- ZIP SHA-256 ve `MANIFEST_V44_3GRUP_SHA256.json` doğrula; eski canlı 4 köşe DB/profillerin tümünün yedeğini almak için kullanıcıdan GUI'deki onayı bekle.
- Windows'ta ekran 4.4, 7 kategori, G3 iki tuşu, HTTPS Excel, gerçek GPU 4K, A/B cam, mevcut onaylı köşe ve 100/1000 job audit testlerini kullanıcıyla kontrol et.
- G3'nin tüm QA satırları PASS olmadan issue #35 kapanmaz, PR merge ya da final GO yapılmaz.
