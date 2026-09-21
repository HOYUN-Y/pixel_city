"""Extend existing artwork with one building selection and two location-only markers.

No network or generation. Projection is a location cue, never geography approval.
"""
import argparse
import math
from pathlib import Path
from shutil import copytree
from PIL import Image, ImageDraw
from city_snapshot import P2, read, write, sha
from landmark_discovery import thumbnail, bounds

BASE=P2/'work/landmark-discovery-20260920'
DEST=P2/'work/landmark-discovery-20260922'
CAPTURE=P2/'work/dense-city-20260916-source/capture.json'
HALL={'id':'sejong-center','title':'세종문화회관','xy':[2110,2142],
      'hitPolygon':[[2037,1974],[2077,1963],[2108,1972],[2256,1945],[2295,1990],[2314,2025],[2310,2058],[2156,2098],[2156,2120],[2110,2142],[2028,2152],[1994,2126],[1994,2052],[2038,2040]]}

def project(lon,lat,capture):
    g=capture['geometry'];near=min(g['points'],key=lambda p:(p['lon']-lon)**2+(p['lat']-lat)**2)
    h=near['terrain'];phi=math.radians(lat);lam=math.radians(lon);e2=6.69437999014e-3
    n=6378137/math.sqrt(1-e2*math.sin(phi)**2)
    world=[(n+h)*math.cos(phi)*math.cos(lam),(n+h)*math.cos(phi)*math.sin(lam),(n*(1-e2)+h)*math.sin(phi)]
    delta=[v-p for v,p in zip(world,g['position'])]
    dot=lambda axis:sum(v*d for v,d in zip(g[axis],delta))
    return [round(capture['canvas'][0]/2+capture['scale_px_per_m']*dot('right')),round(capture['canvas'][1]/2-capture['scale_px_per_m']*dot('up'))],h

def build(dest=DEST):
    if dest.exists():raise ValueError('Immutable output exists; choose a new --dest')
    assert dict(read(P2/'inputs/snapshot/city.json')['names'])[3385]=='세종문화회관'
    copytree(BASE/'snapshot',dest/'snapshot');snapshot=dest/'snapshot'
    m=read(snapshot/'manifest.json');o=read(snapshot/'overlay.json');p=read(snapshot/'places.json');capture=read(CAPTURE)
    evidence=[]
    for card,id in [('landmark-3','king-sejong'),('landmark-4','admiral-yi')]:
        l=next(l for l in p['landmarks'] if l['id']==card);place=next(a for a in p['places'] if a['id']==l['placeId'])
        xy,h=project(*place['coordinates'],capture)
        o['spots'].append({'id':id,'title':l['name'],'xy':xy,'selectionMode':'location-only'})
        l.update(mapSpotId=id,status='위치 안내 · 외형 미확인',discoveryNote='자료 기반 위치 안내 · 배경의 동상 외형 미확인',
            note='수집 좌표와 기존 촬영 배치를 대조한 위치 안내입니다. 현재 AI 그림의 외형·정밀 위치를 보증하지 않습니다.',
            thumbnail=f'thumb_{id}.png',thumbnailCaption='주변 지도 · 동상 외형 미확인')
        evidence.append({'id':id,'contentId':place['contentId'],'coordinates':place['coordinates'],'nearestSampleTerrain':h,'imageXY':xy,
            'sourceCapture':'source_2_2.png' if id=='king-sejong' else 'source_3_3.png',
            'verification':'Projected location agrees with statue/plaza context in original capture; current AI depiction not identified. Not a silhouette or surveyed registration.'})
    o['spots'].append(HALL)
    hall=next(l for l in p['landmarks'] if l['id']=='landmark-5')
    hall.update(mapSpotId=HALL['id'],status='본관 배경 그림 선택 · 실측 정합 미검증',discoveryNote='세종문화회관 본관 · 현재 지도 그림',thumbnail='thumb_sejong-center.png',thumbnailCaption='현재 지도 그림 · 본관 선택')
    artwork=Image.open(P2/'work/dense-polish-20260919/after.png').convert('RGBA')
    for l in p['landmarks'][3:6]:
        s=next(s for s in o['spots'] if s['id']==l['mapSpotId'])
        rect=bounds(s['hitPolygon']) if s.get('hitPolygon') else [s['xy'][0]-80,s['xy'][1]-50,160,100]
        thumbnail(artwork,rect).save(snapshot/l['thumbnail'])
    annotated=artwork.copy();d=ImageDraw.Draw(annotated)
    d.line([tuple(x) for x in HALL['hitPolygon']+[HALL['hitPolygon'][0]]],fill='#ffe68c',width=3)
    for e in evidence:
        x,y=e['imageXY'];d.ellipse((x-12,y-12,x+12,y+12),outline='#ff6644',width=3);d.text((x+16,y),e['id'],fill='#ff6644')
    annotated.crop((1900,1880,2660,2320)).save(dest/'new-landmarks-evidence.png')
    write(snapshot/'overlay.json',o);write(snapshot/'places.json',p)
    m.update(run_id=dest.name,reviewOnly=True,experience='discovery')
    changed=['overlay.json','places.json']+[l['thumbnail'] for l in p['landmarks'][3:6]]
    for name in changed:m['asset_sha256'][name]=sha(snapshot/name)
    write(snapshot/'manifest.json',m)
    (dest/'index.html').write_text((BASE/'index.html').read_text())
    preserved=[name for name in read(BASE/'snapshot/manifest.json')['asset_sha256'] if name not in changed]
    assert all(sha(BASE/'snapshot'/name)==sha(snapshot/name) for name in preserved)
    assert len(o['spots'])==8 and len(o['landmarks'])==3
    write(dest/'report.json',{'reviewOnly':True,'geometryPassed':False,'userVisualApproval':False,'paidCalls':0,'backgroundUnchanged':True,
        'baseManifestSha256':sha(BASE/'snapshot/manifest.json'),'preservedAssetCount':len(preserved),'captureSha256':sha(CAPTURE),
        'linkedCount':8,'objectSelections':6,'locationOnly':evidence,'hall':{'snapshotIndex':3385,'snapshotName':'세종문화회관','selection':HALL,
            'sourceCapture':'source_2_2.png','method':'Identified low broad pale-green-roof main hall west of Sejong statue; roof/body traced in current art. Ancillary buildings excluded.'},
        'limits':['Image coordinates only; ground projection is approximate','Statue artwork not identified','Existing road/seam failures retained','No public deployment']})
    return dest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dest',type=Path,default=DEST);print(build(p.parse_args().dest))
