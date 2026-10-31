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

    def _active_index(self):
        path=self.root/'active_revisions.json'
        if path.is_symlink():raise engine.MaskError('PETEK_REVISION_INDEX_SYMLINK')
        if not path.is_file():return {}
        data=json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(data,dict) or data.get('version')!=1 or
                not isinstance(data.get('entries'),dict)):
            raise engine.MaskError('PETEK_REVISION_INDEX_CORRUPT: kurtarma/yedek gerekli')
        return data['entries']

    def _root_uid(self,uid):
        uid=_safe_id(uid)
        p=self._profile_path(uid)
        if p.exists():
            data=json.loads(p.read_text(encoding='utf-8'))
            return _safe_id(data.get('base_uid') or uid)
        return uid

    def is_current(self,uid):
        uid=_safe_id(uid)
        base=self._root_uid(uid)
        entry=self._active_index().get(base)
        if not entry:
            p=self._profile_path(uid)
            if not p.is_file():return False
            prof=json.loads(p.read_text(encoding='utf-8'))
            # A new approved revision is not used in production until activated.
            return not bool(prof.get('revises_uid'))
        return entry.get('active_uid')==uid

    def link_draft_revision(self,approved_uid,new_uid,*,source_override=None):
        approved_uid=_safe_id(approved_uid);new_uid=_safe_id(new_uid)
        old,_=self.get(approved_uid,require_approved=True,source_override=source_override)
        if not self.is_current(approved_uid):
            raise engine.MaskError('Yalnız mevcut etkin onaylı maskeden revizyon açılabilir.')
        path=self._profile_path(new_uid)
        if path.is_symlink() or not path.is_file():
            raise engine.MaskError('PETEK_REVISION_DRAFT_NOT_FOUND')
        data=json.loads(path.read_text(encoding='utf-8'))
        if (data.get('status')!='DRAFT' or data.get('source_sha')!=old['source_sha'] or
                data.get('uid')!=new_uid or not new_uid.startswith(approved_uid[:70]+'_r')):
            raise engine.MaskError('PETEK_REVISION_LINK_INVALID')
        data['revises_uid']=approved_uid
        data['base_uid']=self._root_uid(approved_uid)
        _atomic_json(path,data)

    def activate_revision(self,approved_uid,new_uid,confirm,*,source_override=None):
        """Switch active *future* selection to approved revision, preserve originals.

        The existing immutable masks and profiles remain byte-identical;
        pending production items can retain their previously selected UID.
        """
        if confirm!='ACTIVATE_REVISED_PETEK_AND_KEEP_OLD':
            raise engine.MaskError('PETEK_REVISION_EXPLICIT_CONFIRM_REQUIRED')
        approved_uid=_safe_id(approved_uid);new_uid=_safe_id(new_uid)
        old,_=self.get(approved_uid,require_approved=True,source_override=source_override)
        new,_=self.get(new_uid,require_approved=True,source_override=source_override)
        if old.get('source_sha')!=new.get('source_sha'):
            raise engine.MaskError('PETEK_REVISION_SOURCE_MISMATCH')
        if new.get('revises_uid')!=approved_uid or new.get('base_uid')!=self._root_uid(approved_uid):
            raise engine.MaskError('PETEK_REVISION_PARENT_MISMATCH')
        if not self.is_current(approved_uid):
            raise engine.MaskError('PETEK_REVISION_CURRENT_CHANGED_RELOAD')
        rootuid=self._root_uid(approved_uid)
        data=self._active_index()
        history=list(data.get(rootuid,{}).get('history',[]))
        if approved_uid not in history:history.append(approved_uid)
        data[rootuid]={'active_uid':new_uid,'history':history,'source_sha':new['source_sha']}
        _atomic_json(self.root/'active_revisions.json',{'version':1,'entries':data})
        return {'base_uid':rootuid,'previous_uid':approved_uid,'active_uid':new_uid,
                'mask_sha':new['mask_sha'],'previous_mask_sha':old['mask_sha']}

    def restore_revision(self,root_uid,previous_uid,confirm,*,source_override=None):
        if confirm!='RESTORE_PREVIOUS_APPROVED_PETEK':
            raise engine.MaskError('PETEK_REVISION_RESTORE_CONFIRM_REQUIRED')
        root_uid=_safe_id(root_uid);previous_uid=_safe_id(previous_uid)
        data=self._active_index();entry=data.get(root_uid)
        if not entry or previous_uid not in entry.get('history',[]):
            raise engine.MaskError('PETEK_REVISION_NOT_IN_HISTORY')
        current,_=self.get(entry['active_uid'],require_approved=True,source_override=source_override)
        prior,_=self.get(previous_uid,require_approved=True,source_override=source_override)
        if current['source_sha']!=prior['source_sha']:
            raise engine.MaskError('PETEK_REVISION_SOURCE_CHANGED')
        history=list(entry['history'])
        if entry['active_uid'] not in history:history.append(entry['active_uid'])
        data[root_uid]={'active_uid':previous_uid,'history':history,'source_sha':prior['source_sha']}
        _atomic_json(self.root/'active_revisions.json',{'version':1,'entries':data})
        return {'active_uid':previous_uid,'previous_active_uid':entry['active_uid']}

    def list(self):
        active=self._active_index()  # one index read; fail closed on corrupted pointer
        rows=[]
        for path in sorted(self.profiles.glob('*.json')):
            if path.is_symlink():continue
            try:
                row=json.loads(path.read_text('utf-8'))
                base=row.get('base_uid') or row['uid']
                current=(active[base].get('active_uid')==row['uid']
                         if base in active else not bool(row.get('revises_uid')))
                rows.append({'uid':row['uid'],'source':row['source'],
                             'status':row['status'],'source_sha':row['source_sha'],
                             'is_current':current})
            except (OSError,ValueError,KeyError):continue
        return rows

    def _profile_path(self,uid):return self.profiles/(_safe_id(uid)+'.json')

    def get(self,uid,require_approved=False,*,source_override=None):
        path=self._profile_path(uid)
        if path.is_symlink() or not path.is_file():raise engine.MaskError('Sablon kaydi bulunamadi.')
        profile=json.loads(path.read_text(encoding='utf-8'))
        if profile.get('uid')!=uid or profile.get('recipe') not in engine.LEGACY_APPROVAL_RECIPES:
            raise engine.MaskError('Sablon kaydi / motor surumu uyusmuyor.')
        if require_approved and profile.get('status')!='APPROVED':
            raise engine.MaskError('Sablon insan onayina sahip degil.')
        original=Path(profile['source'])
        # Historic PETEK approved profiles may point to an old disposable LAB
        # folder. When that source is GONE, an explicitly selected working-pool
        # file may be used for this read ONLY if its SHA and dimensions match.
        # Never rewrite the approved profile or mask, and never bypass a
        # present-but-tampered source or a symlink at the old source path.
        if original.exists() or original.is_symlink() or source_override is None:
            source=engine.safe_file(original)
        else:
            source=engine.safe_file(Path(source_override))
        if engine.digest(source)!=profile['source_sha']:
            raise engine.MaskError('Orijinal sablon degismis: yeni inceleme gerekir.')
        # One decode for both source dimensions and mask QA. Source SHA
        # verification above is still authoritative and never cached here.
        scene=engine.read_bgr(source)
        saved_size=profile.get('source_size')
        if saved_size is not None:
            scene_size=scene.shape
            if [int(scene_size[1]),int(scene_size[0])]!=list(saved_size):
                raise engine.MaskError('PETEK_KAYNAK_BOYUTU_KAYITLA_UYUSMUYOR')
        mask_path=self.masks/(profile['mask_sha']+'.png')
        mask=engine.decode_mask(mask_path)
        if engine.mask_hash(mask)!=profile['mask_sha']:
            raise engine.MaskError('Maske SHA256 degismis; islem durduruldu.')
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
        if previous is not None:
            for key in ('revises_uid','base_uid'):
                if previous.get(key):profile[key]=previous[key]
        _atomic_json(path,profile)
        logging.getLogger('petek_v3').info('MASKE_%s uid=%s kaynak_sha=%s maske_sha=%s', profile['status'],uid,profile['source_sha'],sha)
        return profile

    def approve(self,uid,reviewer,confirm,*,source_override=None):
        if confirm!='I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR':
            raise engine.MaskError('Delik, kavis ve zemini inceleme onayi olmadan sablon kilitlenmez.')
        if not reviewer.strip():raise engine.MaskError('Onaylayan adini girin.')
        p,mask=self.get(uid,source_override=source_override)
        if p['status']!='DRAFT':raise engine.MaskError('Yalniz TASLAK onaylanabilir.')
        # A historical vanished source may have been matched to an explicit
        # working-pool file of identical SHA. Never write to the old source.
        actual_source=source_override if source_override is not None else p['source']
        return self.save(uid,actual_source,p['quad'],mask,p['physical_aspect'],reviewer,approved=True)
