import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import projection_walk as walk

class ProjectionWalkTest(unittest.TestCase):
    def test_configuration(self):walk.validate(walk.qs.read(walk.CONFIG))

    def test_bad_coordinates_and_references(self):
        cfg=walk.qs.read(walk.CONFIG)
        for point in [[-1,3],[float('nan'),3],[1],['x',1]]:
            bad=copy.deepcopy(cfg);bad['route']['points'][0]['xy']=point
            with self.assertRaises(ValueError):walk.validate(bad)
        bad=copy.deepcopy(cfg);bad['route']['points'][0]['behind']=['missing']
        with self.assertRaises(ValueError):walk.validate(bad)

    def test_offline_build_and_tamper(self):
        cfg=walk.qs.read(walk.CONFIG)
        with tempfile.TemporaryDirectory() as temp:
            p2=Path(temp);parent=p2/'eval/vworld/orthographic_lab/runs'/cfg['parent_run'];parent.mkdir(parents=True)
            char=p2/'eval/vworld/seam_lab/runs'/cfg['character_run'];char.mkdir(parents=True)
            for name in ['mosaic.png','before.png','source.png']:Image.new('RGB',(1536,1536),'green').save(parent/name)
            Image.new('RGBA',(24,32),'red').save(char/'traveler.png')
            cfg['image_sha256']=walk.qs.sha(parent/'mosaic.png');cfg['character_sha256']=walk.qs.sha(char/'traveler.png')
            config=p2/'config.json';walk.qs.write(config,cfg)
            with patch.object(walk,'CONFIG',config),patch.object(walk.qs,'P2',p2),patch.object(walk,'ROOT',p2/'output'):
                folder=walk.build();walk.verify(folder)
                self.assertEqual((folder/'final.png').read_bytes(),(parent/'mosaic.png').read_bytes())
                Image.new('L',(1536,1536),0).save(folder/'tower_hit.png')
                with self.assertRaises(ValueError):walk.verify(folder)

if __name__=='__main__':unittest.main()
