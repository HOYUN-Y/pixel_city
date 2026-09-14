"""One aligned VWorld source for the approved 3x3 extension. No AI calls."""
import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import os
import threading
import time
from PIL import Image
import projection_probe as probe
import seam_lab as seam

ROOT = seam.P2 / 'eval/vworld/projection_expand'
SOURCE_RUN = '20260914T091414062775Z'
SIZE = 1920
WIDTH = 2000


def parent():
    folder = probe.resolve(SOURCE_RUN)
    report = probe.vw.read(folder / 'report.json')
    for file, digest in report['files'].items():
        if seam.api.qs.sha(folder / file) != digest:
            raise ValueError('Original projection capture changed')
    mode = report['modes']['orthographic']
    if not probe.check_samples('orthographic', mode['samples'], mode['initial'])['passed']:
        raise ValueError('Parent projection is invalid')
    return mode['samples'][-1]


def capture_page(key, baseline):
    cfg = copy.deepcopy(probe.vw.read(probe.vw.CONFIG))
    cfg['camera'] = probe.CAMERA
    original = probe.vw.page(key, probe.SPEC, cfg)
    start = original.index('      const applyCamera=()=>{')
    end = original.index('    } catch(e){fail(e)}', start)
    script = Path(__file__).with_suffix('.js').read_text()
    return original[:start] + 'const BASE=' + json.dumps(baseline) + ';\n' + script + original[end:]


def check(samples):
    try:
        if len(samples) < 4:
            raise ValueError('Four settled samples required')
        for s in samples:
            if s['viewport'] != [SIZE, SIZE] or s['drawing_buffer'] != [SIZE, SIZE]:
                raise ValueError('Pixel scale changed')
            if not s['orthographic'] or abs(s['width']-WIDTH) > 1e-6:
                raise ValueError('Orthographic width changed')
            m = s['matrix']
            if len(m) != 16 or not all(math.isfinite(v) for v in m) or abs(m[15]-1)>1e-9 or abs(m[11])>1e-9:
                raise ValueError('Invalid parallel projection')
            if any(not math.isfinite(v) or abs(v-96)>1 for v in s['lengths']) or len(s['lengths']) != 3:
                raise ValueError('Depth scale changed')
            if not s['alignment_errors'] or any(not math.isfinite(v) or v>1 for v in s['alignment_errors']):
                raise ValueError('Parent coordinate alignment failed')
            for field, tol in [('position', .01), ('direction', 1e-6), ('up', 1e-6)]:
                if math.dist(s[field], s['expected'][field]) > tol:
                    raise ValueError('Camera moved')
        return {'passed': True, 'max_alignment_error_px': max(max(s['alignment_errors']) for s in samples),
                'reference_100m_raw_px': samples[-1]['lengths'], 'reference_100m_output_px': [v*4/3 for v in samples[-1]['lengths']]}
    except (KeyError, ValueError, TypeError) as e:
        return {'passed': False, 'reason': str(e)}


def capture():
    key = os.environ.get('VWORLD_API_KEY', '').strip()
    if not key:
        raise ValueError('VWORLD_API_KEY is missing')
    baseline = parent()
    content = capture_page(key, baseline).encode()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(content)
        def log_message(self, *_):
            pass
    folder = ROOT / 'captures' / seam.stamp()
    folder.mkdir(parents=True)
    report = {'run_id': folder.name, 'source_run': SOURCE_RUN, 'samples': [], 'ai_requests': 0,
              'source_origin_in_parent': [-480, -416], 'raw_size': SIZE, 'width_m': WIDTH,
              'visual_approved': False, 'key_persisted': False}
    server = ThreadingHTTPServer(('localhost', 8767), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print('CAPTURE='+folder.name, flush=True)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            tab = browser.new_page(viewport={'width': SIZE, 'height': SIZE}, device_scale_factor=1)
            tab.goto('http://localhost:8767/', wait_until='domcontentloaded', timeout=30000)
            tab.wait_for_function('()=>window.__expand?.ready||window.__P2?.error', timeout=90000)
            if tab.evaluate('()=>window.__P2.error'):
                raise ValueError('VWorld initialization failed')
            tab.wait_for_timeout(12000)
            report['warmup_centers']=[[384,384],[1152,384],[1920,384],[384,1152],[384,1920],[1536,1536]]
            for xy in report['warmup_centers']:
                tab.evaluate('xy=>window.__expand.warm(xy)',xy)
                tab.wait_for_timeout(12000)
                print('Warming VWorld building cache (perspective, not an output)',flush=True)
            tab.evaluate('()=>window.__expand.prepare()')
            stable = 0
            deadline = time.monotonic()+90
            while time.monotonic() < deadline:
                tab.wait_for_timeout(2000)
                s = tab.evaluate('()=>window.__expand.measure()')
                report['samples'].append(s)
                stable = stable+1 if s['tiles_loaded'] else 0
                # globe.tilesLoaded does not include VWorld's separate building loader.
                # Give that loader a full minute even when terrain is already ready.
                if len(report['samples']) >= 30 and stable >= 3:
                    break
                if len(report['samples']) % 5 == 0:
                    print('Waiting for aligned source tiles', flush=True)
            report['samples'].append(tab.evaluate('()=>window.__expand.measure()'))
            report['validation'] = check(report['samples'])
            tab.screenshot(path=str(folder/'raw.png'))
            browser.close()
        if report['validation']['passed']:
            Image.open(folder/'raw.png').convert('RGB').resize((2560,2560),Image.Resampling.LANCZOS).save(folder/'input.png')
            Image.open(folder/'input.png').crop((128,128,2432,2432)).save(folder/'source.png')
    except Exception as e:
        report['error'] = probe.vw.redact(str(e), key)
        report['validation'] = {'passed': False, 'reason': 'Capture failed'}
    finally:
        server.shutdown()
        server.server_close()
        report['files'] = {p.name: seam.api.qs.sha(p) for p in folder.glob('*.png')}
        probe.vw.write(folder/'capture.json', probe.vw.secret_safe(report, key))
    print(json.dumps(report['validation']), flush=True)
    return folder


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--allow-external', action='store_true')
    args = p.parse_args()
    if not args.allow_external:
        raise ValueError('Explicit VWorld access required')
    capture()
