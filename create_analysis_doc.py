import os

def create_doc():
    output_path = r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu\SISTEM_ANALIZ_RAPORU.md"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# E-TİCARET GÖRSEL ÜRETİM VE MOCKUP OTOMASYONU - SİSTEM ANALİZ DOSYASI\n\n")
        f.write("## 1. PROJENİN AMACI VE HEDEFLERİ\n")
        f.write("Bu proje, bir e-ticaret satıcısının satmak istediği binlerce tasarımı (tablo, wifi kutusu, cam doğrama vb.) alıp, **insan müdahalesi olmadan milimetrik bir şekilde oda/mekan şablonlarına oturtmayı (mockup) ve Trendyol gibi pazar yerlerine yüklemeye hazır Excel çıktıları üretmeyi** amaçlar.\n\n")
        
        f.write("### Temel Hedefler:\n")
        f.write("- **Yüksek Hız ve Ölçeklenebilirlik:** Yüzlerce ham şablonu (11 farklı açı) ve binlerce tasarımı alıp saatler içinde on binlerce satışa hazır ürün görseli oluşturmak.\n")
        f.write("- **Kaggle AI Entegrasyonu:** Kaggle GPU matbaasında (Stable Diffusion/Midjourney) üretilen yepyeni, eşsiz görsel desenlerini API veya yerel klasör (Onay Mekanizması) üzerinden çekip anında mockuplara basmak.\n")
        f.write("- **Akıllı Maskeleme (OpenCV):** Şablonlarda ürünün nereye basılacağının koordinatlarını bulmak, arkaplanı otomatik beyazlatmak, eşya önünde kalan kısımları hesaplamak (occlusion).\n")
        f.write("- **Çoklu V2 Arayüz (Flask):** Kullanıcının sistemi tek bir komuta tıklar gibi kolay yönetmesini sağlayan Ana Kontrol Merkezi (Port 5000) ve şablonların köşelerinin hassas olarak işaretlendiği Şablon Düzeltici (Port 8080).\n\n")
        
        f.write("## 2. SİSTEM MİMARİSİ\n")
        f.write("1. **V2_KONTROL_MERKEZI (Flask):** Ana gösterge paneli. Kullanıcı iş akışını (Şablon yükle, Düzelticiyi aç, Kaggle Onay, Üretim başlat) buradan yönetir.\n")
        f.write("2. **SABLON_V2_MIMARI (Flask):** SQLite (ayarlar.db) destekli. Kullanıcı arayüzden şablondaki (resimdeki) çerçevenin 4 köşesini ayarlar. OpenCV yardımıyla taşma noktaları belirlenir.\n")
        f.write("3. **pc_master_factory.py (Üretim Motoru):** Kullanıcının `ayarlar.db` de belirlediği köşe koordinatlarını alarak `cv2.getPerspectiveTransform` ve `cv2.warpPerspective` ile ana görselleri şablona giydiren, ardından ImgBB bulutuna yükleyip Excel oluşturan ana işçi scripttir.\n")
        f.write("4. **Kaggle Onay Mekanizması:** Kaggle'dan gelen baskılar `0_KAGGLE_ONAY_BEKLEYENLER` klasöründe tutulur. Flask UI üzerinden 'Onayla' denirse `1_GELEN_KAGGLE_BASKILARI`na alınır ve Üretim Motoruna devredilir.\n\n")

        f.write("## 3. PROJE DOSYALARI VE KODLAR\n\n")
        f.write("Lütfen aşağıdaki tüm kodları inceleyerek; sistemin performansında, veritabanı (SQLite) kullanımında, OpenCV perspektif dönüşümlerinde veya genel Python mimarisinde güvenlik/hız açısından **eksik veya hatalı** bulduğunuz yerleri analiz edin.\n\n")

        files_to_dump = [
            ("SİSTEMİ BAŞLATAN BATCH", "SISTEMI_BASLAT.bat"),
            ("OTOMASYON ÇALIŞTIRICI", "OTOMASYONU_CALISTIR.bat"),
            ("ANA KONTROL MERKEZİ BACKEND", r"V2_KONTROL_MERKEZI\app.py"),
            ("ANA KONTROL MERKEZİ ARAYÜZÜ", r"V2_KONTROL_MERKEZI\templates\index.html"),
            ("ŞABLON DÜZELTİCİ BACKEND", r"SABLON_V2_MIMARI\app.py"),
            ("ŞABLON DÜZELTİCİ DB KATMANI", r"SABLON_V2_MIMARI\core\db.py"),
            ("ŞABLON DÜZELTİCİ GÖRÜNTÜ İŞLEME", r"SABLON_V2_MIMARI\core\vision.py"),
            ("ŞABLON DÜZELTİCİ ARAYÜZ (HTML)", r"SABLON_V2_MIMARI\templates\index.html"),
            ("ŞABLON DÜZELTİCİ ARAYÜZ (JS)", r"SABLON_V2_MIMARI\static\js\main.js"),
            ("ANA ÜRETİM MOTORU", r"99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\pc_master_factory.py")
        ]
        
        base_dir = r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu"
        
        for title, rel_path in files_to_dump:
            abs_path = os.path.join(base_dir, rel_path)
            f.write(f"### {title} ({rel_path})\n")
            if os.path.exists(abs_path):
                ext = os.path.splitext(rel_path)[1].replace(".", "")
                if ext == "bat": ext = "bat"
                elif ext == "py": ext = "python"
                elif ext == "html": ext = "html"
                elif ext == "js": ext = "javascript"
                else: ext = "text"
                
                f.write(f"```{ext}\n")
                with open(abs_path, "r", encoding="utf-8", errors="replace") as code_file:
                    f.write(code_file.read())
                f.write("\n```\n\n")
            else:
                f.write("> Dosya bulunamadı.\n\n")
                
    print(f"Rapor basariyla {output_path} konumuna yazildi.")

if __name__ == '__main__':
    create_doc()
