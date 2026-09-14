"""Bounded context-connected image trials. Every paid intent is persisted, never retried."""
import argparse
import base64
import copy
import fcntl
import html
import io
import json
import os
import re
from pathlib import Path
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
from PIL import Image, ImageDraw
import openrouter_style as api
import seam_zoom as legacy
import vworld_pipeline as vw

P2 = api.qs.P2
ROOT = P2 / 'eval/vworld/seam_lab'
CONFIG = P2 / 'configs/seam_lab.json'
OFFSETS = [(0, 0), (768, 0), (0, 768), (768, 768)]
LIMITS = {'downtown': 4, 'downtown_repair': 2, 'namsan': 4, 'namsan_repair': 1, 'character': 1}


def stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def load_run(name):
    if not name or not re.fullmatch(r'\d{8}T\d{12}Z', name):
        raise ValueError('Invalid run ID')
    folder = ROOT / 'runs' / name
    return folder, api.qs.read(folder / 'report.json')


def capture_namsan():
    """New capture only: does not overwrite old VWorld sources/configuration."""
    key = os.environ.get('VWORLD_API_KEY', '').strip()
    if not key:
        raise ValueError('VWORLD_API_KEY is not set')
    cfg = copy.deepcopy(vw.read(vw.CONFIG))
    cfg['camera'] = {'heading_deg': 22.5, 'pitch_deg': -30, 'range_m': 1800}
    spec = {'id': 'namsan_tower', 'lon': 126.98808, 'lat': 37.55112,
            'size': 1536, 'meters_per_pixel': 1600 / 1536}
    page = vw.page(key, spec, cfg).replace(
        'const target=C.Cartesian3.fromDegrees(SPEC.lon,SPEC.lat,0);',
        '''const h=viewer.scene.globe.getHeight(C.Cartographic.fromDegrees(SPEC.lon,SPEC.lat));
        window.__P2.terrainHeight=Number.isFinite(h)?h:null;
        const target=C.Cartesian3.fromDegrees(SPEC.lon,SPEC.lat,(Number.isFinite(h)?h:270)+80);''')
    page = page.replace('window.__P2.tilesLoaded=Boolean', 'applyCamera(); window.__P2.tilesLoaded=Boolean')
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(page.encode())
        def log_message(self, *_):
            pass
    folder = P2 / 'work/vworld/seam_lab' / stamp()
    folder.mkdir(parents=True)
    server = ThreadingHTTPServer(('localhost', 8767), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            tab = browser.new_page(viewport={'width': 1536, 'height': 1536}, device_scale_factor=1)
            tab.goto('http://localhost:8767/', wait_until='domcontentloaded')
            tab.wait_for_function('window.__P2 && (window.__P2.ready || window.__P2.error)', timeout=90000)
            tab.wait_for_timeout(10000)
            state = tab.evaluate('window.__P2')
            if state.get('error'):
                raise ValueError('VWorld capture failed; no source approved')
            tab.screenshot(path=str(folder / 'source.png'))
            # Same camera: detail is a source crop, never a different scene angle.
            browser.close()
        report = {'source': 'VWorld WebGL 3D', 'spec': spec, 'camera': cfg['camera'],
                  'terrain_height_m': state.get('terrainHeight'), 'tiles_loaded': state.get('tilesLoaded'),
                  'projection': state.get('projectionMode'), 'sha256': api.qs.sha(folder / 'source.png'),
                  'approved': False, 'key_persisted': False}
        api.qs.write(folder / 'capture.json', report)
        print(f'CAPTURE={folder}', flush=True)
    finally:
        server.shutdown(); server.server_close()


def init():
    cfg = api.qs.read(CONFIG)
    source, _, style = api.qs.inputs(api.qs.configuration('q8'))
    folder = ROOT / 'runs' / stamp(); folder.mkdir(parents=True)
    source.save(folder / 'downtown_input.png'); style.save(folder / 'style.png')
    namsan = cfg.get('namsan_capture')
    scenes = ['downtown']
    if namsan:
        capture = P2 / namsan; meta = api.qs.read(capture / 'capture.json')
        if not cfg.get('namsan_visual_approved') or cfg.get('namsan_source_sha256') != meta['sha256'] or meta['sha256'] != api.qs.sha(capture / 'source.png'):
            raise ValueError('Namsan source has not been visually approved')
        Image.open(capture / 'source.png').save(folder / 'namsan_input.png')
        scenes.append('namsan')
    report = {'run_id': folder.name, 'status': 'prepared', 'model': api.MODEL, 'limits': LIMITS,
              'request_limit': 12, 'requests': [], 'scenes': scenes, 'config': cfg,
              'source_hashes': {s: api.qs.sha(folder / f'{s}_input.png') for s in scenes},
              'style_sha256': api.qs.sha(folder / 'style.png'), 'user_visual_approval': False}
    api.qs.write(folder / 'report.json', report)
    print(f'RUN={folder.name}', flush=True)
    return folder


def paid(folder, report, key, group, name, prompt, references, transparent=False, limits=None):
    limits = LIMITS if limits is None else limits
    requests = report['requests']
    if len(requests) >= sum(limits.values()) or sum(r['group'] == group for r in requests) >= limits[group]:
        raise ValueError('Approved request budget exhausted')
    if any(r['name'] == name for r in requests):
        raise ValueError('Already attempted; never retry')
    if any(r['status'] != 'complete' for r in requests):
        raise ValueError('Previous request failed or billing is unresolved')
    for i, im in enumerate(references):
        im.save(folder / f'{name}_ref{i}.png')
    options = {'model': api.MODEL, 'n': 1, 'quality': 'high', 'aspect_ratio': '1:1',
               'background': 'transparent' if transparent else 'opaque',
               'provider': {'only': ['openai'], 'allow_fallbacks': False}}
    entry = {'group': group, 'name': name, 'status': 'requesting', 'prompt': prompt, 'options': options,
             'reference_sha256': [api.qs.sha(folder / f'{name}_ref{i}.png') for i in range(len(references))]}
    requests.append(entry); api.qs.write(folder / 'report.json', report)
    started = time.monotonic()
    try:
        result = api.request_json('/images', key, {**options, 'prompt': prompt,
                                  'input_references': [api.reference(im) for im in references]})
        entry['usage'] = result.get('usage'); entry['seconds'] = round(time.monotonic() - started, 3)
        entries = result.get('data', [])
        if len(entries) != 1:
            raise ValueError('Expected exactly one output')
        blob = base64.b64decode(entries[0]['b64_json'], validate=True)
        (folder / f'{name}_raw.png').write_bytes(blob)
        raw = Image.open(io.BytesIO(blob)); raw.load()
        entry['raw_storage'] = 'original_response_bytes'
        entry['raw_sha256'] = api.qs.sha(folder / f'{name}_raw.png'); entry['native_size'] = list(raw.size)
        if raw.size != (1024, 1024):
            raise ValueError('Native size mismatch; original retained')
        if transparent and ('A' not in raw.getbands() or raw.getchannel('A').getextrema()[0] == 255):
            raise ValueError('Real alpha missing; original retained')
        entry['status'] = 'complete'
        print(json.dumps({'asset': name, 'requests': len(requests), 'seconds': entry['seconds'], 'usage': entry['usage']}), flush=True)
        return raw
    except (Exception, KeyboardInterrupt):
        entry['status'] = 'failed'; report['status'] = 'failed'
        raise RuntimeError('Request/output failed. No retry. Original retained; verify billing before continuing.') from None
    finally:
        costs = [(r.get('usage') or {}).get('cost') for r in requests]
        report['total_cost_usd'] = sum(costs) if all(isinstance(c, (int, float)) for c in costs) else None
        api.qs.write(folder / 'report.json', report)


def context_tile(source, canvas, known, index):
    x, y = OFFSETS[index]
    crop = source.crop(legacy.CROPS[index]).resize((1024, 1024), Image.Resampling.LANCZOS)
    mask = known.crop((x, y, x + 1024, y + 1024))
    mixed = Image.composite(canvas.crop((x, y, x + 1024, y + 1024)), crop, mask)
    return crop, mixed, mask


def commit_tile(canvas, known, image, index):
    x, y = OFFSETS[index]
    box = (x, y, x + 1024, y + 1024)
    locked = Image.composite(canvas.crop(box), image.convert('RGB'), known.crop(box))
    canvas.paste(locked, (x, y)); known.paste(255, box)
    return locked


def generate_scene(folder, report, key, scene):
    if scene not in report['scenes']:
        raise ValueError('Unapproved scene')
    if any(r['group'] == scene for r in report['requests']):
        raise ValueError('Scene was already attempted')
    source = Image.open(folder / f'{scene}_input.png').convert('RGB')
    if api.qs.sha(folder / f'{scene}_input.png') != report['source_hashes'][scene]:
        raise ValueError('Source hash changed')
    style = Image.open(folder / 'style.png').convert('RGB')
    canvas = Image.new('RGB', (1792, 1792)); known = Image.new('L', canvas.size)
    for i in range(4):
        crop, mixed, mask = context_tile(source, canvas, known, i)
        prompt = ('Use case: style-transfer / contextual continuation. Image 1 is the exact scene and geometry. '
                  'Image 2 is ONLY pixel-art style, never layout or an object source. Image 3 is this exact scene '
                  'with already approved pixel art pasted at its correct coordinates. Image 4 is a context mask: '
                  'WHITE pixels mark completed art to preserve exactly; BLACK pixels are the region to redraw. '
                  'Produce ONE continuous pixel-art city scene, seamlessly continuing roads, walls, roof edges, '
                  'tree crowns and palette from the completed art. Preserve camera, crop, building count, silhouettes '
                  'and positions from Image 1. Crisp pixel clusters, warm paving, fresh greens, clear cool roofs. '
                  'No split panels, no masks in output, no text, no added buildings, no farmland from style reference. ')
        refs = [crop, style, mixed, mask.convert('RGB')]
        if scene == 'namsan':
            tower = source.crop(report['config']['tower_reference_box'])
            refs.append(tower)
            prompt += ('This is mountainous Namsan, Seoul: keep the actual slopes, ridgelines, summit elevation, '
                       'winding paths and forest layering, never flatten the hill. Image 5 is a close crop of the '
                       'same source showing N Seoul Tower: preserve its slender shaft, broad observation deck, '
                       'antenna and base IF present in Image 1. Never duplicate it or add it to other quadrants. ')
        raw = paid(folder, report, key, scene, f'{scene}_{i}', prompt, refs)
        commit_tile(canvas, known, raw, i).save(folder / f'{scene}_{i}_locked.png')
    canvas.crop((128, 128, 1664, 1664)).save(folder / f'{scene}_context.png')
    source.crop((192, 256, 1344, 1408)).resize((1536, 1536), Image.Resampling.LANCZOS).save(folder / f'{scene}_source.png')
    report.setdefault('scene_results', {})[scene] = {'context': f'{scene}_context.png', 'status': 'awaiting_review',
        'nominal_seams': [768, 768], 'generation_frontiers': [896, 896], 'known_pixels_preserved': True}
    api.qs.write(folder / 'report.json', report)


def repair(folder, report, key, scene, number):
    spec = report['config']['repairs'][scene][number]
    name = f'{scene}_repair{number}'
    # Repairs are independent candidates; offline review decides which patches to retain.
    base = Image.open(folder / f'{scene}_context.png').convert('RGB')
    box, edit = spec['context_box'], spec['edit_box']
    target = base.crop(box)
    mask = Image.new('L', (1024, 1024)); ImageDraw.Draw(mask).rectangle(
        [edit[0]-box[0], edit[1]-box[1], edit[2]-box[0]-1, edit[3]-box[1]-1], fill=255)
    source = Image.open(folder / f'{scene}_source.png').crop(box)
    prompt = ('Use case: precise-object-edit. Image 1 is the pixel-art scene to repair. Image 2 is the exact '
              'original geometry. Image 3 is an EDIT GUIDE, not art: WHITE is the only repair region; keep BLACK '
              'regions unchanged. Connect broken roof edges, roads, walls and foliage across generation seams. '
              'Keep camera, scale, terrain and existing style unchanged. No new buildings, no labels, no blur. '
              + spec['instruction'])
    refs = [target, source, mask.convert('RGB')]
    if scene == 'namsan':
        refs.append(Image.open(folder / 'namsan_input.png').crop(report['config']['tower_reference_box']))
        prompt += ' Image 4 is the source tower detail: match its observation deck, narrow shaft and antenna.'
    raw = paid(folder, report, key, scene + '_repair', name, prompt, refs)
    patched = base.copy(); patched.paste(raw.convert('RGB'), box[:2], mask)
    patched.save(folder / f'{name}_candidate.png'); mask.save(folder / f'{name}_mask.png')
    report.setdefault('repair_results', {})[name] = {**spec, 'candidate': f'{name}_candidate.png',
                                                   'accepted': False, 'reason': 'awaiting_visual_review'}
    api.qs.write(folder / 'report.json', report)


def character(folder, report, key):
    prompt = ('Use case: stylized-concept. One original full-body tiny pixel-art city traveler, three-quarter '
              'view from above matching a 30-degree tilted city map, facing lower right. Teal jacket, small warm '
              'orange backpack, dark trousers, clear two feet, friendly simple silhouette. Crisp 32-pixel game '
              'sprite design enlarged with nearest-neighbor, limited palette. Exactly one character centered '
              'with padding, no sheet, no text, no floor, no scenery or cast shadow. Genuinely transparent background. '
              'Reference is ONLY palette and pixel treatment; do not copy any existing character.')
    raw = paid(folder, report, key, 'character', 'traveler', prompt,
               [Image.open(folder / 'style.png')], transparent=True).convert('RGBA')
    pack_character(raw, folder / 'traveler.png')


def pack_character(raw, destination):
    bbox = raw.getchannel('A').point(lambda a: 255 if a >= 128 else 0).getbbox()
    if not bbox:
        raise ValueError('Empty character')
    sprite = raw.crop(bbox); sprite.thumbnail((32, 40), Image.Resampling.BOX)
    sprite.putalpha(sprite.getchannel('A').point(lambda a: 255 if a >= 128 else 0))
    sprite.save(destination)


def publish(folder, report):
    """Offline publication; review is explicit, never auto-accept a paid response."""
    review = api.qs.read(P2 / 'configs/seam_lab_review.json')
    if review['run_id'] != folder.name:
        raise ValueError('Review belongs to another run')
    if any(r['status'] != 'complete' for r in report['requests']):
        raise ValueError('Incomplete request ledger')
    if not (folder / 'traveler.png').is_file():
        raise ValueError('No verified character')
    pack_character(Image.open(folder / 'traveler_raw.png').convert('RGBA'), folder / 'traveler.png')
    manifest = {'version': 1, 'run_id': folder.name, 'character': 'traveler.png', 'scenes': {},
                'user_visual_approval': False, 'note': 'Local image coordinates; hand-authored routes and occlusion, not navigation.'}
    cards = []
    for scene in report['scenes']:
        data = review['scenes'][scene]
        original = Image.open(folder / f'{scene}_context.png').convert('RGB'); final = original.copy()
        for number in data['accepted_repairs']:
            name = f'{scene}_repair{number}'; spec = report['repair_results'][name]
            candidate = Image.open(folder / spec['candidate']).convert('RGB'); edit = spec['edit_box']
            final.paste(candidate.crop(edit), edit[:2]); spec['accepted'] = True; spec['reason'] = data['review']
        final.save(folder / f'{scene}_final.png')
        labels = [('source', 'VWorld 원본'), ('context', '문맥 연결 · 보정 전'), ('final', '최종 시험 후보')]
        variants = {}
        if scene == 'downtown':
            old = legacy.ROOT / report['config']['baseline_run'] / 'mosaic.png'
            Image.open(old).save(folder / 'downtown_baseline.png'); labels.insert(1, ('baseline', '기존 독립 생성 2×2'))
        for key, label in labels:
            file = f'{scene}_{key}.png'; variants[key] = {'label': label, 'file': file, 'sha256': api.qs.sha(folder / file)}
            cards.append(f'<figure><figcaption>{html.escape(data["label"])} · {label}</figcaption><a href="{file}"><img src="{file}"></a></figure>')
        for name, spec in report.get('repair_results', {}).items():
            if name.startswith(scene+'_'):
                label = '적용' if spec['accepted'] else '미채택'
                cards.append(f'<figure><figcaption>{name} · {label}</figcaption><a href="{spec["candidate"]}"><img src="{spec["candidate"]}"></a></figure>')
        overlay = {**data['overlay'], 'image_sha256': variants['final']['sha256']}
        api.qs.write(folder / f'{scene}_overlay.json', overlay)
        manifest['scenes'][scene] = {'label': data['label'], 'variants': variants,
            'overlay': f'{scene}_overlay.json', 'review': data['review']}
        # Keep a standard display pyramid for later expansion and validate it independently.
        legacy.pyramid(final, folder / f'{scene}_tiles')
    manifest['asset_sha256'] = {p.name: api.qs.sha(p) for p in folder.glob('*.png')}
    report['status'] = 'awaiting_user_review'; report['review'] = review
    report['raw_storage_note'] = 'First 8 opaque map outputs retain decoded RGB pixels as PNG; repair/character outputs retain original response bytes. Runtime character alpha is thresholded; original alpha is retained.'
    api.qs.write(folder / 'manifest.json', manifest); api.qs.write(folder / 'report.json', report)
    links = ' · '.join(f'<a href="/web/pilot/?view=seam-lab&run={folder.name}&scene={s}">{html.escape(d["label"])} 지도</a>' for s,d in manifest['scenes'].items())
    notes = ''.join(f'<p>{html.escape(d["label"])}: {html.escape(d["review"])}</p>' for d in manifest['scenes'].values())
    page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>연결·남산·캐릭터 비교</title><style>body{{background:#FBF3E4;color:#3A2A1E;font:16px system-ui;margin:24px}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}}figure{{margin:12px}}img{{width:100%;image-rendering:pixelated}}a{{color:#9B491F}}figcaption{{padding:8px 0}}</style>
<h1>2×2 연결·남산·캐릭터 시험</h1><p>{links}</p><p>국토교통부 / VWorld · AI 재해석 · 실측 정합 미검증 · 미감 승인 대기</p>
<p>유료 요청 {len(report['requests'])}/12 · 실제 비용 ${report.get('total_cost_usd')} · <a href="report.json">입력·프롬프트·비용·검수 기록</a></p>{notes}
<main>{''.join(cards)}<figure><figcaption>공유 AI 캐릭터 · 투명 배경</figcaption><img src="traveler.png" style="width:160px"></figure></main></html>'''
    (folder / 'index.html').write_text(page, encoding='utf-8')
    api.qs.write(ROOT / 'current.json', {'run_id': folder.name})
    print(f'GUI=http://127.0.0.1:8766/web/pilot/?view=seam-lab&run={folder.name}', flush=True)


def verify(folder, report):
    """Verify actual saved outputs without network; metrics are diagnostics, not aesthetic scores."""
    if len(report['requests']) > 12:
        raise ValueError('Request budget exceeded')
    for group, limit in LIMITS.items():
        if sum(r['group'] == group for r in report['requests']) > limit:
            raise ValueError('Group request budget exceeded')
    for r in report['requests']:
        if r['status'] != 'complete' or api.qs.sha(folder / f'{r["name"]}_raw.png') != r['raw_sha256']:
            raise ValueError('Incomplete or changed raw output')
    result = {'request_count': len(report['requests']), 'total_cost_usd': report['total_cost_usd'],
              'request_seconds': round(sum(r['seconds'] for r in report['requests']), 3), 'scenes': {},
              'note': 'Edge RGB differences are diagnostics only; not a building/terrain continuity pass.'}
    for scene in report['scenes']:
        canvas = Image.new('RGB', (1792, 1792)); known = Image.new('L', canvas.size)
        for i in range(4):
            before = canvas.copy(); previous = known.copy()
            commit_tile(canvas, known, Image.open(folder / f'{scene}_{i}_raw.png'), i)
            if Image.composite(canvas, before, previous).tobytes() != before.tobytes():
                raise ValueError('Known pixels changed')
        context = Image.open(folder / f'{scene}_context.png').convert('RGB')
        if context.tobytes() != canvas.crop((128, 128, 1664, 1664)).tobytes():
            raise ValueError('Context mosaic differs from raw reconstruction')
        final = Image.open(folder / f'{scene}_final.png').convert('RGB')
        union = Image.new('L', final.size)
        for number in report['review']['scenes'][scene]['accepted_repairs']:
            name = f'{scene}_repair{number}'; x,y,r,b = report['repair_results'][name]['edit_box']
            ImageDraw.Draw(union).rectangle((x,y,r-1,b-1),fill=255)
        if Image.composite(context, final, union).tobytes() != context.tobytes():
            raise ValueError('Repair altered protected pixels')
        metrics = {}
        for variant in ['context','final'] + (['baseline'] if scene == 'downtown' else []):
            a = np.asarray(Image.open(folder / f'{scene}_{variant}.png').convert('RGB'),dtype=float)
            metrics[variant] = {str(k): {'vertical': round(float(np.abs(a[:,k]-a[:,k-1]).mean()),3),
                                        'horizontal': round(float(np.abs(a[k]-a[k-1]).mean()),3)} for k in [768,896]}
        result['scenes'][scene] = {'known_pixels_preserved': True, 'protected_patch_pixels_preserved': True, 'edges': metrics}
    manifest = api.qs.read(folder / 'manifest.json')
    for file, expected in manifest['asset_sha256'].items():
        if api.qs.sha(folder / file) != expected:
            raise ValueError('Asset hash mismatch: '+file)
    api.qs.write(folder / 'verification.json', result)
    print(json.dumps(result), flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['capture', 'init', 'scene', 'repair', 'character', 'publish', 'verify'])
    p.add_argument('--run'); p.add_argument('--scene', choices=['downtown', 'namsan'])
    p.add_argument('--number', type=int, default=0); p.add_argument('--allow-external', action='store_true')
    a = p.parse_args()
    if a.command == 'init':
        init(); return
    if a.command == 'publish':
        folder, report = load_run(a.run); publish(folder, report); return
    if a.command == 'verify':
        folder, report = load_run(a.run); verify(folder, report); return
    if not a.allow_external:
        raise ValueError('--allow-external required')
    if a.command == 'capture':
        capture_namsan(); return
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not key:
        raise ValueError('OPENROUTER_API_KEY is not set')
    folder, report = load_run(a.run)
    lock = (folder / '.generation.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    report = api.qs.read(folder / 'report.json')
    if api.qs.sha(folder / 'style.png') != report['style_sha256']:
        raise ValueError('Style hash changed')
    capability = api.validate_capabilities(api.request_json(f'/images/models/{api.MODEL}/endpoints', key))
    if capability['supported_parameters'].get('input_references', {}).get('max', 0) < 5:
        raise ValueError('Five references unsupported')
    if 'transparent' not in capability['supported_parameters'].get('background', {}).get('values', []):
        raise ValueError('Transparent background unsupported')
    report['capability'] = capability
    if a.command == 'scene': generate_scene(folder, report, key, a.scene)
    elif a.command == 'repair': repair(folder, report, key, a.scene, a.number)
    else: character(folder, report, key)


if __name__ == '__main__':
    main()
