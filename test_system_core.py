import unittest
import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Yolları ekliyoruz
BASE_DIR = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu")
sys.path.insert(0, str(BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"))
sys.path.insert(0, str(BASE_DIR / "ÜRÜN ADI YAZDIRMA BOTU"))
sys.path.insert(0, str(BASE_DIR / "AI_Kalite_Artirici"))
sys.path.insert(0, str(BASE_DIR / "V2_KONTROL_MERKEZI"))

# =====================================================================
# Modüllerin güvenli şekilde yüklenmesi (Hata fırlatmayı engellemek için)
# =====================================================================
try:
    import app
except ImportError:
    app = None

try:
    import manuel_mockup_motoru as manuel_motor
except ImportError:
    manuel_motor = None

try:
    import pc_master_factory as master_factory
except ImportError:
    master_factory = None

class SystemWideQA_TestSuite(unittest.TestCase):
    """
    Tüm sistemin (API, Motorlar, Veritabanı ve Botlar) 
    Defensive Programming standartlarında uçtan uca test kurgusu.
    """

    @classmethod
    def setUpClass(cls):
        """Test ortamını izole et: Geçici dizinler yarat"""
        cls.test_dir = tempfile.TemporaryDirectory()
        cls.test_path = Path(cls.test_dir.name)
        
        # Fake ayarlar.json oluştur (Eksik Key Testleri için)
        cls.fake_settings_path = cls.test_path / "ayarlar.json"
        with open(cls.fake_settings_path, "w", encoding="utf-8") as f:
            json.dump({"bulut_ayarlari": {"imgbb_keys": ["fake_key_123"]}}, f)

    @classmethod
    def tearDownClass(cls):
        cls.test_dir.cleanup()

    # =================================================================
    # 1. PC MASTER FACTORY & SQLITE VERİTABANI TESTLERİ
    # =================================================================
    def test_factory_state_manager_null_handling(self):
        """
        [Kritik] StateManager (SQLite) çökme testi:
        Geçersiz veya boş ürün ID'si gönderildiğinde db kilitlenmemelidir.
        """
        if not master_factory:
            self.skipTest("pc_master_factory modülü bulunamadı.")
            
        with patch('pc_master_factory.DB_PATH', self.test_path / "test.db"):
            sm = master_factory.StateManager()
            
            # None veri beslemesi (Defensive: Exception atmadan false dönmeli veya engellemeli)
            try:
                sm.mark_processed(None, "K1", "01_Wifi_Kutusu")
                result = sm.is_processed(None, "K1", "01_Wifi_Kutusu")
                self.assertFalse(result, "Null ID processed olarak işaretlenmemelidir!")
            except Exception as e:
                self.fail(f"StateManager None değer aldığında çöktü: {e}")

    def test_factory_fast_excel_manager_empty_data(self):
        """
        [Orta] FastExcelManager boş veri listesiyle çağrıldığında
        çökmek yerine uyarı vermelidir.
        """
        if not master_factory:
            self.skipTest("pc_master_factory modülü bulunamadı.")
            
        test_excel = self.test_path / "test_out.xlsx"
        manager = master_factory.FastExcelManager(test_excel)
        
        try:
            # Boş dict gönderiyoruz (Key error veya attribute error olmamalı)
            manager.append_row({})
            manager.save()
            self.assertTrue(test_excel.exists())
        except Exception as e:
            self.fail(f"ExcelManager eksik veride çöktü: {e}")

    # =================================================================
    # 2. MANUEL MOCKUP MOTORU UÇ NOKTA TESTLERİ
    # =================================================================
    @patch('manuel_mockup_motoru.MANUAL_DIR')
    def test_manuel_motor_klasor_bosken_cokmemeli(self, mock_manual_dir):
        """
        [Kritik] MOCKUP A HAZIR GÖRSELLER klasörü boş veya silinmişse,
        sistem sonsuz döngüye girmemeli veya list index out of range vermemeli.
        """
        if not manuel_motor:
            self.skipTest("manuel_mockup_motoru bulunamadı.")
            
        mock_manual_dir.exists.return_value = False
        
        # Çökme olmamalı, sadece log uyarı vermeli ve None dönmeli
        try:
            result = manuel_motor.get_manual_images()
            self.assertEqual(result, [], "Klasör yokken boş liste dönmelidir.")
            
            # Ana process fonksiyonu hata atmadan bitmelidir
            manuel_motor.process_manual_images()
        except Exception as e:
            self.fail(f"Manuel Mockup Motoru klasör yokken çöktü: {e}")

    def test_manuel_motor_adapt_orientation_corrupted_image(self):
        """
        [Yüksek] Kırpma/Adaptasyon motoruna bozuk bir resim yollanınca
        sistem Pillow Error fırlatıp durmamalı, orijinali dönmeli veya atlamalı.
        """
        if not manuel_motor:
            self.skipTest("manuel_mockup_motoru bulunamadı.")
            
        fake_img_path = self.test_path / "corrupted.jpg"
        with open(fake_img_path, "wb") as f:
            f.write(b"This is not a real image data") # Sahte veri
            
        try:
            result = manuel_motor.adapt_image_for_orientation(fake_img_path, "H")
            # Defensive programming: Hata aldığında orijinal yolu geri döndürmeli
            self.assertEqual(result, fake_img_path)
        except Exception as e:
            self.fail(f"Resim kırpma (adapt) fonksiyonu bozuk resimde çöktü: {e}")

    # =================================================================
    # 3. AI KALİTE MOTORU TESTLERİ
    # =================================================================
    def test_kalite_motoru_hatali_katsayi(self):
        """
        [Kritik] AI Motoruna kat sayısı olarak string veya absürt bir değer 
        (örn: 1000) geldiğinde motorun güvenli çalışması test edilir.
        """
        import AI_Kalite_Artirici.kalite_motoru as kalite_motoru
        
        with patch('AI_Kalite_Artirici.kalite_motoru.os.path.exists') as mock_exists, \
             patch('AI_Kalite_Artirici.kalite_motoru.klasor_sec') as mock_sec, \
             patch('subprocess.run') as mock_run:
             
            # Her şey varmış gibi davran
            mock_exists.return_value = True
            mock_sec.return_value = str(self.test_path)
            
            # test_path içine sahte bir resim atalım
            with open(self.test_path / "test.jpg", "w") as f: f.write("test")
            
            try:
                # Absürt bir değer atıyoruz. 
                # Gerçekte argüman olarak "absurt" gidebilir ama uygulama çökmemeli.
                kalite_motoru.kalite_artir("absurt")
            except Exception as e:
                self.fail(f"AI Motoru yanlış kat sayısında çöktü: {e}")

if __name__ == '__main__':
    print("================================================================")
    print("SİSTEM ÇAPINDA QA (KALİTE GÜVENCE) VE SAVUNMA TESTLERİ BAŞLIYOR")
    print("================================================================")
    unittest.main(verbosity=2)
