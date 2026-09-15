"""Actual linked assets, rectangle, sunset, traffic and old tower alpha; no AI calls."""
import argparse
import base64
import functools
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time
from playwright.sync_api import sync_playwright
P2=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P2/'scripts'))
import landmark_link as link

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*_):pass

def check(run):
    folder=link.resolve(run);m=link.qs.read(folder/'manifest.json')
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(P2)));threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}';url=origin+'/web/pilot/?view=landmark-link&run='+run
    report={'passed':False,'manifest_sha256':link.qs.sha(folder/'manifest.json'),'errors':[],'external':[],'views':{},'real_time_playback_seconds':0,'geographic_validation':False,'physical_shadow_validation':False}
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
                frame();assert c.get_attribute('data-playing')=='false' and c.get_attribute('data-traffic-playing')=='false'
                assert c.get_attribute('data-sunset')=='0';p.screenshot(path=str(folder/(name+'_day.png')))
                inspect();p.locator('#lab-follow').uncheck();p.locator('#walk-actor').uncheck();p.locator('#traffic-visible').click();p.locator('button[data-scale="1"]').click();frame()
                # Compare full canvas against independent plate + tower + effect rendering.
                base=origin+f'/eval/vworld/landmark_link/runs/{run}/'
                script='''async ({base,amount})=>{const {SunsetLayer}=await import('./sunset.js');const overlay=await(await fetch(base+'overlay.json')).json();const load=async f=>createImageBitmap(await(await fetch(base+f)).blob());const [plate,sprite,receiver]=await Promise.all(['before.png','sprite.png','receiver.png'].map(load));const size={width:1792,height:1024},sun=new SunsetLayer(sprite,receiver,overlay.sunset,size);sun.set(amount);const c=document.querySelector('#map'),r=c.getBoundingClientRect(),d=devicePixelRatio,s=Number(c.dataset.scale),p=JSON.parse(c.dataset.center),ref=document.createElement('canvas');ref.width=c.width;ref.height=c.height;const x=ref.getContext('2d');x.setTransform(d,0,0,d,0,0);x.fillStyle='#D9CBA5';x.fillRect(0,0,r.width,r.height);x.imageSmoothingEnabled=false;const ox=r.width/2-p.x*s,oy=r.height/2-p.y*s;x.drawImage(plate,ox,oy,1792*s,1024*s);sun.drawShadow(x,ox,oy,s);x.drawImage(sprite,ox,oy,1792*s,1024*s);sun.drawTint(x,ox,oy,s);const a=c.getContext('2d').getImageData(0,0,c.width,c.height).data,b=x.getImageData(0,0,c.width,c.height).data;const mask=sun.mask.getContext('2d').getImageData(0,0,1792,1024).data;const rr=document.createElement('canvas');rr.width=1792;rr.height=1024;const rc=rr.getContext('2d');rc.drawImage(receiver,0,0);const ground=rc.getImageData(0,0,1792,1024).data;let outside=0,shadow=0;for(let i=3;i<mask.length;i+=4){if(mask[i])shadow++;if(mask[i]&&!ground[i])outside++;}return {identical:a.every((v,i)=>v===b[i]),shadow_pixels:shadow,outside_receiver:outside};}'''
                records=[]
                state=[c.get_attribute('data-center'),c.get_attribute('data-scale'),c.get_attribute('data-phase'),c.get_attribute('data-traffic-time')]
                for v in [0,50,100,0]:
                    p.locator('#sunset-amount').evaluate('(e,v)=>{e.value=v;e.dispatchEvent(new Event("input"));}',v);frame()
                    result=p.evaluate(script,{'base':base,'amount':v/100});assert result['identical'];assert result['outside_receiver']==0
                    assert result['shadow_pixels']>0 if v else result['shadow_pixels']==0
                    assert state==[c.get_attribute('data-center'),c.get_attribute('data-scale'),c.get_attribute('data-phase'),c.get_attribute('data-traffic-time')]
                    records.append(result)
                builds=c.get_attribute('data-shadow-builds');p.locator('button[data-scale=".5"]').click() if p.locator('button[data-scale=".5"]').count() else p.locator('button[data-scale="1"]').click();frame();assert c.get_attribute('data-shadow-builds')==builds
                p.locator('#tower-focus').click();frame();inspect();p.locator('#sunset-amount').evaluate('e=>{e.value=100;e.dispatchEvent(new Event("input"));}');frame();p.locator('#inspection summary').click();p.screenshot(path=str(folder/(name+'_sunset.png')))
                inspect();before=c.evaluate('e=>e.toDataURL()');builds=c.get_attribute('data-shadow-builds');p.locator('#sunset-shadow').uncheck();frame();assert c.evaluate('e=>e.toDataURL()')!=before;assert c.get_attribute('data-shadow-builds')==builds
                p.locator('#sunset-shadow').check();frame();assert c.evaluate('e=>e.toDataURL()')==before
                if name.startswith('mobile'):
                    p.locator('#inspection summary').click();p.locator('.mobile-time').click();frame();assert c.get_attribute('data-sunset')=='0';p.locator('.mobile-time').click();frame();assert c.get_attribute('data-sunset')=='1'
                else:
                    p.locator('.daytime button').nth(0).click();frame();assert c.get_attribute('data-sunset')=='0';p.locator('.daytime button').nth(1).click();frame();assert c.get_attribute('data-sunset')=='1';p.locator('#inspection summary').click()
                if name=='desktop':
                    png=p.evaluate('''async base=>{const {SunsetLayer}=await import('./sunset.js');const overlay=await(await fetch(base+'overlay.json')).json(),load=async f=>createImageBitmap(await(await fetch(base+f)).blob());const [plate,sprite,receiver]=await Promise.all(['before.png','sprite.png','receiver.png'].map(load));const c=document.createElement('canvas');c.width=1792;c.height=1024;const x=c.getContext('2d'),sun=new SunsetLayer(sprite,receiver,overlay.sunset,{width:1792,height:1024});sun.set(1);x.drawImage(plate,0,0);sun.drawShadow(x,0,0,1);x.drawImage(sprite,0,0);sun.drawTint(x,0,0,1);return c.toDataURL('image/png').split(',')[1];}''',base)
                    (folder/'sunset.png').write_bytes(base64.b64decode(png))
                    center=json.loads(c.get_attribute('data-center'));s=float(c.get_attribute('data-scale'));p.mouse.click(w/2+(1281-center['x'])*s,h/2+(487-center['y'])*s);frame();assert c.get_attribute('data-selected')==''
                inspect();p.locator('#lab-spot').select_option('jongno-tower');frame();assert c.get_attribute('data-selected')=='jongno-tower';p.locator('[data-lab-clear]').click();inspect()
                p.locator('#walk-actor').check();samples=[]
                for v in range(0,1001,10):
                    p.locator('#lab-phase').evaluate('(e,v)=>{e.value=v;e.dispatchEvent(new Event("input"));}',v);frame();samples.append([int(c.get_attribute('data-actor-visible')),int(c.get_attribute('data-actor-occluded'))])
                assert any(a>0 and b>0 for a,b in samples);assert any(a==0 and b>0 for a,b in samples)
                p.locator('#link-walk-route').select_option('connection');frame();assert c.get_attribute('data-phase')=='0'
                p.locator('#lab-phase').evaluate('e=>{e.value=999;e.dispatchEvent(new Event("input"));}');p.locator('#lab-play').click();p.wait_for_function('()=>document.querySelector("#map").dataset.phase==="1"&&document.querySelector("#map").dataset.playing==="false"');inspect()
                p.locator('#link-walk-route').select_option('tower');frame()
                p.locator('#traffic-visible').click();traffic=[]
                for t in range(61):
                    p.locator('#traffic-phase').evaluate('(e,v)=>{e.value=v;e.dispatchEvent(new Event("input"));}',t*10);frame();cars=json.loads(c.get_attribute('data-vehicles'));assert len(cars)==2;traffic.append(cars)
                assert any(c['xy'][0]<896 for row in traffic for c in row) and any(c['xy'][0]>896 for row in traffic for c in row)
                for mode in ['source','before','final']:
                    p.locator('#map-mode').select_option(mode);frame();assert c.get_attribute('data-sunset')=='1'
                    assert p.locator('#sunset-amount').is_disabled()==(mode!='final')
                p.locator('#debug-zoom').check();p.locator('button[data-scale="2"]').click();frame();assert c.get_attribute('data-scale')=='2';p.locator('#debug-zoom').uncheck();frame();assert c.get_attribute('data-scale')=='1'
                assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
                if name=='desktop':
                    p.locator('#traffic-phase').evaluate('e=>{e.value=0;e.dispatchEvent(new Event("input"));}');p.locator('#traffic-play').click();p.locator('#inspection summary').click()
                    for _ in range(6):p.wait_for_timeout(10000);print('Link traffic playback: 10s interval',flush=True)
                    assert float(c.get_attribute('data-traffic-time'))>50;report['real_time_playback_seconds']=60
                report['views'][name]={'pixel_comparisons':records,'occlusion_samples':101,'partial_and_full_occlusion':True,'traffic_samples':61,'void_click':name=='desktop'};ctx.close()
            ctx=browser.new_context();ctx.route('**/*',guard);p=ctx.new_page()
            p.goto(origin+'/web/pilot/?view=landmark-link&run=bad');p.wait_for_selector('#map-message[data-state="error"]')
            p.route('**/receiver.png',lambda r:r.fulfill(status=404,body='missing'));p.goto(url);p.wait_for_selector('#map-message[data-state="error"]');ctx.close();browser.close()
        assert not report['errors'] and not report['external'];report['passed']=True
    finally:link.qs.write(folder/'browser_qa.json',report);server.shutdown();server.server_close()
    print(json.dumps(report),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();check(a.run)
