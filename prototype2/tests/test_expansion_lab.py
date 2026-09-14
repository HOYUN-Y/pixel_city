import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import expansion_capture as capture
import expansion_lab as lab


def sample():
    matrix=[0.0]*16;matrix[0]=matrix[5]=.001;matrix[10]=-1;matrix[15]=1
    return {'viewport':[1920,1920],'drawing_buffer':[1920,1920],'orthographic':True,'width':2000,
            'matrix':matrix,'lengths':[96,96,96],'alignment_errors':[0]*9,
            'position':[1,2,3],'direction':[0,0,-1],'up':[0,1,0],
            'expected':{'position':[1,2,3],'direction':[0,0,-1],'up':[0,1,0]}}


class ExpansionTest(unittest.TestCase):
    def test_projection_and_grid(self):
        result=capture.check([sample() for _ in range(4)])
        self.assertTrue(result['passed']);self.assertEqual(result['reference_100m_output_px'],[128]*3)
        self.assertFalse(capture.check([sample()])['passed'])

    def test_projection_rejects_drift_missing_and_nonfinite(self):
        for field,value in [('position',[1.1,2,3]),('alignment_errors',[float('nan')]),('alignment_errors',[2]),
                            ('width',1600),('orthographic',False),('drawing_buffer',[3840,3840]),('lengths',[96,96,98])]:
            s=sample();s[field]=value
            self.assertFalse(capture.check([s]*4)['passed'],field)

    def test_five_tile_assembly_and_parent_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);Image.new('RGB',(1536,1536),'green').save(folder/'parent.png')
            r={'requests':[]}
            for i,name in enumerate(lab.ORDER):
                file='map_'+name+'_raw.png';Image.new('RGB',(1024,1024),(30+i*30,0,0)).save(folder/file)
                r['requests'].append({'name':'map_'+name,'status':'complete','raw_sha256':lab.qs.sha(folder/file)})
            canvas,known,owner=lab.assembly(folder,r)
            self.assertEqual(known.crop(lab.CORE).getextrema(),(255,255))
            self.assertEqual(canvas.getpixel((1000,1000)),(0,128,0))
            self.assertEqual(set(np.unique(owner[128:2432,128:2432])),set(range(1,7)))
            self.assertEqual(canvas.crop(lab.CORE).size,(2304,2304))
            r['requests'][0]['status']='failed'
            with self.assertRaises(ValueError):lab.assembly(folder,r)

    def test_repair_border_and_protected_interior(self):
        mask=lab.edit_mask({'context_box':[256,256,1280,1280],'edit_box':[640,640,896,896]})
        self.assertEqual(mask.getbbox(),(640,640,896,896))
        with self.assertRaises(ValueError):lab.edit_mask({'context_box':[256,256,1280,1280],'edit_box':[640,640,897,897]})
        with self.assertRaises(ValueError):lab.edit_mask({'context_box':[0,0,512,512],'edit_box':[0,0,10,10]})
        self.assertTrue(lab.protected()[896,896]);self.assertFalse(lab.protected()[895,1200])

    def test_generation_edges(self):
        owner=np.array([[1,1,2],[1,1,2],[3,3,2]],dtype=np.uint8)
        self.assertEqual(lab.edges(owner),[[[2,0],[2,3]],[[0,2],[2,2]]])

    def test_missing_correspondence_is_not_pass(self):
        ref={'roads':[[0,0],[20,20]],'building':[[10,10],[30,10]]}
        r={'config':{'references':{name:ref for name in lab.ORDER}}}
        self.assertFalse(lab.geometry(r,{})['passed'])
        self.assertTrue(lab.geometry(r,{'geometry':{name:ref for name in lab.ORDER}})['passed'])
        out=copy.deepcopy(ref);out['roads'][0]=[20,20]
        self.assertFalse(lab.geometry(r,{'geometry':{'A':out}})['passed'])

    def test_closed_run_never_checks_remote_capabilities(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'runs'/'20260914T000000000000Z';folder.mkdir(parents=True)
            lab.qs.write(root/'approved_run.json',{'run_id':folder.name})
            lab.qs.write(folder/'report.json',{'limits':lab.LIMITS,'request_limit':8,'model':lab.seam.api.MODEL,
                'input_sha256':{},'requests':[],'generation_closed':True})
            with patch.object(lab,'ROOT',root),patch.object(sys,'argv',['expansion_lab.py','generate','--run',folder.name,'--allow-external']),patch.object(lab.seam.api,'request_json') as remote:
                with self.assertRaises(ValueError):lab.main()
                remote.assert_not_called()

    def test_invalid_run(self):
        for name in ['../x',None,'','bad']:
            with self.assertRaises(ValueError):lab.resolve(name)

    def test_unapproved_source_never_initializes_or_calls_api(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);config=root/'config.json';src=root/'captures'/'test'
            src.mkdir(parents=True)
            lab.qs.write(config,{'capture_run':'test','source_review':{'approved':False}})
            lab.qs.write(src/'capture.json',{'samples':[sample() for _ in range(4)]})
            with patch.object(lab,'ROOT',root),patch.object(lab,'CONFIG',config),patch.object(lab.seam.api,'request_json') as remote:
                with self.assertRaisesRegex(ValueError,'visually reviewed'):lab.init()
                remote.assert_not_called()
                self.assertFalse((root/'approved_run.json').exists());self.assertFalse((root/'runs').exists())

    def test_build_and_verify_synthetic_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'runs'/'20000101T000000000000Z';folder.mkdir(parents=True)
            walk=root/'walk';walk.mkdir()
            cfg=lab.qs.read(lab.seam.P2/'configs/projection_walk.json')
            overlay={k:cfg[k] for k in ['spots','route','occluders','image_sha256']}
            overlay['landmark']={'id':'tower','mode':'highlight_only','hit':'tower_hit.png','occluder_id':'tower-base'}
            lab.qs.write(walk/'overlay.json',overlay)
            Image.new('L',(1536,1536)).save(walk/'tower_hit.png');Image.new('RGBA',(20,40)).save(walk/'traveler.png')
            lab.qs.write(walk/'manifest.json',{'asset_sha256':{p.name:lab.qs.sha(p) for p in walk.glob('*.png')},'overlay_sha256':{'namsan':lab.qs.sha(walk/'overlay.json')}})
            for name in ['parent','source']:
                Image.new('RGB',(1536,1536) if name=='parent' else (2304,2304),'green').save(folder/(name+'.png'))
            r={'requests':[],'limits':lab.LIMITS,'request_limit':8,'model':lab.seam.api.MODEL,'input_sha256':{},'config':{'references':{}}}
            for i,name in enumerate(lab.ORDER):
                file='map_'+name+'_raw.png';Image.new('RGB',(1024,1024),(i*30,10,10)).save(folder/file)
                r['requests'].append({'name':'map_'+name,'group':'map','status':'complete','raw_sha256':lab.qs.sha(folder/file),'reference_sha256':[]})
            lab.qs.write(root/'approved_run.json',{'run_id':folder.name})
            lab.qs.write(folder/'review.json',{'summary':'SYNTHETIC UNIT TEST, not generated art','traffic':{'accepted':False}})
            with patch.object(lab,'ROOT',root),patch.object(lab,'WALK',walk):
                lab.build(folder,r)
                self.assertTrue(lab.qs.read(folder/'verification.json')['protected_parent_identical'])
                new=lab.qs.read(folder/'overlay.json')
                self.assertEqual(new['spots'][0]['xy'],[v+768 for v in cfg['spots'][0]['xy']])
                im=Image.open(folder/'final.png');im.putpixel((1000,1000),(1,1,1));im.save(folder/'final.png')
                with self.assertRaises(ValueError):lab.verify(folder,r)


if __name__=='__main__':unittest.main()
