import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from discovery_extension import build, BASE, CAPTURE, project
from city_snapshot import read, write, sha
from city_release import stage, validate_modules

class ExtendedDiscoveryTests(unittest.TestCase):
    def setUp(self):
        if not CAPTURE.exists() or not (BASE/'snapshot/manifest.json').exists():self.skipTest('local discovery snapshot/capture unavailable')
    def test_projection_and_eight_linked_contract(self):
        self.assertEqual(project(126.9769154284,37.5729534722,read(CAPTURE))[0],[2350,1987])
        with tempfile.TemporaryDirectory() as tmp:
            root=build(Path(tmp)/'extended');s=root/'snapshot';m=read(s/'manifest.json');o=read(s/'overlay.json');p=read(s/'places.json')
            self.assertEqual(m['experience'],'discovery');self.assertTrue(m['reviewOnly'])
            self.assertEqual(len(o['spots']),8);self.assertEqual(len(o['landmarks']),3)
            self.assertEqual(sum(x.get('selectionMode')=='location-only' for x in o['spots']),2)
            self.assertEqual(sum('hitPolygon' in x for x in o['spots']),3)
            self.assertEqual([l['id'] for l in p['landmarks']],[f'landmark-{i}' for i in range(8)])
            self.assertTrue(all(l['mapSpotId'] in {x['id'] for x in o['spots']} for l in p['landmarks']))
            for name,digest in m['asset_sha256'].items():self.assertEqual(sha(s/name),digest)
            base=read(BASE/'snapshot/manifest.json')
            for name,digest in base['asset_sha256'].items():
                if name not in ['places.json','overlay.json']:self.assertEqual(sha(s/name),digest)
            with self.assertRaises(ValueError):build(root)

    def test_review_package_modules_and_unconditional_build_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s=build(root/'extended')/'snapshot'
            with self.assertRaisesRegex(ValueError,'Review-only'):stage(root/'production',snapshot=s)
            stage(root/'package',snapshot=s,local_review=True)
            pkg=root/'package';validate_modules(pkg/'public')
            self.assertIn('data-city-experience="discovery"',(pkg/'public/index.html').read_text())
            self.assertTrue(read(pkg/'release-manifest.json')['localOnly'])
            self.assertTrue((pkg/'public/discovery.js').is_file())
            write(pkg/'release-rights.json',{'approved':True,'userDirectedPilot':True})
            result=subprocess.run(['node','check-release.mjs'],cwd=pkg,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn('Local-only',result.stderr)
            # Module closure validation catches precisely the previous packaging omission.
            (pkg/'public/discovery.js').unlink()
            with self.assertRaisesRegex(ValueError,'Missing packaged module'):validate_modules(pkg/'public')
            with self.assertRaisesRegex(ValueError,'authorization'):stage(root/'mixed',approval=Path('unused'),snapshot=s,local_review=True)
            for f in (pkg/'public').rglob('*'):
                if f.is_file():self.assertNotIn(f.name,['capture.json','report.json','.env','build.json'])
