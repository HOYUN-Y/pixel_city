import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import dense_roads as roads


class RoadReviewTest(unittest.TestCase):
    def test_threshold_keeps_reading_uncertainty(self):
        self.assertEqual(roads.classify_distance(1,2),'pass')
        self.assertEqual(roads.classify_distance(8,2),'needs_repair')
        self.assertEqual(roads.classify_distance(3,2),'inconclusive')
        self.assertEqual(roads.classify_distance(0,6),'inconclusive')

    def test_edge_normal_ignores_along_road_shift(self):
        c={'source':[20,20],'output':[120,22],'kind':'edge','normal':[0,2],'uncertainty_px':1}
        self.assertEqual(roads.measure(c)['distance_px'],2)
        self.assertEqual(roads.measure(c)['status'],'pass')

    def test_corners_use_euclidean_distance(self):
        c={'source':[20,20],'output':[23,24],'kind':'corner','uncertainty_px':0}
        self.assertEqual(roads.measure(c)['distance_px'],5)
        self.assertEqual(roads.measure(c)['status'],'needs_repair')

    def test_hidden_correspondence_never_passes(self):
        self.assertEqual(roads.measure({'source':[0,0],'output':None})['status'],'inconclusive')

    def test_invalid_measurements_rejected(self):
        for d,u in [(float('nan'),0),(0,-1),(float('inf'),1)]:
            with self.assertRaises(ValueError):roads.classify_distance(d,u)
        with self.assertRaises(ValueError):roads.measure({'source':[0,0],'output':[1,1],'kind':'edge','normal':[0,0],'uncertainty_px':1})

    def test_inventory_covers_all_seams_and_junctions(self):
        items=roads.inventory()
        self.assertEqual(len({i['id'] for i in items}),53)
        self.assertEqual(sum(i['kind']=='seam' for i in items),38)
        self.assertEqual(sum(i['kind']=='junction' for i in items),15)
        for i in items:
            l,t,r,b=i['box'];self.assertTrue(0<=l<r<=4608 and 0<=t<b<=3072)

    def test_corridor_centers_keep_unknown_and_boundary_separate(self):
        from PIL import ImageDraw
        mask=Image.new('L',(40,40));ImageDraw.Draw(mask).rectangle((0,10,39,30),fill=255)
        records=[{'xy':[120,y]} for y in (120,110,105)]+[{'xy':[50,120]}]
        result=roads.corridor_checks(records,mask,[100,100,140,140])
        self.assertEqual([r['road_status'] for r in result['records']],
                         ['inside_road','boundary_uncertain','outside_road','outside_review_scope'])
        with self.assertRaises(ValueError):roads.corridor_checks(records,mask,[0,0,20,20])

    def test_review_preserves_gate_and_input_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);image=root/'image.png';Image.new('RGB',(10,10),'gray').save(image)
            inputs={k:v for name in ('source','final') for k,v in [(name,str(image)),(name+'_sha256',roads.sha(image))]}
            roads.write(root/'inputs.json',inputs)
            data={'inputs':inputs,'regions':{i['id']:{'visibility':'no_visible_road','note':'Synthetic test only'} for i in roads.inventory()},
                  'controls':[{'source':[1,1],'output':[1,1],'kind':'corner','uncertainty_px':0}]}
            annotations=root/'annotations.json';roads.write(annotations,data)
            report=roads.review(root,annotations)
            self.assertEqual(report['counts']['pass'],1)
            self.assertFalse(report['geometryPassed']);self.assertFalse(report['all_roads_passed'])
            frozen={'source_sha256':inputs['source_sha256'],
                    'controls':[{k:v for k,v in c.items() if k!='output'} for c in data['controls']]}
            roads.write(root/'source_controls_frozen.json',frozen)
            self.assertEqual(roads.review(root,annotations)['counts']['pass'],1)
            frozen['controls'][0]['source']=[2,2];roads.write(root/'source_controls_frozen.json',frozen)
            with self.assertRaisesRegex(ValueError,'Frozen source controls'):roads.review(root,annotations)
            frozen['controls'][0]['source']=[1,1];roads.write(root/'source_controls_frozen.json',frozen)
            data['regions'].pop('v0_0');roads.write(annotations,data)
            with self.assertRaisesRegex(ValueError,'Incomplete'):roads.review(root,annotations)
            Image.new('RGB',(10,10),'red').save(image)
            with self.assertRaisesRegex(ValueError,'Frozen'):roads.review(root,annotations)


if __name__=='__main__':unittest.main()
