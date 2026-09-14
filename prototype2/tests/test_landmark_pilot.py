import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import landmark_pilot as lab


def spec():
    return {'outline':[[400,400],[599,400],[599,599],[400,599]],'holes':[[[470,430],[529,430],[529,459],[470,459]]],
            'context':[372,372,628,628],'anchor':[500,599],'roads':[[700,700],[800,800]],'neighbor_width':[[200,200],[250,200]]}


class LandmarkPilotTest(unittest.TestCase):
    def test_source_mask_preserves_void(self):
        s=spec();lab.validate_source(s);mask=lab.silhouette(s)
        self.assertEqual(mask.getpixel((500,440)),0);self.assertEqual(mask.getpixel((500,500)),255)

    def test_source_rejects_clipping_and_unmeasured_baseline(self):
        for field,value in [('context',[450,450,706,706]),('roads',[]),('anchor',[float('nan'),10]),('neighbor_width',[[1,1],[1,1]])]:
            s=spec();s[field]=value
            with self.assertRaises(ValueError):lab.validate_source(s)

    def test_repair_is_local(self):
        self.assertEqual(lab.repair_mask({'edit_box':[100,100,200,200]}).getbbox(),(100,100,200,200))
        with self.assertRaises(ValueError):lab.repair_mask({'edit_box':[0,0,1024,1024]})

    def test_no_approved_scene_means_no_run_or_api(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cfg=root/'config.json';src=root/'sources.json'
            lab.qs.write(cfg,{'size':1024,'width_m':800,'request_limits':lab.LIMITS});lab.qs.write(src,{})
            with patch.object(lab,'ROOT',root),patch.object(lab,'CONFIG',cfg),patch.object(lab,'SOURCES',src),patch.object(lab.seam.api,'request_json') as api:
                with self.assertRaisesRegex(ValueError,'No visually approved'):lab.init()
                api.assert_not_called();self.assertFalse((root/'approved_run.json').exists())

    def test_invalid_run(self):
        for value in ['../x','',None,'bad']:
            with self.assertRaises(ValueError):lab.resolve(value)

    def test_closed_run_no_remote_call(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            lab.qs.write(folder/'report.json',{'generation_closed':True})
            with patch.object(lab,'resolve',return_value=folder),patch.object(lab,'inputs_ok'),patch.object(sys,'argv',['landmark_pilot.py','generate','--run','x','--scene','gwanghwamun','--asset','sprite','--allow-external']),patch.object(lab.seam.api,'request_json') as api:
                with self.assertRaisesRegex(ValueError,'closed'):lab.main()
                api.assert_not_called()

    def test_single_use_slots_and_no_budget_transfer(self):
        self.assertEqual(sum(lab.LIMITS.values()),6)
        for scene in lab.SCENES:self.assertEqual(sum(v for k,v in lab.LIMITS.items() if k.startswith(scene+'_')),3)
        with tempfile.TemporaryDirectory() as temp,patch.object(lab.seam.api,'request_json') as api:
            r={'requests':[{'name':'gwanghwamun_background','group':'gwanghwamun_background','status':'complete'}]}
            with self.assertRaises(ValueError):lab.seam.paid(Path(temp),r,'test','gwanghwamun_background','different-name','test',[],limits=lab.LIMITS)
            api.assert_not_called()

    def test_compose_keeps_alpha_uniform_scale_and_void(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);s=spec();r={'sources':{'gwanghwamun':s}}
            Image.new('RGB',(1024,1024),'green').save(folder/'gwanghwamun_background_raw.png')
            cut=lab.silhouette(s).crop(s['context']).resize((1024,1024),Image.Resampling.NEAREST)
            raw=Image.new('RGBA',(1024,1024),'red');raw.putalpha(cut);raw.save(folder/'gwanghwamun_sprite_raw.png')
            review={'generated_anchor':s['anchor'],'roads':s['roads'],'neighbor_width':s['neighbor_width'],'void_reviewed':True,'void_valid':True}
            plate,sprite,hit,final,metrics=lab.compose(folder,r,'gwanghwamun',review)
            self.assertTrue(metrics['landmark_passed']);self.assertTrue(metrics['background_passed']);self.assertEqual(metrics['source_void_opaque_pixels'],0)
            self.assertEqual(final.getpixel((500,440)),plate.getpixel((500,440)))
            self.assertEqual(final.getpixel((500,500)),(255,0,0,255))
            self.assertEqual(final.getpixel((0,0)),plate.getpixel((0,0)))
            missing=lab.compose(folder,r,'gwanghwamun',{})[-1]
            self.assertFalse(missing['landmark_passed']);self.assertFalse(missing['background_passed']);self.assertFalse(missing['void_passed'])
            with self.assertRaises(ValueError):lab.compose(folder,r,'gwanghwamun',{'sprite_offset':[17,0]})
            with self.assertRaises(ValueError):lab.compose(folder,r,'gwanghwamun',{'sprite_scale':float('nan')})
            small=lab.compose(folder,r,'gwanghwamun',{**review,'sprite_scale':.125})[-1]
            self.assertEqual(small['uniform_scale'],.125);self.assertFalse(small['landmark_passed'])

    def test_sprite_cannot_be_opaque_or_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);Image.new('RGB',(1024,1024),'green').save(folder/'gwanghwamun_background_raw.png')
            for alpha in [0,255]:
                Image.new('RGBA',(1024,1024),(255,0,0,alpha)).save(folder/'gwanghwamun_sprite_raw.png')
                with self.assertRaises(ValueError):lab.compose(folder,{'sources':{'gwanghwamun':spec()}},'gwanghwamun',{})

    def test_one_scene_build_verify_and_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'runs'/'20000101T000000000000Z';folder.mkdir(parents=True);s=spec()
            lab.qs.write(folder/'sources.json',{'gwanghwamun':s})
            lab.qs.write(folder/'config.json',{'scenes':{'gwanghwamun':{'label':'SYNTHETIC FIXTURE'}}})
            Image.new('RGB',(1024,1024),'green').save(folder/'gwanghwamun_source.png')
            Image.new('RGBA',(20,40),(255,255,0,255)).save(folder/'traveler.png')
            inputs={p.name:lab.qs.sha(p) for p in folder.iterdir()}
            Image.new('RGB',(1024,1024),'green').save(folder/'gwanghwamun_background_raw.png')
            raw=Image.new('RGBA',(1024,1024),'red');raw.putalpha(lab.silhouette(s).crop(s['context']).resize((1024,1024),Image.Resampling.NEAREST));raw.save(folder/'gwanghwamun_sprite_raw.png')
            requests=[{'name':'gwanghwamun_'+k,'group':'gwanghwamun_'+k,'status':'complete','raw_sha256':lab.qs.sha(folder/('gwanghwamun_'+k+'_raw.png')),'reference_sha256':[]} for k in ['background','sprite']]
            r={'run_id':folder.name,'model':lab.seam.api.MODEL,'request_limit':6,'limits':lab.LIMITS,'sources':{'gwanghwamun':s},'blocked_scenes':{'jongno-tower':'source unavailable'},'input_sha256':inputs,'requests':requests}
            lab.qs.write(root/'approved_run.json',{'run_id':folder.name})
            sr={'publish':True,'summary':'Synthetic unit fixture, not generated art','spots':[{'id':'gwanghwamun','xy':[500,599]},{'id':'front','xy':[500,650]},{'id':'back','xy':[500,580]}],'route':{'points':[{'xy':[400,650]},{'xy':[550,580]}]}}
            lab.qs.write(folder/'review.json',{'scenes':{'gwanghwamun':sr}})
            with patch.object(lab,'ROOT',root):
                lab.build(folder,r)
                m=lab.qs.read(folder/'manifest.json');self.assertEqual(list(m['scenes']),['gwanghwamun']);self.assertIn('jongno-tower',m['blocked_scenes'])
                v=lab.qs.read(folder/'verification.json');self.assertTrue(v['technical_passed']);self.assertFalse(v['geometry']['gwanghwamun']['overall_geometry_passed'])
                im=Image.open(folder/'gwanghwamun_final.png');im.putpixel((0,0),(255,0,0,255));im.save(folder/'gwanghwamun_final.png')
                with self.assertRaisesRegex(ValueError,'composition'):lab.verify(folder,r)


if __name__=='__main__':unittest.main()
