import json

with open("TEST_13ER_TANE_SONUCLAR.json", "r", encoding="utf-8") as f:
    data = json.load(f)

lines = []
lines.append("# Test Mockupları (13'er Tane)")
lines.append(f"Toplam Üretilen ve Buluta Yüklenen Mockup: {data['toplam_mockup']}")
lines.append(f"Toplu ZIP İndirme Dosyası: {data['zip_dosyasi']}\n")

for cat, items in data["kategoriler"].items():
    lines.append(f"## {cat} ({len(items)} Adet)")
    for it in items:
        lines.append(f"- [{it['filename']}]({it['url']})")
    lines.append("")

with open("TEST_LINKS.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("TEST_LINKS.md oluşturuldu!")
