"""Synthetic integration: original details, queue crashes, identity and export safety."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from FABRIKA import petek_v3 as p
from FABRIKA.production import Production,default_config
from FABRIKA.queue_store import Store,export
from FABRIKA.safety import IntegrityError,ProcessLock,immutable,json_atomic,sha


def fixture(slots=9,perspective=False):
    scene=np.full((800,600,3),(70,95,120),np.uint8)
    quad=[[100,180],[500,180],[500,700],[100,700]]
    wood=np.zeros((800,600),np.uint8)
    cv2.rectangle(wood,(100,180),(500,700),255,-1)
    for x in range(100,501):
        arch=round(45*(1-((x-300)/200)**2))
        wood[180:180+arch,x]=0;wood[700-arch:701,x]=0
    for i in range(slots):
        x=round(130+i*340/max(1,slots-1));width=2+(i%4)
        cv2.rectangle(wood,(x-width,280+i%3*7),(x+width,580+i%5*5),0,-1)
    scene[wood>0]=[216,223,230]
    holes=(wood==0)&(p.quad_mask(scene.shape,quad)>0)
    scene[holes]=[23,30,36]
    # Actual colored floor remains visible under bottom arch.
    for x in range(100,501):
        arch=round(45*(1-((x-300)/200)**2));scene[700-arch:701,x]=[65,110,155]
    if perspective:
        q=np.float32([[110,170],[480,220],[520,670],[90,720]])
        matrix=cv2.getPerspectiveTransform(np.float32(quad),q)
        scene=cv2.warpPerspective(scene,matrix,(600,800),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
        wood=cv2.warpPerspective(wood,matrix,(600,800),flags=cv2.INTER_NEAREST)
        quad=q.tolist()
    return scene,quad,wood


def design(w=600,h=800):
    a=np.full((h,w,3),(80,140,230),np.uint8)
    for y in range(0,h,12):a[y:y+4]=[15,30,80]
    cv2.putText(a,'QUALITY 123',(30,min(h-20,160)),cv2.FONT_HERSHEY_SIMPLEX,1.5,(255,255,255),3)
    return a


class FactoryV3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.designs=self.root/'DESIGNS';self.designs.mkdir()
        self.source=self.root/'template.png';scene,self.quad,_=fixture()
        immutable(self.source,p.png(scene));self.scene=scene
        self.art=self.designs/'same_name.png';immutable(self.art,p.png(design()))

    def tearDown(self):self.tmp.cleanup()

    def profile(self):
        analysis=p.analyze(self.scene,self.quad)
        return p.save_profile(self.root/'PROFILES',self.source,self.quad,analysis.mask,analysis.metrics,True)

    def config(self):
        c=default_config();c.update(output=str(self.root/'RESULTS'),designs=str(self.designs),code=str(self.root/'CODE'),runtime=str(self.root/'RUNTIME'),backup='',categories=['06_Petek_Dolabi'],profiles=[str(self.profile())])
        return c

    def test_variable_slots_curves_perspective_masks(self):
        for count in (3,7,13,19):
            for perspective in (False,True):
                with self.subTest(count=count,perspective=perspective):
                    scene,q,truth=fixture(count,perspective);a=p.analyze(scene,q)
                    # Optical interpolation makes a one-pixel boundary uncertain.
                    inner=cv2.erode(truth,np.ones((5,5),np.uint8))>0
                    protected=cv2.erode((truth==0).astype(np.uint8),np.ones((3,3),np.uint8))>0
                    self.assertGreater(np.mean(a.mask[inner]>0),.95)
                    self.assertEqual(np.count_nonzero(a.mask[protected]),0)

    def test_preserved_details_exact_and_no_blur_fill(self):
        scene,q,_=fixture();a=p.analyze(scene,q)
        output,quality=p.render(design(),scene,a.mask,q)
        baseline=cv2.resize(scene,(1200,1600),interpolation=cv2.INTER_CUBIC)
        mask=cv2.resize(a.mask,(1200,1600),interpolation=cv2.INTER_NEAREST)
        self.assertTrue(np.array_equal(output[mask==0],baseline[mask==0]))
        self.assertEqual(quality['protected_pixel_max_difference'],0)
        self.assertFalse(quality['print_blur_fill'])
        self.assertGreater(np.abs(output.astype(float)-baseline).sum(),0)

    def test_center_crop_and_interpolation_variants(self):
        scene,q,_=fixture();a=p.analyze(scene,q)
        for shape in ((900,350),(350,900),(600,800)):
            for method in (cv2.INTER_LINEAR,cv2.INTER_CUBIC,cv2.INTER_LANCZOS4):
                with self.subTest(shape=shape,method=method):
                    output,quality=p.render(design(*shape),scene,a.mask,q,1.0,method)
                    self.assertEqual(output.shape,(1600,1200,3));self.assertEqual(quality['protected_pixel_max_difference'],0)
                    self.assertAlmostEqual(quality['crop_fraction'],1-min(shape)/max(shape),places=6)

    def test_strong_downsample_has_prefilter(self):
        _,quality=p.render(design(3000,3600),self.scene,p.analyze(self.scene,self.quad).mask,self.quad)
        self.assertTrue(quality['minification_prefilter'])

    def test_mask_review_and_source_binding(self):
        a=p.analyze(self.scene,self.quad)
        with self.assertRaises(ValueError):p.save_profile(self.root/'P',self.source,self.quad,a.mask,a.metrics,False)
        profile=self.profile();p.load_profile(profile)
        with self.source.open('ab') as f:f.write(b'changed')
        with self.assertRaises(IntegrityError):p.load_profile(profile)

    def test_mask_tamper_and_quad_crossing_rejected(self):
        profile=self.profile();mask=profile.parent/'PRINT_MASK.png'
        mask.write_bytes(p.png(np.zeros(self.scene.shape[:2],np.uint8)))
        with self.assertRaises(IntegrityError):p.load_profile(profile)
        with self.assertRaises(ValueError):p.quad_mask(self.scene.shape,[self.quad[i] for i in (0,2,1,3)])

    def test_mask_cannot_escape_quad(self):
        a=p.analyze(self.scene,self.quad);a.mask[0,0]=255
        with self.assertRaises(ValueError):p.save_profile(self.root/'P',self.source,self.quad,a.mask,a.metrics,True)

    def test_repeat_retains_outputs_sku_export_and_sources(self):
        config=self.config();original={str(f):sha(f) for f in (self.source,self.art)}
        first,_=Production(config,lambda _:None).run();self.assertEqual(first['rendered'],1,first)
        store=Store(config['output']);row=store.records(first['jobs'])[0];out=Path(row['output']);stamp=out.stat().st_mtime_ns
        excel=Path(first['export']['excel']);excel_stamp=excel.stat().st_mtime_ns
        second,_=Production(config,lambda _:None).run()
        self.assertEqual(second['reused'],1,second);self.assertEqual(second['rendered'],0)
        self.assertEqual(out.stat().st_mtime_ns,stamp);self.assertEqual(excel.stat().st_mtime_ns,excel_stamp)
        self.assertEqual(row['sku'],store.records(second['jobs'])[0]['sku'])
        self.assertEqual(original,{str(f):sha(f) for f in (self.source,self.art)})

    def test_same_name_different_content_and_extension(self):
        Image.fromarray(np.full((400,600,3),170,np.uint8)).save(self.designs/'same_name.jpg')
        config=self.config();report,_=Production(config,lambda _:None).run()
        self.assertEqual(report['rendered'],2,report)
        rows=Store(config['output']).records(report['jobs'])
        self.assertEqual(len({r['sku'] for r in rows}),2);self.assertEqual(len({r['output'] for r in rows}),2)

    def test_product_identity_compatible_with_prior_petek(self):
        from FABRIKA.safety import key
        store=Store(self.root/'S');product=store.product(p.CATEGORY,sha(self.art),'Design')
        old=key({'category':p.CATEGORY,'store':'LOCAL','art_sha':sha(self.art),'recipe':'petek-product-v1'})
        self.assertEqual(product['sku'],'PDK-'+old[:16].upper())
        self.assertNotIn('13',product['description'])

    def test_number_is_not_reused_after_deleted_product(self):
        store=Store(self.root/'S');one=store.product(p.CATEGORY,'a'*64,'A')
        with store.connect() as c:c.execute('DELETE FROM products WHERE product_key=?',(one['product_key'],))
        two=store.product(p.CATEGORY,'b'*64,'B');self.assertGreater(two['number'],one['number'])

    def test_corrupted_output_blocks_no_overwrite(self):
        config=self.config();first,_=Production(config,lambda _:None).run();store=Store(config['output'])
        out=Path(store.records(first['jobs'])[0]['output']);out.write_bytes(b'damaged')
        second,_=Production(config,lambda _:None).run();self.assertEqual(second['status'],'BLOCKED');self.assertEqual(out.read_bytes(),b'damaged')

    def test_crash_after_publish_recovers_identical_orphan(self):
        config=self.config()
        with patch.object(Store,'rendered',side_effect=RuntimeError('injected crash after output')):
            failed,_=Production(config,lambda _:None).run()
        existing=list((Path(config['output'])/'GORSELLER').rglob('*.png'))
        self.assertEqual(len(existing),1);stamp=existing[0].stat().st_mtime_ns
        resumed,_=Production(config,lambda _:None).run()
        self.assertEqual(resumed['completed'],1,resumed);self.assertEqual(existing[0].stat().st_mtime_ns,stamp)

    def test_cancel_and_resume(self):
        config=self.config();control=self.root/'CONTROL.json';json_atomic(control,{'command':'cancel'})
        cancelled,_=Production(config,lambda _:None,control).run();self.assertEqual(cancelled['status'],'CANCELLED_SAFELY');self.assertEqual(cancelled['completed'],0)
        json_atomic(control,{'command':'run'});resumed,_=Production(config,lambda _:None,control).run();self.assertEqual(resumed['completed'],1)

    def test_pause_waits_until_continue(self):
        control=self.root/'CONTROL.json';json_atomic(control,{'command':'pause'});prod=Production({},lambda _:None,control)
        state=[];thread=threading.Thread(target=lambda:state.append(prod.wait()));thread.start();time.sleep(.15);self.assertEqual(state,[])
        json_atomic(control,{'command':'run'});thread.join(2);self.assertEqual(state,[True])

    def test_lock_blocks_second_and_releases(self):
        lock=self.root/'LOCK'
        with ProcessLock(lock):
            with self.assertRaises(IntegrityError):
                with ProcessLock(lock):pass
        with ProcessLock(lock):pass

    def test_immutable_never_overwrites(self):
        target=self.root/'file';self.assertTrue(immutable(target,b'first'));stamp=target.stat().st_mtime_ns
        self.assertFalse(immutable(target,b'first'))
        with self.assertRaises(IntegrityError):immutable(target,b'second')
        self.assertEqual(target.stat().st_mtime_ns,stamp)

    def test_export_tamper_blocks(self):
        config=self.config();first,_=Production(config,lambda _:None).run()
        xlsx=Path(first['export']['excel']);xlsx.write_bytes(b'changed')
        second,_=Production(config,lambda _:None).run();self.assertEqual(second['status'],'BLOCKED');self.assertEqual(xlsx.read_bytes(),b'changed')

    def test_export_interruption_recovers_without_overwrite(self):
        config=self.config();first,_=Production(config,lambda _:None).run()
        excel=Path(first['export']['excel']);receipt=excel.parent/'RECEIPT.json';receipt.unlink();stamp=excel.stat().st_mtime_ns
        second,_=Production(config,lambda _:None).run();self.assertEqual(second['completed'],1,second);self.assertEqual(excel.stat().st_mtime_ns,stamp)

    def test_failed_template_continues_other_jobs(self):
        config=self.config();config['profiles'].append(str(self.root/'missing.json'))
        report,_=Production(config,lambda _:None).run();self.assertEqual(report['completed'],1,report);self.assertTrue(report['failed'])

    def test_untrusted_nested_output_rejected(self):
        config=self.config();config['output']=str(self.designs/'out')
        with self.assertRaises(IntegrityError):Production(config,lambda _:None).run()

    def test_recipe_changes_identity(self):
        config=self.config();first,_=Production(config,lambda _:None).run()
        with patch.object(p,'RECIPE','next-recipe-test'):
            second,_=Production(config,lambda _:None).run()
        self.assertNotEqual(first['jobs'],second['jobs']);self.assertEqual(second['rendered'],1)


if __name__=='__main__':unittest.main(verbosity=2)
