"""Read-only candidate selection from a disposable DB copy."""
import contextlib,json,math,sqlite3
from collections import Counter
from pathlib import PurePosixPath
from session_safety import digest
import checks

ORIENTATIONS={'01_Wifi_Kutusu':'H','02_Cam_Tablo_Dikey':'V','02_Cam_Tablo_Yatay':'H','03_Ahsap_Tablo':'V','04_Cam_Dograma':None,'05_Ocak_Arkasi':'H'}

def compatible(width,height,row):
    try:
        nominal=float(row['nominal_aspect']);orientation=row['orientation']
        return math.isfinite(nominal) and nominal>0 and ((orientation=='H' and width>height and nominal>1) or (orientation=='V' and width<height and nominal<1)) and abs((width/height)/nominal-1)<=.15
    except (ValueError,TypeError,KeyError,ZeroDivisionError):return False

def discover(db,categories,known,runtime,backup,manifest,limit=2):
    selected=[];audit={'skipped':[],'eligible':[],'per_category_limit':limit,'new_templates_only':True};counts=Counter()
    with contextlib.closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as conn:
        conn.row_factory=sqlite3.Row
        if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('DB kopyasi bozuk.')
        rows=[dict(r) for r in conn.execute('SELECT * FROM template_profiles WHERE is_active=1 ORDER BY category,template_uid')]
        multiplicity=Counter(r['template_uid'] for r in rows)
        for row in rows:
            cat=row['category'];uid=row['template_uid']
            if cat not in categories or cat not in ORIENTATIONS or uid in known:continue
            try:
                if multiplicity[uid]!=1:raise ValueError('Birden fazla aktif profil')
                if row['review_status']!='APPROVED' or row['manually_verified']!=1:raise ValueError('Insan onayi eksik')
                if row['has_occlusion']:raise ValueError('On plan engeli')
                orient=row['orientation'];nominal=float(row['nominal_aspect'])
                if not compatible(400 if orient=='H' else 300,300 if orient=='H' else 400,{'orientation':orient,'nominal_aspect':4/3 if orient=='H' else 3/4}):raise ValueError('Yon eksik')
                if not math.isfinite(nominal) or nominal<=0 or (orient=='H')!=(nominal>1):raise ValueError('Fiziksel oran tutarsiz')
                if ORIENTATIONS[cat] and orient!=ORIENTATIONS[cat]:raise ValueError('Kategori yonu uyumsuz')
                if cat=='04_Cam_Dograma':
                    evidence=json.loads(row['component_confidences']) if isinstance(row['component_confidences'],str) else row['component_confidences']
                    marker=(evidence or {}).get('physical_orientation_verified')
                    if not (marker.strip().lower() in ('1','true','yes') if isinstance(marker,str) else bool(marker)):raise ValueError('Fiziksel yon onayi eksik')
                rel=row['source_relative_path'];parts=PurePosixPath(rel).parts
                if len(parts)!=2 or parts[0]!=cat or '..' in parts or '\\' in rel or ':' in rel or PurePosixPath(rel).is_absolute():raise ValueError('Guvensiz kaynak yolu')
                legacy=conn.execute('SELECT data FROM templates WHERE category_id=? AND filename=?',(cat,parts[1])).fetchall()
                if len(legacy)!=1:raise ValueError('Tek kaynak kaydi gerekli')
                data=json.loads(legacy[0][0])
                if not isinstance(data,dict) or data.get('on_plan'):raise ValueError('On plan plani inceleme gerektiriyor')
                quad=json.loads(row['surface_quad'])
                if len(quad)!=4 or any(len(p)!=2 or any(not math.isfinite(float(v)) for v in p) for p in quad):raise ValueError('Gecersiz dort kose')
                for pool in ('2_SABLON_HAVUZU','2_SABLON_HAVUZU_ORIJINAL_YEDEK'):
                    key=pool+'/'+rel
                    if key not in manifest:raise ValueError('Dogrulanmis yedekte yok')
                    for root,field in ((runtime,'source_sha256'),(backup,'backup_sha256')):
                        path=root/key;checks.no_redirect(path)
                        if not path.is_file() or digest(path).upper()!=manifest[key][field].upper():raise ValueError('Kaynak veya yedek degismis')
                    if manifest[key]['source_sha256'].upper()!=manifest[key]['backup_sha256'].upper():raise ValueError('Yedek esit degil')
                if digest(backup/'2_SABLON_HAVUZU'/rel)!=row['source_asset_sha256']:raise ValueError('Onay kaynak SHA uyusmazligi')
                audit['eligible'].append(uid)
                if limit is None or counts[cat]<limit:
                    selected.append({'category':cat,'uid':uid,'relative':rel});counts[cat]+=1
            except (ValueError,TypeError,KeyError,OSError,RuntimeError) as exc:
                audit['skipped'].append({'template_uid':uid,'reason':str(exc)})
    audit['selected_count']=len(selected);audit['remaining_eligible_count']=len(audit['eligible'])-len(selected)
    return selected,audit
