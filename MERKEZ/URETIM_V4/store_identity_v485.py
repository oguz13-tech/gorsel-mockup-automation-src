"""User-approved shared design identity and per-store SKU/filename contract.

A print design is ONE immutable source filename across selected stores.
This module does not visually hash mockups, compute perceptual similarity,
publish images or mutate the existing production ledger.
"""
from __future__ import annotations
from pathlib import Path
import re
import unicodedata

CODES={
    '01_Wifi_Kutusu':'WifiKutusu',
    '02_Cam_Tablo_Dikey':'CamTabloDikey',
    '02_Cam_Tablo_Yatay':'CamTabloYatay',
    '03_Ahsap_Tablo':'AhsapTablo',
    '04_Cam_Dograma':'CamDograma',
    '05_Ocak_Arkasi':'OcakArkasi',
    '06_Petek_Kapama':'PetekDolabi',
}
# Trendyol'un mağaza/kategori alanlarında kullanılan kalıcı kod sözleşmesi.
# ``store_codes`` geçmiş ledger kayıtlarının geriye dönük uyumluluğu için
# korunur; yeni Excel üretimi ``trendyol_codes`` kullanır.
TRENDYOL_CATEGORY_CODES = {
    '01_Wifi_Kutusu': ('Wifi', 'Wifi'),
    '06_Petek_Kapama': ('Petek', 'Pet'),
    '05_Ocak_Arkasi': ('OcakArka', 'Ock'),
    '02_Cam_Tablo_Yatay': ('YtyCamTablo', 'YCam'),
    '02_Cam_Tablo_Dikey': ('DkyCamTablo', 'DCam'),
    '03_Ahsap_Tablo': ('AhspTablo', 'Ahs'),
    '04_Cam_Dograma': ('CamDograma', 'CDog'),
}
DEFAULT_STORE_SHORT_CODES = {'OmzHome': 'OMZ', 'Adeno': 'ADN', 'Wudie': 'WUD'}
_DEFAULT_STORE_SHORT_CODES_CASEFOLD = {k.casefold(): v for k, v in DEFAULT_STORE_SHORT_CODES.items()}
_TRENDYOL_PART = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$')
_SAFE=re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$')
_STOCK=re.compile(r'^([A-Za-z0-9][A-Za-z0-9._-]{0,119})-'
                   r'(WifiKutusu|CamTabloDikey|CamTabloYatay|AhsapTablo|CamDograma|OcakArkasi|PetekDolabi)-'
                   r'([A-Za-z0-9_][A-Za-z0-9_-]{1,35})$')

# PETEK marketplace rows are variants of one product family.  Their order is
# part of the operator-facing Excel contract and must not depend on lexical
# ordering (which puts ``116`` before ``76``).  Keep this rule in the shared
# identity module so every exporter uses the same order.
PETEK_MEASUREMENT_ORDER = {'76': 0, '96': 1, '116': 2, '136': 3}
_PETEK_MEASUREMENT_PREFIX = re.compile(r'^(76|96|116|136)-', re.IGNORECASE)


def _natural_text_key(value: object) -> tuple:
    """Return a deterministic, case-insensitive natural-sort key."""
    text = str(value or '').casefold()
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in re.split(r'(\d+)', text)
        if part
    )


def excel_row_sort_key(item: object) -> tuple:
    """Sort a complete commercial row without separating linked fields.

    ``item`` may be a ledger record dict, a product identity tuple
    ``(sku, barcode, model, category)``, or a row-like object.  PETEK rows are
    ordered by the fixed measurement sequence 76, 96, 116, 136, then by their
    unprefixed product/design identity.  Other categories retain category
    grouping and use deterministic natural ordering of their SKU.
    """
    category = ''
    sku = ''
    art_name = ''
    uid = ''
    if isinstance(item, dict):
        category = str(item.get('category') or '')
        sku = str(item.get('sku') or item.get('Stok Kodu') or '')
        art_name = str(item.get('art_name') or item.get('Ham Baskı Dosyası') or '')
        uid = str(item.get('uid') or item.get('Mockup Dosyası') or '')
    elif isinstance(item, (tuple, list)):
        # Product identity tuples put category in position four.  For a
        # nested ``rows.items()`` value, the caller passes item[0] explicitly.
        values = list(item)
        sku = str(values[0] if values else '')
        category = str(values[3] if len(values) > 3 else '')
        uid = str(values[4] if len(values) > 4 else '')
    else:
        sku = Path(str(item)).name if isinstance(item, Path) else str(item or '')

    match = _PETEK_MEASUREMENT_PREFIX.match(sku)
    match_source = 'sku'
    if match is None:
        match = _PETEK_MEASUREMENT_PREFIX.match(art_name)
        match_source = 'art_name'
    measurement = match.group(1) if match else None
    measurement_rank = PETEK_MEASUREMENT_ORDER.get(measurement, len(PETEK_MEASUREMENT_ORDER))
    base = sku[match.end():] if match and match_source == 'sku' else sku
    if match and match_source == 'art_name' and not sku:
        base = art_name[match.end():]
    # The product/design identity must be the primary key.  Putting
    # ``measurement_rank`` before ``base`` groups every 76 cm row together,
    # then every 96 cm row, which is the historical ordering bug.  Keeping
    # the measurement as the second key makes each design contiguous while
    # still enforcing 76 -> 96 -> 116 -> 136 inside that design.  The tuple
    # is used to sort complete row identities, so codes and image URLs remain
    # attached to the same product row.
    return (
        category.casefold(),
        _natural_text_key(base),
        measurement_rank,
        _natural_text_key(art_name),
        _natural_text_key(uid),
    )

def default_store_short_code(store: str) -> str | None:
    return _DEFAULT_STORE_SHORT_CODES_CASEFOLD.get(str(store or '').casefold())


def design_number(design_path: str | Path) -> str:
    """Return the real artwork filename without *only* its image extension.

    The old implementation used ``Path.stem`` and then applied a numeric
    identifier policy.  That silently rejected perfectly valid names such as
    ``Yatay_Tasarim001.v2.png`` and encouraged callers to invent counters.
    Keep the original stem (including dots and leading zeroes) and fail only
    for unsafe path/control characters.
    """
    raw = Path(str(design_path)).name
    lower = raw.casefold()
    for extension in ('.jpeg', '.webp', '.png', '.jpg'):
        if lower.endswith(extension):
            raw = raw[:-len(extension)]
            break
    number = raw
    if not _TRENDYOL_PART.fullmatch(number) or any(ord(c) < 32 for c in number):
        raise ValueError('HAM_TASARIM_NUMARASI_GUVENSIZ: '+number[:80])
    return number


def normalize_short_code(value: str) -> str:
    """Validate a user-managed, stable store short code."""
    code = str(value or '').strip().upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{1,11}', code):
        raise ValueError('MAGAZA_KISA_KODU_GECERSIZ: 2-12 harf/rakam bekleniyor')
    return code


def trendyol_store_short_code(store: str, configured: str | None = None) -> str:
    """Resolve a store short code without deriving it from generated files.

    Known stores have the requested defaults.  A configured value always wins;
    unknown stores must have an explicit value in the store settings.
    """
    name = str(store or '').strip()
    if not _TRENDYOL_PART.fullmatch(name) or name == 'LOCAL':
        raise ValueError('MAGAZA_ADI_GUVENSIZ: ' + name[:80])
    value = configured if configured is not None else default_store_short_code(name)
    if value is None:
        raise ValueError('MAGAZA_KISA_KODU_TANIMSIZ: ' + name)
    return normalize_short_code(value)


def trendyol_codes(design_name: str | Path, store: str, category: str,
                   *, store_short_code: str | None = None) -> dict:
    """Build the immutable three-code Trendyol identity for one product.

    ``design_name`` is the raw artwork filename; only a supported image
    extension is removed.  No counters, direction labels, template ids or
    generated mockup names enter these values.
    """
    visual = design_number(design_name)
    try:
        category_full, category_short = TRENDYOL_CATEGORY_CODES[category]
    except KeyError as exc:
        raise ValueError('KATEGORI_KODU_TANIMSIZ: ' + str(category)) from exc
    store_name = str(store or '').strip()
    # Existing profiles may contain the historical lowercase ids ``adeno`` /
    # ``wudie``.  Keep their folder/ledger identity intact while using the
    # requested canonical full store name inside new Trendyol codes.
    for canonical in DEFAULT_STORE_SHORT_CODES:
        if canonical.casefold() == store_name.casefold():
            store_name = canonical
            break
    store_short = trendyol_store_short_code(store_name, store_short_code)
    values = {
        'sku': f'{visual}_{category_full}_{store_name}',
        'barcode': f'{visual}_{category_short}_{store_short}',
        'model': f'{visual}_{store_short}_{category_short}',
        'design_name': visual,
        'design_number': visual,
        'store': store_name,
        'store_short_code': store_short,
        'category': category,
        'category_full_code': category_full,
        'category_short_code': category_short,
    }
    return values


def validate_trendyol_codes(codes: dict) -> list[str]:
    """Return explicit field errors; values are never silently truncated."""
    limits = {'sku': 100, 'barcode': 40, 'model': 40}
    errors = []
    for field, limit in limits.items():
        value = str(codes.get(field) or '')
        if not value:
            errors.append(f'{field}: boş')
        elif len(value) > limit:
            errors.append(f'{field}: {len(value)}/{limit} karakter')
    return errors


def petek_measurement_codes(base: dict, cm: str) -> dict:
    """Return PETEK's measurement family identity without changing the model.

    The base ``trendyol_codes`` result remains authoritative.  Only SKU and
    barcode receive the required ``76-``/``96-``/``116-``/``136-`` prefix;
    model code is intentionally byte-for-byte identical across the four rows.
    """
    value = str(cm or '').upper()
    if value.endswith('CM'):
        value = value[:-2]
    if value not in {'76', '96', '116', '136'}:
        raise ValueError('PETEK_OLCU_GECERSIZ: ' + str(cm))
    result = dict(base)
    def unprefix(text: str) -> str:
        for prefix in ('76-', '96-', '116-', '136-'):
            if text.startswith(prefix):
                return text[len(prefix):]
        return text
    sku = unprefix(str(base['sku']))
    barcode = unprefix(str(base['barcode']))
    result['sku'] = f'{value}-{sku}'
    result['barcode'] = f'{value}-{barcode}'
    result['petek_cm'] = value + 'CM'
    return result


def store_codes(number:str,store:str,category:str)->dict:
    if not _SAFE.fullmatch(str(number)) or not _SAFE.fullmatch(str(store)) or store=='LOCAL':
        raise ValueError('MAGAZA_VE_TASARIM_KODU_GUVENSIZ')
    code=CODES.get(category)
    if code is None:raise ValueError('KATEGORI_KODU_TANIMSIZ')
    sku=f'{number}-{code}-{store}'
    return {'sku':sku,'barcode':sku,'model':f'{number}-{store}-{code}',
            'category_code':code,'design_number':number,'store':store}


def codes_from_sku(sku:str)->dict|None:
    # Ambiguous '-' inside names is addressed by using ledger-backed
    # design/store identifiers in new exports, not parsing old hashed SKUs.
    # This parser is only for already-generated codes, with suffix store.
    text = str(sku)
    # New Trendyol SKU: <raw artwork>_<full category>_<full store>.
    for category, (full, short) in TRENDYOL_CATEGORY_CODES.items():
        marker = '_' + full + '_'
        if marker in text:
            design, store = text.rsplit(marker, 1)
            try:
                parsed = trendyol_codes(design, store, category)
            except ValueError:
                parsed = None
            if parsed and parsed['sku'] == text:
                return parsed
    match=_STOCK.fullmatch(text)
    if not match:return None
    design,category_code,store=match.groups()
    if store=='LOCAL':return None
    return {'sku':sku,'barcode':sku,'model':f'{design}-{store}-{category_code}',
            'category_code':category_code,'design_number':design,'store':store}


def template_token(uid:str)->str:
    ident=str(uid)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,96}',ident):
        raise ValueError('SABLON_KIMLIGI_GUVENSIZ')
    hit=re.search(r'(\d+)$',ident)
    return 'TPL'+hit.group(1).zfill(3) if hit else 'TPL_'+ident


def filename(number:str,store:str,category:str,uid:str,variant:int=1,extension:str='.png')->str:
    ids=store_codes(number,store,category)
    if not isinstance(variant,int) or not 1<=variant<=99:
        raise ValueError('MOCKUP_VARYANTI_GECERSIZ')
    if extension not in ('.png','.jpg','.jpeg','.webp'):
        raise ValueError('MOCKUP_UZANTISI_GECERSIZ')
    return f"{number}__{store}__{ids['category_code']}__{template_token(uid)}__V{variant:02d}{extension}"
