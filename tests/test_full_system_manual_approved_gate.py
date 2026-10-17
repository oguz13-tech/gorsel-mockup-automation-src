# -*- coding: utf-8 -*-
"""Manual production must honor immutable REVIEWED source SHA, not legacy JSON."""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
CAT="01_Wifi_Kutusu"
NAME="Wifi_Kutusu_048.png"

CHILD = r'''
import os, sys, sqlite3
from pathlib import Path
sys.path.append("--preflight")
sys.path.insert(0,str(Path.cwd()/"99_SISTEM_MOTORLARI_VE_KODLAR"/"SISTEM_MOTORU"))
from manuel_mockup_motoru import get_template_pool, USER_WORKSPACE_DIR, MANUAL_DIR
root=Path(os.environ["MOCKUP_RUNTIME_WORKSPACE"]).resolve()
assert USER_WORKSPACE_DIR.resolve()==root
assert MANUAL_DIR.parent.resolve()==root
pool=get_template_pool("01_Wifi_Kutusu")
assert len(pool)==1, "APPROVED_VALID_TEMPLATE_NOT_SELECTED:"+str(pool)
name,path,conf=pool[0]
assert name=="Wifi_Kutusu_048.png"
assert conf["output_width"]==1200 and conf["output_height"]==1600
assert conf["marketplace_ready"] is True
assert conf["koseler"]==[[10,12],[90,12],[90,68],[10,68]]
conn=sqlite3.connect(root/"SABLON_V2_MIMARI"/"ayarlar.db")
conn.execute("UPDATE template_profiles SET review_status='REVIEW_REQUIRED'")
conn.commit()
conn.close()
assert get_template_pool("01_Wifi_Kutusu")==[]
print("APPROVED_GATE_AND_GEOMETRY_PASS")
'''

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def test_manual_pipeline_uses_only_sha_verified_approved_profiles_in_correct_workspace():
    with tempfile.TemporaryDirectory(prefix="p0-manual-runtime-") as td:
        runtime=Path(td)/"fake-runtime"
        scene=runtime/"2_SABLON_HAVUZU"/CAT/NAME
        scene.parent.mkdir(parents=True)
        arr=np.full((80,100,3),(190,210,220),dtype=np.uint8)
        ok,buf=cv2.imencode(".png",arr)
        assert ok
        scene.write_bytes(buf.tobytes())
        db=runtime/"SABLON_V2_MIMARI"/"ayarlar.db"
        db.parent.mkdir(parents=True)
        conn=sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("CREATE TABLE categories (id TEXT, label TEXT)")
            conn.execute("CREATE TABLE templates (category_id TEXT, filename TEXT, data TEXT)")
            conn.execute("""CREATE TABLE template_profiles (
                template_uid TEXT, category TEXT, source_relative_path TEXT,
                source_asset_sha256 TEXT, surface_quad TEXT, orientation TEXT,
                nominal_aspect REAL, review_status TEXT, manually_verified INTEGER,
                is_active INTEGER, has_occlusion INTEGER, component_confidences TEXT
            )""")
            conn.execute("INSERT INTO categories VALUES (?,?)",(CAT,"WiFi Kutusu"))
            conn.execute("INSERT INTO templates VALUES (?,?,?)",(CAT,NAME,json.dumps({"koseler":[]},ensure_ascii=False)))
            conn.execute("INSERT INTO template_profiles VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (CAT+"_"+NAME,CAT,CAT+"/"+NAME,digest(scene),
                 json.dumps([[10,12],[90,12],[90,68],[10,68]]),"H",40/30,
                 "APPROVED",1,1,0,"{}"))
            conn.commit()
        finally:
            conn.close()
        before_scene,before_db=digest(scene),digest(db)
        env=os.environ.copy()
        env.update({"MOCKUP_RUNTIME_WORKSPACE":str(runtime),"PYTHONUTF8":"1",
                    "PYTHONDONTWRITEBYTECODE":"1"})
        r=subprocess.run([sys.executable,"-B","-c",CHILD],cwd=str(ROOT),env=env,
                         capture_output=True,text=True,encoding="utf-8",
                         errors="replace",timeout=60)
        assert r.returncode==0,r.stdout+"\n"+r.stderr
        assert "APPROVED_GATE_AND_GEOMETRY_PASS" in r.stdout
        assert digest(scene)==before_scene
        # DB review status was changed ONLY by our synthetic child fixture.
        conn=sqlite3.connect(db)
        try:
            assert conn.execute("SELECT review_status FROM template_profiles").fetchone()[0]=="REVIEW_REQUIRED"
        finally:conn.close()
