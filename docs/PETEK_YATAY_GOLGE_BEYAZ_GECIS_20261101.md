# PETEK — Yatay pencere gölgeleri / soldan merkeze beyaz geçişi

Kullanıcının 01.11.2026 görsel kabul geri bildirimine göre:
- Önceki dikey pencere gölgeleri yanlış yöndeydi. Yeni ışık örüntüsündeki yatay şeritler ön baskının genişliği boyunca uzanır, hafif perspektif eğimi taşır ve aralıklı bulut lekeleri üretmez.
- Beyaz gradyan soldaki gerçek boyalı beyaz gövdenin tonundan başlar; panelin merkezine yaklaşırken açık, mat beyaza geçer. Dijital #FFFFFF patlaması yoktur.
- Gradyan yalnız düşük doygunluklu, açık tasarım bölgelerine uygulanır. Siyah yazılar, desen renkleri ve delikler aynı koordinatta kalır.
- Magenta kaynak fotoğraf beyaz referans olarak kullanılmaz. Kaynak/maskelerin SHA ve kaydı değişmez.
- Mevcut 13–16 yarık geometrisi ve pembe saçak temizleme katmanı korunur.
- A/B önizleme ile gerçek üretim ortak render motorunu kullanır.

Test: 3 yeni kabul testi + mevcut PETEK regresyonları. Gerçek Windows UAT: WINDOWS_NOT_VERIFIED.

Geri dönüş: Yeni ZIP ayrı boş klasörde kurulmalıdır. Bu adayı kapatıp önceki sürümün başlatıcısını açın; çalışma havuzuna veya orijinal fotoğraflara dokunmayın.
