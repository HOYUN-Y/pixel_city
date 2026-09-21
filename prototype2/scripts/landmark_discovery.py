"""Build an immutable, local-only discovery snapshot from existing approved-base art.

No network, AI generation, geography correction, or publication. Polygon coordinates
trace the displayed artwork, not surveyed footprint coordinates.
"""
import argparse
from pathlib import Path
from shutil import copytree
from PIL import Image, ImageDraw, ImageChops
from city_snapshot import P2, read, write, sha

BASE = P2 / 'work/dense-polish-20260919'
DEST = P2 / 'work/landmark-discovery-20260920'
STATIC = [
    {'id': 'geunjeongjeon', 'title': '근정전', 'xy': [1759, 1250],
     'hitPolygon': [[1697,1194],[1733,1185],[1737,1180],[1779,1172],[1801,1170],[1804,1180],[1818,1208],[1810,1214],[1820,1223],[1809,1231],[1808,1243],[1729,1253],[1720,1239],[1711,1215]],
     'snapshotIndex': 1370, 'snapshotName': '경복궁 근정전'},
    {'id': 'gyeonghoeru', 'title': '경회루', 'xy': [1413, 1143],
     'hitPolygon': [[1349,1077],[1366,1079],[1449,1059],[1454,1074],[1463,1095],[1478,1103],[1462,1110],[1461,1132],[1384,1143],[1377,1123],[1367,1119]],
     'snapshotIndex': 1126, 'snapshotName': '경복궁 경회루'},
]

def bounds(points):
    xs, ys = zip(*points)
    return [min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys)]

def thumbnail(image, rect):
    x,y,w,h=rect
    # Keep a little context; letterbox rather than distorting tall landmarks.
    crop=image.crop((x-16,y-16,x+w+16,y+h+16))
    crop.thumbnail((160,100), Image.Resampling.NEAREST)
    frame=Image.new('RGB',(160,100),'#eadbb7')
    frame.paste(crop,((160-crop.width)//2,(100-crop.height)//2))
    return frame

def build(dest=DEST):
    if dest.exists():
        raise ValueError('Immutable output exists; choose a new --dest')
    city=read(P2/'inputs/snapshot/city.json')
    for s in STATIC:
        assert dict(city['names'])[s['snapshotIndex']]==s['snapshotName']
    copytree(BASE/'snapshot',dest/'snapshot')
    snapshot=dest/'snapshot';manifest=read(snapshot/'manifest.json');overlay=read(snapshot/'overlay.json');places=read(snapshot/'places.json')
    overlay['spots'].extend({k:s[k] for k in ['id','title','xy','hitPolygon']} for s in STATIC)
    artwork=Image.open(BASE/'after.png').convert('RGBA')
    reveal=overlay['reveal'];x,y,w,h=reveal['rect']
    target=next(l for l in overlay['landmarks'] if l['id']=='bosingak')
    sprite=Image.open(snapshot/target['sprite']).convert('RGBA');tx,ty,_,_=target['rect']
    patch=Image.open(snapshot/reveal['underlay']).convert('RGBA')
    patch.alpha_composite(sprite,(tx-x,ty-y))
    foreground=Image.open(snapshot/reveal['foregroundMask']).convert('L')
    patch.putalpha(ImageChops.multiply(patch.getchannel('A'),foreground).point(lambda v:round(v*.55)))
    revealed=artwork.copy();revealed.alpha_composite(patch,(x,y))
    uncovered=Image.new('RGBA',(w,h));uncovered.alpha_composite(sprite,(tx-x,ty-y))
    uncovered.putalpha(ImageChops.multiply(uncovered.getchannel('A'),ImageChops.invert(foreground)))
    revealed.alpha_composite(uncovered,(x,y))
    static_by_name={s['title']:s for s in STATIC}
    for l in places['landmarks']:
        if l['name'] in static_by_name:
            l['mapSpotId']=static_by_name[l['name']]['id']
            l['status']='배경 그림 선택 영역 · 실측 정합 미검증'
        if not l.get('mapSpotId'):continue
        spot=next(s for s in overlay['spots'] if s['id']==l['mapSpotId'])
        rect=bounds(spot['hitPolygon']) if 'hitPolygon' in spot else next(o['rect'] for o in overlay['landmarks'] if o['id']==spot['id'])
        l['thumbnail']=f"thumb_{spot['id']}.png"
        l['thumbnailCaption']='AI 재구성·추정 배치' if spot['id']=='bosingak' else '현재 지도 그림 · 실제 사진 아님'
        l['discoveryNote']='경복궁 상위 시설 자료 · 개별 정보 미확인' if l.get('parentPlaceId') else l['thumbnailCaption']
        thumbnail(revealed if spot['id']=='bosingak' else artwork,rect).save(snapshot/l['thumbnail'])
    assert len(places['landmarks'])==8
    assert sum(bool(l.get('mapSpotId')) for l in places['landmarks'])==5
    write(snapshot/'overlay.json',overlay);write(snapshot/'places.json',places)
    manifest['run_id']=dest.name;manifest['reviewOnly']=True
    for name in ['overlay.json','places.json']+[l['thumbnail'] for l in places['landmarks'] if l.get('thumbnail')]:manifest['asset_sha256'][name]=sha(snapshot/name)
    write(snapshot/'manifest.json',manifest)
    html=(BASE/'index.html').read_text().replace('<body data-city-base="./snapshot/">','<body data-city-base="./snapshot/" data-city-experience="discovery">')
    (dest/'index.html').write_text(html)
    evidence=artwork.copy();draw=ImageDraw.Draw(evidence)
    for s in STATIC:draw.line([tuple(p) for p in s['hitPolygon']+[s['hitPolygon'][0]]],fill='#ffe68c',width=3)
    evidence.crop((1250,1000,1900,1330)).save(dest/'palace-selection-evidence.png')
    preserved=[name for name in manifest['asset_sha256'] if name not in ['overlay.json','places.json'] and not name.startswith('thumb_')]
    assert all(sha(snapshot/name)==sha(BASE/'snapshot'/name) for name in preserved)
    write(dest/'report.json',{'reviewOnly':True,'userVisualApproval':False,'geometryPassed':False,'base':str(BASE.relative_to(P2)),
        'backgroundUnchanged':True,'preservedAssetCount':len(preserved),'paidCalls':0,'dynamicTraffic':False,
        'sourceManifestSha256':sha(BASE/'snapshot/manifest.json'),'staticSpots':STATIC,
        'identityEvidence':{'snapshot':'inputs/snapshot/city.json','snapshotSha256':sha(P2/'inputs/snapshot/city.json'),
            'capture':'work/dense-city-20260916-source/capture.json','sourceImage':'work/dense-city-20260916-source/source_1_1.png',
            'method':'Named snapshot buildings and palace layout in VWorld capture; traced current-art roof/body silhouettes. Image-coordinate selections, not geographic registration.'},
        'parentDataOnly':['geunjeongjeon','gyeonghoeru'],'unresolved':'Existing geometry/seam warnings remain. No new visual approval inferred.'})
    return dest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--dest',type=Path,default=DEST)
    print(build(parser.parse_args().dest))
