"""Read-only local comparison UI test; no VWorld or AI network requests."""
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
    folder=P2/'eval/vworld/projection_probe/runs'/run
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(P2)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}'
    report={'passed':False,'errors':[],'external':[],'mutations':[]}
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            for name,width,height,dpr in [('desktop',1440,900,1),('mobile',390,844,2)]:
                context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=dpr)
                def guard(route):
                    if not route.request.url.startswith(origin+'/'):report['external'].append(route.request.url);route.abort()
                    elif route.request.method not in ['GET','HEAD']:report['mutations'].append(route.request.method);route.abort()
                    else:route.continue_()
                context.route('**/*',guard);page=context.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
                page.goto(origin+f'/eval/vworld/projection_probe/runs/{run}/index.html')
                page.wait_for_function('()=>[...document.images].length===2&&[...document.images].every(im=>im.complete&&im.naturalWidth===1536)')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=str(folder/f'comparison_{name}.png'),full_page=True)
                page.locator('#guides').check()
                page.wait_for_function('()=>[...document.images].every(im=>im.src.includes("_guides")&&im.complete&&im.naturalWidth===1536)')
                page.locator('#zoom').click();assert page.locator('body.native').count()==1
                assert page.locator('img').first.evaluate('im=>im.getBoundingClientRect().width')==1536
                page.locator('#zoom').click();page.locator('#guides').uncheck()
                page.wait_for_function('()=>[...document.images].every(im=>!im.src.includes("_guides")&&im.complete&&im.naturalWidth===1536)')
                context.close()
            browser.close()
        assert not report['errors'] and not report['external'] and not report['mutations'],report
        report['passed']=True;print(json.dumps(report))
    finally:
        (folder/'browser_qa.json').write_text(json.dumps(report,indent=2)+'\n');server.shutdown();server.server_close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);check(p.parse_args().run)
