import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import projection_probe as probe


def sample(ortho=True):
    matrix=[0.0]*16;matrix[0]=matrix[5]=1;matrix[10]=-1
    matrix[15]=1 if ortho else 0;matrix[11]=0 if ortho else -1
    return {'viewport':[1536,1536],'drawing_buffer':[1536,1536],
            'position':[1,2,3],'direction':[0,0,-1],'up':[0,1,0],
            'matrix':matrix,'lengths':[96,96,96] if ortho else [123.42857,96,78.54545],
            'orthographic':ortho,'width':1600,'height':251}


class ProjectionProbeTest(unittest.TestCase):
    def test_scale_pass_and_perspective_control(self):
        for ortho,mode in [(True,'orthographic'),(False,'perspective')]:
            self.assertTrue(probe.check_samples(mode,[sample(ortho) for _ in range(4)])['passed'])

    def test_incomplete_samples(self):
        self.assertFalse(probe.check_samples('orthographic',[sample()]*3)['passed'])

    def test_sdk_reversion(self):
        self.assertFalse(probe.check_samples('orthographic',[sample()]*3+[sample(False)])['passed'])

    def test_scale_mismatch(self):
        s=sample();s['lengths']=[94,96,98]
        self.assertFalse(probe.check_samples('orthographic',[s]*4)['passed'])

    def test_camera_moved(self):
        s=sample();s['position'][0]+=1
        self.assertFalse(probe.check_samples('orthographic',[sample()]*3+[s])['passed'])
        self.assertFalse(probe.check_samples('orthographic',[s]*4,initial=sample())['passed'])

    def test_nonfinite_and_dpr(self):
        for field,value in [('lengths',[float('nan'),96,96]),('drawing_buffer',[3072,3072])]:
            s=sample();s[field]=value
            self.assertFalse(probe.check_samples('orthographic',[s]*4)['passed'])

    def test_config_is_not_mutated(self):
        config=probe.vw.read(probe.vw.CONFIG);before=copy.deepcopy(config)
        with patch.object(probe.vw,'read',return_value=config):
            page=probe.page('secret-test-key')
        self.assertEqual(config,before)
        self.assertNotIn('setTimeout(applyCamera',page)
        self.assertIn('100 m',page);self.assertIn('logo:true',page)
        with self.assertRaises(RuntimeError):probe.vw.secret_safe({'error':'apiKey=secret-test-key'},'secret-test-key')
        self.assertNotIn('secret-test-key',probe.vw.redact('apiKey=secret-test-key','secret-test-key'))

    def test_missing_key_no_outputs(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(probe,'ROOT',Path(temp)),patch.dict(os.environ,{},clear=True):
            with self.assertRaises(ValueError):probe.capture()
            self.assertEqual(list(Path(temp).iterdir()),[])

    def test_run_path_restricted(self):
        for value in ['../x','',None,'2026']:
            with self.assertRaises(ValueError):probe.resolve(value)

    def test_failure_report_has_no_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);probe.vw.write(folder/'report.json',{'modes':{},'files':{},'error':'timeout'})
            self.assertFalse(probe.verify(folder)['projection_verified'])


if __name__=='__main__':unittest.main()
