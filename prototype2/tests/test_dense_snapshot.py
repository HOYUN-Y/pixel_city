import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import dense_snapshot as dense
from city_snapshot import write,read,sha
import city_release

def fixture(source):
    """Non-art diagnostic blocks only, never a generated-map substitute."""
    source.mkdir(parents=True)
    Image.new('RGB',(4608,3072),'#777788').save(source/'background.png')
    items=[]
    for i,id in enumerate(['gwanghwamun','bosingak','jongno-tower']):
        Image.new('RGBA',(48,64),'#ffffff').save(source/f'{id}.png');Image.new('L',(48,64),255).save(source/f'{id}_hit.png')
        items.append({'id':id,'sprite':f'{id}.png','hit':f'{id}_hit.png','rect':[500+i*1300,1500,48,64],'anchor':[524+i*1300,1564],'occluder_id':id+'-body','reveal_only':id=='bosingak'})
    Image.new('RGB',(100,100),'#223344').save(source/'underlay.png');Image.new('L',(100,100),255).save(source/'mask.png')
    data={'testFixture':True,'run_id':'diagnostic-not-generated','width':4608,'height':3072,'background':'background.png','landmarks':items,
          'reveal':{'targetId':'bosingak','rect':[1775,1480,100,100],'underlay':'underlay.png','mask':'mask.png'},
          'route':{'playback':'once','points':[{'xy':[450,1570]},{'xy':[650,1570]}]},
          'traffic':{'speed':32,'focus':[2000,1800],'lanes':[{'id':'east','start':[1200,1800],'end':[3200,1800],'offsets':[.15],'sprite':'car_se.png'},{'id':'west','start':[3200,1810],'end':[1200,1810],'offsets':[.15],'sprite':'car_nw.png'}]},
          'acceptance':dict.fromkeys(dense.GATES,True)}
    write(source/'delivery.json',data);return data

class DenseSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.assets=tempfile.TemporaryDirectory();self.addCleanup(self.assets.cleanup)
        root=Path(self.assets.name)
        for name in ['traveler.png','car_se.png','car_nw.png']:Image.new('RGBA',(16,16),'white').save(root/name)
        write(root/'places.json',{'landmarks':[{'id':str(i),'name':name} for i,name in enumerate(['광화문','보신각','종로타워','미연결'])],'places':[]})
        mocked=patch.object(dense,'DEST',root);mocked.start();self.addCleanup(mocked.stop)

    def test_auto_foreground_and_visual_results_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'source';d=fixture(src)
            Image.new('L',(100,100),255).save(src/'foreground.png')
            d['reveal'].update(auto=True,foregroundMask='foreground.png')
            d['visualAcceptance']={'userVisualApproval':False}
            write(src/'delivery.json',d);dest=Path(tmp)/'export';dense.export(src,dest)
            self.assertTrue(read(dest/'overlay.json')['reveal']['auto'])
            self.assertIn('bosingak_foreground.png',read(dest/'manifest.json')['asset_sha256'])
            self.assertFalse(read(dest/'build.json')['visualAcceptance']['userVisualApproval'])
    def test_traffic_occlusion_mask_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'source';d=fixture(src)
            Image.new('L',(20,30),255).save(src/'traffic.png')
            d['traffic']['occluders']=[{'id':'building','rect':[100,100,20,30],'mask':'traffic.png','lanes':['east']}]
            write(src/'delivery.json',d);dest=Path(tmp)/'export';dense.export(src,dest)
            item=read(dest/'overlay.json')['traffic']['occluders'][0]
            self.assertEqual(item['mask'],'traffic_occlusion_0.png')
            self.assertEqual(sha(src/'traffic.png'),read(dest/'manifest.json')['asset_sha256'][item['mask']])

    def test_bad_traffic_occlusion_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'source';d=fixture(src)
            Image.new('L',(20,30),255).save(src/'traffic.png')
            d['traffic']['occluders']=[{'id':'building','rect':[100,100,21,30],'mask':'traffic.png','lanes':['east']}]
            write(src/'delivery.json',d)
            with self.assertRaisesRegex(ValueError,'traffic mask'):dense.export(src,Path(tmp)/'bad-size')
            d['traffic']['occluders'][0]['lanes']=['missing'];write(src/'delivery.json',d)
            with self.assertRaisesRegex(ValueError,'placement'):dense.export(src,Path(tmp)/'bad-lane')
    def test_tile_export_contract_and_fixture_deployment_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'source';fixture(src);dest=Path(tmp)/'export';dense.export(src,dest)
            m=read(dest/'manifest.json');self.assertEqual(len(list((dest/'tiles').rglob('*.png'))),75)
            with Image.open(dest/'preview.png') as im:self.assertEqual(im.size,(1152,768))
            with Image.open(dest/'tiles/0.5/4_2.png') as im:self.assertEqual(im.size,(256,512))
            for file,digest in m['asset_sha256'].items():self.assertEqual(sha(dest/file),digest)
            self.assertFalse((dest/'background.png').exists())
            self.assertEqual(sum(bool(l['mapSpotId']) for l in read(dest/'places.json')['landmarks']),3)
            with self.assertRaisesRegex(ValueError,'fixtures'):city_release.stage(Path(tmp)/'release',snapshot=dest)
            with self.assertRaises(ValueError):dense.export(src,dest)

    def test_reject_incomplete_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'source';d=fixture(src);d['acceptance']['geometryPassed']=False;write(src/'delivery.json',d)
            with self.assertRaisesRegex(ValueError,'acceptance'):dense.export(src,Path(tmp)/'export')

    def test_review_snapshot_preserves_failed_gates_and_cannot_deploy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'source';d=fixture(src)
            d['testFixture']=False;d['acceptance']['geometryPassed']=False;write(src/'delivery.json',d)
            with patch.object(dense,'P2',root):
                with self.assertRaisesRegex(ValueError,'local work'):dense.export(src,root/'outside',review_only=True)
                dest=root/'work/review';dense.export(src,dest,review_only=True)
            self.assertTrue(read(dest/'manifest.json')['reviewOnly'])
            self.assertFalse(read(dest/'build.json')['acceptance']['geometryPassed'])
            with self.assertRaisesRegex(ValueError,'Review-only'):city_release.stage(root/'release',snapshot=dest)

if __name__=='__main__':unittest.main()
