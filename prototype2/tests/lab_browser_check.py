"""Actual local seam-lab browser QA; no AI calls or external requests."""
import argparse
import functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright

P2 = Path(__file__).resolve().parents[1]


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def check(run):
    root = P2 / 'eval/vworld/seam_lab/runs' / run
    output = root / 'browser_qa'; output.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(P2)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    report = {'errors': [], 'external': [], 'mutations': [], 'scenes': {}}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            for name, size, dpr in [('desktop', (1440, 900), 1), ('tablet', (1024, 768), 1), ('mobile', (390, 844), 2), ('mobile_dpr3', (390, 844), 3)]:
                context = browser.new_context(viewport={'width': size[0], 'height': size[1]}, device_scale_factor=dpr, reduced_motion='reduce')
                def guard(route):
                    req = route.request
                    if not req.url.startswith(origin+'/'):
                        report['external'].append(req.url); route.abort()
                    elif req.method not in ('GET', 'HEAD'):
                        report['mutations'].append(req.method); route.abort()
                    else:
                        route.continue_()
                context.route('**/*', guard)
                page = context.new_page(); page.on('pageerror', lambda e: report['errors'].append(str(e)))
                page.goto(origin+'/web/pilot/?view=seam-lab&run='+run)
                page.wait_for_selector('body[data-tiles-ready="true"]')
                page.evaluate('document.fonts.ready')
                assert page.locator('#map').get_attribute('data-playing') == 'false'
                page.screenshot(path=str(output / f'{name}_downtown.png'))
                def inspect():
                    if page.locator('#inspection').get_attribute('open') is None:
                        page.locator('#inspection summary').click()
                for scene in ['downtown', 'namsan']:
                    inspect(); page.locator('#lab-scene').select_option(scene)
                    page.wait_for_function('(s)=>document.querySelector("#map").dataset.scene===s', arg=scene)
                    page.locator('#lab-spot').select_option(index=1)
                    if size[0]<900:
                        assert page.locator('#sheet.expanded').is_visible()
                        page.locator('#sheet-body [data-lab-focus]').click()
                    else:
                        assert page.locator('[data-window="spot"]').is_visible()
                        page.locator('[data-window="spot"] [data-lab-focus]').click()
                    inspect(); page.locator('#lab-tour').click()
                    assert page.locator('[data-lab-start]').is_visible()
                    page.locator('[data-lab-start]').click()
                    page.wait_for_function('()=>document.querySelector("#map").dataset.playing==="true"')
                    inspect(); page.locator('#lab-pause').click()
                    samples=[]
                    for phase in range(0,1001,25):
                        page.locator('#lab-phase').evaluate('(el,p)=>{el.value=p;el.dispatchEvent(new Event("input",{bubbles:true}));}',phase)
                        page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                        samples.append([phase,int(page.locator('#map').get_attribute('data-actor-visible')),int(page.locator('#map').get_attribute('data-actor-occluded'))])
                    assert any(v>0 and h==0 for _,v,h in samples), (scene,'no front sample')
                    assert any(v>0 and h>0 for _,v,h in samples), (scene,'no partial sample')
                    assert any(v==0 and h>0 for _,v,h in samples), (scene,'no hidden sample')
                    report['scenes'][name+'_'+scene]=samples
                    if name == 'desktop':
                        page.locator('button[data-scale="1"]').click()
                        for label, sample in [('front', next(s for s in samples if s[1]>0 and s[2]==0)),
                                              ('partial', next(s for s in samples if s[1]>0 and s[2]>0)),
                                              ('hidden', next(s for s in samples if s[1]==0 and s[2]>0))]:
                            page.locator('#lab-phase').evaluate('(el,p)=>{el.value=p;el.dispatchEvent(new Event("input",{bubbles:true}));}',sample[0])
                            page.locator('#inspection summary').click()
                            page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                            page.screenshot(path=str(output / f'{scene}_actor_{label}.png'))
                            inspect()
                    # Zoom, comparison state and return to final.
                    page.locator('button[data-scale="1"]').click()
                    page.wait_for_function('()=>document.querySelector("#map").dataset.scale==="1"')
                    assert page.locator('#zoom-in').is_disabled()
                    page.locator('#debug-zoom').check();page.locator('button[data-scale="2"]').click()
                    page.wait_for_function('()=>document.querySelector("#map").dataset.scale==="2"')
                    page.locator('#debug-zoom').uncheck();page.locator('#map-mode').select_option('source')
                    page.wait_for_function('()=>document.querySelector("#map").dataset.mode==="source"')
                    assert page.locator('#lab-play').is_disabled()
                    page.locator('#map-mode').select_option('final');page.locator('#fit').click()
                    page.locator('#inspection summary').click()
                    page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                    page.screenshot(path=str(output / f'{name}_{scene}_final.png'))
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    if name == 'desktop':
                        spot = json.loads((root / f'{scene}_overlay.json').read_text())['spots'][0]
                        target = page.locator('#map').evaluate('(el,p)=>{const r=el.getBoundingClientRect(),c=JSON.parse(el.dataset.center),s=Number(el.dataset.scale);return [r.left+r.width/2+(p[0]-c.x)*s,r.top+r.height/2+(p[1]-c.y)*s];}',spot['xy'])
                        page.mouse.click(*target)
                        page.wait_for_function('(id)=>document.querySelector("#map").dataset.selected===id',arg=spot['id'])
                        page.locator('[data-window="spot"] [data-lab-focus]').click()
                        page.locator('#map').press('Escape')
                        page.mouse.move(size[0]/2,size[1]/2);page.mouse.down()
                        page.mouse.move(size[0]/2+80,size[1]/2+30,steps=6);page.mouse.up()
                        page.evaluate('()=>new Promise(r=>requestAnimationFrame(r))')
                        assert page.locator('#map').get_attribute('data-selected') == ''
                context.close()
            # Missing or corrupted images must fail closed, not draw stale overlays.
            for kind in ['missing', 'hash']:
                context = browser.new_context()
                context.route('**/*', guard)
                context.route('**/traveler.png', lambda r, k=kind: r.fulfill(status=404, body='missing') if k=='missing' else r.fulfill(status=200, body='corrupted'))
                page = context.new_page()
                page.goto(origin+'/web/pilot/?view=seam-lab&run='+run)
                page.wait_for_selector('#map-message[data-state="error"]')
                assert page.locator('#zoom-in').is_disabled()
                assert page.locator('body').get_attribute('data-tiles-ready') != 'true'
                context.close()
            browser.close()
        assert not report['errors'] and not report['external'] and not report['mutations'], report
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps({'passed':True,'viewport_scenes':len(report['scenes']),'external':report['external'],'errors':report['errors']}))
    finally:
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        server.shutdown();server.server_close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);check(parser.parse_args().run)
