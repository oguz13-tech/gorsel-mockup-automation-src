# [24.10.2026] V4.4 — GRUP 1 + 2 + 3 TEK WINDOWS KABUL ADAYI

- **Güncel** GitHub kaynak `feature/v44-group3-release-safety-20261024` / [taslak PR #47](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/47). Zincir: PR #45 (Grup 1) → PR #46 (Grup 2) → PR #47 (Grup 3). Main auto merge YOK.
- **Tek ZIP adayı** `GORSEL_URETIM_MERKEZI_V44_GRUP1_GRUP2_GRUP3_TEK_WINDOWS_KABUL_ADAYI.zip`: 402 üye, SHA-256 `5a66367c3fa8f024ee7ad40334793b1f356b0702f34447951d4a921370e0c9b3`, CRC/extract PASS; özel ChatGPT Library `/Gorsel-Uretim-Merkezi/V4.4-G3/`. İçinde 401 dosyalık SHA manifesti. Bu gerçek Windows GO değil.
- G3 yeni kod: salt-okunur `final_guard_v44.py` ve GUI iki buton; SQLite `ayarlar.db` + `v4_ortak_uretim.sqlite3` WAL online backup/izole restore prova, manifest SHA. Sıfır otomatik canlı DB migration. G3 Windows tek-tık read-only BAT.
- Lokal **193 PASS / 2 SKIP**, temiz ZIP çıkarımında **31 G1/G2/G3 odaklı PASS**; 1000 sentetik ledger receipt/SHA/idempotence, iki kesinti karantina ve OS kilit testi. Bunlar **1000 gerçek fotoğraf render** değildir. CI son durumu Actions'tan doğrula.
- Açık: 100/200/1000 gerçek görüntü batch, iki gerçek Windows kill/restart ve çift süreç, live OneDrive iki DB backup/restore, dosya/Excel/SKU ticari mapping, PETEK 34+ Golden ve gerçek cam A/B, ImgBB/FreeImage HTTPS Excel, 4K Vulkan model/exe, offline wheel, approved 4 köşe reapproval, eksik PNG/WebP. Bunlar #35 gerçek kabul kapısını BLOKlar.
- **Oku:** `docs/THREE_GROUP_103_TASK_PLAN.md` → `docs/V44_GRUP2_41_ITEM_STATUS.md` → `docs/V44_GRUP3_19_GOREV_DURUMU.md` → `docs/V44_BIRLESIK_WINDOWS_KURULUM_VE_GERI_DONUS.md` → `docs/V44_GRUP3_DEVIR_GITHUB.md`.

---

# [GÜNCEL 2026-10-23] V4.4 ÜÇ GRUP KONTROL NOKTASI — ÖNCE BUNU OKU

- **103 görevün tamamı** `docs/THREE_GROUP_103_TASK_PLAN.md`: Grup 1 maddeler 1–40,101–103 (43); Grup 2 41–75,95–100 (41); Grup 3 76–94 (19).
- **Aktif:** Grup 1; taslak [PR #45](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/45), branch `feature/v44-group1-ui-upscale-20261023`. Grup 2 [#43](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/43) ve Grup 3 [#44](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/44) *sırada*, tamamlandı değiller.
- G1 kod checkpoint: ana merkez tek 7 kategori üretim, eski 10 şablon GUI shortcut kaldırıldı, bakım araçları gizlenebilir alanda; isteğe bağlı Real-ESRGAN-NCNN 4K 2880×3840 ayrı SHA korumalı çıktı + yerel Excel; katı salt-okunur SHA denetimi. Gerçek `.exe`/model dosyaları ZIP'e dahil değil; kullanıcı güvenli şekilde temin etmeli.
- Yerel **107 seçili regresyon PASS**; ayrıca GitHub Windows/Linux G1 test workflow'su eklenmiştir, anlık CI sonucunu GitHub Actions'tan doğrula. Sentetik ≠ gerçek kullanıcı kabulü.
- Grup 1 **PENDING**: gerçek cam A/B (4 cam kategori), HTTPS ImgBB/FreeImage ağ + Excel tıklama, canlı DB approved köşe revizyon testi, 415MP PNG/WebP stratejisi, Real-ESRGAN gerçek GPU ve 4K A/B, ticari Excel SEO/mağaza sütunları.
- G2 **PENDING**: eski araçlar/şablon tarama/SAM denemeleri/PETEK maske ve Golden Dataset. G3 **PENDING**: 1000 iş, 2x crash, SQLite backup/restore, iki process, 8080, factory doctor, Windows rollback, tek final ZIP. `main` değiştirme; PR auto merge yapma.
- Grup 1 test/checkpoint paketi **final değildir**. 386 dosya, SHA256 `61cb1f434cc7937c6c72814da2cb8d0b7e869ead735fb7344c630f922cea9de6` ve özel Library `/Gorsel-Uretim-Merkezi/V4.4-G1/`. Eski kullanıcı V4.2.2/V4.3 ve onaylı `ayarlar.db`, orijinal fotoğraflar, maskeler korunuyor.
- G1 kabul bitince G2'ye, G2 kabul bitince G3'e geç; final GO yalnız #35 gerçek Windows kabulüyle.

---

# SONRAKİ AJAN — BAŞLANGIÇ TALİMATI / KOTA SONRASI SIFIR KAYIP

1. Önce `docs/WORK_HANDOFF_CURRENT.md` ve `docs/RELEASE_ACCEPTANCE_MATRIX.md` dosyalarını tamamen oku. Ana görev GitHub **issue #36**; test kabul **#35**. Son güncel kaynak dalı `handoff/v422-complete-20261023`, **main değil**.
2. GitHub dalında `MERKEZ/`, `SABLON_V2_MIMARI/`, `TESTLER/`, `tests/`, `BAGIMSIZ_ARACLAR/`, `99_SISTEM_MOTORLARI_VE_KODLAR/`, `LEGACY_REFERANS_KOD/` ve `scripts/` içeriklerini tara. Public dalda eksik olan orijinal tarihî/JSON/ayarlar/manuel geometri kayıtlarını doldurmak için **sıfırdan oluşturma**.
3. ChatGPT Library `/Gorsel-Uretim-Merkezi/V4.2.2/` altında şu özel kaynaklar saklıdır:
   - `GORSEL_URETIM_MERKEZI_V422_GRUP1_GRUP2_FACTORY_DOCTOR_GUVENLI_FINAL_WINDOWS.zip` (379 dosya; SHA256 `ad33e3219c5e2c6e1f6185a2b726730276eb9e2386abd6a78d49b97df566f7ee`).
   - `V422_FULL_PACKAGE_FILE_MANIFEST.csv`, `.json` (tam dosya bazlı hash).
   Bunları Library üzerinden materialize edip ZIP hash / üye envanteri doğrula. **Public repo'ya ZIP'in kendisini push etme**; içinde `ayarlar.json` ve benzeri tarihî ayarlar/referans veri olabilir.
4. Önce `git status --short`, HEAD SHA, PR base/head, dalın source kapsamı, git diff, kontrollü çalışacak test komutlarını kayda geçir. Kodları ilk etapta kullanıcı Windows'una yazma. Kod değişikliği yaparsan küçük, bağımsız commit + draft PR + ilgili issue kayıtlarıyla ilerle.
5. Çalıştırılabilir ilk kalite kapıları (yalnız izolasyon / sentetik geçici dizinlerde): `python -m compileall -q MERKEZ SABLON_V2_MIMARI TESTLER tests`; ardından ayrı pytest/unittest/Xvfb grupları. Varsayarak PASS yazma. Flask HTTP, Windows Tk, Excel hyperlink ve GPU davranışını gerçek sistemde ayrıca test et.
6. **Production değişiklik yasakları:** Live `ayarlar.db`, WAL/SHM, JSON `koseler`, APPROVED geometri, PETEK onaylı maskesi, ham orijinal arşiv, eski SKU/Excel/CSV, müşteri görselleri, kullanıcı dosya isimleri ve `.venv` otomatik silinemez/yer değiştirilemez. No `git push --force`, no auto merge, no destructive reset/clean, no public user data.
7. İlk Windows kabul sırası: (a) kullanıcıdan kaydedilmemiş dört köşe işini bitirdiği teyidi, (b) **ayrı klasöre** V4.2.2 açılışı, (c) yeni program eski 8080'le eşzamanlı değil, (d) 1 güvenli örnek içeri alma/numara, (e) tek 4 köşe/onay, (f) 7 kategoriden örnek render, (g) PETEK maske ve gerçek Excel hyperlink, (h) create-only/restore/no overwrite, (i) backup+rollback, (j) yüksek hacimli crash-resume.
8. Açık uyarılar: Python 3.11 expected / 3.14 current, NumPy 2.4.6 / 2.5.4, Torch 2.5.1+cu121 baseline / None, transformers 5.17.0 / None, CUDA 12.1 / None; OneDrive SQLite sync ve master aspect bleed. Factory Doctor bunları Türkçe açıklar; **uyarı kapansın diye lock, GPU baseline veya SQLite taşımaya girişme**.
9. Kullanıcı 7 kategori isimlendirici son kullanılan numara; Ocak Arkası `WORKING_PNG_NOT_FOUND_OR_UNSAFE` düzeltmesi ve arayüz gözle kabulünü özellikle istedi. Ayrı test et.
10. Her kota sonunda dosya bazında `tamam/eksik/kanıt`, branch HEAD, draft PR linki, exact test commands/result, source archive SHA, blocked Windows kullanıcı adımları ve sonraki tek komut `docs/NEXT_AGENT_TASK.md` içinde güncel kalmalı.

**İlk yeni ajanın görevi:** Kod üretmek yerine önce `handoff/v422-complete-20261023` ile **kanonik ZIP** arasındaki 379-dosya farkını ve branch CI durumunu doğrula; sonra 7 kategorili Windows gerçek kabul için güvenli bir kontrol listesi hazırla. Sahte tamamlandı/GO bildirimi verme.