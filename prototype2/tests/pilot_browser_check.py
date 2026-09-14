"""Real browser QA: test fixture by default, actual run with --run ID. Never calls AI."""
import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_seam_zoom import fixture_images, sz


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def check(run=None, projection=False):
    fixture_tmp = None
    if run:
        folder = (sz.qs.P2 / 'eval/vworld/orthographic_lab/runs' if projection else sz.ROOT) / run
        assert (folder / 'manifest.json').is_file()
    else:
        fixture_tmp = tempfile.TemporaryDirectory()
        folder = Path(fixture_tmp.name)
        report = {}
        sz.publish(folder, Image.new('RGB', (1536, 1536), '#D9CBA5'), fixture_images(), report)
        manifest = json.loads((folder / 'manifest.json').read_text())
        manifest['run_id'] = '20000101T000000000000Z'
        sz.qs.write(folder / 'manifest.json', manifest)
        sz.qs.write(folder / 'report.json', report)
        run = manifest['run_id']
    handler = functools.partial(QuietHandler, directory=str(sz.qs.P2))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    query = '/web/pilot/?' + ('view=projection-lab&' if projection else '') + 'run='
    output = folder if fixture_tmp is None else sz.qs.P2 / 'eval/vworld/openrouter/seam_zoom/fixture_qa'
    output.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            errors, external, mutations = [], [], []
            context = browser.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=1)
            def route(request):
                req = request.request
                if not req.url.startswith(origin + '/'):
                    external.append(req.url);request.abort();return
                if req.method not in ('GET', 'HEAD'):
                    mutations.append(req.method);request.abort();return
                marker = f'/eval/vworld/openrouter/seam_zoom/runs/{run}/'
                if fixture_tmp and marker in req.url:
                    relative = req.url.split(marker, 1)[1]
                    file = folder / relative
                    request.fulfill(path=str(file)) if file.is_file() else request.fulfill(status=404, body='Missing fixture')
                else:
                    request.continue_()
            context.route('**/*', route)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(origin + query + run)
            page.wait_for_selector('body[data-tiles-ready="true"]')
            page.evaluate('()=>document.fonts.ready')
            assert page.locator('.floating-window').count() == 0
            assert not page.locator('#sheet').is_visible()
            page.screenshot(path=str(output / 'gui_desktop.png'))
            page.locator('#inspection summary').click()
            page.locator('#preview-state').select_option('card')
            assert page.locator('#card-modal').is_visible()
            page.keyboard.press('Escape')
            assert not page.locator('#card-modal').is_visible()
            page.locator('#preview-state').select_option('post')
            assert page.locator('[data-window="post"]').is_visible()
            page.locator('[data-close="post"]').click()
            page.locator('#preview-state').select_option('route')
            assert page.locator('#route-bar').is_visible()
            page.locator('[data-close-route]').click()
            page.locator('[data-close="route"]').click()
            for scale in ('0.25', '0.5', '1'):
                page.locator(f'[data-scale="{scale}"]').click()
                page.wait_for_function('(s)=>Number(document.querySelector("#map").dataset.scale)===s', arg=float(scale))
                page.screenshot(path=str(output / f'zoom_{int(float(scale)*100)}.png'))
            assert page.locator('#zoom-in').is_disabled()
            page.locator('#debug-zoom').check()
            page.locator('[data-scale="2"]').click()
            page.wait_for_function('()=>document.querySelector("#map").dataset.scale === "2"')
            page.locator('#seam-lines').check()
            page.screenshot(path=str(output / 'zoom_200_seams.png'))
            # Verify cursor-anchored wheel zoom and real mouse pan away from edge clamps.
            old_center = json.loads(page.locator('#map').get_attribute('data-center'))
            anchor = {'x': old_center['x'] + (950 - 720) / 2, 'y': old_center['y'] + (400 - 450) / 2}
            page.mouse.move(950, 400);page.mouse.wheel(0, 120)
            page.wait_for_function('()=>Number(document.querySelector("#map").dataset.scale)<2')
            zoom = float(page.locator('#map').get_attribute('data-scale'))
            center = json.loads(page.locator('#map').get_attribute('data-center'))
            assert abs(center['x'] + (950 - 720) / zoom - anchor['x']) < .01
            assert abs(center['y'] + (400 - 450) / zoom - anchor['y']) < .01
            page.mouse.move(900, 450);page.mouse.down();page.mouse.move(980, 490);page.mouse.up()
            page.wait_for_function('(x)=>JSON.parse(document.querySelector("#map").dataset.center).x<x', arg=center['x'])
            moved = json.loads(page.locator('#map').get_attribute('data-center'))
            assert abs(moved['x'] - (center['x'] - 80 / zoom)) < .01
            page.locator('#debug-zoom').uncheck()
            page.wait_for_function('()=>document.querySelector("#map").dataset.scale === "1"')
            before = page.locator('#map').get_attribute('data-center')
            page.locator('#map-mode').select_option('source')
            page.wait_for_function('()=>document.querySelector("#map").dataset.mode === "source"')
            assert page.locator('#map').get_attribute('data-center') == before
            if projection:
                page.locator('#map-mode').select_option('before')
                page.wait_for_function('()=>document.querySelector("#map").dataset.mode === "before"')
                assert page.locator('#map').get_attribute('data-center') == before
                assert page.locator('#map').get_attribute('data-scale') == '1'
                page.screenshot(path=str(output / 'gui_before.png'))
            page.locator('#map-mode').select_option('ai')
            page.locator('#seam-lines').uncheck()
            page.locator('#inspection summary').click()
            page.locator('.dock [data-open="chat"]').click()
            center = page.locator('#map').get_attribute('data-center')
            header = page.locator('[data-window="chat"] .window-header').bounding_box()
            page.mouse.move(header['x'] + 100, header['y'] + 20);page.mouse.down()
            page.mouse.move(header['x'] + 170, header['y'] + 70);page.mouse.up()
            assert page.locator('#map').get_attribute('data-center') == center
            page.locator('[data-window="chat"] input').fill('이 질문은 전송하면 안 됩니다')
            page.locator('[data-window="chat"] input').press('Enter')
            assert page.locator('#toast').is_visible()
            assert page.locator('.bubble').count() == 1
            old_zoom = page.locator('#map').get_attribute('data-scale')
            page.locator('[data-window="chat"] .panel-content').hover()
            page.mouse.wheel(0, 120)
            assert page.locator('#map').get_attribute('data-scale') == old_zoom
            for key in ('feed', 'book', 'upload'):
                page.locator(f'.dock [data-open="{key}"]').click()
                assert page.locator(f'[data-window="{key}"]').is_visible()
            page.screenshot(path=str(output / 'gui_windows.png'))
            page.keyboard.press('Escape')
            assert page.locator('[data-window="upload"]').count() == 0
            page.set_viewport_size({'width': 1024, 'height': 768})
            assert page.evaluate('()=>document.documentElement.scrollWidth <= innerWidth')
            for node in page.locator('.floating-window').all():
                box = node.bounding_box();assert box['x'] >= 0 and box['x'] + box['width'] <= 1024
            page.screenshot(path=str(output / 'gui_tablet.png'))
            page.set_viewport_size({'width': 390, 'height': 844})
            assert page.locator('#sheet.expanded').is_visible()
            page.locator('#sheet-body [data-close]').click()
            page.locator('#fit').click()
            page.locator('#toast').wait_for(state='hidden')
            page.screenshot(path=str(output / 'gui_mobile.png'))
            page.locator('.sheet-tabs [data-open="feed"]').click()
            page.screenshot(path=str(output / 'gui_mobile_feed.png'))
            assert page.evaluate('()=>document.documentElement.scrollWidth <= innerWidth')
            page.locator('#sheet-body [data-close]').click()
            page.locator('.upload-fab').click()
            page.locator('#sheet-body [data-upload-kind="route"]').click()
            assert page.locator('#sheet-body .steps li').count() == 2
            page.screenshot(path=str(output / 'gui_mobile_upload.png'))
            page.keyboard.press('Escape')
            # Synthetic pointer events exercise the same pinch handlers; no API needed.
            page.locator('#map').evaluate('''canvas=>{
              canvas.setPointerCapture=()=>{};
              const fire=(type,id,x,y)=>canvas.dispatchEvent(new PointerEvent(type,{pointerId:id,pointerType:'touch',clientX:x,clientY:y,bubbles:true}));
              fire('pointerdown',1,130,360);fire('pointerdown',2,230,360);
              fire('pointermove',1,90,360);fire('pointermove',2,270,360);
              fire('pointercancel',1,90,360);fire('pointerup',2,270,360);
            }''')
            page.wait_for_timeout(100)
            scale = float(page.locator('#map').get_attribute('data-scale'))
            assert .125 <= scale <= 1
            assert 'dragging' not in page.locator('#map').get_attribute('class')
            assert page.locator('input[type="file"]').count() == 0
            assert page.evaluate('()=>localStorage.length') == 0
            assert page.evaluate('()=>sessionStorage.length') == 0
            for dpr in (2, 3):
                ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=dpr)
                ctx.route('**/*', route)
                pg = ctx.new_page();pg.on('pageerror', lambda error: errors.append(str(error)))
                pg.goto(origin + query + run)
                pg.wait_for_selector('body[data-tiles-ready="true"]')
                assert pg.locator('#map').evaluate('c=>c.width') == 390 * dpr
                pg.screenshot(path=str(output / f'gui_mobile_dpr{dpr}.png'))
                ctx.close()
            page.goto(origin + query + 'invalid')
            page.wait_for_selector('#map-message[data-state="error"]')
            assert page.locator('#zoom-in').is_disabled()
            page.route('**/tiles/3/0/0.png', lambda request: request.fulfill(status=404, body='Missing tile test'))
            page.goto(origin + query + run)
            page.wait_for_selector('#map-message[data-state="error"]')
            assert '타일' in page.locator('#map-message p').inner_text()
            assert not external, external
            assert not mutations, mutations
            assert not errors, errors
            browser.close()
        result={'passed': True, 'run': run, 'output': str(output), 'external_requests': external, 'mutations': mutations, 'browser_errors': errors}
        if projection:sz.qs.write(folder/'browser_qa.json',result)
        print(json.dumps(result))
    finally:
        server.shutdown();server.server_close()
        if fixture_tmp:
            fixture_tmp.cleanup()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run')
    parser.add_argument('--projection',action='store_true')
    args=parser.parse_args();check(args.run,args.projection)
