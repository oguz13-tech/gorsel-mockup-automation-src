"""V4.9.4 user-owned notes, tasks and versioned acceptance checks.

The database is always outside the distributed code and production workspace.
NO auto-approval, deletion, mask manipulation, network access or background work.
"""
from __future__ import annotations
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

DB_NAME = 'personel_merkez_v493.sqlite3'
CURRENT_VERSION = 'V4.10.2'

# Stable IDs: adding a new release never re-opens a completed item unless ID changes.
ACCEPTANCE = [
('V4102-PETEK-APPROVAL-LATENCY','PETEK maske onayı: tam liste taraması olmadan hızlı geri bildirim','Kritik',
 '1. PETEK açıkken yüzlerce şablon içinden TASLAK maskeli bir örnek seç.\n'
 '2. Son maske kontrolünden sonra onay kutusu ve “Maskeyi İnsan Onayıyla Kilitle” düğmesine bas.\n'
 '3. Tek şablonun onayı bitince aynı fotoğraf ve maske ekranda kalmalı, tüm 127+ fotoğraf tekrar yüklenmemeli.\n'
 '4. Ekranda saniye bilgisi ve ONAYLI durumu görülmeli; Listeyi Yenile düğmesine basınca kaynak/maske SHA tekrar doğrulanmalı.\n'
 '5. Başka fotoğrafın UID veya kaynak SHA değişikliğiyle onay yapılamadığını doğrula.',
 'Onaydan sonra yalnızca ilgili şablonun durumu güncellenir; SHA/maske güvenlik kapıları korunur. İşlem süresi canlı Windows üzerinde ölçülür.',
 'Onaydan önce ve sonra ekran görüntüsü, geçen süre, varsa hata ve üretim dosyalarının sağlamlığını paylaş.'),
('V4102-MODERN-ANTHRACITE-UI','Şablon İnceleme / Araçlar: modern antrasit kart, hover ve okunurluk','Arayüz',
 '1. Şablon İnceleme ve Profesyonel Araçlar ekranlarını aç.\n'
 '2. Sol menü, sekmeler, kartlar, PETEK kompakt ve fotoğraflı listeyi kontrol et.\n'
 '3. Yeni mavi, Onaylı yeşil, Taslak sarı, Hatalı kırmızı renkleri bozulmamalı.\n'
 '4. Fare ile hover, devre dışı kontrol ve klavye TAB odağı okunabilir olmalı.\n'
 '5. Başka kategorilerdeki dört köşe ve toplu seçim işlevleri eskisi gibi çalışmalı.',
 'Arayüzde kontrastlı antrasit renk ve tutarlı butonlar görünür; veri veya maskeye yan etki yok.',
 'Ekran görüntüleri, düşük çözünürlük sorunları ve bozuk metinleri paylaş.'),
('V4101-PETEK-BULK-VISIBLE-NAMES','PETEK toplu seçimde adlar, kompakt liste ve tiksiz tek onay','Kritik',
 '1. PETEK listesini aç ve Toplu Seçim modunu etkinleştir.\n2. Sarı taslak, yeşil onaylı, mavi yeni ve kırmızı hatalı dosya adlarını doğrula.\n3. Her bir dosya adının yanında seçim kutusu normal boyutta kalmalı.\n4. Hiçbir satıra tik koymadan tüm uygun taslakları TEK ONAYLA.\n5. Eski 8-li tekrar onay penceresi açılmamalı.',
 'Dosya adları kaybolmaz; bir onay tüm görünür uygun maskeleri güvenli olarak sunucuda doğrular; yanlışlar taslak kalır.',
 'Toplu Seçim ekranı, sonuç raporu ve maskeli kayıt adlarını paylaş.'),
('V4101-ALL-SEVEN-STATUS-UI','7 kategoride aynı Yeni/Onaylı/Taslak/Hatalı filtre ve antrasit liste','Arayüz',
 '1. Her yedi kategoride arama ve durum filtresini dene.\n2. Yeni mavi, Onaylı yeşil, Taslak sarı, Hatalı kırmızı görünmeli.\n3. Filtre kapatıp açmak kaydı etkilememeli.\n4. Açık liste ok tuşları kendi kategorisinde kalmalı.',
 'Aynı durum renkleri ve okunaklı dosya adı; seçime/üretime gizli yan etki yok.',
 'Yedi kategori liste ekranını ve varsa uyuşmazlıkları paylaş.'),
('V4101-LIVE-CARD-DRAG-AND-PALETTE','Ana ekranda Kartları Taşı ve ayrı renk seçicileri','Arayüz',
 '1. Ana Sayfada Kartları Taşı modunu aç.\n2. Tutamaçtan bir kartı başka kart üzerine sürükleyip bırak.\n3. Programı kapatıp aç; sıra aynı kalmalı.\n4. Arayüzü Düzenle içinde kart/düğme/zemin/başlık rengini seç.\n5. Geri Al ve Varsayılana Dön dene; üretim düğmeleri normal modda çalışmalı.',
 'Yalnız görünüm JSON kaydı değişir; PETEK/SQLite/üretim verisi dokunulmaz.',
 'Önce/sonra düzen ve yeniden açılmış görünüm ekranlarını paylaş.'),
('V4101-HELPFUL-ERROR-POPUPS','Hata nedeni ve çözüm pop-up; PETEK eksik maske adımı','Arayüz',
 '1. Onaysız yeni PETEK üzerinde otomatik maske taslağı olmadan Önizle dene.\n2. Açılan uyarı nedeni ve ilgili butona git eylemi içermeli.\n3. 4K bulunamadı / Excel kilitli gibi hata durumlarında açıklamalı mesaj gör.\n4. Seri işleme tekil hata için her dosyada modal pencere açmamalı.',
 'Hata ile yapılacak işlem anlaşılır; toplu üretim modal yağmuruyla durmaz.',
 'Uyarı ekranını ve hata sebebi/çözüm adımını paylaş.'),

('STORE-ASSIGN-EXPLICIT-V4100','Mağaza→Kategori→Mockup güvenli atama ve tekrar kullanım kontrolü','Kritik',
 '1. Seri Üretim > Mağaza Profilleri / Şablon Atama aç.\n'
 '2. Mağaza A seç; sonra Wi-Fi kategorisi seç. Kayıtlar önizleme fotoğraflarıyla listelensin.\n'
 '3. Yalnız 2 uygun mockup işaretle. Atama önizlemesinde tam 2 dosya adı ve doğru mağaza görünsün.\n'
 '4. Onayla ve A mağazasındaki atamaları sağ tarafta kontrol et.\n'
 '5. Mağaza B seç: A mağazasındaki 2 mockup kırmızı Kullanılamaz/Mağaza A olarak görünmeli.\n'
 '6. B mağazasına farklı 2 mockup ata. Aynı HAM baskı tasarımını iki mağazada farklı mockuplara uygula.\n'
 '7. Her iki mağaza XLSX/ürün kodu/üretim çıktısını ayrı kontrol et; hiçbir atama otomatik seçilmemeli.',
 'Sadece mağaza ekranında işaretlenen mockuplar atanır; aynı baskı tasarımı mağazalar arasında yeniden kullanılabilir, aynı kaynak mockup fotoğrafı başka mağazaya atanamaz; eski atamalar kaybolmaz.',
 'Mağaza A/B eşleştirme ekranları, atanmış sayılar ve farklı mockuplarla aynı tasarımın örnek çıktılarını sohbete gönder.'),
('PETEK-BULK-APPROVAL-V498','PETEK tüm taslakları tek onayla; tik/sekizli onay zorunlu değil','PETEK',
 '1. Şablon İnceleme > PETEK aç.\n2. PETEK Toplu Seçim bölümünü aç.\n'
 '3. Yeni/Taslak filtrelerini ihtiyaca göre seç; dosyaları tek tek işaretleme.\n'
 '4. “GÖRÜNEN TÜM TASLAKLARI TEK ONAYLA KİLİTLE” düğmesine bas.\n'
 '5. Yalnız bir kez çıkan toplu onay sorusunu onayla.\n'
 '6. Sonuçta onaylananları ve sorun nedeniyle TASLAK kalanları kontrol et.\n'
 '7. Onaylı eski maskelerin ve gerçek şablon dosyalarının değişmediğini doğrula.',
 'Tüm uygun taslaklar kullanıcıyı sekizli turla durdurmadan onaylanır; her maskenin kaynak SHA/UID/QA kontrolü ayrı yapılır. Başarısızlar taslak kalır.',
 'Toplu sonuç raporunu ve onaylı/taslak listesi ekranını sohbete gönder.'),
('PETEK-EDIT-APPROVED-V499','Onaylı PETEK maskesini yeniden düzenle / 4 köşe / geri dönüş','PETEK',
 '1. Önceden ONAYLI bir PETEK şablonu seç.\n'
 '2. “Onaylı Maskeyi Yeniden Düzenle / 4 Köşe” düğmesine bas.\n'
 '3. Açılan yeni TASLAK revizyonunda köşeleri değiştir, otomatik maskeyi yeniden üret, gerekirse Ahşap Boyasını Sil fırçasını kullan.\n'
 '4. Taslak Kaydet, ardından insan onayı ver.\n'
 '5. Yeni revizyonun güncel onaylı olarak seçildiğini ve eski maskenin korunduğunu kontrol et.\n'
 '6. Önceki Onaylı Sürüme Dön düğmesini dene.',
 'Eski onaylı maske ve kaynak fotoğrafın SHA değeri değişmez; yeni revizyon gelecek üretimler için etkinleşir, geri dönüş mümkündür.',
 'İlk/son revizyon UID, onay sonucu ve geri dönüş ekranını sohbete gönder.'),
('PETEK-LIST-KEYBOARD-V499','PETEK listesi ok tuşları / toplu seçimde dosya adları','Arayüz',
 '1. PETEK açıkken ok tuşlarına bas; Wifi şablonlarının değişmediğini kontrol et.\n'
 '2. PETEK Toplu Seçim aç; dosya adları ve kutuların aynı satırda göründüğünü doğrula.\n'
 '3. Durum filtrelerinden Yeni/Mavi, Taslak/Sarı, Onaylı/Yeşil, Hatalı/Kırmızı seçili durumları dene.\n'
 '4. Ahşap Boyasını Sil ile yalnız taslaktaki yeşil işaretleri geri al; orijinal fotoğraf değişmesin.',
 'Aktif kategori doğru klavye olayını kullanır; seçici 100% genişleyip dosya adını gizlemez; tüm durum renkleri okunur.',
 'Toplu seçim açık listeyi, varsa yanlış şablon hareketini ve silgi kullanımını gösteren ekranları gönder.'),
('PETEK-LIST-V498','PETEK kompakt şablon listesi ve fotoğraflı seçenek','Arayüz',
 '1. PETEK bölümünü aç.\n2. Sol listeyi satır satır incele.\n3. Kompakt Liste düğmesi ile fotoğraflı görünüme geç.\n4. Seçim ve durum renkleri korunuyor mu kontrol et.',
 'Satır yüksekliği, kaydırma, renkli durumlar, dosya adları ve PETEK Toplu Seçim normal çalışır.',
 'Liste ekran görüntüsü ve varsa eksik şablon adlarını gönder.'),
('LAYOUT-TABS-V498','Arayüzü Düzenle: sekmeler, kart sıralama ve renk/efekt kaydı','Arayüz',
 '1. Ana Sayfa > Arayüzü Düzenle aç.\n2. Yeni sekme aç, kart sürükleyip sırala, kartı başka sekmeye taşı.\n'
 '3. Renk ve Efekt seç, Kaydet.\n4. Programı kapatıp aç ve düzeni kontrol et.\n5. Varsayılana Dön ve Geri Al işlevlerini dene.',
 'Yalnız kullanıcı görünümü değişir; üretim, PETEK maskeleri, şablon onayı ve SQLite değişmez.',
 'Önce/sonra ana ekran ve sekmelerin ekran görüntülerini gönder.'),
('4K-CHECK-V498','4K Kurulumunu Kontrol Et — ayrı durum düğmesi','4K',
 '1. Seri Üretim > 4K Kurulumunu Kontrol Et düğmesine bas.\n2. Mevcut kurulu modelin yolunu ve hazır durumunu kontrol et.\n'
 '3. Bu tıklamayla modelin yeniden indirilmediğini ve 4K işaretinin değişmediğini doğrula.',
 'Kontrol yalnızca durum gösterir; üretime başlamaz, kurulum/indirme başlatmaz.',
 'Düğmenin sonuç penceresini sohbete gönder.'),
('PETEK-MASK-HELP-V498','Otomatik Maske Taslağı unutulursa açıklamalı uyarı','PETEK',
 '1. Onaysız yeni şablonda dört köşe önerisini hazırla.\n2. Otomatik Maske Taslağına basmadan Önizle.\n'
 '3. Uyarıda doğrudan eksik 2. adımı göstermesini kontrol et.',
 'Yanıltıcı %0.0 baskı alanı mesajı yerine maske taslağını oluşturma talimatı çıkar.',
 'Uyarının ekran görüntüsünü gönder.'),
('MULTI-WINDOW-V495','Ana ekran + Seri Üretim + Şablon İnceleme aynı anda','Performans',
 '1. Ana sayfada Şablonları İncele aç.\n2. Sayfa açıkken Seri Üretim aç.\n3. Hem ana ekranı hem üretim penceresini hem tarayıcıyı sırayla tıkla.\n4. Birini kapatmadan ötekine geç ve geri dön.\n5. Üretimi başlatmadan, onaylı şablon listesini kontrol et.',
 'Hiçbir pencere diğerini kilitlemiyor; çift tıklama ikinci üretim motoru başlatmıyor; onaylar değişmiyor.',
 'Pencerelerin birlikte göründüğü ekran görüntüsünü ve varsa hata metnini bu sohbete gönder.'),
('STARTUP-SPEED-V495','13 saniyelik açılış beklemesi / arayüz tepkisi','Performans',
 '1. Programı yeni başlat.\n2. Seri Üretim düğmesine basınca ilk pencerenin belirme süresini ölç.\n3. Onaylı şablonların tamamının gelme süresini ayrıca ölç.\n4. Şablon İnceleme için aynı 2 süreyi ölç.\n5. Yükleme sırasında ana ekrandaki Notlarım düğmesine tıklayabildiğini kontrol et.',
 'İlk pencere hızlı görünür; bekleme sürerken ana ekran donmaz. Gerçek 13 saniyelik karşılaştırma raporlanır.',
 'Dört süreyi (soğuk/sıcak ekran) ve kilitlenme varsa ekran görüntüsünü gönder.'),
('MODERN-PRODUCTION-V495','Modern Seri Üretim Merkezi görünümü ve seçme araçları','Arayüz',
 '1. Seri Üretim ekranındaki 4 ana kart bölümünü kontrol et.\n2. Kategori filtresini, arama ve seçili sayaçlarını dene.\n3. %125 Windows ölçeklendirmede butonlara eriş.\n4. PETEK, 4K, Mağaza, Excel alanlarını kontrol et.',
 'Koyu modern tema, okunaklı bölümler ve erişilebilir tüm düğmeler; eski üretim ayarları korunur.',
 'Tam pencere ekran görüntüsü ve takılan düğme adlarını gönder.'),
('PETEK-EDGE-ALL-V495','PETEK dört kenar / köşe / 15 ızgara pembe artıklar','PETEK',
 '1. Önce pembe hatalı şablonun bir tasarımını seç.\n2. PETEK A/B > Izgara Orta ve Pembe Temizliği açık olarak çalıştır.\n3. Özellikle sağ-sol, alt sağ-sol köşe, alt kavis ve 15 çizgide pembe iz ara.\n4. Orijinal zemin gölgesi ve beyaz panel bozulmamış olmalı.\n5. Gerçek üretimle A/B görünümünün aynı olduğunu kontrol et.',
 'Pembe marker kalıntıları temizlenmiş; ürün beyaza boyanmış gibi görünmüyor; sahnenin diğer alanları korunuyor.',
 'Önce / Sonra tam fotoğrafı ve sağ-sol alt köşe ile yarıkların yakın çekimlerini gönder.'),
('4K-ON-DEMAND-V495','4K seçildiğinde tek seferlik kurulum kontrolü','4K',
 '1. Seri Üretim ekranını aç; 4K için hiçbir kurulum penceresi açılmadığını kontrol et.\n2. 4K işaretle.\n3. Kurulu x4plus varsa hazır yazısı görünmeli.\n4. 4K işaretini kapat/aç; önbellek durumunu izle.\n5. Bir deneme 4K üretimle gerçek GPU kontrolünü tamamla.',
 'Kurulu motor tekrar indirilmiyor; eksik kurulumda resmi SHA256-kontrollü kurucu tetikleniyor; 1200x1600 çıktılar değişmiyor.',
 '4K durum metni, GPU raporu ve üretilen dosyanın piksel ölçülerini gönder.'),
('REAPPROVE-4-CORNER-V495','Onaylı şablonun 4 köşesini yeniden düzenleme','Şablon',
 '1. Şablonları İncele aç.\n2. Onaylı bir şablonu seç ve mevcut dört köşeleri gör.\n3. Gerekli küçük düzeltmeyi yap.\n4. Bu Şablonu Onayla ile tekrar insan onayı ver.\n5. Yeniden açarak yeni köşelerin korunduğunu ve başka şablonun değişmediğini doğrula.\n6. PETEK için onaylı maskeden yeni revizyon taslağı oluştur.',
 'Onaysız otomatik değişim yok; geçmiş maskeler silinmeden yeniden insan onayı alınır.',
 'Onay ekranı ve yeniden açılmış dört köşe görünümünü gönder.'),
('EXIT-V494', 'Programı Kapat: terminal açmadan güvenli çıkış', 'Arayüz',
 '1. Ana ekranda üst çubuktaki ⏻ Programı Kapat düğmesini bul.\n'
 '2. Programda açık üretim yokken bu düğmeye bas. Program ve açılış terminali kapanmalı.\n'
 '3. Programı yeniden aç; açık üretim varken kapatma düğmesinin üretimi zorla bitirmediğini kontrol et.\n'
 '4. İnceleme sunucusu açıkken kaydet ve kapatmayı dene: onay vermeden çıkmamalı, onay verince yalnız doğrulanmış kendi servisini durdurmalı.\n'
 '5. Not ve test kayıtlarının yeniden açıldığında korunduğunu kontrol et.',
 'Normal çıkışta CMD penceresini elle kapatmaya gerek yok; çalışan işi kesmez, doğrulanamayan sunucuya dokunmaz, notlar kaybolmaz.',
 'Bir sorun varsa kapatma sırasında ekran mesajını, varsa başlatıcı konsol metnini ve Test Merkezi raporunu sohbete gönder.'),
('PETEK-15-REAL', 'PETEK: 15 koyu ızgara son görsel', 'PETEK',
 '1. Şablon İnceleme > PETEK bölümünde bir fotoğraf aç.\n2. Gerçek baskı tasarımı seç.\n3. 15 Izgara A/B Testi > Orta seç ve Önce / Sonra çalıştır.\n4. Düzeltme sonrası 15 koyu yarığın konumunu, perspektifi ve kenarları büyütüp kontrol et.\n5. Onaylı maske ve orijinal fotoğrafın değişmediğini doğrula.',
 'Tam 15 yarık, belirgin iç gölge, gerçek gövdeye oturmuş perspektif; kapak/zemin dışına taşma yok.',
 'Önce/Sonra ekran görüntüsü ve varsa hata raporunu ChatGPT sohbetine gönder.'),
('PETEK-PINK-CORNER', 'PETEK: Sol alt köşede pembe kaçak', 'PETEK',
 '1. Önceden köşesi pembe kalan aynı PETEK sahnesini seç.\n2. A/B panelinde Pembe Kenar Temizliği seçimini aç.\n3. %200 yakınlaşarak sol alt köşeyi ve zemini incele.\n4. Orijinal kaynakla karşılaştır.',
 'Sol alttaki magenta çizgi kaybolmalı; zeminin dokusu ve beyaz ürün yan yüzü korunmalı.',
 'Köşenin %200 yakın görselini ve tam sahneyi bu sohbete gönder.'),
('PETEK-WEB-AB', 'PETEK: Maske inceleme ekranında A/B', 'Arayüz',
 '1. Şablonları İncele > PETEK aç.\n2. Gerçek tasarım seç.\n3. Aynı ekrandaki 15 Izgara A/B denemesini başlat.\n4. Çıkmadan önce/sonra arasında geçiş yap.\n5. Taslak maskenin ve onayın değişmediğini kontrol et.',
 'A/B tek ekrandan ulaşılabilir; yalnız önizlemedir, onaylı maskeler değişmez.',
 'Görünmeyen düğme veya yanlış bağlantı varsa ekran görüntüsü gönder.'),
('MAGENTA-ONCE', 'MAGENTA: Tek seferlik güvenli değiştirme', 'Kritik',
 '1. Şablon inceleme sunucusunu, açık kayıtlarını tamamladıktan sonra güvenle kapat.\n2. Test Merkezi > Magenta Aracını Aç kullan.\n3. Eşleşen/eşleşmeyen dosyaları ve yedek yolunu kontrol et.\n4. İzin verdiğin eşleşmeleri yalnız araç tarafından yedek alındıktan sonra uygula.\n5. Çalışma şablonlarını ve orijinal yedekleri karşılaştır.',
 'STOP_4_KOSE hatası güvenli biçimde giderilmiş; dosyalar doğru eşleşmiş, rollback yedeği var, orijinal arşiv değişmedi.',
 'Aktarım özeti, eşleşme adetleri ve varsa hata metnini bu sohbete gönder.'),
('REAL-ESRGAN-4K', '4K: Real-ESRGAN ağırlık ve GPU kabulü', '4K',
 '1. Seri Üretim > 4K Durum/Kur/GPU Test aç.\n2. Resmî motor ve model ağırlıklarının doğrulama sonucunu kontrol et.\n3. Bir küçük örnekten 2880×3840 çıktı oluştur.\n4. Normal 1200×1600 dosyanın korunduğunu denetle.',
 'Model doğrulanır, test görüntüsü oluşur, normal üretim etkilenmez.',
 'REAL_ESRGAN_KURULUM_SONUC.txt ve GPU hata varsa ekran görüntüsünü sohbete yükle.'),
('FILTERS-SELECT', 'Seri Üretim: filtre ve toplu seçim', 'Arayüz',
 '1. Seri Üretim aç.\n2. PETEK kategorisini filtrele, 2 şablon seç.\n3. Başka kategoriye geçip geri gel.\n4. Ara, sırala, filtrelenenleri seç/temizle işlevlerini dene.',
 'Seçim korunur; seçilmeyen şablonlar üretime girmez.',
 'Yanlış seçim varsa kategori/isimlerle birlikte ekran görüntüsü gönder.'),
('PERSONAL-NOTES', 'Notlarım ve Görevlerim: kalıcılık', 'Arayüz',
 '1. Ana sayfa > Notlarım ve Görevlerim aç.\n2. Bir not ve görev ekle.\n3. Programı kapat ve yeniden aç.\n4. Notun, görevin ve tamamlandı bilgisinin korunduğunu kontrol et.',
 'Yeniden açılışta veriler durmalı; şablon DB değişmemeli.',
 'Sorun olursa Test Raporunu Kopyala ve ilgili ekranı sohbete gönder.'),
('TOOLS-SEARCH', 'Özellik / Araç Ara: hızlı erişim', 'Arayüz',
 '1. Ana sayfa > Özellik / Araç Ara aç.\n2. «yatay», «şablon», «4k», «petek» ve «excel» ara.\n3. Sonuçtan bir araç aç.\n4. Açılmayan aracı kayıt altına al.',
 'Tüm kayıtlı araçlar bulunur, yönlendirme doğru sayfaya gider.',
 'Aradığın kelime ve düğmenin ekran görüntüsünü sohbete gönder.'),
('STAGE-SAFE', 'Yeni Şablon Ekle: güvenli havuz', 'Veri',
 '1. Ana sayfa > Yeni Şablon Ekle aç.\n2. İki yeni dosya seç, kategoriyi belirt.\n3. YENI-BOS MOCKUP SABLON HAVUZU altında doğrula.\n4. Kaynak dosya ve eski onaylı şablonların değişmediğini kontrol et.',
 'Yalnız yeni havuza kopyalar; isim çakışması yok; otomatik onay vermez.',
 'Gelen şablon sayısı ve hedef klasör görüntüsünü sohbete gönder.'),
('ORIENTATION-TOOL', 'YATAY / DİKEY / KARE ayırıcı', 'Araç',
 '1. Profesyonel Araçlar > Yatay-Dikey Görsel Seçici aç.\n2. Üç farklı yön ve aynı adlı iki dosyayla dene.\n3. Kaynak dosyaların değişmediğini doğrula.',
 'Üç ayrı klasör; aynı adlı dosyalar kaybolmadan ayrılır.',
 'İşlem CSV ve varsa hata kaydını sohbete yükle.'),
('7CAT-REGRESSION', 'Yedi kategori: üretim ve güvenli veri testi', 'Kritik',
 '1. Her kategoriden bir onaylı şablonla ayrı deneme üret.\n2. PETEK maskesini, dört köşeleri ve çalışma/orijinal dosyaları kontrol et.\n3. Üretilen görsellerin fiziksel ölçü/yönünü doğrula.',
 'Yedi kategori çıktı üretiyor; mevcut onaylar ve dosyalar zarar görmüyor.',
 'Yedi örnek görsel ve işlem raporunu sohbete gönder.'),
('STORE-EXCEL-CLOUD', 'Mağaza, Excel ve bağlantı iş akışı', 'Kritik',
 '1. İki mağaza profili seç.\n2. Aynı tasarımla farklı onaylı şablon kullan.\n3. İstersen ayrıca çevrimiçi paylaşım için açık onay ver.\n4. İki mağazanın XLSX dosyalarını kontrol et.',
 'Mağaza bazlı dosya/SKU ayrımı çalışır, link onaysız internete yüklenmez.',
 'Özel bilgileri gizleyerek XLSX örneği veya rapor gönder.'),
('UI-ALL-SCREENS', 'Yeni arayüz: tüm ekranlar ve düğmeler', 'Arayüz',
 '1. Ana ekranı, Şablonlar, PETEK, Seri Üretim, Profesyonel Araçlar ve Raporlar ekranlarını aç.\n2. Okunamayan yazı veya tıklanamayan düğme olup olmadığını kontrol et.\n3. Eski görünüme dönüş başlatıcısının çalıştığını dene.',
 'Kritik eylemlere ulaşılır; ekran taşması/kopuk düğme yok.',
 'Düğmenin adı, hangi ekranda olduğu ve ekran görüntüsünü gönder.'),
('TEST-CENTER-PERSIST', 'Test Merkezi: Beklet / Onayla / Arşiv', 'Arayüz',
 '1. Bu testi Beklet yap.\n2. Programı kapatıp aç.\n3. Beklet durumunun durduğunu kontrol et.\n4. Gerçekten tamamladıysan Onayla ve Kaldır seç.\n5. Arşivde kaldığını doğrula.',
 'Bekleyen test silinmez; onaylı test arşive gider ve sürüm güncellemesinde geri açılmaz.',
 'Test merkezindeki Raporu Dışa Aktar ile TXT oluşturup sohbete ekle.'),
]


def state_path(env=None):
    env = os.environ if env is None else env
    base=env.get('GORSEL_PERSONAL_DATA_DIR') or env.get('LOCALAPPDATA')
    if base:
        root=Path(base)/'GorselMockup'/'PersonalCenter'
    else:
        root=Path.home()/'.gorsel_mockup'/'PersonalCenter'
    root.mkdir(parents=True, exist_ok=True)
    return root

class Store:
    def __init__(self, path=None):
        self.path=Path(path) if path else state_path()/DB_NAME
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS acceptance (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, area TEXT NOT NULL,
                    steps TEXT NOT NULL, success TEXT NOT NULL, evidence TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'BEKLIYOR', notes TEXT NOT NULL DEFAULT '',
                    added_version TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL, body TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL, details TEXT NOT NULL DEFAULT '',
                    done INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_acceptance_status ON acceptance(status);
            ''')
        self.seed()

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=12)
        try:
            db.execute('PRAGMA busy_timeout=12000')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat(timespec='seconds')

    def seed(self):
        with self.connect() as db:
            db.executemany('''INSERT OR IGNORE INTO acceptance
                (id,title,area,steps,success,evidence,added_version,updated_at)
                VALUES(?,?,?,?,?,?,?,?)''',[
                (id,title,area,steps,success,evidence,CURRENT_VERSION,self.now())
                for id,title,area,steps,success,evidence in ACCEPTANCE])

    def tests(self,archived=False):
        with self.connect() as db:
            db.row_factory=sqlite3.Row
            return [dict(r) for r in db.execute(
                "SELECT * FROM acceptance WHERE status {} 'ONAYLANDI' ORDER BY CASE status WHEN 'SORUN_VAR' THEN 0 WHEN 'BEKLIYOR' THEN 1 WHEN 'BEKLETILDI' THEN 2 ELSE 3 END, id".format('=' if archived else '!='))]

    def update_test(self, uid, status, notes):
        if status not in ('BEKLIYOR','BEKLETILDI','SORUN_VAR','ONAYLANDI'):
            raise ValueError('Geçersiz durum')
        with self.connect() as db:
            cur=db.execute('UPDATE acceptance SET status=?,notes=?,updated_at=? WHERE id=?',
                    (status,notes,self.now(),uid))
            if cur.rowcount != 1: raise ValueError('Test kaydı bulunamadı')

    def items(self,kind):
        if kind not in ('notes','tasks'): raise ValueError('Invalid kind')
        with self.connect() as db:
            db.row_factory=sqlite3.Row
            return [dict(r) for r in db.execute('SELECT * FROM '+kind+' ORDER BY id DESC')]

    def upsert_item(self,kind,title,detail,uid=None):
        if kind not in ('notes','tasks'): raise ValueError('Invalid kind')
        title=title.strip()[:160]
        if not title: raise ValueError('Başlık boş olamaz')
        if len(detail)>20000:raise ValueError('Not çok uzun')
        with self.connect() as db:
            if uid is None:
                if kind=='notes': db.execute('INSERT INTO notes(title,body,updated_at) VALUES(?,?,?)',(title,detail,self.now()))
                else: db.execute('INSERT INTO tasks(title,details,updated_at) VALUES(?,?,?)',(title,detail,self.now()))
            else:
                col='body' if kind=='notes' else 'details'
                db.execute(f'UPDATE {kind} SET title=?,{col}=?,updated_at=? WHERE id=?',(title,detail,self.now(),uid))

    def toggle_task(self,uid,done):
        with self.connect() as db:
            db.execute('UPDATE tasks SET done=?,updated_at=? WHERE id=?',(int(done),self.now(),uid))

    def delete_item(self,kind,uid):
        if kind not in ('notes','tasks'):raise ValueError('Invalid kind')
        with self.connect() as db: db.execute('DELETE FROM '+kind+' WHERE id=?',(uid,))

    def export(self):
        path=state_path()/'TEST_KABUL_RAPORU.txt'
        lines=['GÖRSEL ÜRETİM MERKEZİ — TEST/KABUL RAPORU',f'Sürüm: {CURRENT_VERSION}',
               f'UTC: {self.now()}','Her test kullanıcı onayıyla işaretlenir; otomatik geçme yok.','']
        for a in self.tests()+self.tests(archived=True):
            lines += [f"[{a['status']}] {a['id']} — {a['title']}",
                      'Yapılacaklar: '+a['steps'],'Başarı koşulu: '+a['success'],
                      'Gönderilecek: '+a['evidence'],'Not: '+a['notes'],'']
        # Atomic replaces only this generated report, never any original workspace.
        tmp=path.with_suffix('.txt.tmp')
        tmp.write_text('\n'.join(lines),encoding='utf-8')
        os.replace(tmp,path)
        return path


def _window(root,title,width=1070,height=710):
    w=tk.Toplevel(root);w.title(title)
    w.geometry(f'{width}x{height}');w.minsize(780,530);w.configure(bg='#121625')
    return w


def open_acceptance(root,launch_magenta=None):
    store=Store();win=_window(root,f'Yapmam Gereken Testler — {CURRENT_VERSION} Kabul Merkezi')
    frame=ttk.Frame(win,padding=16);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Yapmam Gereken Testler',font=('Segoe UI',19,'bold')).pack(anchor='w')
    ttk.Label(frame,text='BEKLET = kaybolmaz. SORUN VAR = açık kalır. ONAYLA VE KALDIR = arşive taşınır; kayıt silinmez.',
              wraplength=980).pack(anchor='w',pady=(5,10))
    toolbar=ttk.Frame(frame);toolbar.pack(fill='x',pady=(0,9))
    archive=tk.BooleanVar(value=False)
    left=ttk.Frame(frame);left.pack(side='left',fill='y',padx=(0,12))
    scrollbar=ttk.Scrollbar(left);scrollbar.pack(side='right',fill='y')
    listing=tk.Listbox(left,width=47,height=28,yscrollcommand=scrollbar.set,exportselection=False,
                       font=('Segoe UI',11),bg='#1b2032',fg='#eff0fa',
                       selectbackground='#6f4db5',selectforeground='#ffffff',
                       highlightthickness=0,relief='flat')
    listing.pack(side='left',fill='y');scrollbar.config(command=listing.yview)
    detail=ttk.Frame(frame);detail.pack(side='left',fill='both',expand=True)
    headline=tk.StringVar();ttk.Label(detail,textvariable=headline,wraplength=640,font=('Segoe UI',13,'bold')).pack(anchor='w')
    instructions=scrolledtext.ScrolledText(detail,height=9,wrap='word',font=('Segoe UI',11),
                       bg='#1c2032',fg='#f2f1ff',insertbackground='#ffffff',
                       selectbackground='#5a438e',relief='flat',padx=12,pady=11,state='disabled')
    instructions.pack(fill='both',expand=True,pady=(9,8))
    ttk.Label(detail,text='Sonuç / notun (kalıcı kaydedilir):').pack(anchor='w')
    notes=scrolledtext.ScrolledText(detail,height=2,wrap='word',font=('Segoe UI',11),
                       bg='#1c2032',fg='#f2f1ff',insertbackground='#ffffff',
                       selectbackground='#5a438e',relief='flat',padx=9,pady=7)
    notes.pack(fill='x',pady=(3,9))
    btns=ttk.Frame(detail);btns.pack(fill='x')
    records=[]
    def current():
        i=listing.curselection()
        return records[i[0]] if i and i[0]<len(records) else None
    def show(_=None):
        rec=current()
        if rec is None: headline.set('Test seç');instructions.configure(state='normal');instructions.delete('1.0','end');instructions.configure(state='disabled');notes.delete('1.0','end');return
        headline.set(rec['title']+' — '+rec['status'])
        text=f"KATEGORİ: {rec['area']}  |  KAYIT: {rec['id']}\n\nNASIL TEST EDECEKSİN?\n{rec['steps']}\n\nBAŞARI KRİTERİ:\n{rec['success']}\n\nSONUCU NEREYE GÖNDERECEKSİN?\n{rec['evidence']}"
        instructions.configure(state='normal');instructions.delete('1.0','end');instructions.insert('1.0',text);instructions.configure(state='disabled')
        notes.delete('1.0','end');notes.insert('1.0',rec['notes'])
    def refresh(select_id=None):
        nonlocal records
        records=store.tests(archived=archive.get())
        listing.delete(0,'end')
        for item in records: listing.insert('end',f"[{item['status']}] {item['title']}")
        if records:
            ix=next((i for i,r in enumerate(records) if r['id']==select_id),0)
            listing.selection_set(ix);listing.see(ix)
        show()
    def update(status):
        rec=current()
        if not rec:return
        if status=='ONAYLANDI' and not messagebox.askyesno('Kullanıcı kabulü',
                'Bu testi GERÇEKTEN uygulayıp başarı kriterlerinin tamamını doğruladın mı?\n\nOnaylı olarak arşivlenecek; silinmeyecek.',parent=win):return
        try:
            store.update_test(rec['id'],status,notes.get('1.0','end-1c'))
            refresh(rec['id'] if status!='ONAYLANDI' else None)
        except Exception as exc:messagebox.showerror('Kaydedilemedi',str(exc),parent=win)
    def export():
        try:
            path=store.export()
            win.clipboard_clear();win.clipboard_append(path.read_text(encoding='utf-8'))
            messagebox.showinfo('Test raporu hazır',f'{path}\n\nRapor panoya da kopyalandı. Bu sohbete yapıştırabilir veya dosyayı yükleyebilirsin.',parent=win)
        except Exception as exc:messagebox.showerror('Rapor hatası',str(exc),parent=win)
    ttk.Checkbutton(toolbar,text='Tamamlananlar / Arşiv',variable=archive,command=refresh).pack(side='left')
    ttk.Button(toolbar,text='Test Raporu Oluştur + Kopyala',command=export).pack(side='right')
    if launch_magenta:
        ttk.Button(toolbar,text='Magenta Son Aktarım Aracı',command=launch_magenta).pack(side='right',padx=8)
    actions=ttk.Frame(btns);actions.pack(fill='x')
    ttk.Button(actions,text='Notu Kaydet',command=lambda:update(current()['status'] if current() else 'BEKLIYOR')).pack(side='left',padx=3)
    ttk.Button(actions,text='Beklet',command=lambda:update('BEKLETILDI')).pack(side='left',padx=3)
    ttk.Button(actions,text='Sorun Var',command=lambda:update('SORUN_VAR')).pack(side='left',padx=3)
    ttk.Button(actions,text='Bekleyen Yap',command=lambda:update('BEKLIYOR')).pack(side='left',padx=3)
    ttk.Button(btns,text='Test Ettim, Onayla ve Kaldır',command=lambda:update('ONAYLANDI')).pack(fill='x',pady=(6,0))
    listing.bind('<<ListboxSelect>>',show)
    refresh()
    return win


def open_personal(root):
    store=Store();win=_window(root,'Notlarım ve Görevlerim')
    book=ttk.Notebook(win);book.pack(fill='both',expand=True,padx=12,pady=12)
    for kind,caption in [('notes','Notlarım'),('tasks','Görevlerim')]:
        frame=ttk.Frame(book,padding=12);book.add(frame,text=caption)
        left=ttk.Frame(frame);left.pack(side='left',fill='y',padx=(0,13))
        listing=tk.Listbox(left,width=33,height=26,exportselection=False,
                   font=('Segoe UI',11),bg='#1b2032',fg='#eff0fa',
                   selectbackground='#6f4db5',selectforeground='#ffffff',relief='flat');listing.pack(fill='y',expand=True)
        right=ttk.Frame(frame);right.pack(side='left',fill='both',expand=True)
        ttk.Label(right,text='Başlık').pack(anchor='w')
        name=ttk.Entry(right);name.pack(fill='x',pady=(2,9))
        ttk.Label(right,text='Not / görev detayları').pack(anchor='w')
        editor=scrolledtext.ScrolledText(right,wrap='word',height=12,font=('Segoe UI',11),
                    bg='#1c2032',fg='#f2f1ff',insertbackground='#ffffff',
                    selectbackground='#5a438e',relief='flat',padx=11,pady=9);editor.pack(fill='both',expand=True,pady=(2,10))
        row=ttk.Frame(right);row.pack(fill='x')
        records=[]
        def make_funcs(kind=kind,listing=listing,name=name,editor=editor,frame=frame,row=row):
            current_id=[None]
            def refresh():
                nonlocal records
                data=store.items(kind);frame._records=data
                listing.delete(0,'end')
                for item in data:
                    status=('☑ ' if item.get('done') else '□ ') if kind=='tasks' else '▤ '
                    listing.insert('end',status+item['title'])
            def pick(event=None):
                selection=listing.curselection()
                if not selection:return
                rec=frame._records[selection[0]]
                current_id[0]=rec['id']
                name.delete(0,'end');name.insert(0,rec['title'])
                editor.delete('1.0','end');editor.insert('1.0',rec.get('body',rec.get('details','')))
            def clear():
                current_id[0]=None;name.delete(0,'end');editor.delete('1.0','end');listing.selection_clear(0,'end')
            def save():
                try:store.upsert_item(kind,name.get(),editor.get('1.0','end-1c'),current_id[0]);refresh();clear()
                except Exception as exc:messagebox.showerror('Kaydedilemedi',str(exc),parent=win)
            def remove():
                if current_id[0] is None:return
                if messagebox.askyesno('Silinsin mi?','Bu kişisel kayıt kalıcı silinecek, emin misin?',parent=win):
                    store.delete_item(kind,current_id[0]);refresh();clear()
            def completed():
                if current_id[0] is None:return
                item=next((r for r in frame._records if r['id']==current_id[0]),None)
                if item:
                    store.toggle_task(current_id[0],not bool(item['done']));refresh()
            listing.bind('<<ListboxSelect>>',pick)
            ttk.Button(row,text='Yeni',command=clear).pack(side='left',padx=4)
            ttk.Button(row,text='Kaydet',command=save).pack(side='left',padx=4)
            if kind=='tasks':ttk.Button(row,text='Yapıldı / Geri Al',command=completed).pack(side='left',padx=4)
            ttk.Button(row,text='Sil',command=remove).pack(side='right',padx=4)
            refresh()
        make_funcs()
    return win

# All entries resolve to existing methods; the feature index is deliberately
# searchable without opening the app's database or touching original images.
TOOL_INDEX = [
 ('Şablonları İncele ve Onayla','dört köşe maske şablon petek','open_legacy_review'),
 ('Seri Mockup Üretimi','kategori mağaza üretim excel 4k','open_unified_v4'),
 ('Güvenli Yeni Şablon Ekle','yeni boş havuz aktar içe al','open_safe_stage_v493'),
 ('YATAY - DİKEY Görsel Seçici','dikey kare yatay ayrıştırma','open_orientation_v493'),
 ('Profesyonel Araçlar','format filigran isimlendirici seo link','open_legacy_tools'),
 ('HAM Baskı Tasarımları','ham tasarım klasör','open_ham_design_folder'),
 ('PETEK Maskeleri ve 15 Izgara A/B','petek ızgara maske önizle','open_legacy_review'),
 ('4K Real-ESRGAN Kur / GPU Test','ağırlık model upscale','open_4k_setup_v493'),
 ('Magenta Tek Seferlik Değiştirme','magenta lab aktarım onay','open_magenta_replace_v486'),
 ('Mağaza Profilleri ve Excel','mağaza stok barkod excel','open_unified_v4'),
 ('G3 Bütünlük Kontrolü','veri güvenlik hash denetim','g3_audit'),
 ('SQLite Güvenli Yedek','geri yükleme yedek','g3_backup'),
 ('Üretim Kayıt Denetimi','çıktı sha rapor','open_unified_audit'),
 ('HAM Numara Denetimi','ham ismi isim numara','show_ham_design_audit'),
 ('Notlarım ve Görevlerim','kişisel not görev','open_notes_v493'),
 ('Yapmam Gereken Testler','kabul test rapor beklet onay','open_tests_v493'),
 ('Ana Çalışma Klasörü','klasör seçim değiştirme','select_runtime'),
 ('Sistem Durumu','sağlık kurulum servis','show_health'),
 ('Kesinti Kurtarma','kilit durmuş iş','open_crash_recovery'),
 ('Görsel İsimlendirici','dosya yeniden adlandırma numara','open_rename_v493'),
 ('PNG / JPG Format Çevirici','format dönüştür jpg jpeg png','open_format_v493'),
 ('Otomatik Filigran','logo marka filigran watermark','open_watermark_v493'),
 ('Görsel Kalite Artırıcı 4K','AI upscale esrgan','open_quality_v493'),
 ('Görsel Link / Excel','im gbb upload excel url','open_links_v493'),
 ('SEO Ürün Adı Üretici','trendyol etsy ürün başlığı','open_seo_title_v493'),
 ('SEO Açıklama Üretici','anahtar kelime metin açıklama','open_seo_desc_v493'),
 ('Recursive PNG Dönüştürücü','alt klasör png çevirme','open_recursive_v493'),
 ('3:4 Dikey Uzatma','blur mozaik buzlu cam','open_legacy_tools'),
 ('KONTROL_GEREKENLER Raporu','yeniden tarama kontrol dosyası','open_legacy_tools'),
 ('Golden Dataset Görsel Denetimi','referans test gerçek kalite','open_legacy_tools'),
]

def open_tool_search(app):
    win=_window(app.root,'Özellik / Araç Ara — Hızlı Erişim',920,640)
    frame=ttk.Frame(win,padding=16);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Özellik / Araç Ara',font=('Segoe UI',19,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Araç, düğme veya özelliği yaz; seçili kayda çift tıkla ya da Aç düğmesine bas.',wraplength=850).pack(anchor='w',pady=(0,10))
    query=tk.StringVar();entry=ttk.Entry(frame,textvariable=query,font=('Segoe UI',12));entry.pack(fill='x',pady=6)
    listing=tk.Listbox(frame,exportselection=False,font=('Segoe UI',12),height=22,
                  bg='#1b2032',fg='#eff0fa',selectbackground='#6f4db5',
                  selectforeground='#ffffff',relief='flat');listing.pack(fill='both',expand=True,pady=8)
    result=[]
    def filter_items(*_):
        nonlocal result
        txt=query.get().casefold().strip()
        result=[r for r in TOOL_INDEX if txt in (r[0]+' '+r[1]).casefold()]
        listing.delete(0,'end')
        for r in result:listing.insert('end',r[0])
        if result:listing.selection_set(0)
    def launch(_=None):
        cur=listing.curselection()
        if not cur:return
        label,_,fn=result[cur[0]]
        try:
            getattr(app,fn)()
        except Exception as exc:messagebox.showerror('Araç açılamadı',f'{label}: {exc}',parent=win)
    ttk.Button(frame,text='Seçili Aracı Aç',command=launch).pack(anchor='e')
    query.trace_add('write',filter_items)
    listing.bind('<Double-Button-1>',launch)
    entry.bind('<Return>',launch)
    filter_items();entry.focus_set()
    return win
