"""Two-request extension of the existing OpenRouter trial; all other stages are offline."""
import argparse
import fcntl
import os
import shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import seam_lab as seam

api = seam.api
P2 = seam.P2
CONFIG = P2 / 'configs/living_lab.json'
LIMITS = {'background': 1, 'cars': 1}


def mask(polygons, size=(1536, 1536)):
    im = Image.new('L', size)
    for polygon in polygons:
        ImageDraw.Draw(im).polygon([tuple(p) for p in polygon], fill=255)
    return im


def init():
    cfg = api.qs.read(CONFIG)
    parent, _ = seam.load_run(cfg['parent_run'])
    manifest = api.qs.read(parent / 'manifest.json')
    folder = seam.ROOT / 'runs' / seam.stamp(); folder.mkdir()
    files = {manifest['character'], 'style.png'}
    for scene in manifest['scenes'].values():
        files.add(scene['overlay'])
        files.update(v['file'] for v in scene['variants'].values())
    for file in files:
        if file in manifest['asset_sha256'] and api.qs.sha(parent / file) != manifest['asset_sha256'][file]:
            raise ValueError('Parent asset changed')
        shutil.copyfile(parent / file, folder / file)
    manifest['run_id'] = folder.name
    manifest['parent_run'] = cfg['parent_run']
    api.qs.write(folder / 'parent_manifest.json', manifest)
    report = {'kind': 'living_lab', 'run_id': folder.name, 'parent_run': cfg['parent_run'],
              'model': api.MODEL, 'request_limit': 2, 'limits': LIMITS, 'requests': [],
              'input_sha256': {f: api.qs.sha(folder / f) for f in files}, 'config': cfg,
              'status': 'prepared', 'user_visual_approval': False}
    api.qs.write(folder / 'report.json', report)
    print('RUN=' + folder.name)


def generate(folder, report, name):
    if report.get('kind') != 'living_lab' or report['request_limit'] != 2:
        raise ValueError('Wrong budget ledger')
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not key:
        raise ValueError('OPENROUTER_API_KEY is missing')
    for file, digest in report['input_sha256'].items():
        if api.qs.sha(folder / file) != digest:
            raise ValueError('Input changed')
    cap = api.validate_capabilities(api.request_json(f'/images/models/{api.MODEL}/endpoints', key))
    if 'transparent' not in cap['supported_parameters'].get('background', {}).get('values', []):
        raise ValueError('Transparent output unsupported')
    cfg = report['config']
    if name == 'background':
        crop = cfg['tower_crop']
        source = Image.open(folder / 'namsan_final.png').crop(crop).resize((1024,1024), Image.Resampling.NEAREST)
        guide = mask([cfg['tower_polygon'], cfg['shadow_polygon']]).crop(crop).resize((1024,1024), Image.Resampling.NEAREST)
        prompt = ('Use case: precise-object-edit. Image 1 is the exact pixel-art edit target. Image 2 is a black/white edit guide: white means remove and reconstruct, black means preserve. '
                  'Remove ONLY the tall white N Seoul observation tower, its red antenna, cylindrical viewing deck, supporting pillar, rectangular foundation building and attached shadow. '
                  'Fill the removed silhouette naturally with continuous pixel-art forest, the existing stone wall behind the tower and a small empty summit clearing at its base. '
                  'Preserve the separate shorter orange-and-white lattice mast to the LEFT completely. Keep camera, pixel scale, surrounding trees, paths and wall unchanged. '
                  'No new tower, building, antenna, labels or scenery redesign. This is a clean background plate, not a restyled scene.')
        refs = [source, guide]
    else:
        prompt = ('Use case: stylized-concept. Asset type: transparent two-view pixel-art vehicle sprite sheet. '
                  'Create exactly TWO views of the SAME small cream-colored city hatchback, no logos, clearly distinct dark front windshield and rear window. '
                  'Square canvas split into two equal VERTICAL columns. Center one complete isolated car inside each column with generous transparent padding. '
                  'LEFT column: front three-quarter view, nose pointing diagonally DOWN RIGHT, screen direction southeast at 45 degrees. '
                  'RIGHT column: rear three-quarter view, nose pointing diagonally UP LEFT, screen direction northwest at 225 degrees. '
                  'Fixed elevated city-game camera about 30 degrees above horizon. Crisp limited-palette pixel clusters suitable for 32-pixel-long vehicles, nearest-neighbor look. '
                  'Reference image is ONLY the palette/pixel style, not a scene to reproduce. No ground, cast shadow, road, labels, dividers, glow, extra cars or checkerboard. Genuinely transparent background.')
        refs = [Image.open(folder / 'downtown_final.png')]
    seam.paid(folder, report, key, name, name, prompt, refs, transparent=name == 'cars', limits=LIMITS)


def build(folder, report):
    cfg = api.qs.read(CONFIG)
    if cfg['review_run'] != folder.name or not cfg['accepted']:
        raise ValueError('Explicit run-bound visual review required')
    if len(report['requests']) != 2 or any(r['status'] != 'complete' for r in report['requests']):
        raise ValueError('Two completed requests required')
    for r in report['requests']:
        if api.qs.sha(folder / (r['name'] + '_raw.png')) != r['raw_sha256']:
            raise ValueError('Raw output changed')
    original = Image.open(folder / 'namsan_final.png').convert('RGB')
    tower_mask = mask([cfg['tower_polygon']])
    # A small restoration border removes antialias/roof-edge remnants. Original
    # border pixels travel with the restore layer; picking remains tower-only.
    removal = mask([cfg['tower_polygon'], cfg['shadow_polygon']]).filter(ImageFilter.MaxFilter(15))
    crop = cfg['tower_crop']; plate = original.copy()
    repaired = Image.open(folder / 'background_raw.png').convert('RGB').resize((512,512), Image.Resampling.NEAREST)
    plate.paste(repaired, tuple(crop[:2]), removal.crop(crop))
    plate.save(folder / 'namsan_background.png')
    sprite = original.convert('RGBA'); sprite.putalpha(removal); sprite.save(folder / 'tower.png')
    tower_mask.save(folder / 'tower_hit.png')
    light = Image.new('RGBA', original.size, (255,210,100,0))
    light_mask = mask(cfg['light_polygons'])
    light.putalpha(Image.fromarray((np.minimum(np.asarray(light_mask), np.asarray(tower_mask)).astype(np.uint16)*160//255).astype(np.uint8)))
    light.save(folder / 'tower_light.png')
    cars = Image.open(folder / 'cars_raw.png').convert('RGBA')
    for i, name in enumerate(['car_se.png','car_nw.png']):
        im = cars.crop((i*512,0,(i+1)*512,1024))
        box = im.getchannel('A').point(lambda v: 255 if v>=128 else 0).getbbox()
        if not box: raise ValueError('Missing car view')
        im = im.crop(box); im.thumbnail((32,32), Image.Resampling.BOX)
        im.putalpha(im.getchannel('A').point(lambda v:255 if v>=128 else 0)); im.save(folder / name)
    manifest = api.qs.read(folder / 'parent_manifest.json')
    downtown = api.qs.read(folder / manifest['scenes']['downtown']['overlay'])
    downtown['traffic'] = {'lanes': cfg['lanes'], 'speed': 28, 'occluders': cfg['traffic_occluders']}
    namsan = api.qs.read(folder / manifest['scenes']['namsan']['overlay'])
    namsan['landmark'] = {'id':'tower','background':'namsan_background.png','sprite':'tower.png',
                          'hit':'tower_hit.png','light':'tower_light.png','occluder_id':'tower-base'}
    for scene, overlay in [('downtown',downtown),('namsan',namsan)]:
        api.qs.write(folder / manifest['scenes'][scene]['overlay'], overlay)
    files = {manifest['character'], 'namsan_background.png', 'tower.png', 'tower_hit.png', 'tower_light.png', 'car_se.png', 'car_nw.png'}
    files.update(v['file'] for scene in manifest['scenes'].values() for v in scene['variants'].values())
    manifest['asset_sha256'] = {file:api.qs.sha(folder / file) for file in sorted(files)}
    manifest['overlay_sha256'] = {s:api.qs.sha(folder / d['overlay']) for s,d in manifest['scenes'].items()}
    manifest['scenes']['downtown']['review'] += ' · 차량 4대: 그림 경로 기반 풍경용 주행, 실제 교통 아님.'
    manifest['scenes']['namsan']['review'] += ' · 타워 본체 선택·조명·숨김 가능. 숨김 뒤 배경은 AI 추정.'
    api.qs.write(folder / 'manifest.json', manifest)
    report['review'] = cfg; report['status'] = 'awaiting_user_review'
    report['total_cost_usd'] = round(sum(r['usage']['cost'] for r in report['requests']),6)
    api.qs.write(folder / 'report.json', report)
    verify(folder, report)
    page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>랜드마크·차량 시험</title>
<style>body{font:16px system-ui;background:#fbf3e4;color:#3a2a1e}img{max-width:48%;image-rendering:pixelated}</style>
<h1>랜드마크·차량 시험</h1><p>타워 외관은 원본 픽셀. 숨긴 뒤 배경은 AI 추정. 차량은 풍경용이며 실제 교통 아님.</p>
<a href="report.json">프롬프트·비용</a> · <a href="verification.json">검증</a>
<h2>타워 표시 / 숨김</h2><img src="namsan_final.png"><img src="namsan_background.png">
<h2>차량 원본</h2><img src="cars_raw.png"></html>'''
    (folder / 'index.html').write_text(page,encoding='utf8')
    print('BUILT=' + folder.name)


def verify(folder, report):
    manifest = api.qs.read(folder / 'manifest.json')
    for request in report['requests']:
        if request['status']!='complete' or api.qs.sha(folder / (request['name']+'_raw.png'))!=request['raw_sha256']:
            raise ValueError('Raw output incomplete or changed')
    for file, digest in report['input_sha256'].items():
        if file.endswith('.png') and api.qs.sha(folder/file)!=digest:raise ValueError('Original input changed')
    for file, digest in manifest['asset_sha256'].items():
        if api.qs.sha(folder / file) != digest: raise ValueError('Asset changed: '+file)
    for scene, digest in manifest['overlay_sha256'].items():
        if api.qs.sha(folder / manifest['scenes'][scene]['overlay']) != digest: raise ValueError('Overlay changed')
    original = Image.open(folder / 'namsan_final.png').convert('RGBA')
    background = Image.open(folder / 'namsan_background.png').convert('RGBA')
    tower = Image.open(folder / 'tower.png').convert('RGBA')
    if Image.alpha_composite(background,tower).tobytes() != original.tobytes():
        raise ValueError('Original reconstruction differs')
    light=np.asarray(Image.open(folder/'tower_light.png'))[...,3]
    hit=np.asarray(Image.open(folder/'tower_hit.png'))
    if ((light>0)&(hit==0)).any():raise ValueError('Light outside tower')
    if len(report['requests'])!=2 or {r['group'] for r in report['requests']}!=set(LIMITS):
        raise ValueError('Wrong request budget')
    result = {'request_count':2,'total_cost_usd':report['total_cost_usd'],
              'exact_original_reconstruction':True,'outside_removal_preserved':True,
              'user_visual_approval':False,'note':'Background inference, hand-authored routes, no real traffic.'}
    api.qs.write(folder / 'verification.json',result)
    print(result)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['init','generate','build','verify','activate'])
    p.add_argument('--run');p.add_argument('--asset',choices=list(LIMITS));p.add_argument('--allow-external',action='store_true')
    args=p.parse_args()
    if args.command=='init':init();return
    folder, report=seam.load_run(args.run)
    if report.get('kind')!='living_lab':raise ValueError('Not a living-lab run')
    if args.command=='generate':
        if not args.allow_external or not args.asset:raise ValueError('Explicit external opt-in and asset required')
        with (folder / '.generation.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            generate(folder,api.qs.read(folder/'report.json'),args.asset)
    elif args.command=='build':build(folder,report)
    elif args.command=='verify':verify(folder,report)
    else:
        verify(folder,report)
        qa=api.qs.read(folder/'living_browser_qa.json')
        if not qa.get('passed') or qa.get('manifest_sha256')!=api.qs.sha(folder/'manifest.json'):
            raise ValueError('Matching browser QA required before activation')
        api.qs.write(seam.ROOT/'current.json',{'run_id':folder.name})


if __name__=='__main__':main()
