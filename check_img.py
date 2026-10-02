import cv2
import numpy as np

img = cv2.imdecode(np.fromfile(r'C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu\2_SABLON_HAVUZU\05_Ocak_Arkasi\OcakArkasi_045.png', dtype=np.uint8), cv2.IMREAD_UNCHANGED)
if img is not None:
    print(img.shape)
    # Check if there is a cyan checkerboard
    # Just save a thumbnail
    resized = cv2.resize(img, (200, 200))
    cv2.imencode('.png', resized)[1].tofile('thumb.png')
    print("Saved thumb")
else:
    print("Image is None")
