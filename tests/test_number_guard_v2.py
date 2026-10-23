"""NUMBER_GUARD_V2: loss and collision acceptance on disposable files only."""
import hashlib
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from PIL import Image
from SABLON_V2_MIMARI import tools_runner as tools
from SABLON_V2_MIMARI.core import file_safety as fs
from SABLON_V2_MIMARI.core import template_identity as ids

CAT='01_Wifi_Kutusu'
ROOT=Path(__file__).resolve().parents[1]

class NumberGuardAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.runtime=self.root/'runtime'
        self.db=self.runtime/'SABLON_V2_MIMARI/ayarlar.db';self.db.parent.mkdir(parents=True)
        sqlite3.connect(self.db).close()
        self.external=self.root/'input';self.external.mkdir()
    def img(self,name='source.png',color=50,parent=None):
        p=(parent or self.external)/name;p.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGB',(40,30),(color,75,120)).save(p);return p
    def test_01_same_name_same_extension_keeps_both_bytes(self):
        a=self.img();b=self.img('Art_001.png',90);before=(a.read_bytes(),b.read_bytes())
        with self.assertRaises(FileExistsError):tools.rename_images([a],'Art_',self.runtime)
        self.assertEqual((a.read_bytes(),b.read_bytes()),before)
    def test_02_same_name_other_extension_keeps_both_bytes(self):
        a=self.img();b=self.img('Art_001.jpg',90);before=(a.read_bytes(),b.read_bytes())
        with self.assertRaises(FileExistsError):tools.rename_images([a],'Art_',self.runtime)
        self.assertEqual((a.read_bytes(),b.read_bytes()),before)
    def test_03_history_from_only_raw_archive_blocks_old_number(self):
        self.img('Wifi_Kutusu_999.jpg',parent=self.runtime/'_GUVENLI_GELEN_HAM_GORSELLER'/CAT/'oldtxn')
        with self.assertRaises(ids.TemplateNumberConflictError) as e:ids.validate_number_block(self.runtime,CAT,5,1)
        self.assertEqual(e.exception.suggested_start,1000)
    def test_04_nested_processing_recovery_blocks_old_number(self):
        p=self.runtime/'_KURTARMA_PROCESSING'/CAT/'Wifi_Kutusu_711__20261019.jpg';p.parent.mkdir(parents=True);p.write_bytes(b'RAW')
        with self.assertRaises(ids.TemplateNumberConflictError):ids.validate_number_block(self.runtime,CAT,700,1)
    def test_05_lifecycle_journal_preserves_number(self):
        p=self.runtime/'SABLON_V2_MIMARI/recovery/lifecycle/old/manifest.json';p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'category':CAT,'moved':[{'name':'Wifi_Kutusu_800.png'}]}))
        with self.assertRaises(ids.TemplateNumberConflictError):ids.validate_number_block(self.runtime,CAT,799,1)
    def test_06_invalid_history_fails_closed(self):
        p=self.runtime/'SABLON_V2_MIMARI/recovery/staging_transactions/bad.json';p.parent.mkdir(parents=True);p.write_text('{bad')
        with self.assertRaisesRegex(RuntimeError,'NUMBER_HISTORY_UNREADABLE'):ids.validate_number_block(self.runtime,CAT,1000,1)
    def test_07_sqlite_high_water_rechecked_inside_transaction(self):
        real=ids.validate_number_block
        def interleave(*a,**kw):
            value=real(*a,**kw)
            ids.claim_number_once(self.runtime,CAT,500,canonical_name='Wifi_Kutusu_500.png')
            return value
        with patch.object(ids,'validate_number_block',side_effect=interleave):
            with self.assertRaises(ids.TemplateNumberConflictError):
                ids.claim_number_block_once(self.runtime,CAT,100,1,canonical_names=['Wifi_Kutusu_100.png'])
        with contextlib.closing(sqlite3.connect(self.db)) as c:self.assertEqual(c.execute('SELECT template_number FROM template_number_registry').fetchall(),[(500,)])
    def test_08_direct_claim_cannot_reuse_a_gap(self):
        ids.claim_number_once(self.runtime,CAT,500,canonical_name='Wifi_Kutusu_500.png')
        with self.assertRaises(ids.TemplateNumberConflictError):ids.claim_number_once(self.runtime,CAT,5,canonical_name='Wifi_Kutusu_005.jpg')
    def test_09_successful_rename_has_independent_durable_raw_snapshot(self):
        p=self.img();raw=p.read_bytes();out=tools.rename_images([p],'Art_',self.runtime)
        self.assertFalse(p.exists());self.assertEqual(out[0].read_bytes(),raw)
        journal=list((self.external/'_GORSEL_ISIMLENDIRME_YEDEKLERI').glob('*/manifest.json'))[0]
        d=json.loads(journal.read_text());self.assertEqual(d['state'],'COMMITTED')
        snap=Path(d['files'][0]['snapshot']);self.assertEqual(snap.read_bytes(),raw)
        out[0].write_bytes(b'MODIFIED_LATER');self.assertEqual(snap.read_bytes(),raw)
    def test_10_partial_publish_failure_restores_all_sources(self):
        a=self.img('a.png');b=self.img('b.png',90);before=(a.read_bytes(),b.read_bytes());real=os.link
        def fail(src,dst,*args,**kw):
            if Path(dst).name=='Art_002.png':raise OSError('DISK_ERROR')
            return real(src,dst,*args,**kw)
        with patch.object(os,'link',side_effect=fail):
            with self.assertRaises(OSError):tools.rename_images([a,b],'Art_',self.runtime)
        self.assertEqual((a.read_bytes(),b.read_bytes()),before)
    def test_11_late_cleanup_failure_still_preserves_every_original(self):
        a=self.img('a.png');b=self.img('b.png',90);before=(a.read_bytes(),b.read_bytes());real=Path.unlink;count=[0]
        def fail(p,*args,**kw):
            if p.name.startswith('.__jarvis_rename_'):
                count[0]+=1
                if count[0]==2:raise OSError('LATE_UNLINK_FAILURE')
            return real(p,*args,**kw)
        with patch.object(Path,'unlink',fail):
            with self.assertRaises(OSError):tools.rename_images([a,b],'Art_',self.runtime)
        self.assertEqual((a.read_bytes(),b.read_bytes()),before)
    def test_12_crash_leaves_snapshot_and_blocks_silent_restart(self):
        p=self.img();raw=p.read_bytes();target=self.external/'Art_001.png'
        script='''import os,sys\nfrom pathlib import Path\nfrom SABLON_V2_MIMARI.core.file_safety import rename_safety_transaction,move_create_only\na=Path(sys.argv[1]);b=Path(sys.argv[2])\nwith rename_safety_transaction([a],[b]):\n move_create_only(a,a.with_name('.crash-held.png'))\n os._exit(73)\n'''
        child=subprocess.run([sys.executable,'-B','-c',script,str(p),str(target)],capture_output=True)
        self.assertEqual(child.returncode,73,child.stderr.decode(errors='replace'))
        journal=list((self.external/'_GORSEL_ISIMLENDIRME_YEDEKLERI').glob('*/manifest.json'))[0]
        d=json.loads(journal.read_text());self.assertEqual(Path(d['files'][0]['snapshot']).read_bytes(),raw)
        other=self.img('another.png')
        with self.assertRaisesRegex(RuntimeError,'RENAME_BUSY_OR_RECOVERY_REQUIRED'):tools.rename_images([other],'Art_',self.runtime)
    def test_13_duplicate_selected_source_rejected(self):
        p=self.img();before=p.read_bytes()
        with self.assertRaisesRegex(ValueError,'DUPLICATE_SOURCE'):tools.rename_images([p,p],'Art_',self.runtime)
        self.assertEqual(p.read_bytes(),before)
    def test_14_staging_and_recovery_sources_cannot_be_renamed(self):
        for rel in ['YENI-BOS MOCKUP SABLON HAVUZU','_GUVENLI_GELEN_HAM_GORSELLER','_KURTARMA_PROCESSING','SILINEN_SABLONLAR_COP_KUTUSU']:
            with self.subTest(root=rel):
                p=self.img(parent=self.runtime/rel/CAT)
                with self.assertRaises(ValueError):tools.rename_images([p],'Art_',self.runtime)
                self.assertTrue(p.is_file())
    def test_15_parallel_converters_publish_30_distinct_outputs(self):
        p=self.img();raw=p.read_bytes()
        with ThreadPoolExecutor(max_workers=10) as pool:outputs=list(pool.map(lambda _:tools.convert_images([p],'JPG')[1][0],range(30)))
        self.assertEqual(len(set(outputs)),30);self.assertEqual(p.read_bytes(),raw)
        for out in outputs:
            with Image.open(out) as image:self.assertEqual(image.size,(40,30));image.verify()
    def test_16_preexisting_conversion_output_never_changes(self):
        p=self.img();dest=p.parent/'FORMAT_JPG_CIKTILARI/source.jpg';dest.parent.mkdir();dest.write_bytes(b'KEEP_EXISTING')
        out=tools.convert_images([p],'JPG')[1][0]
        self.assertNotEqual(out,dest);self.assertEqual(dest.read_bytes(),b'KEEP_EXISTING')
    def test_17_recursive_conversion_race_keeps_existing_bytes(self):
        p=self.img('photo.jpg');output=self.root/'converted';real=os.link
        def collide(src,dst,*a,**kw):
            if Path(dst).name=='photo.png':Path(dst).write_bytes(b'OTHER_PROCESS')
            return real(src,dst,*a,**kw)
        with patch.object(os,'link',side_effect=collide):report=tools.convert_folder_to_png_recursive(self.external,output_dir=output,runtime_root=self.runtime)
        self.assertEqual(report['converted_count'],0);self.assertEqual(report['skipped_existing_count'],1)
        self.assertEqual((output/'photo.png').read_bytes(),b'OTHER_PROCESS');self.assertTrue(p.is_file())
    def test_18_recursive_output_inside_original_archive_blocked(self):
        p=self.img('photo.jpg');output=self.runtime/'2_SABLON_HAVUZU_ORIJINAL_YEDEK'/CAT
        output.mkdir(parents=True)
        with self.assertRaises(ValueError):tools.convert_folder_to_png_recursive(self.external,output_dir=output,runtime_root=self.runtime)
        self.assertTrue(p.is_file());self.assertEqual(list(output.iterdir()),[])
    def test_19_same_names_from_two_accounts_get_unique_receipts(self):
        a=self.img('same.png',20,parent=self.root/'mailA');b=self.img('same.png',80,parent=self.root/'mailB')
        records=[]
        for p in [a,b]*10:records+=tools.stage_incoming_safely([p],CAT,self.runtime)['receipts']
        self.assertEqual(len({r['staged_name'] for r in records}),20)
        for r in records:
            path=self.runtime/'YENI-BOS MOCKUP SABLON HAVUZU'/CAT/r['staged_name']
            self.assertEqual(fs.sha256_file(path),r['sha256'])
        self.assertTrue(a.is_file());self.assertTrue(b.is_file())
    def test_20_receipt_commit_failure_keeps_source_and_published_snapshot(self):
        p=self.img();raw=p.read_bytes();real=os.replace
        def fail(src,dst,*a,**kw):
            if Path(dst).parent.name=='intake_receipts':raise OSError('RECEIPT_COMMIT_FAIL')
            return real(src,dst,*a,**kw)
        with patch.object(os,'replace',side_effect=fail):
            with self.assertRaisesRegex(RuntimeError,'INTAKE_RECEIPT_RECOVERY_REQUIRED'):tools.stage_incoming_safely([p],CAT,self.runtime)
        self.assertEqual(p.read_bytes(),raw)
        staged=list((self.runtime/'YENI-BOS MOCKUP SABLON HAVUZU'/CAT).glob('*.png'));self.assertEqual(len(staged),1);self.assertEqual(staged[0].read_bytes(),raw)
    def test_21_interactive_stage_category_prompt_is_reachable(self):
        p=self.img();message=types.SimpleNamespace(showinfo=lambda *a,**k:None,showerror=lambda *a,**k:self.fail(str(a)))
        fake=types.SimpleNamespace(destroy=lambda:None)
        dialog=types.SimpleNamespace(askopenfilenames=lambda **k:[str(p)])
        simple=types.SimpleNamespace(askinteger=lambda *a,**k:1)
        with patch.object(tools,'_ui',return_value=(fake,dialog,message,simple)),patch.object(tools,'stage_incoming_safely',return_value={'staged_count':1}) as intake:
            self.assertEqual(tools.interactive_safe_stage(),0);self.assertEqual(intake.call_args.args[1],CAT)
    def test_22_parallel_process_number_claim_single_winner(self):
        script='''from pathlib import Path\nimport sys\nfrom SABLON_V2_MIMARI.core.template_identity import claim_number_once,TemplateNumberConflictError\ntry:claim_number_once(Path(sys.argv[1]),'01_Wifi_Kutusu',900,canonical_name='Wifi_Kutusu_900.png')\nexcept TemplateNumberConflictError:sys.exit(4)\n'''
        procs=[subprocess.Popen([sys.executable,'-B','-c',script,str(self.runtime)],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(6)]
        codes=[]
        for p in procs:p.communicate(timeout=60);codes.append(p.returncode)
        self.assertEqual(codes.count(0),1,codes);self.assertEqual(codes.count(4),5,codes)
    def test_23_unsupported_hard_links_fail_without_source_loss(self):
        p=self.img();raw=p.read_bytes()
        with patch.object(os,'link',side_effect=OSError('UNSUPPORTED_FS')):
            with self.assertRaises(OSError):tools.rename_images([p],'Art_',self.runtime)
        self.assertEqual(p.read_bytes(),raw)
    def test_24_watermark_parallel_outputs_do_not_replace(self):
        p=self.img();logo=self.img('logo.png',10);raw=p.read_bytes()
        with ThreadPoolExecutor(max_workers=5) as pool:outputs=list(pool.map(lambda _:tools.watermark_images(logo,[p])[1][0],range(12)))
        self.assertEqual(len(set(outputs)),12);self.assertEqual(p.read_bytes(),raw)
    def test_25_copy_publication_never_replaces_existing_target(self):
        a=self.img();b=self.external/'other.png';b.write_bytes(b'KEEP')
        with self.assertRaises(FileExistsError):fs.copy_exclusive(a,b)
        self.assertEqual(b.read_bytes(),b'KEEP');self.assertTrue(a.exists())
    def test_26_parallel_generic_names_cannot_share_identity(self):
        a=self.img('a.png');b=self.img('b.jpg',90)
        def go(p):
            try:return tools.rename_images([p],'Art_',self.runtime)
            except (FileExistsError,RuntimeError):return None
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(go,[a,b]))
        self.assertEqual(sum(x is not None for x in result),1)
        self.assertEqual(len(list(self.external.glob('Art_001.*'))),1)
    def test_27_source_change_during_snapshot_stops_before_rename(self):
        p=self.img();real=fs.copy_exclusive
        def change(src,dst):real(src,dst);Path(src).write_bytes(b'NEW_CONTENT')
        with patch.object(fs,'copy_exclusive',side_effect=change):
            with self.assertRaisesRegex(RuntimeError,'SOURCE_CHANGED'):tools.rename_images([p],'Art_',self.runtime)
        self.assertEqual(p.read_bytes(),b'NEW_CONTENT');self.assertFalse((self.external/'Art_001.png').exists())
    def test_28_case_extension_identity_is_normalized(self):
        self.assertTrue(ids.same_identity('Wifi_Kutusu_135.PNG','wifi_kutusu_135.jpeg'))
    def test_29_missing_production_db_does_not_switch_to_offline(self):
        self.db.unlink();(self.runtime/'2_SABLON_HAVUZU').mkdir();p=self.img()
        with self.assertRaisesRegex(RuntimeError,'DB_MISSING_FAIL_CLOSED'):tools.rename_images([p],'Wifi_Kutusu_',self.runtime,500)
        self.assertTrue(p.exists())
    def test_30_legacy_control_uses_shared_number_history(self):
        spec=importlib.util.spec_from_file_location('number_test_control',ROOT/'V2_KONTROL_MERKEZI/app.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        mod.BASE_DIR=str(self.runtime)
        ids.claim_number_once(self.runtime,CAT,500,canonical_name='Wifi_Kutusu_500.png')
        p=self.img()
        with self.assertRaises(ids.TemplateNumberConflictError):mod.safe_two_phase_rename([str(p)],'Wifi_Kutusu_')
        self.assertTrue(p.exists())


class WatcherRealDatabaseAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=ROOT/'99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/sablon_oto_izleyici.py'
        spec=importlib.util.spec_from_file_location('number_guard_real_watcher',path)
        cls.w=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.w)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.stage=self.root/'YENI-BOS MOCKUP SABLON HAVUZU'/CAT
        self.work=self.root/'2_SABLON_HAVUZU'/CAT;self.backup=self.root/'2_SABLON_HAVUZU_ORIJINAL_YEDEK'/CAT
        for p in (self.stage,self.work,self.backup):p.mkdir(parents=True)
        self.db=self.root/'SABLON_V2_MIMARI/ayarlar.db';self.db.parent.mkdir()
        dbmodule=sys.modules[self.w.save_template.__module__]
        p=patch.object(dbmodule,'DB_PATH',str(self.db));p.start();self.addCleanup(p.stop)
        dbmodule.init_db();dbmodule.save_category(CAT,'Wifi')
        for key,value in {'BASE_DIR':self.root,'STAGING_DIR':self.stage.parent,'YEDEK_DIR':self.backup.parent,'SABLON_DIR':self.work.parent}.items():
            p=patch.object(self.w,key,value);p.start();self.addCleanup(p.stop)
        p=patch.dict(os.environ,{'MOCKUP_STAGING_IMPORT_APPROVED':'I_REVIEWED_AND_APPROVED_STAGING_IMPORT'});p.start();self.addCleanup(p.stop)
        # Naming/DB acceptance uses a deterministic corner PROPOSAL, never APPROVED.
        p=patch.object(self.w,'analyze_new_template_once',side_effect=self.proposal);p.start();self.addCleanup(p.stop)
    @staticmethod
    def proposal(path,cat,img):
        q=[[1,1],[38,1],[38,28],[1,28]]
        return ({'tip':'perspektif','koseler':q,'review_status':'REVIEW_REQUIRED'},
                {'template_uid':cat+'_'+path.name,'category':cat,'source_relative_path':cat+'/'+path.name,
                 'source_asset_sha256':fs.sha256_file(path),'analyzer_version':'number-acceptance-proposal','surface_quad':q,'orientation':'H','nominal_aspect':4/3,
                 'review_status':'REVIEW_REQUIRED','manually_verified':False})
    def incoming(self,name='Wifi_Kutusu_005.jpg',color=70):
        p=self.stage/name;Image.new('RGB',(40,30),(color,50,20)).save(p);return p
    def test_31_actual_registration_preserves_old_files_and_manual_approval(self):
        old=self.work/'Wifi_Kutusu_137.png';Image.new('RGB',(40,30),(1,2,3)).save(old)
        raw=old.read_bytes();self.backup.joinpath(old.name).write_bytes(raw)
        conf,profile=self.proposal(old,CAT,None);profile.update(review_status='APPROVED',manually_verified=True)
        self.w.save_template(CAT,old.name,conf);self.w.save_template_profile(str(self.db),profile)
        with contextlib.closing(sqlite3.connect(self.db)) as c:before=c.execute('SELECT * FROM template_profiles').fetchall()
        source=self.incoming();source_raw=source.read_bytes()
        self.assertTrue(self.w.process_from_staging(source))
        self.assertEqual(old.read_bytes(),raw);self.assertEqual(self.backup.joinpath(old.name).read_bytes(),raw)
        with contextlib.closing(sqlite3.connect(self.db)) as c:
            preserved=c.execute('SELECT * FROM template_profiles WHERE template_uid=?',(profile['template_uid'],)).fetchall()
            added=c.execute('SELECT review_status,manually_verified,source_relative_path FROM template_profiles WHERE template_uid<>?',(profile['template_uid'],)).fetchall()
        self.assertEqual(preserved,before);self.assertEqual(len(added),1);self.assertEqual(added[0][:2],('REVIEW_REQUIRED',0))
        self.assertEqual(added[0][2],CAT+'/Wifi_Kutusu_138.png')
        archived=[p.read_bytes() for p in (self.root/'_GUVENLI_GELEN_HAM_GORSELLER').rglob('*') if p.is_file()]
        self.assertIn(source_raw,archived)
    def test_32_missing_journal_must_stop_before_output_or_claim(self):
        source=self.incoming();raw=source.read_bytes()
        with patch.object(self.w,'_begin_staging_txn',side_effect=OSError('JOURNAL_DISK_FAIL')):
            self.assertFalse(self.w.process_from_staging(source))
        self.assertEqual(source.read_bytes(),raw);self.assertEqual(list(self.work.iterdir()),[]);self.assertEqual(list(self.backup.iterdir()),[])
        with contextlib.closing(sqlite3.connect(self.db)) as c:self.assertEqual(c.execute('SELECT count(*) FROM template_number_registry').fetchone()[0],0)
    def test_33_working_write_failure_preserves_raw_and_backup_and_burns_id(self):
        source=self.incoming();raw=source.read_bytes();real=self.w._write_png_atomic
        def fail(path,img):return False if Path(path).parent==self.work else real(path,img)
        with patch.object(self.w,'_write_png_atomic',side_effect=fail):self.assertFalse(self.w.process_from_staging(source))
        self.assertEqual(source.read_bytes(),raw);self.assertEqual(len(list(self.backup.glob('*.png'))),1)
        with contextlib.closing(sqlite3.connect(self.db)) as c:self.assertEqual(c.execute('SELECT count(*) FROM template_number_registry').fetchone()[0],1)
        self.assertTrue(self.w.process_from_staging(source))
        self.assertEqual(len(list(self.backup.glob('*.png'))),2)
    def test_34_profile_db_failure_keeps_all_recovery_copies(self):
        source=self.incoming();raw=source.read_bytes()
        with patch.object(self.w,'save_template_profile',side_effect=sqlite3.OperationalError('SIMULATED_DB_FAILURE')):
            self.assertFalse(self.w.process_from_staging(source))
        self.assertEqual(source.read_bytes(),raw);self.assertEqual(len(list(self.work.glob('*.png'))),1);self.assertEqual(len(list(self.backup.glob('*.png'))),1)
        with contextlib.closing(sqlite3.connect(self.db)) as c:self.assertEqual(c.execute('SELECT count(*) FROM template_profiles').fetchone()[0],0)
    def test_35_processing_target_conflict_never_replaces(self):
        source=self.incoming();raw=source.read_bytes();processing=source.with_suffix('.jpg.processing');processing.write_bytes(b'ANOTHER_PROCESS')
        self.assertFalse(self.w.process_from_staging(source));self.assertEqual(source.read_bytes(),raw);self.assertEqual(processing.read_bytes(),b'ANOTHER_PROCESS')
    def test_36_staging_without_explicit_opt_in_is_unchanged(self):
        source=self.incoming();raw=source.read_bytes()
        with patch.dict(os.environ,{'MOCKUP_STAGING_IMPORT_APPROVED':''}):self.assertFalse(self.w.process_from_staging(source))
        self.assertEqual(source.read_bytes(),raw);self.assertEqual(list(self.work.iterdir()),[])

class AdditionalEntryPointAcceptance(unittest.TestCase):
    setUp=NumberGuardAcceptance.setUp
    img=NumberGuardAcceptance.img
    def legacy(self):
        spec=importlib.util.spec_from_file_location('number_legacy_extra',ROOT/'V2_KONTROL_MERKEZI/app.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.BASE_DIR=str(self.runtime);return m
    def test_37_legacy_converter_concurrency_uses_create_only_publication(self):
        m=self.legacy();p=self.img();raw=p.read_bytes()
        with ThreadPoolExecutor(max_workers=5) as pool:outputs=list(pool.map(lambda _:m.safe_format_conversion([str(p)],'JPG')[1][0],range(12)))
        self.assertEqual(len(set(outputs)),12);self.assertEqual(p.read_bytes(),raw)
    def test_38_legacy_watermark_cannot_write_into_original_archive(self):
        m=self.legacy();logo=self.img('logo.png');source=self.img(parent=self.runtime/'2_SABLON_HAVUZU_ORIJINAL_YEDEK'/CAT)
        raw=source.read_bytes()
        with self.assertRaises(ValueError):m.safe_watermark_conversion(str(logo),[str(source)])
        self.assertEqual(source.read_bytes(),raw)
        self.assertFalse((source.parent/'FILIGRANLI_GORSELLER').exists())
    def test_39_corrupt_trash_history_fails_closed(self):
        p=self.runtime/'SILINEN_SABLONLAR_COP_KUTUSU/bad_meta.json';p.parent.mkdir();p.write_text('{bad')
        with self.assertRaisesRegex(RuntimeError,'NUMBER_TRASH_HISTORY_UNREADABLE'):ids.validate_number_block(self.runtime,CAT,1000,1)
    def test_40_snapshot_cannot_be_renamed(self):
        p=self.img();tools.rename_images([p],'Art_',self.runtime)
        snap=list((self.external/'_GORSEL_ISIMLENDIRME_YEDEKLERI').glob('*/raw/*.png'))[0];before=snap.read_bytes()
        with self.assertRaisesRegex(ValueError,'RENAME_SNAPSHOT_IMMUTABLE'):tools.rename_images([snap],'Other_',self.runtime)
        self.assertEqual(snap.read_bytes(),before)
    def test_41_recursive_conversion_excludes_recovery_snapshots(self):
        p=self.img('source.jpg');tools.rename_images([p],'Art_',self.runtime)
        report=tools.convert_folder_to_png_recursive(self.external,runtime_root=self.runtime)
        self.assertEqual(report['scanned_image_count'],1);self.assertEqual(report['converted_count'],1)


if __name__=='__main__':unittest.main()
