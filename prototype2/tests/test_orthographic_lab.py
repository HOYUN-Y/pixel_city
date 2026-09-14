import copy
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import orthographic_lab as lab

class OrthographicLabTest(unittest.TestCase):
    def exact(self):
        ref=lab.REFERENCE
        return {'final':{'tower':[lab.project(p) for p in ref['tower']], 'roads':[lab.project(p) for p in ref['roads']],
            'buildings':[{**b,'line':[lab.project(p) for p in b['line']]} for b in ref['buildings']]}}

    def test_crop_and_scale(self):
        self.assertEqual(lab.project([192,256]),[0,0]);self.assertEqual(lab.project([1344,1408]),[1536,1536])
        self.assertEqual(96*lab.project([193,256])[0],128)
        self.assertEqual(lab.seam.OFFSETS,[(0,0),(768,0),(0,768),(768,768)])

    def test_geometry_exact(self):self.assertTrue(lab.geometry({'reference_source':lab.REFERENCE},self.exact())['passed'])

    def test_geometry_missing(self):
        x=self.exact();x['final']['buildings'][0]['line']=None
        self.assertFalse(lab.geometry({'reference_source':lab.REFERENCE},x)['passed'])
        self.assertFalse(lab.geometry({'reference_source':lab.REFERENCE},{})['measured'])

    def test_geometry_drift(self):
        for field in ['roads','tower']:
            x=self.exact();x['final'][field][0][0]+=100
            self.assertFalse(lab.geometry({'reference_source':lab.REFERENCE},x)['passed'])
        x=self.exact();x['final']['buildings'][0]['line'][1][0]+=100
        self.assertFalse(lab.geometry({'reference_source':lab.REFERENCE},x)['passed'])

    def test_geometry_nonfinite(self):
        x=self.exact();x['final']['roads'][0][0]=float('nan')
        self.assertFalse(lab.geometry({'reference_source':lab.REFERENCE},x)['passed'])

    def test_budget_and_failure_block_without_api(self):
        with tempfile.TemporaryDirectory() as t,patch.object(lab.seam.api,'request_json') as call:
            folder=Path(t)
            cases=[{'requests':[{'group':'tower','name':'tower_repair','status':'complete'}]},
                   {'requests':[{'group':'namsan','name':'x','status':'failed'}]},
                   {'requests':[{'group':'namsan','name':str(i),'status':'complete'} for i in range(4)]}]
            for r in cases:
                with self.assertRaises(ValueError):lab.seam.paid(folder,r,'test','tower' if len(r['requests'])==1 else 'namsan','tower_repair','',[],limits=lab.LIMITS)
            call.assert_not_called()

    def test_generate_no_restart(self):
        with patch.object(lab.seam.api,'request_json') as call:
            with self.assertRaises(ValueError):lab.generate(Path('/unused'),{'requests':[{}]},'test')
            call.assert_not_called()

    def test_lock_and_source_alignment(self):
        canvas=Image.new('RGB',(1792,1792));known=Image.new('L',canvas.size)
        lab.seam.commit_tile(canvas,known,Image.new('RGB',(1024,1024),'red'),0)
        locked=lab.seam.commit_tile(canvas,known,Image.new('RGB',(1024,1024),'blue'),1)
        self.assertEqual(locked.getpixel((255,500)),(255,0,0));self.assertEqual(locked.getpixel((256,500)),(0,0,255))

    def test_invalid_run(self):
        for run in [None,'../bad','x']:
            with self.assertRaises(ValueError):lab.load(run)

    def test_mock_lifecycle_and_protected_repair(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)
            Image.new('RGB',(1536,1536),'green').save(folder/'input.png')
            Image.new('RGB',(32,32),'blue').save(folder/'style.png')
            Image.open(folder/'input.png').crop(lab.CORE).resize((1536,1536)).save(folder/'source.png')
            r={'requests':[],'model':lab.seam.api.MODEL,'limits':lab.LIMITS,'request_limit':6,
               'source_sha256':lab.qs.sha(folder/'input.png'),'style_sha256':lab.qs.sha(folder/'style.png'),
               'reference_source':copy.deepcopy(lab.REFERENCE),'repairs':{}}
            def fake_paid(folder,r,key,group,name,prompt,refs,limits):
                self.assertEqual(limits,lab.LIMITS)
                raw=refs[0];raw.save(folder/(name+'_raw.png'))
                r['requests'].append({'name':name,'group':group,'status':'complete','prompt':prompt,'raw_sha256':lab.qs.sha(folder/(name+'_raw.png'))})
                return raw
            with patch.object(lab.seam,'paid',side_effect=fake_paid):lab.generate(folder,r,'test')
            self.assertTrue(lab.verify(folder,r)['technical_passed']);self.assertEqual(len(r['requests']),4)
            candidate=Image.open(folder/'before.png');candidate.putpixel((100,100),(255,0,0));candidate.save(folder/'seam_candidate.png')
            r['repairs']['seam']={'candidate':'seam_candidate.png','edit_box':[200,200,300,300],'accepted':False}
            with self.assertRaisesRegex(ValueError,'protected'):lab.verify(folder,r)

if __name__=='__main__':unittest.main()
