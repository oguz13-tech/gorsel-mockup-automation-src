# PETEK — magenta saçak, gradyan ve kesintisiz uzun gölgeler

Bu aday sürüm, önizleme açılan son çalışır 409 sürümü üzerine hazırlanmıştır.
Dikey yarık sayısı ve fiziksel eksen algoritmalarına **dokunulmadı**.

## Sızıntı
- Baskı maskesinin içinde alfa kaynaklı mor/pembe geri karışım engeli korunur.
- Maske dışında yalnız orijinal fotoğrafta bulunan, gerçek magenta işaretinin
  14 piksel yakınındaki ince, doğrulanmış saçakları anlık çıktıda onarır.
- Tüm korunan siyah yarıklar, kavis, beyaz dolap, zemin vb. değişmemiş kalır.
- Maske veya orijinal fotoğrafın üzerine yazılmaz.
- Geniş/belirsiz magenta lekelerde fail closed kalır, körlemesine boyamaz.

## Efekt
- Gerçek fotoğraftan kalibre edilen beyaz + tek yönde kademeli aydınlık gradyanı.
- Mat yüzeyde 3 adet kesintisiz uzun, yumuşak pencere gölgesi.
- Belirgin modda çok hafif stokastik MDF mürekkep mikro dokusu.
- İkinci gölge motorunun yüze leke eklemesi PETEK için kaldırıldı.
- A/B önizleme/üretim ortak görsel motorunu kullanmaya devam eder.

## Durum
- Linux sentetik testleri Windows canlı kabulü değildir.
- Orijinal fotoğraflar, maske kayıtları, dört köşeler, SQLite, mağaza atamaları değişmedi.
- Kod/veri yedeklerini silmeyin, paketi ayrı klasöre açın.
