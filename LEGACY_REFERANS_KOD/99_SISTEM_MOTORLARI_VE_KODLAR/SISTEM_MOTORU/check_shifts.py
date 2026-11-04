import json

d1 = json.load(open('C:\\Users\\oguzc\\OneDrive\\Masaüstü\\GörselÜretme-ve-Mockup Otomasyonu\\99_SISTEM_MOTORLARI_VE_KODLAR\\SISTEM_MOTORU\\ayarlar.json.user_backup_20260920_000450', encoding='utf-8'))
d2 = json.load(open('C:\\Users\\oguzc\\OneDrive\\Masaüstü\\GörselÜretme-ve-Mockup Otomasyonu\\99_SISTEM_MOTORLARI_VE_KODLAR\\SISTEM_MOTORU\\ayarlar.json.user_backup_20260920_001352', encoding='utf-8'))

for cat in d1['kategoriler']:
    if cat not in d2['kategoriler']: continue
    
    list1 = list(d1['kategoriler'][cat]['sablonlar'].keys())
    list2 = list(d2['kategoriler'][cat]['sablonlar'].keys())
    
    print(f"--- {cat} ---")
    for i in range(min(len(list1), len(list2))):
        name1 = list1[i].replace('.jpeg', '.png').replace('.webp', '.png').replace('.jpg', '.png')
        name2 = list2[i]
        if name1 != name2:
            print(f"Shift detected: Original {name1} -> Shifted {name2}")
