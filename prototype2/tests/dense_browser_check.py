"""Dense renderer QA against a diagnostic fixture or reviewed snapshot. No AI calls."""
import argparse
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

def check(dest,snapshot=None):
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
                page.locator('[data-city-reveal]').click();page.wait_for_function('()=>document.querySelector("#map").dataset.revealAmount==="1"')
                page.screenshot(path=str(dest/f'{width}_bosingak.png'))
                page.keyboard.press('Escape');page.locator('.city-landmarks [data-city-focus="jongno-tower"]').click();page.keyboard.press('Escape')
                page.wait_for_function('()=>document.querySelector("#map").dataset.reveal==="false"')
                page.screenshot(path=str(dest/f'{width}_tower.png'))
                page.locator('#city-road').click();page.locator('#city-traffic').click()
                before_time=float(page.locator('#map').get_attribute('data-traffic-time'))
                page.wait_for_function('(t)=>Number(document.querySelector("#map").dataset.trafficTime)>t',arg=before_time)
                page.screenshot(path=str(dest/f'{width}_traffic.png'))
                page.locator('#city-traffic').click()
                page.locator('#fit').click();page.screenshot(path=str(dest/f'{width}_whole.png'))
                # Newly requested unavailable tiles must not make the map unusable or retry forever.
                page.route('**/tiles/**',lambda route:route.fulfill(status=503,body='offline'))
                page.locator('#fit').click();page.locator('.city-landmarks [data-city-focus="gwanghwamun"]').click();page.keyboard.press('Escape')
                page.locator('#map').focus()
                for _ in range(20):page.keyboard.press('ArrowUp')
                page.wait_for_function('()=>document.querySelector("#map").dataset.tilePending==="0"')
                before=page.locator('#map').get_attribute('data-tile-requests');page.wait_for_timeout(250)
                assert page.locator('#map').get_attribute('data-tile-requests')==before
                assert page.locator('body').get_attribute('data-city-ready')=='true'
                assert not posts and not errors,(posts,errors)
                results.append({'viewport':[width,height],'testFixture':is_fixture,'cache':int(page.locator('#map').get_attribute('data-tile-cache')),'failedTiles':int(page.locator('#map').get_attribute('data-tile-failed')),'errors':errors,'paidCalls':0,'navigationRevealFallback':True,'trafficAdvances':True})
                page.close()
            browser.close()
    finally:server.shutdown();server.server_close()
    (dest/'browser_qa.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dest',type=Path,required=True);p.add_argument('--snapshot',type=Path);a=p.parse_args();check(a.dest,a.snapshot)
