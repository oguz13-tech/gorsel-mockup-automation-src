import re

with open('SABLON_DUZELTICI.py', 'r', encoding='utf-8') as f:
    code = f.read()
match = re.search(r'HTML_CONTENT = \"\"\"(.*?)\"\"\"', code, re.DOTALL)
if match:
    html = match.group(1)
    with open('debug_html.html', 'w', encoding='utf-8') as out:
        out.write(html)
    print('HTML dumped to debug_html.html')
else:
    print('HTML_CONTENT not found')
