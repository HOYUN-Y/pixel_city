"""Local/public-candidate UI regression. Does not send paid guide requests."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

def check(url, dest):
    dest.mkdir(parents=True, exist_ok=True)
    results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for name,width,height,reduced in [('desktop',1440,1000,'no-preference'),('mobile',390,844,'reduce')]:
            ctx=browser.new_context(viewport={'width':width,'height':height},reduced_motion=reduced)
            page=ctx.new_page();errors=[];posts=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
            page.goto(url);page.wait_for_selector('body[data-city-ready="true"]')
            assert page.locator('#inspection').count()==0 or page.locator('#inspection').is_hidden()
            page.screenshot(path=str(dest/(name+'_map.png')))
            page.locator('.dock [data-open="book"]' if width>900 else '.sheet-tabs [data-open="book"]').click()
            assert page.locator('[data-city-place^="landmark-"]').count()==8
            page.locator('[data-city-place="landmark-6"]').click()
            assert '보신각' in page.locator('.panel-content').last.inner_text()
            if page.locator('[data-city-reveal]').count():
                assert page.locator('#map').get_attribute('data-reveal')=='false'
                page.locator('[data-city-reveal]').click()
                page.wait_for_function('()=>Number(document.querySelector("#map").dataset.revealAmount)===1')
                page.screenshot(path=str(dest/(name+'_bosingak.png')))
                if width<900:
                    page.locator('.sheet-tabs [data-open="book"]').click()
                    page.locator('[data-city-place="landmark-6"]').click()
                assert 'AI 재구성' in page.locator('.panel-content').last.inner_text()
                page.locator('[data-reveal-opacity="0.25"]').click()
                page.locator('[data-city-reveal]').click()
                page.wait_for_function('()=>Number(document.querySelector("#map").dataset.revealAmount)===0')
                assert page.locator('#map').get_attribute('data-reveal')=='false'
                if width<900:
                    page.locator('.sheet-tabs [data-open="book"]').click()
                    page.locator('[data-city-place="landmark-6"]').click()
            page.locator('[data-collect]').click()
            assert page.evaluate('JSON.parse(localStorage.getItem("pixel-city.collection.v1"))').count('landmark-6')==1
            page.reload();page.wait_for_selector('body[data-city-ready="true"]')
            assert page.evaluate('JSON.parse(localStorage.getItem("pixel-city.collection.v1"))')==['landmark-6']
            page.locator('.city-controls [data-open="places"]').click()
            page.locator('[data-city-search] input').fill('보신각');page.locator('[data-city-search] button').click()
            assert page.locator('.city-place').count()==1
            page.locator('.city-place').click();assert '보신각터' in page.locator('.panel-content').last.inner_text()
            page.screenshot(path=str(dest/(name+'_place.png')))
            page.keyboard.press('Escape')
            # Mobile toolbar intentionally hides desktop controls; rain must also be reachable there.
            rain=page.locator('[aria-label="날씨 미리보기 변경"]:visible').first
            rain.click();page.wait_for_timeout(150);page.screenshot(path=str(dest/(name+'_rain.png')))
            page.locator('#city-road').click();page.wait_for_timeout(150)
            assert float(page.locator('#map').get_attribute('data-scale'))<=1
            if reduced=='reduce':assert page.locator('#map').get_attribute('data-traffic-playing')=='false'
            else:
                a=float(page.locator('#map').get_attribute('data-traffic-time'));page.wait_for_timeout(150);assert float(page.locator('#map').get_attribute('data-traffic-time'))>a
            assert not posts,'No guide POST before explicit submit'
            page.route('**/api/guide',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps({'answer':'<img src=x onerror=alert(1)> 보신각 자료 안내입니다.','sources':[],'placeIds':[]})))
            page.locator('.search').click();page.locator('[data-city-guide] input').fill('보신각 소개');page.locator('[data-city-guide] button').click()
            page.wait_for_function('()=>document.querySelector(".city-messages")?.textContent.includes("자료 안내입니다")')
            assert page.locator('.city-messages img').count()==0
            page.unroute('**/api/guide');page.route('**/api/guide',lambda r:r.fulfill(status=503,content_type='application/json',body='{"error":"disabled"}'))
            page.locator('[data-city-guide] input').fill('한 번 더');page.locator('[data-city-guide] button').click()
            page.wait_for_function('()=>document.querySelector(".city-messages")?.textContent.includes("지도와 도감은 계속")')
            assert page.locator('body').get_attribute('data-city-ready')=='true'
            # Exercise two independent alpha masks with synthetic test fixtures only.
            result=page.evaluate('''async()=>{
              const {LivingLayer}=await import(new URL('./living.js',document.querySelector('script[type="module"]').src));
              const spots=[{id:'a'},{id:'b'}],occluders=[{id:'ma'},{id:'mb'}];
              const overlay={spots,occluders,landmarks:[{id:'a',occluder_id:'ma',mode:'independent',sprite:'sa',hit:'ha'},{id:'b',occluder_id:'mb',mode:'independent',sprite:'sb',hit:'hb'}]};
              const picture=async(base,file)=>{const c=document.createElement('canvas');c.width=64;c.height=64;const x=c.getContext('2d');x.fillStyle='white';x.fillRect(file.endsWith('a')?10:30,10,10,10);return createImageBitmap(c);};
              const l=await LivingLayer.load(overlay,'/',{sa:'x',ha:'x',sb:'x',hb:'x'},picture,{width:64,height:64});
              const hits=[l.hit({x:15,y:15}),l.hit({x:35,y:15}),l.hit({x:25,y:15})];l.setLandmarkVisible('a',false);
              const after=[l.hit({x:15,y:15}),l.hit({x:35,y:15}),l.occluderEnabled('ma'),l.occluderEnabled('mb')];l.close();return {hits,after};
            }''')
            assert result=={'hits':['a','b',None],'after':[None,'b',False,True]},result
            reveal=page.evaluate('''async()=>{
              const {RevealLayer}=await import(new URL('./reveal.js',document.querySelector('script[type="module"]').src));
              const size={width:16,height:16},make=()=>Object.assign(document.createElement('canvas'),size);
              const hit=new Uint8ClampedArray(16*16*4);hit[(8*16+8)*4]=255;
              const layer=new RevealLayer({targetId:'b'},make(),hit,size);layer.patch=make();layer.outline=make();
              const pc=layer.patch.getContext('2d');pc.fillStyle='#0000ff';pc.fillRect(6,6,4,4);
              const c=make(),ctx=c.getContext('2d'),sample=()=>Array.from(ctx.getImageData(8,8,1,1).data);
              const reset=()=>{ctx.fillStyle='#ff0000';ctx.fillRect(0,0,16,16);};
              reset();layer.draw(ctx,0,0,1,0,null);const normal=sample(),hiddenHit=layer.hit({x:8,y:8});
              layer.set(true);layer.amount=1;reset();layer.draw(ctx,0,0,1,1,null);
              const blend=sample(),outside=Array.from(ctx.getImageData(0,0,1,1).data),visibleHit=layer.hit({x:8,y:8}),emptyHit=layer.hit({x:1,y:1});
              layer.set(false);layer.amount=0;reset();layer.draw(ctx,0,0,1,2,null);return{normal,hiddenHit,blend,outside,visibleHit,emptyHit,restored:sample(),moving:layer.moving};
            }''')
            assert reveal['normal']==reveal['restored']==reveal['outside']==[255,0,0,255],reveal
            assert reveal['hiddenHit'] is None and reveal['visibleHit']=='b' and reveal['emptyHit'] is None and not reveal['moving'],reveal
            assert abs(reveal['blend'][0]-115)<=1 and abs(reveal['blend'][2]-140)<=1,reveal
            assert not errors,errors
            results.append({'viewport':name,'errors':errors,'paidRequests':0,'mockGuideRequests':len(posts),'collection':True,'search':True,'rain':True,'zoom':True,'multipleAlphaMasks':True,'revealBlendRestoreHit':True})
            ctx.close()
        browser.close()
    (dest/'browser_qa.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8768/web/pilot/index.html?view=city-pilot');p.add_argument('--dest',type=Path,default=Path('prototype2/work/city-qa-20260916'));a=p.parse_args();check(a.url,a.dest)
