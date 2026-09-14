import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import landmark_capture as capture


def sample():
    m=[0.0]*16;m[0]=m[5]=.0025;m[10]=-1;m[15]=1
    vectors={'position':[1,2,3],'direction':[0,0,-1],'up':[0,1,0]}
    return {'viewport':[1024,1024],'drawing_buffer':[1024,1024],
            'orthographic':True,'width':800,'matrix':m,'lengths':[128]*3,
            'ground_anchor':[512,600],'expected':copy.deepcopy(vectors),**vectors}


class LandmarkCaptureTest(unittest.TestCase):
    def test_fixed_projection(self):
        r=capture.check([sample() for _ in range(4)])
        self.assertTrue(r['passed']);self.assertEqual(r['reference_100m_px'],[128]*3)

    def test_invalid_samples(self):
        for field,value in [('viewport',[1536,1536]),('width',1600),('orthographic',False),
                            ('lengths',[128,128,131]),('lengths',[float('nan')]*3),
                            ('position',[1.1,2,3]),('ground_anchor',[-1,100]),('ground_anchor',[float('nan'),100])]:
            s=sample();s[field]=value
            self.assertFalse(capture.check([s]*4)['passed'],field)
        self.assertFalse(capture.check([sample()])['passed'])

    def test_recomputed_expected_cannot_hide_camera_drift(self):
        samples=[sample() for _ in range(4)];samples[-1]['position'][0]=2;samples[-1]['expected']['position'][0]=2
        self.assertFalse(capture.check(samples)['passed'])

    def test_ephemeral_page_has_requested_scene_and_camera(self):
        page=capture.page('TEST_SECRET','jongno-tower')
        self.assertIn('TEST_SECRET',page)  # In memory only, never a stored page.
        self.assertIn('126.983656',page);self.assertIn('new C.OrthographicFrustum()',page)
        self.assertIn('f.width=800',page);self.assertNotIn('setTimeout(applyCamera',page)

    def test_missing_key_stops_before_server(self):
        with patch.dict('os.environ',{'VWORLD_API_KEY':''}),patch.object(capture,'ThreadingHTTPServer') as server:
            with self.assertRaisesRegex(ValueError,'missing'):capture.capture('gwanghwamun')
            server.assert_not_called()


if __name__=='__main__':unittest.main()
