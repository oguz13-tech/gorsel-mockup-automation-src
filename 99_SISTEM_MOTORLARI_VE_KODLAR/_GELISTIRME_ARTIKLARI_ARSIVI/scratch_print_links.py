import json

with open("TEST_13ER_TANE_SONUCLAR.json", "r", encoding="utf-8") as f:
    d = json.load(f)

targets = [
    "TEST_ct-M_02_Gemini_Generated_Image_484mjl484mjl484m (2).jpg",
    "TEST_ct-M_03_Gemini_Generated_Image_484mjl484mjl484m (4).jpg",
    "TEST_ct-M_04_Gemini_Generated_Image_484mjl484mjl484m (5).jpg",
    "TEST_ct-M_11_Gemini_Generated_Image_jv0dmwjv0dmwjv0d.jpg",
    "TEST_ct-M_12_Gemini_Generated_Image_pu3lkgpu3lkgpu3l.jpg",
    "TEST_ct-M_13_085603757622e65a356d0ab700c4eb5b.jpg",
    "TEST_cty-M_12_c0a3fa27a2aab9fc9ec71014913b5474.jpg",
    "TEST_cty-M_13_il_1140xN.7596374617_r1g4.jpg",
    "TEST_oact-M_04_1_org_zoom (2).jpg",
    "TEST_oact-M_05_1_org_zoom (3).jpg",
    "TEST_oact-M_06_1_org_zoom (4).jpg",
    "TEST_oact-M_09_2222.jpg"
]

for cat, items in d.get("kategoriler", {}).items():
    for it in items:
        if it["filename"] in targets:
            print(f"{it['filename']} -> {it['url']}")
