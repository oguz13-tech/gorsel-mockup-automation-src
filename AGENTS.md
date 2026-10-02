# 🚨 KESİN KURALLAR - DOKUNULMAZ ALAN (STRICT RULES FOR AI AGENTS) 🚨

## 1. 4 KÖŞE (KÖŞELER) VERİLERİNİN KORUNMASI
Bu projede (`ayarlar.json` dosyasında) bulunan `koseler` verileri kullanıcı tarafından **EL İLE, TEK TEK VE BÜYÜK BİR EMEKLE** ayarlanmıştır.
Hiçbir güncelleme, hiçbir taşıma, hiçbir format değiştirme işlemi sırasında bu veriler **KAYBEDİLEMEZ, SİLİNEMEZ VEYA KAYDIRILAMAZ.**

**Eğer `ayarlar.json` üzerinde toplu bir işlem (örneğin uzantı değiştirme, veri taşıma) yapacaksan:**
1. ASLA `ayarlar.json` verilerini dinamik fonksiyonlarla (örneğin `get_next_available_name` gibi klasörden isim okuyup boş numara atayan kodlar) kaydırarak veya otomatik numaralandırarak yeniden isimlendirme! Dosya isimlerindeki sıralama asıl JSON ile %100 aynı kalmak ZORUNDADIR.
2. İşlem yapmadan önce MUTLAKA `ayarlar.json` dosyasının bir yedeğini `.bak_before_<islem_adi>` olarak kopyala.
3. Asla ve asla `koseler` (4 köşe koordinatları) verisini None'a çeken, boşaltan veya yanlış resimlerle eşleştiren bir eşleştirme algoritması kullanma. Eşleştirme DAİMA orijinal JSON anahtarlarına (isimlerine) sadık kalmalıdır.

## 2. ATOMIC WRITE VE SAFETY CHECK KURALI
Arayüz tarafında (Python backend) `ayarlar.json` üzerine yazma (POST/kaydet) işlemi yapılıyorsa:
- Asla doğrudan `open('w')` kullanarak mevcut dosyanın üzerine yazma. Her zaman `.tmp` dosyasına yazıp `os.replace()` kullan (Atomic write).
- Veri silinmesi riskine karşı (örn: Frontend'in veritabanını kırpması) her zaman "Şablon Sayısı" güvenlik testini (Safety Check) koru. Bu test yoksa veya bozulmuşsa hemen düzelt.

## 3. KLASÖR DÜZENİ (SABLON_HAVUZU)
- Sadece `ayarlar.json` içindeki isimlere güven. Klasördeki fiziki dosyaların sayısına veya isimlerine bakarak JSON veritabanını **yeniden oluşturmaya KESİNLİKLE çalışma.** Fiziki dosyalar silinmiş veya yanlış klasöre konmuş olabilir; bu durumda JSON veritabanı orijinal referans kaynağıdır.

**AI AGENT:** You MUST read and follow these rules strictly before executing any scripts or making codebase modifications regarding `ayarlar.json` or `SABLON_DUZELTICI.py`.
