"""Polish-specific interaction and pixel evidence on the existing local server."""
import argparse
import base64
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

def check(url,dest):
    dest.mkdir(parents=True,exist_ok=True);results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for width,height in [(1440,1000),(390,844)]:
            page=browser.new_page(viewport={'width':width,'height':height},reduced_motion='reduce')
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/api/guide',lambda r:r.fulfill(status=200,content_type='application/json',body='{"enabled":false}'))
            page.goto(url);page.wait_for_selector('body[data-city-ready="true"]')
            page.locator('.city-landmarks [data-city-focus="bosingak"]').click()
            page.wait_for_function('()=>document.querySelector("#map").dataset.revealAmount==="1"')
            if width<900:
                page.locator('.sheet-tabs [data-open="book"]').click();page.locator('[data-city-place="landmark-6"]').click()
            page.locator('[data-reveal-opacity="0.65"]').click()
            page.locator('[data-city-reveal]').click()
            page.wait_for_function('()=>document.querySelector("#map").dataset.revealAmount==="0"')
            # Re-selecting the same object must not override manual restore.
            page.locator('.city-landmarks [data-city-focus="bosingak"]').click()
            assert page.locator('#map').get_attribute('data-reveal')=='false'
            page.keyboard.press('Escape')
            page.locator('#bosingak-marker').click()
            page.wait_for_function('()=>document.querySelector("#map").dataset.revealAmount==="1"')
            page.locator('[data-beta-close]').click()
            assert page.locator('#map').get_attribute('data-reveal')=='true'
            page.locator('#toast').wait_for(state='hidden')
            page.screenshot(path=str(dest/f'{width}_auto_bosingak.png'))
            page.locator('#map').click(position={'x':width-30,'y':300})
            page.wait_for_function('()=>document.querySelector("#map").dataset.revealAmount==="0"')
            for region in ['jongno','sejong']:
                page.locator(f'[data-traffic-focus="{region}"]').click()
                page.wait_for_function('()=>document.querySelector("#map").dataset.tilePending==="0"')
                cars=json.loads(page.locator('#map').get_attribute('data-vehicles'))
                assert len(cars)==len({v['vehicleId'] for v in cars})==4
                page.screenshot(path=str(dest/f'{width}_{region}.png'))
            pixel=page.evaluate('''async()=>{
              const {CroppedObjects,CroppedReveal}=await import('/web/pilot/dense-map.js');
              const {tilePicture}=await import('/web/pilot/tile-layer.js');
              const make=(w,h)=>Object.assign(document.createElement('canvas'),{width:w,height:h});
              const base=new URL(document.body.dataset.cityBase,location.href),m=await(await fetch(new URL('manifest.json',base))).json(),o=await(await fetch(new URL('overlay.json',base))).json();
              const objects=await CroppedObjects.load(o,base,m.asset_sha256),reveal=await CroppedReveal.load(o.reveal,objects,base,m.asset_sha256);
              const [rx,ry,rw,rh]=o.reveal.rect,bg=make(rw,rh),bc=bg.getContext('2d');
              for(let y=Math.floor(ry/512);y<=Math.floor((ry+rh-1)/512);y++)for(let x=Math.floor(rx/512);x<=Math.floor((rx+rw-1)/512);x++){
                const f=`tiles/1/${x}_${y}.png`,im=await tilePicture(base,f,m.asset_sha256[f]);bc.drawImage(im,x*512-rx,y*512-ry);im.close();
              }
              const paint=()=>{const c=make(rw,rh),ctx=c.getContext('2d');ctx.drawImage(bg,0,0);reveal.draw(ctx,-rx,-ry,1,performance.now(),null);return c;};
              const bytes=c=>c.getContext('2d').getImageData(0,0,c.width,c.height).data;
              const original=bytes(paint());reveal.set(true);const shown=paint(),changed=bytes(shown);
              const mask=await tilePicture(base,o.reveal.mask,m.asset_sha256[o.reveal.mask]),mc=make(rw,rh);mc.getContext('2d').drawImage(mask,0,0);mask.close();const mb=bytes(mc);
              let outside=0,difference=0;for(let i=0;i<original.length;i+=4)if(original.slice(i,i+4).some((v,j)=>v!==changed[i+j])){difference++;if(mb[i]<128)outside++;}
              reveal.set(false);const restored=bytes(paint());if(outside||!difference||original.some((v,i)=>v!==restored[i]))throw Error('Reveal mask/restore regression');
              reveal.reduced={matches:false};reveal.set(true);
              const fadeCanvas=make(rw,rh),fadeContext=fadeCanvas.getContext('2d');
              for(const [time,expected] of [[1000,0],[1050,.25],[1100,.5],[1150,.75],[1200,1]]){reveal.draw(fadeContext,-rx,-ry,1,time,null);if(Math.abs(reveal.amount-expected)>1e-8)throw Error('200ms fade regression');}
              reveal.reduced={matches:true};reveal.set(false);
              const {paintVehicle}=await import('/web/pilot/dense-core.js');
              const car=make(4,4);car.getContext('2d').fillRect(0,0,4,4);const masked=make(4,4);
              paintVehicle(masked.getContext('2d'),car,[0,0,4,4],[{rect:[0,0,4,4],shape:car,opacity:.45}]);
              if(Math.abs(bytes(masked)[3]-140)>1)throw Error('Translucent foreground vehicle alpha regression');
              const frames=[],rects={jongno:[3540,1900,720,380],sejong:[2080,1500,480,620]};
              // Existing independently traced corridor; do not widen it to fit cars.
              const frozen=await(await fetch('/work/dense-roads-20260917/road_corridor_frozen.json')).json();
              const roadImage=await createImageBitmap(await(await fetch('/work/dense-roads-20260917/'+frozen.mask)).blob());
              const rc=make(roadImage.width,roadImage.height);rc.getContext('2d').drawImage(roadImage,0,0);roadImage.close();const road=bytes(rc),rr=frozen.rect;
              const roadPixel=(x,y)=>x>=rr[0]&&y>=rr[1]&&x<rr[2]&&y<rr[3]?road[((y-rr[1])*rc.width+x-rr[0])*4]>=128:null;
              const counts={inside:0,outside:0,boundary:0,unverified:0};
              const period=Math.max(...o.traffic.lanes.map(l=>Math.hypot(l.end[0]-l.start[0],l.end[1]-l.start[1])/o.traffic.speed));
              const dummy=make(1,1),steps=Math.ceil(period*o.traffic.speed);
              for(let i=0;i<=steps;i++){
                objects.seconds=period*i/steps;objects.drawTraffic(dummy.getContext('2d'),0,0,1,reveal);
                for(const sample of objects.samples){
                  if(sample.alpha===0)continue;
                  const layer=objects.vehicleLayers.get(sample.vehicleId),pixels=bytes(layer);
                  for(let y=0;y<layer.height;y++)for(let x=0;x<layer.width;x++){
                    if(!pixels[(y*layer.width+x)*4+3])continue;
                    const wx=sample.rect[0]+x,wy=sample.rect[1]+y,value=roadPixel(wx,wy);
                    if(value===null){counts.unverified++;continue;}
                    let edge=false,scope=true;for(let dy=-2;dy<=2;dy++)for(let dx=-2;dx<=2;dx++){const neighbor=roadPixel(wx+dx,wy+dy);if(neighbor===null)scope=false;else if(neighbor!==value)edge=true;}
                    counts[!scope?'unverified':edge?'boundary':value?'inside':'outside']++;
                  }
                }
              }
              for(const [region,r] of Object.entries(rects)){
                const background=make(r[2],r[3]),c=background.getContext('2d');
                for(let y=Math.floor(r[1]/512);y<=Math.floor((r[1]+r[3]-1)/512);y++)for(let x=Math.floor(r[0]/512);x<=Math.floor((r[0]+r[2]-1)/512);x++){
                  const f=`tiles/1/${x}_${y}.png`,im=await tilePicture(base,f,m.asset_sha256[f]);c.drawImage(im,x*512-r[0],y*512-r[1]);im.close();
                }
                for(let i=0;i<9;i++){
                  const frame=make(r[2],r[3]),fc=frame.getContext('2d');fc.drawImage(background,0,0);objects.draw(fc,-r[0],-r[1],1,null);objects.seconds=period*i/8;objects.drawTraffic(fc,-r[0],-r[1],1,reveal);frames.push({region,index:i,png:frame.toDataURL().split(',')[1]});
                }
              }
              const result={outsideMaskPixels:outside,changedPixels:difference,restoredExactly:true,fade200ms:true,translucentVehicleAlpha:true,vehicleBuffers:objects.vehicleLayers.size,maxStepPx:period*32/steps,visiblePixelRoadCounts:counts,roadPassed:counts.outside===0&&counts.boundary===0,unverifiedScope:'Includes all Sejong pixels and western/hidden Jongno; not a pass',frames,revealPNG:shown.toDataURL().split(',')[1]};objects.close();return result;
            }''')
            from PIL import Image
            for region in ['jongno','sejong']:
                frames=[f for f in pixel['frames'] if f['region']==region];sheet=None
                for f in frames:
                    file=dest/f"{width}_{region}_cycle_{f['index']}.png";file.write_bytes(base64.b64decode(f['png']))
                    with Image.open(file) as im:
                        if sheet is None:sheet=Image.new('RGB',(im.width*3,im.height*3))
                        sheet.paste(im,((f['index']%3)*im.width,(f['index']//3)*im.height))
                sheet.save(dest/f'{width}_{region}_cycle.png')
            (dest/f'{width}_reveal.png').write_bytes(base64.b64decode(pixel.pop('revealPNG')));pixel.pop('frames')
            assert not errors,errors
            results.append({'viewport':[width,height],'autoManualSelection':True,'panelClosePreservesSelection':True,'blankClickRestores':True,'pixels':pixel,'errors':errors})
            page.close()
        browser.close()
    (dest/'polish_qa.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--dest',type=Path,required=True);a=p.parse_args();check(a.url,a.dest)
