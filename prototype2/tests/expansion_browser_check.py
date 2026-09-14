"""2304px interaction regression. --fixture is synthetic, never a generated map result."""
import argparse
import copy
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
from PIL import Image,ImageDraw
from playwright.sync_api import sync_playwright

P2=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P2/'scripts'))
import qwen_style as qs

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*_):pass


def fixture(root):
    (root/'web').symlink_to(P2/'web',target_is_directory=True)
    folder=root/'eval/vworld/projection_expand/runs/20000101T000000000000Z';folder.mkdir(parents=True)
    walk=P2/'eval/vworld/projection_walk/runs/20260914T115537004661Z'
    original=qs.read(walk/'manifest.json');overlay=copy.deepcopy(qs.read(walk/'overlay.json'))
    im=Image.new('RGB',(2304,2304),'#BCD39B');im.paste(Image.open(walk/'final.png'),(768,768))
    draw=ImageDraw.Draw(im);draw.text((100,100),'SYNTHETIC TEST FIXTURE - NOT GENERATED EXPANSION',fill='black')
    for name in ['final','before','source']:im.save(folder/(name+'.png'))
    shift=lambda p:[v+768 for v in p]
    for s in overlay['spots']:s['xy']=shift(s['xy'])
    for p in overlay['route']['points']:p['xy']=shift(p['xy'])
    for o in overlay['occluders']:o['polygon']=[shift(p) for p in o['polygon']]
    overlay['image_sha256']=qs.sha(folder/'final.png')
    overlay['generation_edges']=[[[768,0],[768,2304]],[[0,768],[2304,768]]]
    overlay['traffic']={'speed':28,'lanes':[
        {'id':'forward','sprite':'car_se.png','start':[600,600],'end':[1100,1100],'offsets':[.13,.63]},
        {'id':'back','sprite':'car_nw.png','start':[1110,1090],'end':[610,590],'offsets':[.31,.81]}],
        'occluders':[{'id':'fixture-mask','polygon':[[790,790],[830,790],[830,830],[790,830]]}]}
    qs.write(folder/'overlay.json',overlay)
    hit=Image.new('L',(2304,2304));hit.paste(Image.open(walk/'tower_hit.png'),(768,768));hit.save(folder/'tower_hit.png')
    shutil.copyfile(walk/'traveler.png',folder/'traveler.png')
    for f in ['car_se.png','car_nw.png']:shutil.copyfile(P2/'eval/vworld/seam_lab/runs/20260914T084137369841Z'/f,folder/f)
    manifest={'version':1,'kind':'projection-expand','run_id':folder.name,'width':2304,'height':2304,'character':'traveler.png',
      'asset_sha256':{p.name:qs.sha(p) for p in folder.glob('*.png')},'overlay_sha256':{'namsan':qs.sha(folder/'overlay.json')},
      'scenes':{'namsan':{'label':'TEST FIXTURE','review':'Synthetic runtime fixture, not a map result','overlay':'overlay.json',
      'variants':{key:{'label':key,'file':key+'.png','sha256':qs.sha(folder/(key+'.png'))} for key in ['source','before','final']}}}}
    qs.write(folder/'manifest.json',manifest)
    return folder


def check(root,folder,is_fixture=False):
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(root)))
    threading.Thread(target=server.serve_forever,daemon=True).start();origin=f'http://127.0.0.1:{server.server_port}'
    url=origin+'/web/pilot/?view=projection-expand&run='+folder.name
    report={'passed':False,'fixture':is_fixture,'road_visual_validation':False,'errors':[],'external':[],'views':{}}
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            for name,w,h,dpr,motion in [('desktop',1440,900,1,'no-preference'),('tablet',1024,768,1,'reduce'),('mobile',390,844,2,'reduce'),('mobile3',390,844,3,'no-preference')]:
                ctx=browser.new_context(viewport={'width':w,'height':h},device_scale_factor=dpr,reduced_motion=motion)
                def guard(route):
                    if not route.request.url.startswith(origin+'/'):report['external'].append(route.request.url);route.abort()
                    elif route.request.method not in ['GET','HEAD']:report['errors'].append('Mutation attempted');route.abort()
                    else:route.continue_()
                ctx.route('**/*',guard);p=ctx.new_page();p.on('pageerror',lambda e:report['errors'].append(str(e)))
                p.goto(url);p.wait_for_selector('body[data-tiles-ready="true"]');c=p.locator('#map')
                def frame():p.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                def inspect():
                    if p.locator('#inspection').get_attribute('open') is None:p.locator('#inspection summary').click()
                frame();assert c.get_attribute('data-playing')=='false';assert c.get_attribute('data-traffic-playing')=='false'
                assert json.loads(c.get_attribute('data-center'))=={'x':1152,'y':1152}
                assert float(c.get_attribute('data-scale'))*2304<=min(w,h)
                p.screenshot(path=str(folder/f'{name}_initial.png'))
                inspect();p.locator('#tower-focus').click();frame();inspect();p.locator('#lab-spot').select_option('tower');frame()
                assert c.get_attribute('data-selected')=='tower';p.locator('[data-lab-clear]').click()
                inspect();assert p.locator('#tower-light').is_hidden();assert p.locator('#tower-visible').is_hidden()
                p.locator('#lab-follow').uncheck()
                occlusions=[]
                for v in range(0,1001,25):
                    p.locator('#lab-phase').evaluate('(e,v)=>{e.value=v;e.dispatchEvent(new Event("input"));}',v);frame()
                    occlusions.append([int(c.get_attribute('data-actor-visible')),int(c.get_attribute('data-actor-occluded'))])
                assert any(a==0 and b>0 for a,b in occlusions)
                has_traffic=p.locator('#traffic-controls').is_visible()
                if has_traffic:
                    p.locator('#traffic-focus').click();frame();inspect();p.locator('#traffic-play').click();p.wait_for_timeout(200);frame()
                    assert float(c.get_attribute('data-traffic-time'))>0
                    p.locator('#traffic-play').click();frame();stopped=c.get_attribute('data-traffic-time');p.wait_for_timeout(100);assert c.get_attribute('data-traffic-time')==stopped
                    samples=[]
                    for v in range(0,601,10):
                        p.locator('#traffic-phase').evaluate('(e,v)=>{e.value=v;e.dispatchEvent(new Event("input"));}',v);frame()
                        vehicles=json.loads(c.get_attribute('data-vehicles'));assert len(vehicles)==4
                        assert all(0<=v<=2304 for car in vehicles for v in car['xy'])
                        samples.append(vehicles)
                    p.screenshot(path=str(folder/f'{name}_traffic.png'))
                    p.locator('#traffic-visible').click();frame();assert json.loads(c.get_attribute('data-vehicles'))==[]
                    p.locator('#traffic-visible').click()
                    if name=='desktop':
                        p.locator('#traffic-phase').evaluate('e=>{e.value=0;e.dispatchEvent(new Event("input"));}');p.locator('#traffic-play').click()
                        for _ in range(6):
                            p.wait_for_timeout(10000);print('Expansion browser: 60s playback in progress',flush=True)
                        p.locator('#traffic-play').click();frame();assert float(c.get_attribute('data-traffic-time'))>30
                        report['real_time_playback_seconds']=60
                        p.locator('#traffic-play').click()
                        p.evaluate('()=>{Object.defineProperty(document,"hidden",{configurable:true,get:()=>true});document.dispatchEvent(new Event("visibilitychange"));}')
                        frame();frozen=c.get_attribute('data-traffic-time');p.wait_for_timeout(250);assert c.get_attribute('data-traffic-time')==frozen
                        p.evaluate('()=>{delete document.hidden;document.dispatchEvent(new Event("visibilitychange"));}');p.wait_for_timeout(100);p.locator('#traffic-play').click()
                center=c.get_attribute('data-center');scale=c.get_attribute('data-scale')
                for mode in ['source','before','final']:
                    p.locator('#map-mode').select_option(mode);frame()
                    assert c.get_attribute('data-playing')=='false';assert c.get_attribute('data-traffic-playing')=='false'
                    assert c.get_attribute('data-center')==center and c.get_attribute('data-scale')==scale
                    if mode!='final':assert json.loads(c.get_attribute('data-vehicles'))==[] and p.locator('#lab-play').is_disabled()
                p.locator('#lab-pins').uncheck();p.locator('#lab-route').uncheck();p.locator('#walk-actor').uncheck()
                if has_traffic:p.locator('#traffic-visible').click()
                p.locator('button[data-scale="1"]').click();frame()
                same=p.evaluate('''async url=>{const c=document.querySelector('#map'),r=c.getBoundingClientRect(),d=devicePixelRatio,s=Number(c.dataset.scale),p=JSON.parse(c.dataset.center);const im=await createImageBitmap(await(await fetch(url)).blob());const ref=document.createElement('canvas');ref.width=c.width;ref.height=c.height;const x=ref.getContext('2d');x.setTransform(d,0,0,d,0,0);x.fillStyle='#D9CBA5';x.fillRect(0,0,r.width,r.height);x.imageSmoothingEnabled=false;x.drawImage(im,r.width/2-p.x*s,r.height/2-p.y*s,2304*s,2304*s);const a=c.getContext('2d').getImageData(0,0,c.width,c.height).data,b=x.getImageData(0,0,c.width,c.height).data;return a.every((v,i)=>v===b[i]);}''',origin+f'/eval/vworld/projection_expand/runs/{folder.name}/final.png')
                assert same
                p.locator('#debug-zoom').check();p.locator('button[data-scale="2"]').click();frame();assert c.get_attribute('data-scale')=='2'
                p.locator('#debug-zoom').uncheck();frame();assert c.get_attribute('data-scale')=='1'
                p.locator('#seam-lines').check();frame();p.screenshot(path=str(folder/f'{name}_seams.png'))
                assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
                report['views'][name]={'base_canvas_identical':same,'traffic_samples':len(samples) if has_traffic else 0,'occlusions':occlusions}
                ctx.close()
            ctx=browser.new_context();ctx.route('**/*',guard);p=ctx.new_page()
            p.goto(origin+'/web/pilot/?view=projection-expand&run=bad');p.wait_for_selector('#map-message[data-state="error"]')
            p.route('**/tower_hit.png',lambda r:r.fulfill(status=404,body='missing'));p.goto(url);p.wait_for_selector('#map-message[data-state="error"]')
            p.unroute('**/tower_hit.png');p.route('**/overlay.json',lambda r:r.fulfill(status=200,body='{}'));p.goto(url);p.wait_for_selector('#map-message[data-state="error"]')
            browser.close()
        assert not report['external'] and not report['errors'];report['passed']=True
    finally:
        qs.write(folder/'expansion_browser_qa.json',report);server.shutdown();server.server_close()
    print(json.dumps(report),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--run');g.add_argument('--fixture',action='store_true');a=p.parse_args()
    if a.fixture:
        with tempfile.TemporaryDirectory(prefix='pixel-expansion-qa-') as temp:
            root=Path(temp);result=check(root,fixture(root),True)
            qs.write(P2/'eval/vworld/projection_expand/fixture_browser_qa.json',result)
    else:
        import expansion_lab
        check(P2,expansion_lab.resolve(a.run))
