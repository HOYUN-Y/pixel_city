"""Local-only actual-run tower/traffic QA; no AI calls."""
import argparse
import functools
import hashlib
import json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright

P2=Path(__file__).resolve().parents[1]
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*_):pass

def check(run):
    folder=P2/'eval/vworld/seam_lab/runs'/run
    output=folder/'living_browser_qa';output.mkdir(exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(P2)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}'
    report={'passed':False,'manifest_sha256':hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest(),'errors':[],'external':[],'mutations':[],'views':{}}
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            for name,width,height,dpr in [('desktop',1440,900,1),('tablet',1024,768,1),('mobile',390,844,2),('mobile3',390,844,3)]:
                context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=dpr,reduced_motion='reduce')
                def guard(route):
                    if not route.request.url.startswith(origin+'/'):report['external'].append(route.request.url);route.abort()
                    elif route.request.method not in ['GET','HEAD']:report['mutations'].append(route.request.method);route.abort()
                    else:route.continue_()
                context.route('**/*',guard)
                page=context.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
                page.goto(origin+'/web/pilot/?view=seam-lab&run='+run)
                page.wait_for_selector('body[data-tiles-ready="true"]')
                def frame():page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                def inspect():
                    if page.locator('#inspection').get_attribute('open') is None:page.locator('#inspection summary').click()
                assert page.locator('#map').get_attribute('data-traffic-playing')=='false'
                inspect();page.locator('#traffic-play').click()
                page.wait_for_function('()=>Number(document.querySelector("#map").dataset.trafficTime)>.1')
                page.locator('#traffic-play').click();frame()
                paused=page.locator('#map').get_attribute('data-traffic-time');page.wait_for_timeout(150);assert page.locator('#map').get_attribute('data-traffic-time')==paused
                samples=[]
                for n in range(0,601,10):
                    page.locator('#traffic-phase').evaluate('(el,v)=>{el.value=v;el.dispatchEvent(new Event("input",{bubbles:true}));}',n);frame()
                    cars=json.loads(page.locator('#map').get_attribute('data-vehicles'));assert len(cars)==4;samples.extend(cars)
                assert any(c['visible']>0 and c['occluded']==0 for c in samples)
                assert any(c['visible']>0 and c['occluded']>0 for c in samples)
                assert any(c['visible']==0 and c['occluded']>0 for c in samples)
                page.locator('#traffic-phase').evaluate('(el)=>{el.value=100;el.dispatchEvent(new Event("input",{bubbles:true}));}')
                page.locator('#traffic-focus').click();frame();page.screenshot(path=str(output/f'{name}_traffic.png'))
                inspect();page.locator('#traffic-visible').click();frame();assert json.loads(page.locator('#map').get_attribute('data-vehicles'))==[]
                page.locator('#map-mode').select_option('source');frame();assert page.locator('#traffic-play').is_disabled()
                page.locator('#lab-scene').select_option('namsan');page.wait_for_function('()=>document.querySelector("#map").dataset.scene==="namsan"')
                page.locator('#tower-focus').click();frame()
                def target(p):return page.locator('#map').evaluate('(el,p)=>{const r=el.getBoundingClientRect(),c=JSON.parse(el.dataset.center),s=Number(el.dataset.scale);return [r.left+r.width/2+(p[0]-c.x)*s,r.top+r.height/2+(p[1]-c.y)*s];}',p)
                page.mouse.click(*target([781,640]));page.wait_for_function('()=>document.querySelector("#map").dataset.selected==="tower"')
                # Close detail while retaining tower focus.
                page.locator('[data-lab-focus="tower"]').last.click();inspect();page.locator('#tower-focus').click();frame()
                page.screenshot(path=str(output/f'{name}_tower.png'))
                inspect();page.locator('#tower-light').click();frame();assert page.locator('#map').get_attribute('data-tower-light')=='true'
                page.locator('#inspection summary').click();frame();page.screenshot(path=str(output/f'{name}_light.png'))
                inspect();page.locator('#tower-visible').click();frame();assert page.locator('#map').get_attribute('data-tower-visible')=='false';assert page.locator('#tower-light').is_disabled()
                page.locator('#inspection summary').click();frame();page.screenshot(path=str(output/f'{name}_hidden.png'))
                inspect();page.locator('#tower-visible').click();page.locator('#tower-light').click();frame()
                # The tower-related walker occluder disappears when the tower is hidden.
                affected=[]
                for n in range(0,201,10):
                    page.locator('#lab-phase').evaluate('(el,v)=>{el.value=v;el.dispatchEvent(new Event("input",{bubbles:true}));}',n);frame()
                    if int(page.locator('#map').get_attribute('data-actor-occluded'))>0:
                        page.locator('#tower-visible').click();frame();affected.append(int(page.locator('#map').get_attribute('data-actor-occluded')));page.locator('#tower-visible').click();frame()
                assert affected and all(v==0 for v in affected),affected
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                report['views'][name]={'car_samples':len(samples),'tower_occlusion_samples':len(affected)}
                context.close()
            # Non-reduced-motion starts traffic, old records remain optional.
            context=browser.new_context(reduced_motion='no-preference');context.route('**/*',guard)
            page=context.new_page();page.goto(origin+'/web/pilot/?view=seam-lab&run='+run)
            page.wait_for_function('()=>Number(document.querySelector("#map").dataset.trafficTime)>.1')
            page.evaluate('()=>{Object.defineProperty(document,"hidden",{configurable:true,get:()=>true});document.dispatchEvent(new Event("visibilitychange"));}')
            frozen=page.locator('#map').get_attribute('data-traffic-time');page.wait_for_timeout(150)
            assert page.locator('#map').get_attribute('data-traffic-time')==frozen
            context.close()
            for file in ['car_se.png','namsan_background.png','namsan_overlay.json']:
                context=browser.new_context();context.route('**/*',guard)
                context.route('**/'+file,lambda r:r.fulfill(status=200,body='corrupted'))
                page=context.new_page();scene='downtown' if file=='car_se.png' else 'namsan'
                page.goto(origin+'/web/pilot/?view=seam-lab&run='+run+'&scene='+scene)
                page.wait_for_selector('#map-message[data-state="error"]');assert page.locator('#zoom-in').is_disabled()
                context.close()
            browser.close()
        assert not report['errors'] and not report['external'] and not report['mutations'],report
        report['passed']=True;print(json.dumps(report))
    finally:
        (folder/'living_browser_qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        server.shutdown();server.server_close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);check(p.parse_args().run)
