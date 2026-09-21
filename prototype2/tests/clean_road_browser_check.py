"""Local comparison regression; never calls an AI provider."""
import argparse
import base64
import json
from pathlib import Path
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

def check(root,url):
    dest=root/'qa';dest.mkdir(exist_ok=True)
    frozen=json.loads((root/'frozen_mask.json').read_text())
    a=np.asarray(Image.open(root/'before.png'));b=np.asarray(Image.open(root/'after.png'));mask=np.asarray(Image.open(root/'mask.png'))>0
    assert not np.any(a[~mask]!=b[~mask])
    full=Image.open(root/'source/dense_background_candidate.png').convert('RGB')
    assert np.array_equal(np.asarray(full.crop(tuple(frozen['crop']))),b)
    checked=0
    for scale in [.25,.5,1]:
        expected=full.resize((int(full.width*scale),int(full.height*scale)),Image.Resampling.NEAREST)
        for file in (root/'snapshot/tiles'/str(scale if scale!=1 else 1)).glob('*.png'):
            x,y=map(int,file.stem.split('_'));actual=Image.open(file)
            assert np.array_equal(np.asarray(actual),np.asarray(expected.crop((x*512,y*512,x*512+actual.width,y*512+actual.height))))
            checked+=1
    results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for width,height in [(1440,1000),(390,844)]:
            page=browser.new_page(viewport={'width':width,'height':height},reduced_motion='reduce');errors=[];posts=[]
            page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
            page.goto(url);page.wait_for_selector('#review[data-ready="true"]')
            canvas=page.locator('#review');assert canvas.get_attribute('data-mode')=='before'
            for scale in ['0.5','1']:
                page.locator(f'button[data-scale="{scale}"]').click()
                for mode in ['before','empty','after']:
                    page.locator(f'button[data-mode="{mode}"]').click()
                    page.wait_for_function('(m)=>document.querySelector("#review").dataset.mode===m',arg=mode)
                    cars=json.loads(canvas.get_attribute('data-vehicles'));assert len(cars)==(0 if mode=='empty' else 2)
                    page.screenshot(path=str(dest/f'{width}_{scale}_{mode}.png'))
            page.locator('#motion').click();page.wait_for_function('()=>Number(document.querySelector("#review").dataset.time)>0.1')
            start=json.loads(canvas.get_attribute('data-vehicles'));t=float(canvas.get_attribute('data-time'))
            page.wait_for_function('(t)=>Number(document.querySelector("#review").dataset.time)>=t+2',arg=t)
            end=json.loads(canvas.get_attribute('data-vehicles'));elapsed=float(canvas.get_attribute('data-time'))-t
            for x,y in zip(start,end):assert abs(np.linalg.norm(np.array(x['xy'])-y['xy'])/elapsed-32)<1
            page.locator('#motion').click();paused=canvas.get_attribute('data-time');page.wait_for_timeout(150);assert canvas.get_attribute('data-time')==paused
            cycle=page.evaluate('''async()=>{
              const {CroppedObjects}=await import('/web/pilot/dense-map.js');const {tilePicture}=await import('/web/pilot/tile-layer.js');
              const cfg=await(await fetch('./review.json')).json(),base=new URL(cfg.snapshot,location.href),m=await(await fetch(new URL('manifest.json',base))).json(),o=await(await fetch(new URL('overlay.json',base))).json();
              const objects=await CroppedObjects.load(o,base,m.asset_sha256),bg=await tilePicture(new URL('./',location.href),cfg.after,cfg.hashes[cfg.after]);
              const c=Object.assign(document.createElement('canvas'),{width:480,height:620}),ctx=c.getContext('2d'),rect=[2080,1500,480,620];
              const period=Math.max(...o.traffic.lanes.map(l=>Math.hypot(l.end[0]-l.start[0],l.end[1]-l.start[1])/o.traffic.speed)),steps=Math.ceil(period*32),frames=[];
              for(let i=0;i<=steps;i++){objects.seconds=i*period/steps;objects.drawTraffic(ctx,-rect[0],-rect[1],1);if(objects.samples.length!==2||objects.samples.some(s=>s.xy.some(v=>!Number.isFinite(v))))throw Error('Bad full-cycle sample');}
              for(let i=0;i<9;i++){ctx.clearRect(0,0,c.width,c.height);ctx.drawImage(bg,cfg.rect[0]-rect[0],cfg.rect[1]-rect[1]);objects.draw(ctx,-rect[0],-rect[1],1,null);objects.seconds=i*period/8;objects.drawTraffic(ctx,-rect[0],-rect[1],1);frames.push(c.toDataURL().split(',')[1]);}
              objects.close();bg.close();return{period,maxStepPx:period*32/steps,samples:steps+1,frames};
            }''')
            sheet=Image.new('RGB',(480*3,620*3))
            for i,png in enumerate(cycle.pop('frames')):
                f=dest/f'{width}_cycle_{i}.png';f.write_bytes(base64.b64decode(png))
                with Image.open(f) as im:sheet.paste(im,((i%3)*480,(i//3)*620))
            sheet.save(dest/f'{width}_cycle.png')
            assert not errors and not posts,(errors,posts)
            results.append({'viewport':[width,height],'threeModes':True,'scales':[.5,1],'twoSejongCars':True,'speed32':True,'pause':True,'cycle':cycle,'errors':errors,'paidCalls':0})
            page.close()
        browser.close()
    report={'outsideMaskChangedPixels':0,'tilesExactlyMatch':checked,'candidateAccepted':False,'browser':results}
    (dest/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--url',required=True);a=p.parse_args();check(a.root,a.url)
