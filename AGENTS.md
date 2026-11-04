# AI AGENT START HERE — 23 EKİM 2026 / V4.2.2

1. İlk okunacak dosya: [`docs/WORK_HANDOFF_CURRENT.md`](docs/WORK_HANDOFF_CURRENT.md), sonra [`docs/NEXT_AGENT_TASK.md`](docs/NEXT_AGENT_TASK.md), [`docs/RELEASE_ACCEPTANCE_MATRIX.md`](docs/RELEASE_ACCEPTANCE_MATRIX.md), [`docs/FINAL_RELEASE_STATUS.md`](docs/FINAL_RELEASE_STATUS.md).
2. Bu GitHub dalı V4.2.2'nin **public-safe kod devri**. Tam 379 dosyalık ZIP ve SHA envanteri ChatGPT Library `/Gorsel-Uretim-Merkezi/V4.2.2/` altındadır; public GitHub'a kişisel fotoğraf/ayarlar/db konmaz.
3. **Asla** insanın onayladığı dört köşe, `ayarlar.db`, `ayarlar.json` `koseler`, PETEK maske, ham orijinal, SKU/Excel/CSV değişikliği veya silme. Kaynak gizli yedek/senkronizasyona karışmasın. `APPROVED` ve eksik çalışma dosyasına karşı fail-closed.
4. Full Windows release sonucu **henüz kabul edilmedi**. Sentetik Linux/Xvfb PASS gerçek Windows GO değildir. Hiçbir issue otomatik kapanmaz, PR merge/force push yapılmaz.
5. Her küçük güvenli değişiklikte sentetik test kanıtı + commit + ilgili issue + draft PR; kota bitmeden HEAD, test, blocker, sonraki tek adımı dokümana işle. Kodu sıfırdan yazma; V4.2.2 modülleriyle devam et.