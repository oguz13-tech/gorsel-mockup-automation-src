"""Ensure the browser CSS and Tk dashboard consume the same purple token values."""
from pathlib import Path
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
TOKENS=ROOT/'MERKEZ/ui_mor_tokens_vnext.json'
CSS=ROOT/'SABLON_V2_MIMARI/static/css/mor_premium_vnext.css'


def test_theme_shared_tokens_match_css_and_tk():
    t=json.loads(TOKENS.read_text(encoding='utf-8'))
    css=CSS.read_text(encoding='utf-8')
    for field in ['background','panel','border','accent','text','muted']:
        cssname='--mor-'+field
        expr=re.compile(r'(?m)^\s*'+re.escape(cssname)+r':\s*(#[0-9a-fA-F]{6})\s*;')
        got=expr.search(css)
        assert got is not None,(field,'CSS missing')
        assert got.group(1).upper()==t[field].upper(),field
    sys.path.insert(0,str(ROOT/'MERKEZ'))
    import dark_theme_v42 as dark
    for var,field in [('BG','background'),('PANEL','panel'),('ENTRY','raised'),
                      ('FG','text'),('ACCENT','accent')]:
        assert getattr(dark,var).upper()==t[field].upper(),field
