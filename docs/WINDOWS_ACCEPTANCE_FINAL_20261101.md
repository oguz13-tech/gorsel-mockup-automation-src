# Windows kabul raporu — 2026-11-01

## Gerçekleştirilen

- İzole paket kopyası oluşturuldu; canlı SQLite, profiller, maskeler ve
  mağaza kayıtları değiştirilmedi.
- `TESTLER\test_final_integrity.py` ve
  `TESTLER\test_v46_chroma_batch.py`: **11/11 PASS**.
- Python syntax/import smoke checks: **PASS**.
- Dört gerçek PETEK fotoğrafı ve `ts1.jpg` ile gerçek render pilotu: **PASS**.
- Master grid ölçümü: `50fa3951` 16, `79ffa43d` 16, `8fa31037` 16,
  `Gemini` 14 gerçek yarık.
- Dört master overlay bağımsız kaynak-koyu piksel ve izinli maske denetiminden
  geçti. Pembe kalan piksel: dört pilotta **0**.
- Eski procedural `classic` iki uzun yumuşak gölge alanı, `strong` render
  yolunda gerçekten uygulandı. Duvar değişen piksel sayıları sırasıyla
  539523, 173934, 16116 ve 75329 olarak ölçüldü.
- Dört revizyon Registry kopyasında `DRAFT_REVIEW_ONLY` kaldı; canlı aktivasyon
  yapılmadı.

## WINDOWS_NOT_VERIFIED

- GUI'nin fiziksel Windows tıklama kabulü.
- `KURULUM.bat` ile temiz makine kurulum testi.
- `BASLAT.bat` ile uzun süreli GUI oturumu.
- Yedi kategorinin gerçek artwork ile ticari seri üretimi.
- Mağaza linkleri, Excel dışa aktarımı ve tekil hata sonrası devam akışı.
- Canlı Registry revizyon aktivasyonu ve insan görsel onayı.

Bu adımlar çalıştırılmadığı için PASS olarak işaretlenmemiştir.
