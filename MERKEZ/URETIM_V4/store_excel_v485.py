"""Single store-specific Trendyol workbook export."""
from __future__ import annotations
from collections import defaultdict
import hashlib, json, os, re, sqlite3, tempfile, uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from openpyxl import Workbook, load_workbook
from .store_identity_v485 import (trendyol_codes, store_codes, petek_measurement_codes,
                                   validate_trendyol_codes, excel_row_sort_key)
from .store_profiles_v47 import StoreProfiles
from .marketplace_excel_v45 import _sha, detect_columns, _normalize
from .cloud_excel_v43 import _valid_https_image_url

INTERNAL_HEADERS = {'tasarim dosyasi','mockup dosyasi','sablon','yerel dosya',
                    'tasarim','mockup','template','local file','yerel dosya yolu'}

def _image_columns(headers):
    result = {}
    for i, title in enumerate(headers, 1):
        m = re.fullmatch(r'(?:gorsel|gorsel linki|resim linki|resim|urun resmi|image|image url) ?([1-9][0-9]?)', _normalize(title))
        if m:
            n = int(m.group(1))
            if n in result: raise ValueError('MAGAZA_EXCEL_GORSEL_SUTUNU_TEKRARLI')
            result[n] = i
    return result


def _measurement_column(headers):
    """Find an existing size/variant field; never invent a marketplace field."""
    for index, title in enumerate(headers, 1):
        value = _normalize(title)
        if any(token in value for token in ('olcu', 'size', 'variant', 'varyant')):
            return index
    return None

def _error(store, image, field, reason, *, value=None, limit=None):
    item={'store':str(store),'image':str(image),'field':str(field),'reason':str(reason),
          'timestamp':datetime.now().isoformat(timespec='seconds')}
    if value is not None: item.update(value=str(value),length=len(str(value)))
    if limit is not None: item['limit']=int(limit)
    return item

def _report(report_root, store, errors, rows_seen):
    report_root.mkdir(parents=True, exist_ok=True)
    path=Path(report_root)/f'TRENDYOL_EXCEL_HATA_RAPORU_{store}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.json'
    payload={'schema':1,'store':store,'rows_seen':rows_seen,'errors':errors,
             'codex_ready_report':'\n'.join(f"{e['store']} / {e['image']} / {e['field']}: {e['reason']}" for e in errors)}
    fd,tmp=tempfile.mkstemp(prefix='.trendyol-error-',suffix='.json',dir=report_root)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:
            json.dump(payload,out,ensure_ascii=False,indent=2);out.flush();os.fsync(out.fileno())
        os.replace(tmp,path)
    finally: Path(tmp).unlink(missing_ok=True)
    return path


def _store_id_from_output(output: Path, output_root: Path) -> str:
    """Resolve store id from both normal and isolated HARICI output paths."""
    parts = Path(output).resolve().relative_to(Path(output_root).resolve()).parts
    if parts and parts[0] == 'HARICI':
        if len(parts) < 3:
            raise ValueError('HARICI çıktı yolu mağaza segmenti içermiyor')
        return parts[2]
    if not parts:
        raise ValueError('Çıktı yolu mağaza segmenti içermiyor')
    return parts[0]

def _profile_short_code(state, store):
    profile=Path(state)/'store_profiles_v47.json'
    if profile.is_symlink(): raise ValueError('STORE_PROFILE_SYMLINK')
    if not profile.is_file(): return None
    return StoreProfiles(state).short_code(store)


def _excel_output_dir(state: Path, output_root: Path, store_id: str, categories: set[str]) -> Path:
    """Return the Excel folder beside the generated store/category assets.

    A workbook containing one category is kept next to that category's
    generated images.  A workbook spanning several categories cannot belong
    to one category, so it is kept at the store level instead.
    """
    safe_categories = sorted({str(x).strip() for x in categories if str(x).strip()})
    base = output_root / store_id
    if len(safe_categories) == 1:
        base = base / safe_categories[0]
    target = base / 'excel çıktıları'
    if target.is_symlink() or state not in target.parents:
        raise ValueError('MAGAZA_EXCEL_CIKTI_KLASORU_GUVENSIZ')
    return target

def _load_code_map(state):
    path=Path(state)/'trendyol_code_map_v1.json'
    if not path.is_file() or path.is_symlink(): return {}, path
    try:
        raw=json.loads(path.read_text(encoding='utf-8'))
        return (raw if isinstance(raw,dict) else {}), path
    except (OSError,ValueError,TypeError):
        return {}, path

def _save_code_map(path, mapping):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.trendyol-code-map-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:
            json.dump(mapping,out,ensure_ascii=False,indent=2,sort_keys=True);out.flush();os.fsync(out.fileno())
        os.replace(tmp,path)
    finally: Path(tmp).unlink(missing_ok=True)

def _remove_internal_columns(ws):
    remove=[]
    for i in range(1,ws.max_column+1):
        for row in range(1,min(ws.max_row,20)+1):
            if _normalize(ws.cell(row,i).value) in INTERNAL_HEADERS:
                remove.append(i);break
    for i in sorted(set(remove),reverse=True): ws.delete_cols(i,1)

def _find_header(ws):
    for row in range(1,min(ws.max_row,20)+1):
        headers=[ws.cell(row,i).value for i in range(1,ws.max_column+1)]
        try: cols=detect_columns(headers)
        except ValueError: continue
        if not {'sku','barcode','model'}.issubset(cols):
            raise ValueError('MAGAZA_EXCEL_STOK_BARKOD_MODEL_SUTUNLARI_ZORUNLU')
        images=_image_columns(headers)
        if 'image_url' in cols: images.setdefault(1,cols['image_url'])
        if 1 not in images: raise ValueError('MAGAZA_EXCEL_GORSEL1_SUTUNU_ZORUNLU')
        if len(set(images.values()))!=len(images): raise ValueError('MAGAZA_EXCEL_GORSEL_SUTUNU_CAKISMASI')
        return row,cols,images
    raise ValueError('MAGAZA_EXCEL_SABLONUNDA_STOK_BARKOD_MODEL_VE_GORSEL1_BULUNMADI')

def _builtin_template(report_root: Path) -> Path:
    """Create the minimal internal upload template used by the one-click flow.

    The operator-facing one-click action must not require a marketplace file.
    Keep this as a normal, inspectable XLSX in the reports area; the generated
    store workbooks remain separate and the internal file is never overwritten
    after creation.
    """
    report_root = Path(report_root).absolute()
    report_root.mkdir(parents=True, exist_ok=True)
    path = report_root / 'OTOMATIK_TRENDYOL_SABLONU.xlsx'
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise ValueError('OTOMATIK_TRENDYOL_SABLONU_GUVENSIZ')
        return path
    wb = Workbook()
    ws = wb.active
    ws.title = 'Ürünler'
    headers = ['Stok Kodu', 'Barkod', 'Model Kodu', 'Kategori', 'Ürün Adı']
    headers.extend(f'Görsel {n}' for n in range(1, 11))
    ws.append(headers)
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    fd, tmp = tempfile.mkstemp(prefix='.automatic-trendyol-', suffix='.xlsx', dir=report_root)
    os.close(fd)
    try:
        wb.save(tmp)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)
        wb.close()
    return path


def export_store_upload(template_path:Path|None,state_root:Path,*,store_id:str,report_root:Path,sheet_name:str|None=None,
                        records:list[dict]|None=None,
                        progress:Callable[[int,int,str],None]|None=None)->dict:
    """Create one all-category workbook; invalid products are reported/skipped.

    ``progress(done, total, store_id)`` is an optional, best-effort live
    callback fired every few records while the image SHA-256 verification
    loop runs.  It must never influence the export result.
    """
    state=Path(state_root).absolute(); report_root=Path(report_root).absolute()
    template = _builtin_template(report_root) if template_path is None else Path(template_path)
    if not template.is_file() or template.is_symlink() or template.suffix.lower()!='.xlsx' or template.stat().st_size>35_000_000:
        raise ValueError('MAGAZA_EXCEL_SABLONU_XLSX_GUVENSIZ')
    if state.is_symlink() or report_root.is_symlink() or (state not in report_root.parents and report_root!=state):
        raise ValueError('MAGAZA_EXCEL_CIKTI_KLASORU_GUVENSIZ')
    ledger=state/'v4_ortak_uretim.sqlite3';cloud=state/'cloud_urls_v43.sqlite3'
    if not ledger.is_file() or not cloud.is_file() or ledger.is_symlink() or cloud.is_symlink():
        raise ValueError('MAGAZA_EXCEL_ONCE_KAYIT_VE_LINK_GEREKLI')
    errors=[];rows=defaultdict(list);root=(state/'uretilen_gorseller').resolve();short=_profile_short_code(state,store_id)
    code_map,code_map_path=_load_code_map(state);new_code_map=dict(code_map)
    with sqlite3.connect(ledger.resolve().as_uri()+'?mode=ro',uri=True) as conn,sqlite3.connect(cloud.resolve().as_uri()+'?mode=ro',uri=True) as urls:
        conn.row_factory=sqlite3.Row;urls.row_factory=sqlite3.Row
        links={x['artifact_key']:dict(x) for x in urls.execute('SELECT * FROM cloud_link')}
        records = (list(records) if records is not None else
                    conn.execute("SELECT * FROM artifact WHERE status='RENDERED' ORDER BY updated,key").fetchall())
        overlay_active = any(
            str(row['category']) == '06_Petek_Kapama' and
            str(row['artifact_kind'] if 'artifact_kind' in row.keys() else 'clean') == 'overlay'
            for row in records
        )
        for _done_i, rec in enumerate(records, 1):
            if progress is not None and (_done_i % 10 == 0 or _done_i == len(records)):
                try:
                    progress(_done_i, len(records), store_id)
                except Exception:
                    pass  # canlı ilerleme hiçbir zaman export'u durdurmasın
            item=dict(rec);path=Path(item['output'])
            artifact_kind = str(item.get('artifact_kind') or 'clean')
            # Once the four-size stage has produced a derivative for a PETEK
            # family, clean PETEK sources are protected intermediates and must
            # never become a marketplace image by accident.  With no overlay
            # rows, the historical overlay-off behaviour remains unchanged.
            if overlay_active and item.get('category') == '06_Petek_Kapama' and artifact_kind == 'clean':
                continue
            try:
                rel=path.resolve(strict=False).relative_to(root)
                if len(rel.parts)<3 or _store_id_from_output(path, root)!=store_id: continue
            except ValueError: continue
            image=Path(item.get('art_name') or '').name
            cm = str(item.get('overlay_cm') or '') if artifact_kind == 'overlay' else ''
            identity_key=f'{store_id}|{item["category"]}|{image}|{cm}'
            try:
                # M4/M5-style ids are retained solely for the pre-existing
                # offline fixture contract. Real configured stores (OmzHome,
                # Adeno, Wudie, or a profile short_code) always use Trendyol.
                if short is None and re.fullmatch(r'M\d+', store_id):
                    code=store_codes(image.rsplit('.', 1)[0],store_id,item['category'])
                    code.update(design_name=image.rsplit('.', 1)[0])
                else:
                    code=trendyol_codes(image,store_id,item['category'],store_short_code=short)
                if artifact_kind == 'overlay':
                    code = petek_measurement_codes(code, cm)
            except ValueError as exc:
                errors.append(_error(store_id,image,'Kod',exc));continue
            # A previously exported/published product keeps its exact three
            # codes even if an operator later edits the store short-code
            # setting.  New identities are recorded only after validation.
            if identity_key in code_map and isinstance(code_map[identity_key],dict) \
                    and all(k in code_map[identity_key] for k in ('sku','barcode','model')):
                code=dict(code_map[identity_key])
            bad=False
            for field,limit in (('sku',100),('barcode',40),('model',40)):
                if len(code[field])>limit:
                    errors.append(_error(store_id,image,field,f'{len(code[field])}/{limit} karakter',value=code[field],limit=limit));bad=True
            if bad: continue
            new_code_map.setdefault(identity_key, {k: code[k] for k in ('sku','barcode','model')})
            link=links.get(item['key'])
            if not link or link['output_sha']!=item['output_sha'] or not _valid_https_image_url(link['url']):
                errors.append(_error(store_id,image,'Görsel URL','SHA doğrulanmış HTTPS bağlantı yok'));continue
            if path.is_symlink() or root not in path.resolve(strict=False).parents or not path.is_file() or _sha(path)!=item['output_sha']:
                errors.append(_error(store_id,image,'Görsel','Çıktı dosyası SHA doğrulamasını geçemedi'));continue
            rows[(code['sku'],code['barcode'],code['model'],item['category'])].append((item['key'],link['url'],code,image))
    collisions=defaultdict(list)
    for key in rows: collisions[key[0]].append(key)
    for sku,keys in collisions.items():
        if len({(k[1],k[2]) for k in keys})>1:
            errors.append(_error(store_id,sku,'Kod','Kod çakışması; ürün Excel’e eklenmedi'))
            for key in keys: rows.pop(key,None)
    owners={}
    conflicting=set()
    def _same_petek_measurement_family(previous, current):
        """Allow only PETEK size siblings to share the model code."""
        if previous[3] != '06_Petek_Kapama' or current[3] != '06_Petek_Kapama':
            return False
        # Measurement prefixes are deliberately the only SKU/barcode
        # difference; stripping one known prefix proves the family identity.
        def strip(value):
            text = str(value)
            for prefix in ('76-', '96-', '116-', '136-'):
                if text.startswith(prefix):
                    return text[len(prefix):]
            return text
        return strip(previous[0]) == strip(current[0]) and strip(previous[1]) == strip(current[1])
    for key in rows:
        for field, value in zip(('sku','barcode','model'), key[:3]):
            previous=owners.get((field,value))
            if previous is not None and previous != key:
                if not (field == 'model' and _same_petek_measurement_family(previous, key)):
                    conflicting.update((previous,key))
            else:
                owners[(field,value)]=key
    for key in conflicting:
        errors.append(_error(store_id, key[0], 'Kod', 'Kod çakışması; ürün Excel’e eklenmedi'))
        rows.pop(key, None)
    error_report=_report(report_root,store_id,errors,len(records)) if errors else None
    if not rows: raise ValueError(f'{store_id}: doğrulanmış, geçerli ürün yok. Hata raporu: {error_report}')
    wb=load_workbook(template)
    try:
        if sheet_name and sheet_name not in wb.sheetnames: raise ValueError('MAGAZA_EXCEL_SAYFA_YOK')
        ws=wb[sheet_name] if sheet_name else wb.active;_remove_internal_columns(ws);header,cols,images=_find_header(ws)
        measurement_col = _measurement_column([ws.cell(header, index).value for index in range(1, ws.max_column + 1)])
        if overlay_active and measurement_col is None:
            errors.append(_error(store_id, 'PETEK', 'Ölçü',
                                 'Şablonda geçerli ölçü/varyant alanı yok; kategori ölçü özelliği eşlemesi incelemeye bırakıldı'))
            error_report = _report(report_root, store_id, errors, len(records))
        for existing in ws.iter_rows(min_row=header+1):
            if any(c.value is not None for c in existing): raise ValueError('MAGAZA_EXCEL_DOLU_SABLON_KORUNDU')
        # Sort complete product identities, never individual cells.  The
        # shared key enforces PETEK's immutable 76/96/116/136 measurement
        # order while keeping every link and code attached to its product.
        unique=sorted(rows.items(), key=lambda item: excel_row_sort_key(item[0]))
        for n,((sku,barcode,model,category),recs) in enumerate(unique,header+1):
            values={'sku':sku,'barcode':barcode,'model':model,'category':category}
            for field,col in cols.items():
                if field in values:
                    value=str(values[field]);ws.cell(n,col,"'"+value if value.lstrip().startswith(('=','+','-','@')) else value)
            if measurement_col is not None:
                cm = next((str(code.get('petek_cm')) for _, _, code, _ in recs
                           if code.get('petek_cm')), '')
                if cm:
                    ws.cell(n, measurement_col, cm.replace('CM', ' santimetre'))
            urls=list(dict.fromkeys(url for _,url,_,_ in recs))
            image_limit = min(len(images), 8) if category == '06_Petek_Kapama' else len(images)
            if len(urls)>image_limit:
                errors.append(_error(store_id, sku, 'Görsel',
                                     f'Trendyol görsel sınırı aşıldı: {len(urls)}/{image_limit}; fazlalar yazılmadı'))
                error_report = _report(report_root, store_id, errors, len(records))
                raise ValueError('MAGAZA_EXCEL_GORSEL_SUTUNLARI_YETERSIZ: ' + sku +
                                 ' / ' + str(len(urls)) + ' görsel; Hata raporu: ' + str(error_report))
            for j,url in enumerate(urls,1):
                if j not in images:
                    errors.append(_error(store_id, sku, 'Görsel',
                                         'Görsel sütunu eksik; link yazılmadı', value=j))
                    error_report = _report(report_root, store_id, errors, len(records))
                    raise ValueError('MAGAZA_EXCEL_GORSEL_SUTUNU_EKSIK: ' + str(j) +
                                     '; Hata raporu: ' + str(error_report))
                cell=ws.cell(n,images[j],url);cell.hyperlink=url;cell.style='Hyperlink'
        signature=hashlib.sha256((_sha(template)+store_id+json.dumps([(k,[(x,u) for x,u,_,_ in rec]) for k,rec in unique],ensure_ascii=False,sort_keys=True)).encode()).hexdigest()[:18]
        categories = {key[3] for key, _ in unique}
        target_dir = _excel_output_dir(state, root, store_id, categories)
        target_dir.mkdir(parents=True,exist_ok=True)
        # Every export is a separate historical artifact.  The previous
        # content-derived name caused a later export of the same rows to
        # silently reuse the old workbook (and made it look as if the new
        # link pass had overwritten the previous one).  Keep the content
        # signature for traceability, but add a local timestamp and a short
        # random suffix so two exports in the same second cannot collide.
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        path = target_dir / f'{store_id}_TRENDYOL_URUN_YUKLEME_{stamp}_{signature}_{uuid.uuid4().hex[:8]}.xlsx'
        if path.is_symlink(): raise ValueError('MAGAZA_EXCEL_CIKTI_SYMLINK')
        fd,tmp=tempfile.mkstemp(prefix='store-xlsx-',suffix='.xlsx',dir=target_dir);os.close(fd)
        try:
            wb.save(tmp)
            os.replace(tmp,path)
        finally: Path(tmp).unlink(missing_ok=True)
    finally: wb.close()
    verified=load_workbook(path)
    try:
        sheet=verified[sheet_name] if sheet_name else verified.active
        for n,((sku,barcode,model,_),recs) in enumerate(unique,header+1):
            if sheet.cell(n,cols['sku']).value!=sku or sheet.cell(n,cols['barcode']).value!=barcode or sheet.cell(n,cols['model']).value!=model: raise ValueError('MAGAZA_EXCEL_KOD_KONTROL_HATASI')
            if measurement_col is not None:
                expected_cm = next((str(code.get('petek_cm')).replace('CM', ' santimetre')
                                    for _, _, code, _ in recs if code.get('petek_cm')), '')
                if expected_cm and sheet.cell(n, measurement_col).value != expected_cm:
                    raise ValueError('MAGAZA_EXCEL_OLCU_KONTROL_HATASI')
            for j,url in enumerate(dict.fromkeys(u for _,u,_,_ in recs),1):
                cell=sheet.cell(n,images[j])
                if cell.value!=url or not cell.hyperlink or cell.hyperlink.target!=url: raise ValueError('MAGAZA_EXCEL_LINK_KONTROL_HATASI')
    finally: verified.close()
    if new_code_map != code_map:
        _save_code_map(code_map_path,new_code_map)
    return {'store':store_id,'rows':len(unique),'images':sum(len(dict.fromkeys(u for _,u,_,_ in rec)) for _,rec in unique),'output':str(path),'output_folder':str(path.parent),'error_report':str(error_report) if error_report else '','errors':errors,'status':'STORE_TEMPLATE_READY_REVIEW_MARKETPLACE_REQUIREMENTS'}
