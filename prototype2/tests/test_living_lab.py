import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import living_lab as lab


class LivingLabTest(unittest.TestCase):
    def test_mask_preserves_source_reconstruction(self):
        original=Image.new('RGBA',(32,32),'red')
        m=lab.mask([[[5,5],[20,5],[20,20],[5,20]]],(32,32))
        sprite=original.copy();sprite.putalpha(m)
        background=original.copy();background.paste(Image.new('RGBA',(32,32),'blue'),(0,0),m)
        self.assertEqual(Image.alpha_composite(background,sprite).tobytes(),original.tobytes())

    def test_separate_two_request_limit_blocks_third(self):
        with tempfile.TemporaryDirectory() as temp:
            report={'requests':[{'group':'background','name':'background','status':'complete'},{'group':'cars','name':'cars','status':'complete'}]}
            with patch.object(lab.api,'request_json') as request:
                with self.assertRaises(ValueError):
                    lab.seam.paid(Path(temp),report,'secret','cars','extra','prompt',[],limits=lab.LIMITS)
                request.assert_not_called()

    def test_review_must_be_run_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(lab.api.qs,'read',return_value={'review_run':'another','accepted':True}):
                with self.assertRaises(ValueError):lab.build(Path(temp),{})

    def test_wrong_ledger_cannot_generate(self):
        with self.assertRaises(ValueError):lab.generate(Path('/unused'),{'kind':'seam_lab'},'cars')

    def test_light_inside_tower(self):
        cfg=lab.api.qs.read(lab.CONFIG)
        tower=lab.mask([cfg['tower_polygon']]);light=lab.mask(cfg['light_polygons'])
        self.assertFalse(((lab.np.asarray(light)>0)&(lab.np.asarray(tower)==0)).any())


if __name__=='__main__':unittest.main()
