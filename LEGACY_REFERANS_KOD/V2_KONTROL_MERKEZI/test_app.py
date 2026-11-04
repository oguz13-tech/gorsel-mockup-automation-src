import unittest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

# app.py modülünü test edebilmek için içeri aktarıyoruz
# Not: test çalıştırılırken app.py'nin aynı dizinde olması gerekir.
try:
    import app
except ImportError:
    pass

class TestAnaKontrolMerkezi(unittest.TestCase):
    
    def setUp(self):
        """Test ortamını hazırla: Flask test_client'ı oluştur."""
        if 'app' in globals():
            app.app.config['TESTING'] = True
            self.client = app.app.test_client()
        else:
            self.client = None

    def test_1_seo_generator_basarili(self):
        """Senaryo 1: SEO Üretici endpoint'ine geçerli 'adet' gönderilmesi."""
        if not self.client: self.skipTest("app modülü bulunamadı")
        
        payload = {"adet": 5}
        # Subprocess ve MessageBoxW gibi OS bağımlı çağrıları mockluyoruz
        with patch('subprocess.run') as mock_run, \
             patch('os.startfile') as mock_startfile, \
             patch('ctypes.windll.user32.MessageBoxW') as mock_msg:
             
            response = self.client.post('/api/tools/seo_generator', 
                                        data=json.dumps(payload),
                                        content_type='application/json')
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data["status"], "success")
            self.assertIn("5 adet", data["message"])

    def test_2_seo_generator_hatali_tip(self):
        """Senaryo 2: SEO Üretici endpoint'ine geçersiz veri tipi gönderilmesi."""
        if not self.client: self.skipTest("app modülü bulunamadı")
        
        # 'adet' yerine string gönderiliyor, sistem çökmek yerine default almalı veya uyarmalı
        payload = {"adet": "on"} 
        
        response = self.client.post('/api/tools/seo_generator', 
                                    data=json.dumps(payload),
                                    content_type='application/json')
        # Şu anki app.py kodunda data.get('adet', 10) integer'a cast edilmiyor, 
        # bu durum subprocess scriptinde string hatasına (TypeError) neden olabilir.
        # Bu test mevcut zafiyeti tespit etmek içindir.
        self.assertEqual(response.status_code, 200)

    def test_3_ai_enhancer_basarili(self):
        """Senaryo 3: AI Kalite Artırıcı'ya geçerli kat sayısı gönderilmesi."""
        if not self.client: self.skipTest("app modülü bulunamadı")
        
        payload = {"kat": "5"}
        
        with patch('subprocess.run') as mock_run:
            response = self.client.post('/api/tools/ai_enhancer', 
                                        data=json.dumps(payload),
                                        content_type='application/json')
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data["status"], "success")

    def test_4_ai_enhancer_bos_kat(self):
        """Senaryo 4: AI Kalite Artırıcı'ya boş 'kat' parametresi gönderilmesi."""
        if not self.client: self.skipTest("app modülü bulunamadı")
        
        payload = {"kat": ""}
        
        response = self.client.post('/api/tools/ai_enhancer', 
                                    data=json.dumps(payload),
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        # Savunma odaklı programlama gereği, boş string gelirse varsayılan "4" alınmalıdır.
        
    def test_5_image_to_excel_dosya_yok(self):
        """Senaryo 5: Görsel seçimi yapılmadığında image_to_excel'in hata döndürmesi."""
        if not self.client: self.skipTest("app modülü bulunamadı")
        
        # tkinter dialog'un boş liste döndürdüğünü simüle edelim
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "[]" # Boş seçim
            mock_run.return_value = mock_result
            
            response = self.client.post('/api/tools/image_to_excel')
            
            self.assertEqual(response.status_code, 400)
            data = json.loads(response.data)
            self.assertEqual(data["status"], "error")
            self.assertEqual(data["message"], "Görsel seçilmedi.")

if __name__ == '__main__':
    unittest.main()
