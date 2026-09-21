"""Real local browser QA for the appearance-only pilot. No paid calls."""
import functools
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright
from object_browser_check import QuietHandler

P2 = Path(__file__).resolve().parents[1]
OUTPUT = P2 / 'work/object-material-pilot/browser_qa'


def check():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(P2)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    errors, external, mutations = [], [], []
    results = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for label, width, height, dpr in [('desktop',1440,900,1), ('mobile',390,844,2)]:
                context = browser.new_context(viewport={'width':width,'height':height}, device_scale_factor=dpr, reduced_motion='reduce')
                def guard(route):
                    request = route.request
                    if not request.url.startswith(origin + '/'):
                        external.append(request.url); route.abort()
                    elif request.method not in ('GET', 'HEAD'):
                        mutations.append(request.method); route.abort()
                    else:
                        route.continue_()
                context.route('**/*', guard)
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(origin + '/web/pilot/?view=objects-materials')
                page.wait_for_selector('body[data-tiles-ready="true"]')
                page.evaluate('()=>document.fonts.ready')
                assert page.locator('#map').get_attribute('data-object-count') == '18'
                assert not page.locator('#object-walk').is_visible()
                assert page.evaluate('()=>document.documentElement.scrollWidth <= innerWidth')
                assert page.locator('#map-mode option').count() == 3
                def pixels():
                    return page.locator('#map').evaluate('(c)=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(c.toDataURL()))))')
                def inspection():
                    if page.locator('#inspection').get_attribute('open') is None:
                        page.locator('#inspection summary').click()
                def state():
                    return page.locator('#map').evaluate('(c)=>[c.dataset.scale,c.dataset.center]')
                inspection()
                page.locator('[data-scale="1"]').click()
                page.locator('#object-select').select_option('4485')
                original = pixels()
                selected = state()
                images = {}
                for mode in ('source','previous','ai'):
                    page.locator('#map-mode').select_option(mode)
                    images[mode] = pixels()
                    assert state() == selected, 'Mode switch must preserve viewport'
                    assert page.locator('#map').get_attribute('data-selected') == '4485'
                    page.screenshot(path=str(OUTPUT / f'{label}_{mode}.png'))
                assert len(set(images.values())) == 3, 'Three modes must show distinct real images'
                assert original == images['ai']
                page.locator('#object-hide').click()
                hidden = pixels()
                assert hidden != original
                inspection(); page.locator('#object-hide').click()
                assert pixels() == original
                assert page.locator('#object-light').is_disabled()
                inspection()
                page.locator('#object-select').select_option('0')
                for zoom in ('0.25','0.5','1'):
                    page.locator(f'[data-scale="{zoom}"]').click()
                    page.wait_for_function('(s)=>Number(document.querySelector("#map").dataset.scale)===s',arg=float(zoom))
                    pixels()
                    page.screenshot(path=str(OUTPUT / f'{label}_zoom_{zoom}.png'))
                if page.locator('#inspection').get_attribute('open') is not None:
                    page.locator('#inspection summary').click()
                pixels()
                rect = page.locator('#map').bounding_box()
                before = state()
                page.mouse.move(rect['x']+rect['width']*.5, rect['y']+rect['height']*.6)
                page.mouse.down(); page.mouse.move(rect['x']+rect['width']*.5+30, rect['y']+rect['height']*.6+20, steps=4); page.mouse.up()
                pixels()
                assert before != state(), 'Pan must update viewport'
                assert page.locator('#map').get_attribute('data-selected') == '0', 'Drag must not select'
                page.locator('#fit').click(); pixels()
                page.screenshot(path=str(OUTPUT / f'{label}_overview.png'))
                results[label] = {'objects':18, 'modes':3, 'viewport_preserved':True, 'hide_restore':True, 'pan':True, 'zoom':True}
                # Self-contained review index and all 18 comparisons load locally.
                page.goto(origin + '/assets/object_material_pilot/index.html')
                assert page.locator('article').count() == 18
                page.wait_for_function('()=>[...document.images].every(i=>i.complete&&i.naturalWidth>0)')
                context.close()
            browser.close()
        assert not errors, errors
        assert not external, external
        assert not mutations, mutations
        results.update(js_errors=errors, external_requests=len(external), paid_calls=0, passed=True)
        (OUTPUT / 'report.json').write_text(json.dumps(results, indent=2)+'\n')
        print(json.dumps(results, indent=2))
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    check()
