"""Local real-browser selection/walk/occlusion regression; no external requests."""
import argparse
import functools
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright

P2=Path(__file__).resolve().parents[1]
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*_):pass

def check(run):
    folder=P2/'eval/vworld/projection_walk/runs'/run
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(P2)))
    threading.Thread(target=server.serve_forever,daemon=True).start();origin=f'http://127.0.0.1:{server.server_port}'
    url=origin+'/web/pilot/?view=projection-walk&run='+run
    report={'passed':False,'errors':[],'external':[],'mutations':[],'views':{}}
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            for name,w,h,dpr,motion in [('desktop',1440,900,1,'no-preference'),('tablet',1024,768,1,'reduce'),('mobile',390,844,2,'reduce'),('mobile3',390,844,3,'no-preference')]:
                ctx=browser.new_context(viewport={'width':w,'height':h},device_scale_factor=dpr,reduced_motion=motion)
                def guard(route):
                    if not route.request.url.startswith(origin+'/'):report['external'].append(route.request.url);route.abort()
                    elif route.request.method not in ['GET','HEAD']:report['mutations'].append(route.request.method);route.abort()
                    else:route.continue_()
                ctx.route('**/*',guard);p=ctx.new_page();p.on('pageerror',lambda e:report['errors'].append(str(e)))
                p.goto(url);p.wait_for_selector('body[data-tiles-ready="true"]');p.evaluate('document.fonts.ready')
                canvas=p.locator('#map')
                def frame():p.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                def inspect():
                    if p.locator('#inspection').get_attribute('open') is None:p.locator('#inspection summary').click()
                def phase(value):
                    inspect();p.locator('#lab-phase').evaluate('(e,v)=>{e.value=v;e.dispatchEvent(new Event("input",{bubbles:true}));}',value);frame()
                assert canvas.get_attribute('data-playing')=='false'
                p.screenshot(path=str(folder/f'{name}_initial.png'))
                inspect();assert p.locator('#tower-light').is_hidden();assert p.locator('#tower-visible').is_hidden()
                p.locator('#lab-spot').select_option('tower');frame();assert canvas.get_attribute('data-selected')=='tower'
                p.screenshot(path=str(folder/f'{name}_selected.png'))
                p.locator('[data-lab-clear]').click();frame();assert canvas.get_attribute('data-selected')==''
                inspect();p.locator('#lab-follow').uncheck()
                samples=[]
                for v in range(0,1001,10):
                    phase(v);samples.append([v,int(canvas.get_attribute('data-actor-visible')),int(canvas.get_attribute('data-actor-occluded'))])
                assert any(v>0 and h==0 for _,v,h in samples),'No front sample'
                assert any(v>0 and h>0 for _,v,h in samples),'No partial sample'
                assert any(v==0 and h>0 for _,v,h in samples),'No fully hidden sample'
                report['views'][name]={'occlusion_samples':samples}
                for label,sample in [('front',next(s for s in samples if s[1]>0 and s[2]==0)),('partial',next(s for s in samples if s[1]>0 and s[2]>0)),('hidden',next(s for s in samples if s[1]==0 and s[2]>0))]:
                    phase(sample[0]);p.locator('#inspection summary').click();p.screenshot(path=str(folder/f'{name}_{label}.png'))
                phase(999);p.locator('#lab-play').click();p.wait_for_function('()=>document.querySelector("#map").dataset.phase==="1"&&document.querySelector("#map").dataset.playing==="false"')
                inspect();p.locator('#walk-reset').click();frame();assert canvas.get_attribute('data-phase')=='0'
                p.locator('#lab-play').click();p.wait_for_timeout(150);inspect();p.locator('#lab-pause').click();frame();paused=canvas.get_attribute('data-phase');p.wait_for_timeout(150);assert canvas.get_attribute('data-phase')==paused
                center=canvas.get_attribute('data-center');scale=canvas.get_attribute('data-scale')
                for mode in ['source','before','final']:
                    p.locator('#map-mode').select_option(mode);frame();assert canvas.get_attribute('data-playing')=='false';assert canvas.get_attribute('data-center')==center;assert canvas.get_attribute('data-scale')==scale
                    if mode!='final':assert p.locator('#lab-play').is_disabled()
                p.locator('#lab-pins').uncheck();p.locator('#lab-route').uncheck();p.locator('#walk-actor').uncheck();p.locator('#walk-clear').click();p.locator('button[data-scale="1"]').click();frame()
                # Entire canvas must match direct rendering of the unchanged background.
                same=p.evaluate('''async url=>{const c=document.querySelector('#map'),r=c.getBoundingClientRect(),d=devicePixelRatio,center=JSON.parse(c.dataset.center),s=Number(c.dataset.scale);const im=await createImageBitmap(await(await fetch(url)).blob());const ref=document.createElement('canvas');ref.width=c.width;ref.height=c.height;const x=ref.getContext('2d');x.setTransform(d,0,0,d,0,0);x.fillStyle='#D9CBA5';x.fillRect(0,0,r.width,r.height);x.imageSmoothingEnabled=false;x.drawImage(im,r.width/2-center.x*s,r.height/2-center.y*s,1536*s,1536*s);const a=c.getContext('2d').getImageData(0,0,c.width,c.height).data,b=x.getImageData(0,0,c.width,c.height).data;return a.every((v,i)=>v===b[i]);}''',origin+f'/eval/vworld/projection_walk/runs/{run}/final.png')
                assert same,'Base canvas differs';report['views'][name]['base_canvas_identical']=same
                assert p.locator('#zoom-in').is_disabled();p.locator('#debug-zoom').check();p.locator('button[data-scale="2"]').click();frame();assert canvas.get_attribute('data-scale')=='2';p.locator('#debug-zoom').uncheck();frame();assert canvas.get_attribute('data-scale')=='1'
                assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
                if name=='desktop':
                    p.locator('#inspection summary').click()
                    def clickxy(x,y):
                        s=float(canvas.get_attribute('data-scale'));c=json.loads(canvas.get_attribute('data-center'));p.mouse.click(w/2+(x-c['x'])*s,h/2+(y-c['y'])*s);frame()
                    clickxy(781,630);assert canvas.get_attribute('data-selected')=='tower'
                    p.locator('[data-lab-clear]').click();clickxy(700,735);assert canvas.get_attribute('data-selected')==''
                    clickxy(900,600);assert canvas.get_attribute('data-selected')==''
                    # A pan starting on the tower must not select it.
                    c=json.loads(canvas.get_attribute('data-center'));x=w/2+781-c['x'];y=h/2+630-c['y'];p.mouse.move(x,y);p.mouse.down();p.mouse.move(x+30,y+30);p.mouse.up();frame();assert canvas.get_attribute('data-selected')==''
                    canvas.evaluate('''c=>{const capture=c.setPointerCapture;c.setPointerCapture=()=>{};const fire=(type,id,x,y)=>c.dispatchEvent(new PointerEvent(type,{pointerId:id,pointerType:'touch',clientX:x,clientY:y,bubbles:true}));fire('pointerdown',51,700,450);fire('pointerdown',52,760,450);fire('pointermove',51,680,450);fire('pointerup',51,680,450);fire('pointerup',52,760,450);c.setPointerCapture=capture;}''');frame();assert canvas.get_attribute('data-selected')==''
                    inspect();p.locator('#walk-reset').click();p.locator('#lab-play').click();p.wait_for_timeout(150)
                    p.evaluate('()=>{Object.defineProperty(document,"hidden",{configurable:true,get:()=>true});document.dispatchEvent(new Event("visibilitychange"));}')
                    frozen=canvas.get_attribute('data-phase');p.wait_for_timeout(250);assert canvas.get_attribute('data-phase')==frozen
                    p.evaluate('()=>{delete document.hidden;document.dispatchEvent(new Event("visibilitychange"));}')
                    p.wait_for_timeout(150);inspect();p.locator('#lab-pause').click();frame();assert 0<=float(canvas.get_attribute('data-phase'))-float(frozen)<.01
                    report['views'][name]['synthetic_visibility_and_pinch_passed']=True
                ctx.close()
            ctx=browser.new_context();ctx.route('**/*',guard);p=ctx.new_page()
            p.goto(origin+'/web/pilot/?view=projection-walk&run=bad');p.wait_for_selector('#map-message[data-state="error"]')
            p.route('**/tower_hit.png',lambda r:r.fulfill(status=404,body='missing'));p.goto(url);p.wait_for_selector('#map-message[data-state="error"]');assert p.locator('#zoom-in').is_disabled()
            p.unroute('**/tower_hit.png');p.route('**/overlay.json',lambda r:r.fulfill(status=200,body='{}'));p.goto(url);p.wait_for_selector('#map-message[data-state="error"]')
            browser.close()
        assert not report['errors'] and not report['external'] and not report['mutations'];report['passed']=True
    finally:
        (folder/'browser_qa.json').write_text(json.dumps(report,indent=2)+'\n');server.shutdown();server.server_close()
    print(json.dumps({'passed':report['passed'],'views':list(report['views']),'errors':report['errors'],'external':report['external']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);check(p.parse_args().run)
