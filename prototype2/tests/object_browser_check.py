"""Local real-browser object QA. Uses committed assets, never generates images."""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright

P2 = Path(__file__).resolve().parents[1]
OUTPUT = P2 / 'eval/object_pilot/browser_qa'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


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
            def guard(route):
                r = route.request
                if not r.url.startswith(origin + '/'):
                    external.append(r.url); route.abort(); return
                if r.method not in ('GET', 'HEAD'):
                    mutations.append(r.method); route.abort(); return
                route.continue_()
            for label, width, height, dpr in [('desktop', 1440, 900, 1), ('tablet', 1024, 768, 1), ('mobile', 390, 844, 2)]:
                context = browser.new_context(viewport={'width': width, 'height': height}, device_scale_factor=dpr, reduced_motion='reduce')
                context.route('**/*', guard)
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(origin + '/web/pilot/?view=objects')
                page.wait_for_selector('body[data-tiles-ready="true"]')
                page.evaluate('()=>document.fonts.ready')
                assert page.locator('#map').get_attribute('data-object-count') == '18'
                assert not page.locator('#object-card').is_visible()
                assert page.locator('.floating-window').count() == 0
                assert page.evaluate('()=>document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(OUTPUT / f'{label}.png'))
                page.locator('#inspection summary').click()
                for scale in ['0.25', '0.5', '1']:
                    page.locator(f'[data-scale="{scale}"]').click()
                    page.wait_for_function('(s)=>Number(document.querySelector("#map").dataset.scale)===s', arg=float(scale))
                    if label == 'desktop':
                        page.screenshot(path=str(OUTPUT / f'zoom_{int(float(scale)*100)}.png'))
                assert page.locator('#zoom-in').is_disabled()
                page.locator('#debug-zoom').check()
                page.locator('[data-scale="2"]').click()
                page.wait_for_function('()=>document.querySelector("#map").dataset.scale === "2"')
                page.locator('#debug-zoom').uncheck()
                page.wait_for_function('()=>document.querySelector("#map").dataset.scale === "1"')
                page.locator('#object-select').select_option('4485')
                assert page.locator('#object-card').is_visible()
                assert '#4485' in page.locator('#object-card').inner_text()
                page.wait_for_function('()=>document.querySelector("#map").dataset.selected === "4485"')
                def canvas_pixels():
                    return page.locator('#map').evaluate('(c)=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(c.toDataURL()))))')
                def control(selector):
                    if page.locator('#inspection').get_attribute('open') is None:
                        page.locator('#inspection summary').click()
                    page.locator(selector).click()
                before = canvas_pixels()
                control('#object-hide')
                page.wait_for_function('()=>document.querySelector("#object-hide").textContent === "건물 복원"')
                after = canvas_pixels()
                assert before != after, 'Hiding must redraw real objects/ground'
                control('#object-hide')
                restored = canvas_pixels()
                assert restored == before, 'Restore must reproduce the scene'
                if not page.locator('#object-light').is_disabled():
                    control('#object-light')
                    lit = canvas_pixels()
                    assert lit != before, label + ': light mask must change visible windows: ' + str(page.locator('#map').evaluate('(c)=>({...c.dataset})'))
                    page.screenshot(path=str(OUTPUT / f'{label}_lit.png'))
                    control('#object-light')
                    assert canvas_pixels() == before
                    results[label + '_lighting'] = True
                else:
                    results[label + '_lighting'] = False
                assert results[label + '_lighting'], 'Accepted building must have a reviewed window mask'
                if label == 'desktop':
                    samples = []
                    for phase in range(0, 1000, 50):
                        page.locator('#walk-phase').evaluate('(el,v)=>{el.value=String(v)}', phase)
                        page.locator('#walk-phase').dispatch_event('input')
                        page.wait_for_function('(v)=>Math.abs(Number(document.querySelector("#map").dataset.walkerPhase)-v/1000)<.001', arg=phase)
                        samples.append([phase, int(page.locator('#map').get_attribute('data-walker-visible')), int(page.locator('#map').get_attribute('data-walker-occluded'))])
                    assert any(s[1] > 0 for s in samples)
                    assert any(s[2] > 0 for s in samples)
                    results['walker_samples'] = samples
                    page.locator('#object-walk').check()
                    page.wait_for_function('()=>Number(document.querySelector("#map").dataset.walkerPhase)>.95')
                    page.locator('#object-walk').uncheck()
                if page.locator('#inspection').get_attribute('open') is None:
                    page.locator('#inspection summary').click()
                page.locator('#map-mode').select_option('source')
                page.wait_for_function('()=>document.querySelector("#map").dataset.mode === "source"')
                page.locator('#map-mode').select_option('ai')
                page.locator('#object-select').select_option('0')
                page.locator('#inspection summary').click()
                if label == 'desktop':
                    # Real pointer hit test against a visible window on building 4485.
                    state = page.locator('#map').evaluate('(c)=>({scale:Number(c.dataset.scale),center:JSON.parse(c.dataset.center)})')
                    px = width / 2 + (364 * 3 - state['center']['x']) * state['scale']
                    py = height / 2 + (241 * 3 - state['center']['y']) * state['scale']
                    page.mouse.click(px, py)
                    page.wait_for_function('()=>document.querySelector("#map").dataset.selected === "4485"')
                    page.keyboard.press('Escape')
                    page.mouse.move(px, py); page.mouse.down(); page.mouse.move(px - 50, py + 20); page.mouse.up()
                    assert page.locator('#map').get_attribute('data-selected') == '0', 'Dragging must not select a building'
                assert page.evaluate('()=>localStorage.length===0 && sessionStorage.length===0')
                context.close()
            context = browser.new_context()
            context.route('**/*', guard)
            context.route('**/building_4485_depth.png', lambda r: r.fulfill(status=404, body='missing test asset'))
            page = context.new_page(); page.goto(origin + '/web/pilot/?view=objects')
            page.wait_for_selector('#map-message[data-state="error"]')
            assert page.locator('#zoom-in').is_disabled()
            context.close()
            # Magnified selected asset for pixel-level light-mask review, not an image edit.
            page = browser.new_page(viewport={'width': 680, 'height': 1120})
            page.goto(origin + '/assets/object_pilot/building_4485.png')
            page.locator('img').evaluate('(im)=>{im.style.width="620px";im.style.height="1070px";im.style.imageRendering="pixelated";}')
            page.screenshot(path=str(OUTPUT / 'building_4485_magnified.png'))
            browser.close()
        assert not errors, errors
        assert not external, external
        assert not mutations, mutations
        results.update(external_requests=0, mutations=0, browser_errors=errors)
        (OUTPUT / 'report.json').write_text(json.dumps(results, indent=2) + '\n')
        print(json.dumps(results))
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    check()
