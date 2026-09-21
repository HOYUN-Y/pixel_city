"""18-building material pilot. Geometry is rendered, never generated.

generate is the only network operation (six distinct images, $2 separate cap).
build is offline; it never replaces the original object pilot.
"""
import argparse
import base64
import copy
import fcntl
import math
import os
from pathlib import Path
import shutil
import time

import numpy as np
from PIL import Image, ImageDraw

import object_pilot as op

ROOT = op.P2 / 'work/object-material-pilot'
OLD = op.P2 / 'assets/object_pilot'
DEST = op.P2 / 'assets/object_material_pilot'
TYPES = ('wood', 'masonry', 'modern')
JOBS = tuple(f'{kind}_{surface}' for kind in TYPES for surface in ('wall', 'roof'))
LIMIT = 2.0
RESERVE = .75
EXPECTED_PRICES = {'input_image': .000008, 'input_text': .000005, 'output_image': .00003}


def archetype(building):
    return 'wood' if building['kind'] else ('modern' if building['height'] >= 30 else 'masonry')


def prompt(name):
    kind, surface = name.split('_')
    material = {
        'wood_wall': 'warm Korean timber frame, cream plaster, ONE centered dark teal wooden lattice window',
        'wood_roof': 'blue-gray Korean ceramic roof tiles, subtle warm highlights and cool crevices',
        'masonry_wall': 'warm ochre masonry, ONE centered blue-gray double window with cream sill and lintel',
        'masonry_roof': 'muted warm gray flat-roof stone or concrete slabs with sparse joints',
        'modern_wall': 'cool blue glass, ONE centered large window panel, slim cream structural mullions',
        'modern_roof': 'quiet blue-gray flat-roof membrane panels, sparse seams, no equipment',
    }[name]
    return (
        'Use case: stylized-concept. Asset type: repeatable pixel-art building material, NOT a building sprite. '
        'Image 1 is ONLY an art-style reference: use its deliberate pixel clusters, warm highlights, rich but controlled '
        'palette and crisp readable game details; do not copy its farm layout, buildings or characters. '
        f'Create {material}. '
        + ('A single square facade bay seen exactly front-on, representing one story. Keep the window entirely '
           'inside the central 60% with plain matching material along all four edges. No door, cornice, roof or ground. '
           if surface == 'wall' else
           'An edge-to-edge square roof material swatch seen exactly top-down. Opposite edges must repeat. '
           'No building outline, roof outline, facade, ridge silhouette or surrounding ground. ')
        + 'Opaque material fills the entire image. Flat orthographic surface; no perspective, no isometric view, '
        'no depth foreshortening, no cast shadows or lighting gradient. Design readable when reduced to 32 by 32 pixels. '
        'No text, logos, labels, borders, collage, sky, vegetation, people, vehicles or extra objects.'
    )


def validate_price(capability):
    prices = {p['billable']: p['cost_usd'] for p in capability.get('pricing', [])}
    if prices != EXPECTED_PRICES:
        raise ValueError('Pricing changed or missing; no paid request')
    if 'opaque' not in capability['supported_parameters'].get('background', {}).get('values', []):
        raise ValueError('Opaque background unavailable')
    return prices


def generate(allow_external=False):
    if not allow_external:
        raise ValueError('Generation requires --allow-external')
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not key:
        raise ValueError('OPENROUTER_API_KEY not set')
    cfg, _, _, _ = op.inputs()
    style = op.P2 / cfg['style_reference']
    if op.sha(style) != cfg['style_sha256']:
        raise ValueError('Style reference changed')
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'generation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (ROOT / 'generation.json').exists():
            raise ValueError('This six-call experiment was already started; no automatic retry or new batch')
        cap = op.api.validate_capabilities(op.api.request_json(f'/images/models/{op.api.MODEL}/endpoints', key))
        prices = validate_price(cap)
        with Image.open(style) as source:
            source.load()
            if max(source.size) > 1024:
                raise ValueError('Reference exceeds reserved input size')
            ref = op.api.reference(source)
        shutil.copyfile(style, ROOT / 'style_input.png')
        report = {'status': 'generating', 'model': op.api.MODEL, 'provider': 'openai',
                  'limit_usd': LIMIT, 'max_calls': 6, 'style_sha256': op.sha(style),
                  'snapshot_sha256': op.sha(op.geo.DATA / 'snapshot.json'), 'capability': cap,
                  'total_cost_usd': 0, 'requests_started': 0, 'assets': [],
                  'reservation_basis': {'prices': prices, 'per_call_usd': RESERVE,
                      'max_output_image_tokens': math.ceil(48 * 48 * (2000000 + 4096 * 4096) / 4000000),
                      'max_input_image_tokens': 16384, 'max_input_text_tokens': 4096,
                      'note': 'Conservative reservation; one <=1024 reference, <=4096-byte prompt; no retries'},
                  'user_visual_approval': False}
        op.write(ROOT / 'generation.json', report)
        try:
            for name in JOBS:
                spent = report['total_cost_usd']
                if spent is None or spent + RESERVE > LIMIT or report['requests_started'] >= 6:
                    raise ValueError('Insufficient budget or unsettled billing')
                text = prompt(name)
                if len(text.encode()) > 4096:
                    raise ValueError('Prompt exceeds reservation')
                item = {'name': name, 'prompt': text, 'status': 'reserved', 'reservation_usd': RESERVE,
                        'reference_sha256': op.sha(ROOT / 'style_input.png')}
                report['assets'].append(item)
                report['requests_started'] += 1
                report['reserved_unknown_usd'] = RESERVE
                op.write(ROOT / 'generation.json', report)
                start = time.monotonic()
                result = op.api.request_json('/images', key, {
                    'model': op.api.MODEL, 'prompt': text, 'quality': 'high', 'aspect_ratio': '1:1',
                    'background': 'opaque', 'n': 1, 'input_references': [ref],
                    'provider': {'only': ['openai'], 'allow_fallbacks': False}})
                item['seconds'] = round(time.monotonic() - start, 3)
                item['generation_id'] = op.api.safe_generation_id(result.get('id'))
                cost = (result.get('usage') or {}).get('cost')
                item['cost_usd'] = cost
                valid_cost = isinstance(cost, (int, float)) and not isinstance(cost, bool) and math.isfinite(cost) and 0 <= cost <= RESERVE
                report['total_cost_usd'] = round(spent + cost, 8) if valid_cost else None
                report['reserved_unknown_usd'] = 0 if valid_cost else RESERVE
                if len(result.get('data', [])) == 1:
                    path = ROOT / f'{name}_raw.png'
                    path.write_bytes(base64.b64decode(result['data'][0]['b64_json'], validate=True))
                    item.update(raw=path.name, sha256=op.sha(path))
                op.write(ROOT / 'generation.json', report)
                if not valid_cost:
                    raise ValueError('Unknown billing or reservation exceeded; halt')
                image = op.decode_asset(result, False)
                if not np.all(np.asarray(image)[..., 3] == 255):
                    raise ValueError('Opaque material required')
                item.update(status='generated', size=list(image.size))
                op.write(ROOT / 'generation.json', report)
                print(f'{name}: complete, cost ${cost:.6f}, {item["seconds"]}s', flush=True)
            report['status'] = 'awaiting_user_review'
        except (Exception, KeyboardInterrupt) as exc:
            report['status'] = 'failed'
            report['error'] = {'type': type(exc).__name__, 'http_status': getattr(exc, 'http_status', None),
                               'message': 'Stopped without retry. Inspect retained output and billing.'}
            op.write(ROOT / 'generation.json', report)
            raise RuntimeError(report['error']['message']) from None
        op.write(ROOT / 'generation.json', report)
        return report


def paint_face(face, cam, x, y, tiles, kind):
    """Face-local metre coordinates, not a stretched screen-space decal."""
    vertices = np.asarray(face['points'], dtype=float)
    screen = np.array([op.project(p, cam) for p in vertices])
    matrix = np.column_stack((screen, np.ones(len(screen))))
    coef = np.linalg.lstsq(matrix, vertices, rcond=None)[0]
    world = np.stack((x, y, np.ones_like(x)), -1) @ coef
    roof = face['surface'] == 1
    tile = tiles[f'{kind}_{"roof" if roof else "wall"}']
    if roof:
        u, v = world[..., 0] / 4, world[..., 1] / 4
        active = np.ones(x.shape, dtype=bool)
    else:
        delta = vertices[1, :2] - vertices[0, :2]
        length = np.linalg.norm(delta)
        along = (world[..., :2] - vertices[0, :2]) @ (delta / length)
        high, low = vertices[:, 2].max(), vertices[:, 2].min()
        bay = 2.5 if kind == 'wood' else 3.0
        count = math.floor((length + 1e-8) / bay)
        margin = (length - count * bay) / 2
        stories = math.floor((high - low + 1e-8) / bay)
        u, v = (along - margin) / bay, (world[..., 2] - low) / bay
        active = (u >= 0) & (u < count) & (v >= 0) & (v < stories)
        v = -v  # Image rows run downward; buildings rise upward.
    height, width = tile.shape[:2]
    tx = np.floor((u % 1) * width).astype(int) % width
    ty = np.floor((v % 1) * height).astype(int) % height
    rgb = tile[ty, tx].astype(float)
    if not roof:
        # Incomplete bays get plain edge material, never half a stretched window.
        edge = np.concatenate((tile[0], tile[-1], tile[:, 0], tile[:, -1]))
        rgb[~active] = np.median(edge, axis=0)
    shade = 1.0 if roof else (.95 if face['surface'] == 2 else .72)
    return np.clip(np.rint(rgb * shade), 0, 255).astype(np.uint8)


def composite(manifest, directory, field):
    pixels = np.asarray(Image.open(directory / manifest['ground']).convert('RGBA')).copy()
    depth = np.zeros(pixels.shape[:2], dtype=np.uint32)
    def codes(file):
        z = np.asarray(Image.open(directory / file).convert('RGB')).astype(np.uint32)
        return z[..., 0] * 65536 + z[..., 1] * 256 + z[..., 2]
    depth[:] = codes(manifest['ground_depth'])
    ids = np.zeros(depth.shape, dtype=np.uint32)
    for b in manifest['objects']:
        a = np.asarray(Image.open(directory / b[field]).convert('RGBA'))
        z = codes(b['depth'])
        x, y = b['xy']; w, h = b['size']
        zd, owner = depth[y:y+h, x:x+w], ids[y:y+h, x:x+w]
        take = (a[..., 3] >= 128) & ((z > zd) | ((z == zd) & ((owner == 0) | (b['id'] < owner))))
        pixels[y:y+h, x:x+w][take] = a[take]
        zd[take], owner[take] = z[take], b['id']
    return Image.fromarray(pixels)


def build(run=ROOT, destination=DEST):
    run, dest = Path(run), Path(destination)
    report = op.read(run / 'generation.json')
    if report['status'] != 'awaiting_user_review' or [a['name'] for a in report['assets']] != list(JOBS):
        raise ValueError('Six completed materials required')
    cfg, city, _, _ = op.inputs()
    old = op.read(OLD / 'manifest.json')
    if report['snapshot_sha256'] != old['snapshot_sha256'] or old['snapshot_sha256'] != op.sha(op.geo.DATA / 'snapshot.json'):
        raise ValueError('Frozen snapshot mismatch')
    for file, digest in old['asset_sha256'].items():
        if op.sha(OLD / file) != digest:
            raise ValueError('Original pilot asset changed: ' + file)
    if dest.resolve() == OLD.resolve() or dest.exists():
        raise ValueError('Destination must be new; preserve prior candidates')
    tiles = {}
    for item in report['assets']:
        path = run / item['raw']
        if item['status'] != 'generated' or op.sha(path) != item['sha256']:
            raise ValueError('Unverified generated material')
        tiles[item['name']] = np.asarray(Image.open(path).convert('RGB').resize((32, 32), Image.Resampling.BOX))
    dest.mkdir(parents=True)
    manifest = copy.deepcopy(old)
    manifest.update(run_id='object-material-pilot', appearance_mode='face_materials',
                    user_visual_approval=False, ground_base=old['ground'], preview='preview.png',
                    ai_building_ids=cfg['building_ids'], materials=[], generation={
                        'model': report['model'], 'requests_started': report['requests_started'],
                        'total_cost_usd': report['total_cost_usd']},
                    review_summary='18동 면별 AI 재료 · 기하 고정 · 미감 미승인 · 이전 AI 채택은 1동',
                    attribution=old['attribution'] + ' · 외관 시험: 평면 지형·추정 양식·층간격')
    for file in {old['ground'], old['ground_depth']}:
        shutil.copyfile(OLD / file, dest / file)
    checks = []
    for b in manifest['objects']:
        shape = op.faces(city, b['id']); kind = archetype(b)
        plain, depth, _ = op.raster(shape, old['camera'])
        art, art_depth, _ = op.raster(shape, old['camera'], lambda f, c, x, y: paint_face(f, c, x, y, tiles, kind))
        x, y = b['xy']; w, h = b['size']; box = (x, y, x+w, y+h)
        expected = np.asarray(Image.open(OLD / b['base']).convert('RGBA'))
        np.testing.assert_array_equal(np.asarray(plain.crop(box)), expected)
        np.testing.assert_array_equal(np.asarray(art)[..., 3], np.asarray(plain)[..., 3])
        np.testing.assert_array_equal(depth, art_depth)
        np.testing.assert_array_equal(np.asarray(op.encode_depth(depth[y:y+h, x:x+w])), np.asarray(Image.open(OLD / b['depth'])))
        for file in (b['base'], b['depth']):
            shutil.copyfile(OLD / file, dest / file)
        b['previous'] = f'building_{b["id"]}_previous.png'
        shutil.copyfile(OLD / b['sprite'], dest / b['previous'])
        art.crop(box).save(dest / b['sprite'])
        Image.new('RGBA', (w, h)).save(dest / b['light'])
        b.update(previous_status=b['status'], status='material_candidate_unreviewed', has_light=False, archetype=kind)
        for stale in ('alpha_iou', 'full_alpha_iou'):
            b.pop(stale, None)
        checks.append({'id': b['id'], 'archetype': kind, 'alpha_equal': True, 'depth_equal': True,
                       'placement_equal': True, 'base_equal': True})
    for name, tile in tiles.items():
        Image.fromarray(tile).save(dest / f'{name}.png')
        Image.fromarray(np.tile(tile, (3, 3, 1))).save(dest / f'{name}_repeat.png')
        manifest['materials'].append({'name': name, 'image': f'{name}.png', 'repeat': f'{name}_repeat.png'})
    for field, file in [('base', 'source.png'), ('previous', 'previous.png'), ('sprite', 'preview.png')]:
        composite(manifest, dest, field).save(dest / file)
    board = Image.new('RGB', (1536, 540), '#fbf3e4')
    draw = ImageDraw.Draw(board)
    for i, (file, label) in enumerate([('source.png', 'BASE GEOMETRY'), ('previous.png', 'PREVIOUS: 1 AI BUILDING'), ('preview.png', 'NEW: 18 FACE-MAPPED BUILDINGS')]):
        draw.text((i*512+8, 7), label, fill='#3a2a1e')
        board.paste(Image.open(dest / file).convert('RGB'), (i*512, 28))
    board.save(dest / 'comparison.png')
    for oid in (4628, 4577, 4485):
        b = next(b for b in manifest['objects'] if b['id'] == oid)
        w, h = b['size']; strip = Image.new('RGBA', (w*3, h))
        for i, field in enumerate(('base', 'previous', 'sprite')):
            strip.paste(Image.open(dest / b[field]), (i*w, 0))
        strip.save(dest / f'representative_{oid}.png')
        strip.resize((w*9, h*3), Image.Resampling.NEAREST).save(dest / f'representative_{oid}_3x.png')
    op.write(dest / 'generation.json', report)
    op.write(dest / 'geometry_checks.json', {'buildings': checks, 'ground_equal': op.sha(dest / manifest['ground']) == op.sha(OLD / old['ground']),
              'snapshot_sha256': old['snapshot_sha256'], 'real_world_accuracy_verified': False,
              'user_visual_approval': False, 'assumptions': 'same flat ground; 3m story/bay, timber 2.5m; 4m roof repeat; not measured facades'})
    manifest['asset_sha256'] = {p.name: op.sha(p) for p in sorted(dest.glob('*.png'))}
    op.write(dest / 'manifest.json', manifest)
    cards = ''.join(f'<article><h3>#{b["id"]} · {b["archetype"]} · {b["height"]}m</h3>'
                    + ''.join(f'<figure><img src="{b[f]}"><figcaption>{label}</figcaption></figure>' for f, label in
                              [('base', '기본 도형'), ('previous', '이전 후보'), ('sprite', '새 외관')]) + '</article>' for b in manifest['objects'])
    reps = ''.join(f'<h3>#{oid} 원배율 / 3배</h3><img src="representative_{oid}.png"><br><img src="representative_{oid}_3x.png">' for oid in (4628, 4577, 4485))
    materials = ''.join(f'<figure><img src="{name}_repeat.png"><figcaption>{name} · 3×3 반복</figcaption></figure>' for name in JOBS)
    (dest / 'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>18동 외관 비교</title><style>body{font:16px system-ui;background:#fbf3e4;color:#3a2a1e;margin:20px}img{max-width:100%;image-rendering:pixelated}article{border-top:1px solid #cbb;padding:12px 0}figure{display:inline-block;margin:8px;vertical-align:top}figure img{max-width:28vw}figcaption{font-size:13px}a{color:#235e57}</style>'
        '<h1>덕수궁 북측 18동 — 외관만 바꾼 비교</h1><p>기본 도형 / 이전 후보(실제 AI 채택 1동) / 새 면별 재료(18동). 같은 바닥·카메라·윤곽·깊이. 미감 미승인.</p>'
        '<p>전체 지도나 실제 외관 복원이 아닙니다. 기존 목조 지붕의 단순한 형상과 바닥 반복 무늬도 그대로 남습니다.</p>'
        '<p><a href="../../web/pilot/?view=objects-materials">상호작용 비교 화면</a> · <a href="generation.json">프롬프트·비용</a> · <a href="geometry_checks.json">기하 검사</a></p>'
        '<a href="comparison.png"><img src="comparison.png" alt="세 방식 전체 비교"></a><h2>대표 3동</h2>' + reps + '<h2>재료 반복</h2>' + materials + '<h2>18동 개별 비교</h2>' + cards, encoding='utf-8')
    print(f'Built {dest}: 18 fixed-geometry objects', flush=True)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['generate', 'build'])
    parser.add_argument('--allow-external', action='store_true')
    args = parser.parse_args()
    generate(args.allow_external) if args.command == 'generate' else build()
