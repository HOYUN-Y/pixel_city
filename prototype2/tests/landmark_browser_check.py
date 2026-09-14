"""Real local browser validation for independent landmark composition; no AI requests."""
import argparse
import functools
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from PIL import Image
from playwright.sync_api import sync_playwright

P2=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P2/'scripts'))
import landmark_pilot as lab

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*_):pass


def check(run):
    folder=lab.resolve(run);manifest=lab.qs.read(folder/'manifest.json');review=lab.qs.read(folder/'review.json')
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(P2)))
    threading.Thread(target=server.serve_forever,daemon=True).start();origin=f'http://127.0.0.1:{server.server_port}'
    report={'passed':False,'manifest_sha256':lab.qs.sha(folder/'manifest.json'),'errors':[],'external':[],'views':{},'geographic_validation':False}
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
                url=origin+'/web/pilot/?view=landmark-pilot&run='+run
                p.goto(url);p.wait_for_selector('body[data-tiles-ready="true"]');c=p.locator('#map')
                def frame():p.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                def inspect():
                    if p.locator('#inspection').get_attribute('open') is None:p.locator('#inspection summary').click()
                report['views'][name]={}
                for scene in manifest['scenes']:
                    inspect();p.locator('#lab-scene').select_option(scene);p.wait_for_function('(scene)=>document.querySelector("#map").dataset.scene===scene',arg=scene);frame()
                    assert c.get_attribute('data-playing')=='false'
                    p.locator('#inspection summary').click();p.screenshot(path=str(folder/f'{name}_{scene}_initial.png'))
                    inspect();assert p.locator('#tower-light').is_hidden();assert p.locator('#tower-visible').is_hidden();assert p.locator('#traffic-controls').is_hidden()
                    p.locator('#lab-spot').select_option(scene);frame();assert c.get_attribute('data-selected')==scene
                    p.screenshot(path=str(folder/f'{name}_{scene}_selected.png'));p.locator('[data-lab-clear]').click();frame()
                    inspect();p.locator('#lab-follow').uncheck();p.locator('#tower-focus').click();frame()
                    def clickxy(point):
                        center=json.loads(c.get_attribute('data-center'));s=float(c.get_attribute('data-scale'));p.mouse.click(w/2+(point[0]-center['x'])*s,h/2+(point[1]-center['y'])*s);frame()
                    # Click a manually reviewed structural void, not a random transparent corner.
                    void=review['scenes'][scene].get('void_point');void_ok=None
                    if void and name=='desktop':
                        clickxy(void);void_ok=c.get_attribute('data-selected')=='';assert void_ok
                    inspect();occlusions=[]
                    for v in range(0,1001,10):
                        p.locator('#lab-phase').evaluate('(e,v)=>{e.value=v;e.dispatchEvent(new Event("input"));}',v);frame()
                        occlusions.append([int(c.get_attribute('data-actor-visible')),int(c.get_attribute('data-actor-occluded'))])
                    assert any(a>0 and b==0 for a,b in occlusions);assert any(b>0 for _,b in occlusions)
                    partial=next(i*10 for i,(a,b) in enumerate(occlusions) if b>0)
                    p.locator('#lab-phase').evaluate('(e,v)=>{e.value=v;e.dispatchEvent(new Event("input"));}',partial);frame()
                    p.locator('#inspection summary').click();p.screenshot(path=str(folder/f'{name}_{scene}_occlusion.png'));inspect()
                    p.locator('#lab-phase').evaluate('e=>{e.value=999;e.dispatchEvent(new Event("input"));}');p.locator('#lab-play').click()
                    p.wait_for_function('()=>document.querySelector("#map").dataset.phase==="1"&&document.querySelector("#map").dataset.playing==="false"')
                    inspect();p.locator('#walk-reset').click();frame();assert c.get_attribute('data-phase')=='0'
                    center=c.get_attribute('data-center');scale=c.get_attribute('data-scale')
                    for mode in ['source','before','final']:
                        p.locator('#map-mode').select_option(mode);frame();assert c.get_attribute('data-playing')=='false'
                        assert c.get_attribute('data-center')==center and c.get_attribute('data-scale')==scale
                        if mode!='final':assert p.locator('#lab-play').is_disabled()
                    for selector in ['#lab-pins','#lab-route','#walk-actor']:p.locator(selector).uncheck()
                    p.locator('#walk-clear').click();p.locator('button[data-scale="1"]').click();frame()
                    # Independently render the published plate + sprite and compare every pixel.
                    same=p.evaluate('''async urls=>{const c=document.querySelector('#map'),r=c.getBoundingClientRect(),d=devicePixelRatio,s=Number(c.dataset.scale),p=JSON.parse(c.dataset.center);const ref=document.createElement('canvas');ref.width=c.width;ref.height=c.height;const x=ref.getContext('2d');x.setTransform(d,0,0,d,0,0);x.fillStyle='#D9CBA5';x.fillRect(0,0,r.width,r.height);x.imageSmoothingEnabled=false;for(const url of urls){const im=await createImageBitmap(await(await fetch(url)).blob());x.drawImage(im,r.width/2-p.x*s,r.height/2-p.y*s,1024*s,1024*s);}const a=c.getContext('2d').getImageData(0,0,c.width,c.height).data,b=x.getImageData(0,0,c.width,c.height).data;return a.every((v,i)=>v===b[i]);}''',[origin+f'/eval/vworld/landmark_pilot/runs/{run}/{scene}_{kind}.png' for kind in ['before','sprite']])
                    assert same
                    p.locator('#debug-zoom').check();p.locator('button[data-scale="2"]').click();frame();assert c.get_attribute('data-scale')=='2'
                    p.locator('#debug-zoom').uncheck();frame();assert c.get_attribute('data-scale')=='1'
                    assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    report['views'][name][scene]={'independent_composite_identical':same,'occlusion_samples':101,'partial_occlusion':any(a>0 and b>0 for a,b in occlusions),'full_occlusion':any(a==0 and b>0 for a,b in occlusions),'void_click_unselected':void_ok}
                    for selector in ['#lab-pins','#lab-route','#walk-actor']:p.locator(selector).check()
                ctx.close()
            ctx=browser.new_context();ctx.route('**/*',guard);p=ctx.new_page()
            p.goto(origin+'/web/pilot/?view=landmark-pilot&run=bad');p.wait_for_selector('#map-message[data-state="error"]')
            p.goto(url+'&scene=missing');p.wait_for_selector('#map-message[data-state="error"]')
            p.route('**/*_hit.png',lambda r:r.fulfill(status=404,body='missing'));p.goto(url);p.wait_for_selector('#map-message[data-state="error"]')
            p.unroute('**/*_hit.png');p.route('**/*_overlay.json',lambda r:r.fulfill(status=200,body='{}'));p.goto(url);p.wait_for_selector('#map-message[data-state="error"]')
            browser.close()
        assert not report['errors'] and not report['external'];report['passed']=True
    finally:
        lab.qs.write(folder/'browser_qa.json',report);server.shutdown();server.server_close()
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();check(a.run)
