"""Local-only desktop/mobile acceptance; guide requests are mocked, never paid."""
import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from pathlib import Path
from playwright.sync_api import sync_playwright

def check(url,dest):
    dest.mkdir(parents=True,exist_ok=True)
    results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for width,height in [(1440,1000),(390,844)]:
            page=browser.new_page(viewport={'width':width,'height':height},reduced_motion='reduce')
            errors=[];posts=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
            page.route('**/api/guide',lambda r:r.fulfill(status=200,content_type='application/json',body='{"enabled":false}'))
            page.goto(url);page.wait_for_selector('body[data-city-ready="true"]')
            assert page.locator('#city-traffic').count()==0
            base=page.evaluate('()=>new URL(document.body.dataset.cityBase,location.href).href')
            places=page.request.get(base+'places.json').json()
            ids=[(l['id'],l['mapSpotId']) for l in places['landmarks'] if l.get('mapSpotId')]
            overlay=page.request.get(base+'overlay.json').json()
            for card,spot in ids:
                page.locator('[data-open="landmarks"]').click()
                assert page.locator('[data-discovery-place]').count()==8
                page.locator(f'[data-discovery-place="{card}"]').click()
                page.wait_for_function('(id)=>document.querySelector("#map").dataset.selected===id',arg=spot)
                page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                page.wait_for_function('()=>document.querySelector("#map").dataset.tilePending==="0"')
                assert float(page.locator('#map').get_attribute('data-scale'))<=1
                assert page.locator('#map').get_attribute('data-vehicles')=='[]'
                assert json.loads(page.evaluate('localStorage.getItem("pixel-city.collection.v1")||"[]"'))==[]
                if width<900:assert abs(page.locator('#sheet').bounding_box()['height']-height*.4)<2
                # Building center remains outside the detail panel, below the toolbar.
                entry=next(s for s in overlay['spots'] if s['id']==spot)
                obj=next((l for l in overlay['landmarks'] if l['id']==spot),None)
                points=entry.get('hitPolygon')
                xy=[obj['rect'][0]+obj['rect'][2]/2,obj['rect'][1]+obj['rect'][3]/2] if obj else [sum(p[i] for p in points)/len(points) for i in [0,1]] if points else entry['xy']
                center=json.loads(page.locator('#map').get_attribute('data-center'));scale=float(page.locator('#map').get_attribute('data-scale'))
                sx=width/2+(xy[0]-center['x'])*scale;sy=height/2+(xy[1]-center['y'])*scale
                panel=page.locator('#sheet' if width<900 else '.floating-window').bounding_box()
                assert sy>page.locator('.toolbar').bounding_box()['y']+page.locator('.toolbar').bounding_box()['height']
                assert sy<panel['y'] if width<900 else sx>panel['x']+panel['width']
                page.screenshot(path=str(dest/f'{width}_{spot}.png'))
                page.locator('[data-beta-close]').click()
                assert page.locator('#map').get_attribute('data-selected')==spot
                # Map hit itself opens details without changing the camera.
                if points:
                    before=page.locator('#map').get_attribute('data-center')
                    page.mouse.click(sx,sy)
                    assert page.locator('#map').get_attribute('data-selected')==spot
                    assert page.locator('#map').get_attribute('data-center')==before
                    page.locator('[data-beta-close]').click()
                    page.mouse.move(sx,sy);page.mouse.down();page.mouse.move(sx+60,sy+30,steps=5);page.mouse.up()
                    assert page.locator('#map').get_attribute('data-selected')==spot
                    if width<900:
                        cdp=page.context.new_cdp_session(page)
                        cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':120,'y':300},{'x':220,'y':300}]})
                        cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':100,'y':300},{'x':240,'y':300}]})
                        cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
                        assert page.locator('#map').get_attribute('data-selected')==spot
                page.keyboard.press('Escape')
                page.wait_for_function('()=>!document.querySelector("#map").dataset.selected')
            page.locator('[data-open="landmarks"]').click();page.locator('[data-discovery-place="landmark-1"]').click()
            page.locator('[data-collect="landmark-1"]').click()
            assert page.locator('[data-collect="landmark-1"]').evaluate('(b)=>document.activeElement===b')
            page.reload();page.wait_for_selector('body[data-city-ready="true"]')
            page.locator('.sheet-tabs [data-open="book"]' if width<900 else '.dock [data-open="book"]').click()
            assert page.locator('.card-grid button').count()==8
            assert page.locator('.card-grid img').count()==len(ids)
            assert page.locator('.card-grid .missing').count()==8-len(ids)
            assert page.locator('.collection-head').inner_text().endswith('1/8')
            page.locator('[data-book-filter="saved"]').click()
            assert page.locator('.card-grid button').count()==1
            page.locator('[data-book-filter="all"]').click()
            page.screenshot(path=str(dest/f'{width}_collection.png'))
            # Unlinked cards and ordinary nearby-place details must survive map deselection.
            for l in places['landmarks']:
                if l.get('mapSpotId'):continue
                page.locator(f'[data-city-place="{l["id"]}"]').click()
                assert page.locator('.panel-content h2').inner_text()==l['name']
                assert page.locator('[data-city-focus]').count()==len([s for s in overlay['spots'] if s.get('hitPolygon') or s.get('selectionMode')=='location-only'])
                page.locator('.sheet-tabs [data-open="book"]' if width<900 else '.dock [data-open="book"]').click()
            page.locator('[data-open="places"]').click()
            first=places['places'][0]
            page.locator(f'[data-city-place="{first["id"]}"]').click()
            assert page.locator('.panel-content h2').inner_text()==first['name']
            page.keyboard.press('Escape')
            page.route('**/thumb_*.png',lambda r:r.fulfill(status=503,body='unavailable'))
            page.route('**/tiles/**/*.png',lambda r:r.fulfill(status=503,body='unavailable'))
            page.reload();page.wait_for_selector('body[data-city-ready="true"]')
            page.locator('[data-open="landmarks"]').click()
            page.wait_for_function('()=>document.querySelectorAll(".discovery-list .missing").length===8')
            page.locator('[data-discovery-place="landmark-1"]').click()
            page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            page.wait_for_function('()=>Number(document.querySelector("#map").dataset.tileFailed)>0&&document.querySelector("#map").dataset.tilePending==="0"')
            page.locator('[data-beta-close]').click()
            # A courtyard point outside the traced building clears selection.
            center=json.loads(page.locator('#map').get_attribute('data-center'));scale=float(page.locator('#map').get_attribute('data-scale'))
            page.mouse.click(width/2+(1685-center['x'])*scale,height/2+(1160-center['y'])*scale)
            page.wait_for_function('()=>!document.querySelector("#map").dataset.selected')
            page.screenshot(path=str(dest/f'{width}_fallback.png'))
            assert not errors,errors
            assert not posts,posts
            assert int(page.locator('#map').get_attribute('data-tile-cache'))<=48
            results.append({'viewport':[width,height],'linkedSelections':len(ids),'collectionPersistence':True,'collectionFilter':True,'nearbyDetails':True,'dragNoSelection':True,'pinchNoSelection':width<900,'thumbnailFallback':True,'tile503Fallback':True,'outsideClears':True,'paidPosts':len(posts),'errors':errors})
            page.close()
        browser.close()
    (dest/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(json.dumps(results,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8766/work/landmark-discovery-20260920/');parser.add_argument('--dest',type=Path,default=Path('prototype2/work/landmark-discovery-20260920/browser'));parser.add_argument('--public-root',type=Path)
    args=parser.parse_args()
    if args.public_root:
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(args.public_root.resolve())))
        Thread(target=server.serve_forever,daemon=True).start()
        try:check(f'http://127.0.0.1:{server.server_port}/',args.dest)
        finally:server.shutdown();server.server_close()
    else:check(args.url,args.dest)
