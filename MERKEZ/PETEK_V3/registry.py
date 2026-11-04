"""Private source-SHA-bound PETEK V3 immutable mask approval registry."""
from __future__ import annotations
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import tempfile
from . import engine


def store_root():
    """Production output on local Windows disk rather than synchronized OneDrive."""
    override=os.getenv('PETEK_V3_LOCAL_STATE','').strip()
    return Path(override).expanduser().resolve() if override else Path(os.getenv('LOCALAPPDATA') or (Path.home()/'AppData'/'Local'))/'GorselMockup'/'PetekV3'


def _atomic_json(path,data):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():raise engine.MaskError('Veri dosyasi symlink')
    fd,temp=tempfile.mkstemp(prefix='.petek-json-',suffix='.tmp',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(data,f,indent=2,ensure_ascii=False,sort_keys=True)
            f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def _safe_id(value):
    if not re.fullmatch('[A-Za-z0-9_-]{2,100}',str(value or '')):
        raise engine.MaskError('Sablon kimligi gecersiz.')
    return str(value)


class Registry:
    def __init__(self,root=None):
        self.root=Path(root or store_root()).resolve()
        if self.root.is_symlink():raise engine.MaskError('Kayit klasoru symlink.')
        self.profiles=self.root/'profiles'
        self.masks=self.root/'masks'
        self.output=self.root/'uretilen_gorseller'
        self.reports=self.root/'raporlar'
        for p in (self.profiles,self.masks,self.output,self.reports):
            if p.is_symlink():raise engine.MaskError('Kayit alt klasoru symlink.')
            p.mkdir(parents=True,exist_ok=True)
        log=logging.getLogger('petek_v3')
        if not log.handlers:
            log.setLevel(logging.INFO)
            handler=RotatingFileHandler(self.root/'app.log',maxBytes=3_000_000,backupCount=4,encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
            log.addHandler(handler)

    def list(self):
        rows=[]
        for path in sorted(self.profiles.glob('*.json')):
            if path.is_symlink():continue
            try:
                row=json.loads(path.read_text('utf-8'))
                rows.append({'uid':row['uid'],'source':row['source'],
                             'status':row['status'],'source_sha':row['source_sha']})
            except (OSError,ValueError,KeyError):continue
        return rows

    def _profile_path(self,uid):return self.profiles/(_safe_id(uid)+'.json')

    def get(self,uid,require_approved=False):
        path=self._profile_path(uid)
        if path.is_symlink() or not path.is_file():raise engine.MaskError('Sablon kaydi bulunamadi.')
        profile=json.loads(path.read_text(encoding='utf-8'))
        if profile.get('uid')!=uid or profile.get('recipe') not in engine.LEGACY_APPROVAL_RECIPES:
            raise engine.MaskError('Sablon kaydi / motor surumu uyusmuyor.')
        if require_approved and profile.get('status')!='APPROVED':
            raise engine.MaskError('Sablon insan onayina sahip degil.')
        source=engine.safe_file(Path(profile['source']))
        if engine.digest(source)!=profile['source_sha']:
            raise engine.MaskError('Orijinal sablon degismis: yeni inceleme gerekir.')
        mask_path=self.masks/(profile['mask_sha']+'.png')
        mask=engine.decode_mask(mask_path)
        if engine.mask_hash(mask)!=profile['mask_sha']:
            raise engine.MaskError('Maske SHA256 degismis; islem durduruldu.')
        scene=engine.read_bgr(source)
        engine.mask_check(mask,scene,profile['quad'])
        return profile,mask

    def save(self,uid,source,quad,mask,physical_aspect,reviewer='',approved=False,*,curve_points=None,base_mask=None):
        uid=_safe_id(uid)
        source=engine.safe_file(source)
        scene=engine.read_bgr(source)
        points=engine.validated_quad(quad,scene.shape)
        qa=engine.mask_check(mask,scene,points)
        if not .12 <= physical_aspect <= 12:
            raise engine.MaskError('Fiziksel baski orani gecersiz.')
        previous=None
        path=self._profile_path(uid)
        if path.is_file():
            previous=json.loads(path.read_text(encoding='utf-8'))
            if previous.get('source_sha')!=engine.digest(source):
                raise engine.MaskError('Sablon kimligi farkli kaynak gorusele ait: yeni UID gerekli.')
            if previous.get('status')=='APPROVED':
                raise engine.MaskError('Onayli maske kilitli: degistirmek icin farkli bir sablon kimligi (_r2) kullanin.')
        if approved and not reviewer.strip():raise engine.MaskError('Insan inceleyenin adi gerekli.')
        if approved and previous is not None and curve_points is None:
            curve_points=previous.get('curve_points')
            if previous.get('base_mask_sha'):
                base_mask=engine.decode_mask(self.masks/(previous['base_mask_sha']+'.png'))
        from . import curves as curve_math
        safe_points={k:[] for k in ('top','bottom')}
        if curve_points is not None:
            for kind in safe_points:
                selected=list(curve_points.get(kind,[]))
                if selected:
                    curve_math.normalized(selected)
                    if curve_math.coverage(selected,points)<.92:
                        raise engine.MaskError('Kavis uçları dörtgeni yeterince kapsamıyor.')
                    safe_points[kind]=selected
        if any(safe_points.values()) and base_mask is None:
            raise engine.MaskError('Kavis temel maskesi yok; yeni otomatik maske ve kavis işaretlemesi gerekli.')
        if base_mask is not None:
            if base_mask.shape!=mask.shape or base_mask.dtype!=__import__('numpy').uint8:
                raise engine.MaskError('Kavis temel maskesi boyut/tür uyuşmazlığı.')
            if engine.count_outside_panel(base_mask,scene,points):
                raise engine.MaskError('Temel maske dörtgen dışında kalamaz.')
            expected=curve_math.apply(base_mask,points,safe_points['top'],safe_points['bottom'])
            if not __import__('numpy').array_equal(expected,mask):
                raise engine.MaskError('Kavis temel maskesiyle kaydedilecek maske uyuşmuyor.')
        sha=engine.mask_hash(mask)
        dest=self.masks/(sha+'.png')
        encoded=engine.png_bytes(mask)
        if not dest.exists():engine.atomic_new_file(dest,encoded)
        elif engine.mask_hash(engine.decode_mask(dest))!=sha:
            raise engine.MaskError('Kayitli maske dosyasi cakismasi.')
        base_sha=None
        if base_mask is not None:
            base_sha=engine.mask_hash(base_mask)
            base_dest=self.masks/(base_sha+'.png')
            if not base_dest.exists():engine.atomic_new_file(base_dest,engine.png_bytes(base_mask))
            elif engine.mask_hash(engine.decode_mask(base_dest))!=base_sha:
                raise engine.MaskError('Temel maske kaydı farklı içerikte.')
        profile={'uid':uid,'source':str(source),'source_sha':engine.digest(source),
                 'source_size':[scene.shape[1],scene.shape[0]],
                 'quad':points.astype(float).tolist(),'mask_sha':sha,
                 'physical_aspect':float(physical_aspect),'recipe':engine.RECIPE,
                 'status':'APPROVED' if approved else 'DRAFT',
                 'reviewer':reviewer.strip() if approved else '', 'mask_qa':qa,
                 'curve_points':safe_points, 'base_mask_sha':base_sha}
        _atomic_json(path,profile)
        logging.getLogger('petek_v3').info('MASKE_%s uid=%s kaynak_sha=%s maske_sha=%s', profile['status'],uid,profile['source_sha'],sha)
        return profile

    def approve(self,uid,reviewer,confirm):
        if confirm!='I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR':
            raise engine.MaskError('Delik, kavis ve zemini inceleme onayi olmadan sablon kilitlenmez.')
        if not reviewer.strip():raise engine.MaskError('Onaylayan adini girin.')
        p,mask=self.get(uid)
        if p['status']!='DRAFT':raise engine.MaskError('Yalniz TASLAK onaylanabilir.')
        return self.save(uid,p['source'],p['quad'],mask,p['physical_aspect'],reviewer,approved=True)
