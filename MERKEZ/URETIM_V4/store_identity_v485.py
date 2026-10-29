"""User-approved shared design identity and per-store SKU/filename contract.

A print design is ONE immutable numbered source across selected stores.
This module does not visually hash mockups, compute perceptual similarity,
publish images or mutate the existing production ledger.
"""
from __future__ import annotations
from pathlib import Path
import re

CODES={
    '01_Wifi_Kutusu':'WifiKutusu',
    '02_Cam_Tablo_Dikey':'CamTabloDikey',
    '02_Cam_Tablo_Yatay':'CamTabloYatay',
    '03_Ahsap_Tablo':'AhsapTablo',
    '04_Cam_Dograma':'CamDograma',
    '05_Ocak_Arkasi':'OcakArkasi',
    '06_Petek_Kapama':'PetekDolabi',
}
_SAFE=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$')
_STOCK=re.compile(r'^([A-Za-z0-9][A-Za-z0-9_-]{0,79})-'
                   r'(WifiKutusu|CamTabloDikey|CamTabloYatay|AhsapTablo|CamDograma|OcakArkasi|PetekDolabi)-'
                   r'([A-Za-z0-9_][A-Za-z0-9_-]{1,35})$')


def design_number(design_path: str | Path) -> str:
    # No trimming, renumbering, stripping leading zeros or silent conversion.
    number=Path(design_path).stem
    if not _SAFE.fullmatch(number):
        raise ValueError('HAM_TASARIM_NUMARASI_GUVENSIZ: '+number[:80])
    return number


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
    match=_STOCK.fullmatch(str(sku))
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
