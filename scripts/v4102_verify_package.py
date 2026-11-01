"""V4.10.2 extracted file manifest verifier; read-only, no user data touched."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]

def main():
    try:
        obj=json.loads((ROOT/'SHA256_MANIFEST.json').read_text('utf-8'))
        if obj.get('version') not in ('V4.10.2', 'V4.10.2+F07_STORE_BULK_UNASSIGN_CANDIDATE', 'MOR_VNEXT_UI_PARTIAL_20261031', 'PETEK_MEASURED_GEOMETRY_VNEXT_20261101', 'PETEK_DYNAMIC_13_16_CURVE_BRUSH_20261101', 'PETEK_DYNAMIC_PREVIEW_ACCEPT_REAL_13_16_20261101', 'MAGAZA_URETIM_SECIM_TESHIS_VNEXT_20261101', 'STORE_P0_ISSUE79_20261101', 'PETEK_OPTIONAL_AB_STRAIGHT_VENTS_20261101', 'PETEK_OPTIONAL_AB_STRAIGHT_VENTS_20261101_R2', 'PETEK_SOFTEDGE_TONE_20261101', 'PETEK_DOGAL_BEYAZ_UZUN_GOLGE_20261101', 'PETEK_BELIRGIN_GOLGE_BAT_FIX_20261101', 'PETEK_RENDER_PARITY_GEOMETRY_VNEXT_20261101', 'PETEK_8080_HTML_JSON_PORT_FIX_20261101', 'PETEK_HTTP500_MODULE_IMPORT_FIX_20261101', 'PETEK_PINK409_ARTWORK_REFERENCE_FIX_20261101', 'PETEK_PROTECTED_SOURCE_IMMUTABLE_FIX_20261101', 'PETEK_PEMBE_SACAK_ONARIM_GERI_20261101', 'PETEK_SOURCE_MARKER_ALL_EDGES_GRADIENT_LONG_SHADOWS_20261101', 'PETEK_HORIZONTAL_SHADOW_LEFT_WHITE_GRADIENT_20261101', 'PETEK_EDGE_REALISM_PRINT_ONLY_20261101', 'PETEK_2_WALL_SCENE_SHADOWS_20261101', 'SEVEN_CATEGORY_PHOTO_DAYLIGHT_V1_20261101', 'SEVEN_CATEGORY_PHOTO_DAYLIGHT_V2_LIGHTER_WHITE_20261101', 'SEVEN_CATEGORY_LIGHTER_WHITE_PETEK_CORNER_GRAZE_V1_20261101'):raise ValueError('Version mismatch')
        records=obj['files'];names=set();faults=[]
        for row in records:
            rel=row['path']
            if not isinstance(rel,str) or rel.startswith('/') or '..' in Path(rel).parts or rel in names:
                faults.append((rel,'path/duplicate'));continue
            names.add(rel)
            target=ROOT/rel
            if target.is_symlink() or not target.is_file():faults.append((rel,'missing/symlink'));continue
            if target.stat().st_size!=row['bytes'] or hashlib.sha256(target.read_bytes()).hexdigest()!=row['sha256']:
                faults.append((rel,'SHA256/size mismatch'))
        print('V4.10.2 manifest:',len(records),'file, error:',len(faults))
        for row in faults[:15]:print('ERROR',row)
        return 0 if not faults else 1
    except (OSError,ValueError,TypeError,KeyError) as e:
        print('MANIFEST ERROR:',str(e));return 1
if __name__=='__main__':sys.exit(main())
