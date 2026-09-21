import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from landmark_discovery import build, BASE
from city_snapshot import read, sha

class DiscoveryTests(unittest.TestCase):
    def test_local_snapshot_contract(self):
        if not (BASE/'snapshot/manifest.json').exists():self.skipTest('local dense-polish snapshot unavailable')
        with tempfile.TemporaryDirectory() as temp:
            root=build(Path(temp)/'discovery');snapshot=root/'snapshot'
            m=read(snapshot/'manifest.json');o=read(snapshot/'overlay.json');p=read(snapshot/'places.json');r=read(root/'report.json')
            self.assertTrue(m['reviewOnly']);self.assertFalse(r['userVisualApproval']);self.assertFalse(r['geometryPassed'])
            self.assertEqual(r['paidCalls'],0);self.assertEqual(len(o['landmarks']),3);self.assertEqual(len(o['spots']),5)
            self.assertEqual([l['id'] for l in p['landmarks']],[f'landmark-{i}' for i in range(8)])
            linked=[l for l in p['landmarks'] if l.get('mapSpotId')];self.assertEqual(len(linked),5)
            for l in linked:
                with Image.open(snapshot/l['thumbnail']) as im:self.assertEqual(im.size,(160,100))
                self.assertEqual(m['asset_sha256'][l['thumbnail']],sha(snapshot/l['thumbnail']))
            for name in ['overlay.json','places.json']:self.assertEqual(m['asset_sha256'][name],sha(snapshot/name))
            original=read(BASE/'snapshot/manifest.json')
            for name in original['asset_sha256']:
                if name not in ['overlay.json','places.json']:self.assertEqual(sha(snapshot/name),sha(BASE/'snapshot'/name))
            for l in p['landmarks'][1:3]:self.assertEqual(l['parentPlaceId'],'126508');self.assertIsNone(l['placeId'])
            with self.assertRaises(ValueError):build(root)
