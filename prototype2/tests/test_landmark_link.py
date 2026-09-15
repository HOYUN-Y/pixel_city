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
import landmark_link as link
import link_capture as capture

class LinkTests(unittest.TestCase):
    def test_run_validation(self):
        for v in ['',None,'../escape','20260915']:
            with self.assertRaises(ValueError):link.resolve(v)
    def test_ownership(self):
        a=np.asarray(link.ownership({'seam':[[850,0],[900,500],[850,1024]]}))
        self.assertTrue((a[:,:768]==0).all());self.assertTrue((a[:,1025:]==255).all());self.assertEqual(set(np.unique(a)),{0,255})
        with self.assertRaises(ValueError):link.ownership({'seam':[[500,0],[500,1024]]})
    def test_missing_geometry_not_passed(self):
        cfg={'references':{'left':{'roads':[[10,10],[20,20]],'building':[[0,0],[10,0]]}}}
        self.assertFalse(link.geometry(cfg,{})['passed'])
        self.assertTrue(link.geometry(cfg,{'references':cfg['references']})['passed'])
    def test_repair_scope(self):
        link.repair_mask({'context':[0,0,1024,1024],'box':[800,100,900,200]})
        with self.assertRaises(ValueError):link.repair_mask({'context':[0,0,1024,1024],'box':[0,0,1024,1024]})
    def test_capture_gate(self):
        s={'viewport':[1792,1024],'drawing_buffer':[1792,1024],'orthographic':True,'width':1400,'matrix':[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],
           'position':[0,0,0],'direction':[0,0,-1],'up':[0,1,0],'expected':{'position':[0,0,0],'direction':[0,0,-1],'up':[0,1,0]},'lengths':[128]*3,'alignment_errors':[0]*9}
        self.assertTrue(capture.check([s]*4)['passed']);self.assertFalse(capture.check([s]*3)['passed'])
        bad=copy.deepcopy(s);bad['lengths'][2]=float('nan');self.assertFalse(capture.check([s,s,s,bad])['passed'])
        bad=copy.deepcopy(s);bad['position'][0]=1;bad['expected']['position'][0]=1;self.assertFalse(capture.check([s,s,s,bad])['passed'])
    def test_no_key_before_server(self):
        with patch.dict('os.environ',{},clear=True),patch.object(capture,'ThreadingHTTPServer') as server:
            with self.assertRaises(ValueError):capture.capture()
            server.assert_not_called()
    def test_closed_no_api(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run='20260915T130211965290Z';folder=root/'runs'/run;folder.mkdir(parents=True)
            link.qs.write(root/'approved_run.json',{'run_id':run});link.qs.write(folder/'report.json',{'model':link.seam.api.MODEL,'limits':link.LIMITS,'request_limit':4,'input_sha256':{},'generation_closed':True,'requests':[]})
            with patch.object(link,'ROOT',root),patch.object(sys,'argv',['landmark_link.py','generate','--run',run,'--asset','right','--allow-external']),patch.object(link.seam.api,'request_json') as request:
                with self.assertRaises(ValueError):link.main()
                request.assert_not_called()
    def test_build_verify_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run='20260915T130211965290Z';f=root/'runs'/run;f.mkdir(parents=True)
            link.qs.write(root/'approved_run.json',{'run_id':run})
            Image.new('RGB',link.SIZE,'white').save(f/'source.png')
            for name in ['left','right']:Image.new('RGB',(1024,1024),'gray').save(f/(name+'_raw.png'))
            im=Image.new('RGBA',(1024,1024));im.paste((0,128,128,255),(450,450,550,610));im.save(f/'jongno-tower_sprite.png');im.getchannel('A').save(f/'jongno-tower_hit.png');im.crop((450,450,460,470)).save(f/'traveler.png')
            parent={'spots':[{'id':'jongno-tower','xy':[500,600]},{'id':'front','xy':[500,630]},{'id':'back','xy':[500,580]}],
              'occluders':[{'id':'landmark-body','polygon':[[450,450],[550,450],[550,610]]}],
              'landmark':{'id':'jongno-tower','mode':'independent','occluder_id':'landmark-body'}}
            route={'points':[{'xy':[1200,630]},{'xy':[1300,630]}],'playback':'once','title':'test'}
            review={'seam':[[896,0],[896,1024]],'receiver':[[[1200,500],[1400,500],[1400,700]]],'route':route,'connection_route':route,'spots':[{'id':'front','xy':[1200,630]},{'id':'back','xy':[1300,630]}],'summary':'fixture'}
            for name,data in [('parent_overlay',parent),('review',review),('config',{'references':{'left':{'roads':[[1,1],[2,2]],'building':[[1,1],[3,1]]}}}),('capture',{'samples':[{'east_screen':[1,-.2]}]})]:link.qs.write(f/(name+'.json'),data)
            report={'model':link.seam.api.MODEL,'limits':link.LIMITS,'request_limit':4,'input_sha256':{},'requests':[]}
            with patch.object(link,'ROOT',root):
                link.build(f,report);link.verify(f,report)
                Image.new('RGBA',link.SIZE).save(f/'final.png')
                # Even a matching manifest hash cannot bless edits unrelated to the compositor.
                manifest=link.qs.read(f/'manifest.json');manifest['asset_sha256']['final.png']=link.qs.sha(f/'final.png');link.qs.write(f/'manifest.json',manifest)
                with self.assertRaises(ValueError):link.verify(f,report)

if __name__=='__main__':unittest.main()
