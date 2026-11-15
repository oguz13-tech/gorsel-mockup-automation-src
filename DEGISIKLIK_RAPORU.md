# Değişiklik raporu — 2026-11-02

## Uygulanan düzeltmeler

1. Normal Windows başlangıcında hiçbir PETEK master revizyonu canlı profile yazılmıyor.
2. Normal arayüz açılışında PETEK klasörleri otomatik oluşturulmuyor; bu işlem açık kullanıcı eylemine bırakıldı. Böylece sürekli yeni klasör oluşması engellendi.
3. Master revizyon aktivasyon aracı `ONAYLIYORUM: PETEK_MASTER_REVISION_AKTIFLESTIR` token’ı olmadan duruyor.
4. Aktivasyon kaynağı için sabit OneDrive yolları kaldırıldı; yalnızca `GORSEL_RUNTIME_ROOT` veya profilin doğrulanmış mevcut kaynağı kullanılacak.
5. Güvenlik kapılarını doğrulayan yeni test dosyası eklendi.

## Korunan mimari kararlar

- V4’ün 10–16 gerçek kaynak yarığı desteği korunuyor; kaynakta olmayan delik/çizgi uydurulmuyor.
- Kaynak/mask/quad SHA kontrolleri ve DRAFT/APPROVED ayrımı korunuyor.
- Preview ve gerçek render aynı PETEK koruma sözleşmesini kullanıyor.
- Ledger resume/recovery ve kaydedilmemiş çıktıyı güvenli tekrar deneme davranışı korunuyor.
- Pembe temizlik QA ve maske dışı piksel koruması kapatılmadı.

