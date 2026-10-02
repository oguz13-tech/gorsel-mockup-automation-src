import urllib.request
import urllib.error
import json

url = 'http://127.0.0.1:8999/api/ayarlar'
data = {
    "kategoriler": {
        "01_Wifi_Kutusu": {
            "sablonlar": {
                "Wifi_Kutusu_001.png": {}
            }
        }
    }
}
payload = json.dumps(data).encode('utf-8')

req = urllib.request.Request(url, data=payload, method='POST')
req.add_header('Content-Type', 'application/json')
req.add_header('Content-Length', str(len(payload)))

try:
    with urllib.request.urlopen(req) as response:
        print(f"Başarılı (Beklenmiyordu!): {response.status}")
except urllib.error.HTTPError as e:
    print(f"Hata kodu (Beklenen): {e.code}")
    print(f"Hata mesajı: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Sunucuya ulaşılamadı veya hata: {e}")
