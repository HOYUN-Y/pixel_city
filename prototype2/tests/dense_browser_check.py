"""Dense renderer QA against a diagnostic fixture or reviewed snapshot. No AI calls."""
import argparse
import base64
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
from test_dense_snapshot import fixture
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from dense_snapshot import export
from city_snapshot import P2

def check(dest,snapshot=None,full_regression=False):
    dest.mkdir(parents=True,exist_ok=True)
    source=dest/'source';public=snapshot.resolve() if snapshot else dest/'assets'
    if not snapshot and not public.exists():fixture(source);export(source,public)
    manifest=json.loads((public/'manifest.json').read_text())
    is_fixture=bool(manifest.get('testFixture'))
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path=='/api/guide':
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"enabled":false}');return
            if self.path=='/':
                body=(P2/'web/pilot/index.html').read_text().replace('src="app.js"','src="/web/pilot/beta-app.js"').replace('href="style.css"','href="/web/pilot/style.css"').replace('<body>','<body data-city-base="/assets/city_pilot/">')
                self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(body.encode());return
            super().do_GET()
        def translate_path(self,path):
            if path.startswith('/assets/city_pilot/'):return str(public/path.removeprefix('/assets/city_pilot/'))
            return super().translate_path(path)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(P2)));threading.Thread(target=server.serve_forever,daemon=True).start()
    results=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()
            for width,height in [(1440,1000),(390,844)]:
                page=browser.new_page(viewport={'width':width,'height':height},reduced_motion='reduce');errors=[];posts=[]
                page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
                page.goto(f'http://127.0.0.1:{server.server_port}/');page.wait_for_selector('body[data-city-ready="true"]')
                page.wait_for_function('()=>document.querySelector("#map").dataset.tilePending==="0"')
                assert page.locator('#map').get_attribute('data-scale')=='.5' or float(page.locator('#map').get_attribute('data-scale'))==.5
                assert page.locator('.city-landmarks button').count()==3
                page.screenshot(path=str(dest/f'{width}_initial.png'))
                pixel_qa=page.evaluate('''async()=>{
                  const {paintVehicle}=await import('/web/pilot/dense-core.js');
                  const make=(w,h)=>Object.assign(document.createElement('canvas'),{width:w,height:h});
                  const car=make(8,8),cc=car.getContext('2d');cc.fillStyle='red';cc.fillRect(0,0,8,8);
                  const layer=make(8,8),lc=layer.getContext('2d'),shape=make(4,8);shape.getContext('2d').fillRect(0,0,4,8);
                  paintVehicle(lc,car,[10,10,8,8],[{rect:[14,10,4,8],shape}]);
                  const count=c=>{const p=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<p.length;i+=4)if(p[i])n++;return n;};
                  if(count(layer)!==32)throw Error('Partial alpha masking failed');
                  paintVehicle(lc,car,[10,10,8,8],[]);if(count(layer)!==64)throw Error('Vehicle did not restore after leaving mask');
                  const base=new URL('/assets/city_pilot/',location.href),m=await(await fetch(new URL('manifest.json',base))).json(),o=await(await fetch(new URL('overlay.json',base))).json();
                  let real=null;
                  if(o.traffic.occluders?.length){
                    const {CroppedObjects}=await import('/web/pilot/dense-map.js');const objects=await CroppedObjects.load(o,base,m.asset_sha256);
                    const board=make(1,1),ctx=board.getContext('2d');let hidden=0,partial=0,visible=0;
                    const maxima=new Map();
                    for(const lane of o.traffic.lanes){const im=objects.images.get(lane.sprite),c=make(im.width*2,im.height*2);c.getContext('2d').imageSmoothingEnabled=false;c.getContext('2d').drawImage(im,0,0,c.width,c.height);maxima.set(lane.sprite,count(c));}
                    const periods=o.traffic.lanes.map(l=>{const p=l.points??[l.start,l.end];return p.slice(1).reduce((s,v,i)=>s+Math.hypot(v[0]-p[i][0],v[1]-p[i][1]),0)/o.traffic.speed;});
                    const duration=Math.max(...periods),times=new Set([0,duration]);
                    // At most one native pixel of travel between samples.
                    const steps=Math.ceil(duration*o.traffic.speed);
                    for(let i=0;i<=steps;i++)times.add(duration*i/steps);
                    o.traffic.lanes.forEach((l,i)=>l.offsets.forEach(offset=>{const wrap=(1-offset)*periods[i];for(const dt of [-.001,0,.001])times.add(wrap+dt);}));
                    const records=[];
                    for(const t of [...times].sort((a,b)=>a-b)){objects.seconds=t;objects.drawTraffic(ctx,0,0,1);for(const lane of o.traffic.lanes){
                      const sample=objects.samples.find(s=>s.lane===lane.id),n=count(objects.vehicleLayers.get(sample.vehicleId)),max=maxima.get(lane.sprite);
                      if(!n)hidden++;else if(n<max)partial++;else visible++;
                      if(!sample.occluderOverlaps&&n!==max)throw Error('Unoccluded vehicle pixels lost');
                      if(!sample.xy.every(Number.isFinite)||sample.alpha<0||sample.alpha>1)throw Error('Invalid cycle position');
                      records.push({time:t,...sample,pixels:n,unmaskedPixels:max});
                    }}
                    const {vehiclePosition}=await import('/web/pilot/living-core.js');
                    for(const [i,l] of o.traffic.lanes.entries())for(const offset of l.offsets){
                      const a=vehiclePosition(l,0,offset,o.traffic.speed),b=vehiclePosition(l,periods[i],offset,o.traffic.speed);
                      if(Math.hypot(a.xy[0]-b.xy[0],a.xy[1]-b.xy[1])>1e-7)throw Error('Cycle does not restore position');
                      const wrap=(1-offset)*periods[i];if(vehiclePosition(l,wrap,offset,o.traffic.speed).alpha>1e-7)throw Error('Visible wrap teleport');
                    }
                    // Render native-resolution evidence with the production vehicle renderer,
                    // verified level-1 background tiles and independent landmark sprites.
                    const rect=o.traffic.focus[0]>3000?[3540,1900,720,380]:[2080,1500,480,620];
                    const bg=make(rect[2],rect[3]),bc=bg.getContext('2d');bc.imageSmoothingEnabled=false;
                    const {tilePicture}=await import('/web/pilot/tile-layer.js');
                    for(let y=Math.floor(rect[1]/512);y<=Math.floor((rect[1]+rect[3]-1)/512);y++)for(let x=Math.floor(rect[0]/512);x<=Math.floor((rect[0]+rect[2]-1)/512);x++){
                      const file=`tiles/1/${x}_${y}.png`,im=await tilePicture(base,file,m.asset_sha256[file]);bc.drawImage(im,x*512-rect[0],y*512-rect[1]);im.close();
                    }
                    const frames=[];
                    for(let i=0;i<=8;i++){const t=duration*i/8,c=make(rect[2],rect[3]),cc=c.getContext('2d');cc.imageSmoothingEnabled=false;cc.drawImage(bg,0,0);objects.draw(cc,-rect[0],-rect[1],1,null);objects.seconds=t;objects.drawTraffic(cc,-rect[0],-rect[1],1);frames.push({time:t,png:c.toDataURL('image/png').split(',')[1]});}
                    real={hidden,partial,visible,maskCount:objects.trafficOccluders.length,duration,periods,maxTravelPerSamplePx:duration*o.traffic.speed/steps,fullCycle:true,wrapFadeVerified:true,records,frames,frameRect:rect};objects.close();
                    // A Sejong route may never overlap the separately scoped Jongno masks.
                    if(o.traffic.focus[0]>3000&&(!hidden||!partial||!visible))throw Error('Actual Jongno occlusion transition missing');
                  }
                  return {partialAlpha:true,restore:true,real};
                }''')
                cycle=pixel_qa.get('real')
                if cycle and cycle.get('fullCycle'):
                    from PIL import Image,ImageDraw
                    frames=cycle.pop('frames');records=cycle.pop('records')
                    (dest/f'{width}_traffic_cycle.json').write_text(json.dumps({'duration':cycle['duration'],'records':records},indent=2))
                    w,h=cycle['frameRect'][2:];sheet=Image.new('RGB',(w*2,(h+24)*5),'#222');draw=ImageDraw.Draw(sheet)
                    for i,frame in enumerate(frames):
                        path=dest/f'{width}_cycle_{i}.png';path.write_bytes(base64.b64decode(frame['png']))
                        with Image.open(path) as im:sheet.paste(im,((i%2)*w,(i//2)*(h+24)+24))
                        draw.text(((i%2)*w+5,(i//2)*(h+24)+5),f"t={frame['time']:.3f}s native 100%",fill='white')
                    sheet.save(dest/f'{width}_traffic_cycle.png')
                page.locator('.city-landmarks [data-city-focus="gwanghwamun"]').click();page.keyboard.press('Escape')
                page.locator('#map').focus()
                for _ in range(14):page.keyboard.press('ArrowRight')
                for _ in range(6):page.keyboard.press('ArrowDown')
                page.wait_for_function('()=>document.querySelector("#map").dataset.tilePending==="0"')
                assert int(page.locator('#map').get_attribute('data-tile-cache'))<=48
                # Bosingak is hidden by default, but explicitly reachable via catalog.
                page.locator('.city-landmarks [data-city-focus="bosingak"]').click()
                if width<900:
                    page.locator('.sheet-tabs [data-open="book"]').click();page.locator('[data-city-place="landmark-6"]').click()
                if page.locator('#map').get_attribute('data-reveal')!='true':page.locator('[data-city-reveal]').click()
                page.wait_for_function('()=>document.querySelector("#map").dataset.revealAmount==="1"')
                page.screenshot(path=str(dest/f'{width}_bosingak.png'))
                page.keyboard.press('Escape');page.locator('.city-landmarks [data-city-focus="jongno-tower"]').click();page.keyboard.press('Escape')
                page.wait_for_function('()=>document.querySelector("#map").dataset.reveal==="false"')
                page.screenshot(path=str(dest/f'{width}_tower.png'))
                page.locator('#city-road').click();page.locator('#city-traffic').click()
                before_time=float(page.locator('#map').get_attribute('data-traffic-time'))
                before_cars=json.loads(page.locator('#map').get_attribute('data-vehicles'))
                page.screenshot(path=str(dest/f'{width}_traffic_start.png'))
                page.wait_for_function('(t)=>Number(document.querySelector("#map").dataset.trafficTime)>t',arg=before_time)
                crossing=None
                if manifest.get('reviewOnly'):
                    page.wait_for_function('(t)=>Number(document.querySelector("#map").dataset.trafficTime)>=t+8',arg=before_time)
                    after_time=float(page.locator('#map').get_attribute('data-traffic-time'))
                    after_cars=json.loads(page.locator('#map').get_attribute('data-vehicles'))
                    assert len(before_cars)==len(after_cars) and len(after_cars) in [2,4]
                    distances=[((a['xy'][0]-b['xy'][0])**2+(a['xy'][1]-b['xy'][1])**2)**.5 for a,b in zip(after_cars,before_cars)]
                    assert all(abs(d/(after_time-before_time)-32)<1 for d in distances),distances
                    crossing=any(int(a['xy'][0]//768)!=int(b['xy'][0]//768) for a,b in zip(after_cars,before_cars))
                    assert crossing,'Vehicle did not cross a generation-core boundary'
                page.screenshot(path=str(dest/f'{width}_traffic.png'))
                page.locator('#city-traffic').click()
                for _ in range(6):
                    if page.locator('#zoom-in').is_disabled():break
                    page.locator('#zoom-in').click()
                assert float(page.locator('#map').get_attribute('data-scale'))==1
                assert page.locator('#zoom-in').is_disabled()
                for _ in range(10):
                    if page.locator('#zoom-out').is_disabled():break
                    page.locator('#zoom-out').click()
                assert 0<float(page.locator('#map').get_attribute('data-scale'))<.5
                page.locator('#fit').click();page.screenshot(path=str(dest/f'{width}_whole.png'))
                # Newly requested unavailable tiles must not make the map unusable or retry forever.
                page.route('**/tiles/**',lambda route:route.fulfill(status=503,body='offline'))
                page.locator('#fit').click();page.locator('.city-landmarks [data-city-focus="gwanghwamun"]').click();page.keyboard.press('Escape')
                page.locator('#map').focus()
                for _ in range(20):page.keyboard.press('ArrowUp')
                page.wait_for_function('()=>document.querySelector("#map").dataset.tilePending==="0"')
                before=page.locator('#map').get_attribute('data-tile-requests');page.wait_for_timeout(250)
                assert page.locator('#map').get_attribute('data-tile-requests')==before
                assert int(page.locator('#map').get_attribute('data-tile-failed'))>0,'Failure fallback was not exercised'
                assert page.locator('body').get_attribute('data-city-ready')=='true'
                assert not posts and not errors,(posts,errors)
                results.append({'viewport':[width,height],'testFixture':is_fixture,'reviewOnly':bool(manifest.get('reviewOnly')),'cache':int(page.locator('#map').get_attribute('data-tile-cache')),'failedTiles':int(page.locator('#map').get_attribute('data-tile-failed')),'errors':errors,'paidCalls':0,'navigationRevealFallback':True,'trafficAdvances':True,'trafficCrossesCore':crossing,'zoomLimit100Percent':True,'vehiclePixels':pixel_qa})
                page.close()
            browser.close()
        if full_regression:
            from city_browser_check import check as city_check
            city_check(f'http://127.0.0.1:{server.server_port}/',dest/'city-regression')
    finally:server.shutdown();server.server_close()
    (dest/'browser_qa.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dest',type=Path,required=True);p.add_argument('--snapshot',type=Path);p.add_argument('--full-regression',action='store_true');a=p.parse_args();check(a.dest,a.snapshot,a.full_regression)
