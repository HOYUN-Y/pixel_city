"""Integrate reviewed, offline reveal assets without changing the closed source run."""
import argparse
from pathlib import Path
from shutil import copyfile
from PIL import Image, ImageChops
from city_snapshot import DEST, read, write, sha

FILES = {'underlay.png': 'bosingak_underlay.png', 'bosingak.png': 'bosingak.png',
         'bosingak_reveal_hit.png': 'bosingak_hit.png', 'reveal_mask.png': 'bosingak_reveal_mask.png'}

def integrate(source, dest=DEST):
    completion = read(source / 'completion.json')
    if completion['status'] != 'complete_reconstructed_reveal': raise ValueError('Incomplete generation')
    if sha(dest / 'final.png') not in completion['source_sha256'].values(): raise ValueError('Base mismatch')
    mask = Image.open(source / 'reveal_mask.png').convert('L')
    sprite = Image.open(source / 'bosingak.png').convert('RGBA')
    hit = Image.open(source / 'bosingak_reveal_hit.png').convert('L')
    if any(Image.open(source / f).size != (1792,1024) for f in FILES): raise ValueError('Wrong dimensions')
    if ImageChops.multiply(sprite.getchannel('A'), ImageChops.invert(mask)).getbbox(): raise ValueError('Sprite outside mask')
    if ImageChops.multiply(hit, ImageChops.invert(mask)).getbbox(): raise ValueError('Hit outside mask')
    for src, name in FILES.items(): copyfile(source / src, dest / name)
    overlay = read(dest / 'overlay.json')
    overlay['landmarks'] = [l for l in overlay['landmarks'] if l['id'] != 'bosingak'] + [
        {'id':'bosingak','mode':'independent','sprite':'bosingak.png','hit':'bosingak_hit.png',
         'occluder_id':'bosingak-body','reveal_only':True}]
    overlay['spots'] = [s for s in overlay['spots'] if s['id'] != 'bosingak'] + [
        {'id':'bosingak','title':'보신각 · 재구성 시험','xy':[1333,659],
         'description':'AI 재구성 · 도형 기반 추정 배치, 실측 높이 미검증'}]
    overlay['occluders'] = [o for o in overlay['occluders'] if o['id'] != 'bosingak-body'] + [
        {'id':'bosingak-body','polygon':[[1311,635],[1355,635],[1355,669],[1311,669]]}]
    overlay['reveal'] = {'targetId':'bosingak','underlay':'bosingak_underlay.png','mask':'bosingak_reveal_mask.png',
                         'geometryVerified':False,'label':'AI 재구성 · 추정 배치'}
    write(dest / 'overlay.json', overlay)
    manifest = read(dest / 'manifest.json')
    manifest['asset_sha256'].update({f:sha(dest / f) for f in FILES.values()})
    manifest['overlay_sha256']['jongno-link'] = sha(dest / 'overlay.json')
    manifest['scenes']['jongno-link']['review'] = 'AI 재해석 지도 · 보신각 가림 해제는 추정 배치 재구성 · 실제 길찾기 아님'
    write(dest / 'manifest.json', manifest)
    data = read(dest / 'places.json')
    for l in data['landmarks']:
        if l['name'] == '보신각': l.update(mapSpotId='bosingak', geometryStatus='estimated')
    write(dest / 'places.json', data)
    build = read(dest / 'build.json')
    build['reveal'] = {'imageCalls':completion['image_requests'],'costUsd':completion['actual_cost_usd'],
                       'geometryVerified':False,'files':{f:sha(dest / f) for f in FILES.values()}}
    write(dest / 'build.json', build)
    return build['reveal']

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--dest',type=Path,default=DEST)
    a=p.parse_args();print(integrate(a.source,a.dest))
