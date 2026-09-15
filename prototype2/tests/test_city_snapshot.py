import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import city_snapshot as city
import city_release

class CitySnapshotTest(unittest.TestCase):
    def test_plain_text(self):
        self.assertEqual(city.plain('<p>서울 &amp; 종로</p><script>secret</script><br>안내'), '서울 & 종로 안내')
        self.assertEqual(city.plain('a'*20, 5), 'aaaaa')

    def test_collected_data_and_source_immutable(self):
        if not city.SOURCE.exists(): self.skipTest('local TourAPI collection unavailable')
        hashes={f:city.sha(city.SOURCE/f) for f in ['manifest.json','places.json','landmarks.json']}
        old_manifest=city.sha(city.RUN/'manifest.json')
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'snapshot';city.build(dest=dest)
            data=city.read(dest/'places.json')
            self.assertEqual(len(data['places']),36);self.assertEqual(len(data['landmarks']),8)
            self.assertEqual(sum(bool(l['parentPlaceId']) for l in data['landmarks']),2)
            self.assertFalse((dest/'source.png').exists())
            text=(dest/'places.json').read_text()
            for forbidden in ['<script','firstimage','/Users/','serviceKey','OPENROUTER_API_KEY']:self.assertNotIn(forbidden,text)
            self.assertEqual(city.sha(dest/'final.png'),city.sha(city.RUN/'final.png'))
            overlay=city.read(dest/'overlay.json');self.assertNotIn('sunset',overlay);self.assertEqual(len(overlay['landmarks']),1)
        self.assertEqual(hashes,{f:city.sha(city.SOURCE/f) for f in hashes})
        self.assertEqual(old_manifest,city.sha(city.RUN/'manifest.json'))

    def test_public_candidate_allowlist(self):
        if not city.DEST.exists(): self.skipTest('snapshot not built')
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'release';city_release.stage(dest)
            self.assertFalse(city.read(dest/'release-rights.json')['approved'])
            self.assertIn('Public image rights approval required',(dest/'check-release.mjs').read_text())
            html=(dest/'public/index.html').read_text()
            self.assertNotIn('id="inspection"',html);self.assertNotIn('src="app.js"',html)
            for p in (dest/'public').rglob('*'):
                if p.is_file():self.assertNotIn(p.name,['source.png','style.png','build.json','config.json','report.json'])
                if p.suffix in ['.json','.html','.js','.css']:
                    self.assertNotIn('/Users/',p.read_text());self.assertNotIn('hoyun0131.pro@gmail.com',p.read_text())
            with self.assertRaises(ValueError):city_release.stage(dest)

    def test_user_decision_is_not_rights_approval(self):
        if not city.DEST.exists(): self.skipTest('snapshot not built')
        with tempfile.TemporaryDirectory() as tmp:
            decision=Path(tmp)/'decision.json'
            city.write(decision,{'userAuthorized':True,'rightsVerified':False,
                'finalSha256':city.sha(city.DEST/'final.png'),'acknowledgement':'Pilot requested; rights unresolved'})
            dest=Path(tmp)/'release';city_release.stage(dest,decision=decision)
            self.assertEqual(city.read(dest/'release-rights.json'),{'approved':False,'userDirectedPilot':True,'rightsVerified':False})

if __name__=='__main__':unittest.main()
