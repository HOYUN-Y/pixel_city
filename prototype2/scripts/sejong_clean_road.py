"""One masked Sejong repair, existing billing ledger, isolated local comparison."""
import argparse
from pathlib import Path
from shutil import copyfile
from PIL import Image, ImageDraw
import numpy as np
from city_snapshot import P2, read, write, sha
from dense_seams import bounded_repair
from dense_snapshot import export
from copy import deepcopy

ROOT=P2/'work/sejong-clean-road-20260919'
BASE=P2/'work/dense-polish-20260919/source'
GEN=P2/'work/dense-city-20260916-source'
NAME='sejong_clean_road_20260919'
RECT=(1920,1408,2944,2432)
# Native crop coordinates, manually traced vehicle bodies and their shadows.
BOXES=[(272,307,299,337),(301,321,315,334),(300,335,318,353),
       (284,342,301,360),(316,335,340,363),(324,355,339,369),
       (338,360,361,379),(356,362,383,390),(333,376,360,405),
       (365,403,381,417),(358,411,379,430),(376,420,396,440),
       (329,435,340,451),(385,437,399,452),(379,441,390,457),
       (395,449,415,472),(410,467,423,485),(427,469,444,488),
       (426,487,443,504),(444,498,464,519),(438,509,451,523),
       (465,515,477,529),(454,522,473,544),(469,526,483,547),
       (484,535,499,551),(509,558,536,590),(500,596,520,617),
       (524,595,538,610),(565,635,600,671)]

def inspect():
    if (GEN/f'{NAME}_intent.json').exists():raise ValueError('Preserve attempted generation inputs')
    ROOT.mkdir(parents=True,exist_ok=True)
    d=read(BASE/'delivery.json');im=Image.open(BASE/d['background']).convert('RGB').crop(RECT)
    im.save(ROOT/'before.png')
    for i,box in enumerate([(170,200,400,440),(300,390,610,710)]):
        crop=im.crop(box).resize(((box[2]-box[0])*3,(box[3]-box[1])*3),Image.Resampling.NEAREST)
        draw=ImageDraw.Draw(crop)
        for x in range((box[0]//20+1)*20,box[2],20):
            xx=(x-box[0])*3;draw.line((xx,0,xx,crop.height),fill='#ff00aa',width=1);draw.text((xx+2,0),str(x),fill='white')
        for y in range((box[1]//20+1)*20,box[3],20):
            yy=(y-box[1])*3;draw.line((0,yy,crop.width,yy),fill='#ff00aa',width=1);draw.text((0,yy+2),str(y),fill='white')
        crop.save(ROOT/f'inspect_{i}.png')

def prepare():
    if (GEN/f'{NAME}_intent.json').exists():raise ValueError('Never retry an attempted request')
    im=Image.open(ROOT/'before.png').convert('RGB');mask=Image.new('L',im.size);draw=ImageDraw.Draw(mask)
    for box in BOXES:draw.rectangle(box,fill=255)
    mask.save(ROOT/'mask.png');preview=im.copy();pd=ImageDraw.Draw(preview)
    for i,box in enumerate(BOXES):pd.rectangle(box,outline='magenta',width=1);pd.text(box[:2],str(i+1),fill='yellow')
    preview.save(ROOT/'mask_review.png')
    write(ROOT/'frozen_mask.json',{'backgroundSHA':sha(BASE/read(BASE/'delivery.json')['background']),'crop':list(RECT),'boxes':BOXES,'maskSHA':sha(ROOT/'mask.png'),'basis':'Manually identified road vehicle bodies/shadows; parking and sidewalks excluded'})
    for f in ['before','mask']:copyfile(ROOT/f'{f}.png',GEN/f'{NAME}_{f}.png')
    task={'group':'repair','references':[f'{NAME}_before.png',f'{NAME}_mask.png'],'prompt':'''Use case: precise-object-edit. Edit image1, a native1024x1024 pixel-art Seoul city map. Image2 is a WHITE permitted-edit mask: each white patch marks a road vehicle and its shadow. Black must remain unchanged.
Remove the marked cars, buses, trucks AND their cast/contact shadows completely. Reconstruct empty asphalt and any hidden lane dashes or crosswalk stripes by continuing the neighboring direction, spacing and colors. Every marked vehicle must disappear; do not substitute another vehicle. This is a clean road background for separately animated cars.
Preserve the existing road width, alignment, curbs, lane lines and crosswalks. Preserve ALL buildings, trees, sidewalks, parking areas and unmasked cars. Keep exact camera, native pixel scale, palette and framing. No zoom, crop, warp, perspective change, blur, global repainting, extra objects or annotations. Repair only white mask patches with crisp matching pixel clusters. Return one opaque1024x1024 image with unchanged surrounding pixels.''' }
    tasks=read(GEN/'generation_tasks.json')
    if NAME in tasks and tasks[NAME]!=task:raise ValueError('Prepared task differs')
    tasks[NAME]=task;write(GEN/'generation_tasks.json',tasks)
    auth=read(GEN/'authorization.json');auth['names']=list(dict.fromkeys([*auth['names'],NAME]));write(GEN/'authorization.json',auth)
    approval=read(GEN/'repair_approval.json');approval['names']=list(dict.fromkeys([*approval['names'],NAME]))
    approval['sejong_clean_road']={'date':'2026-09-19','user_statement':'Implement the plan.','scope':'One Sejong masked vehicle removal. Upload current-art crop and frozen vehicle mask to existing OpenRouter/OpenAI. Total ledger $5/32, reserve $.75, no retries.'};write(GEN/'repair_approval.json',approval)
    write(ROOT/'authorization.json',{'task':task,'approval':approval['sejong_clean_road'],'reservation_usd':.75})

def build():
    if (ROOT/'source').exists() or (ROOT/'snapshot').exists():raise ValueError('Never overwrite snapshot')
    raw=Image.open(GEN/f'{NAME}_raw.png').convert('RGB')
    original=Image.open(ROOT/'before.png').convert('RGB');mask=np.asarray(Image.open(ROOT/'mask.png'))>0
    if raw.size!=(1024,1024):raise ValueError('Unexpected output size')
    result=bounded_repair(np.asarray(original),np.asarray(raw),mask)
    Image.fromarray(result).save(ROOT/'after.png')
    delta=np.any(result!=np.asarray(original),axis=2)
    report={'outsideMaskChangedPixels':int(np.count_nonzero(delta&~mask)),'maskPixels':int(mask.sum()),'changedPixels':int(delta.sum()),'userVisualApproval':False,'candidateAccepted':False,'baselineUnchanged':True,'budget':read(GEN/'report.json')['budget_accounting']}
    source=ROOT/'source'
    if source.exists():raise ValueError('Never overwrite snapshot')
    source.mkdir()
    d=deepcopy(read(BASE/'delivery.json'))
    for p in BASE.glob('*.png'):copyfile(p,source/p.name)
    full=Image.open(BASE/d['background']).convert('RGB');full.paste(Image.fromarray(result),RECT[:2]);full.save(source/d['background'])
    d['run_id']=NAME;d['traffic']['lanes']=[l for l in d['traffic']['lanes'] if l['id'].startswith('sejong-')];d['traffic']['occluders']=[]
    d['traffic']['focus']=next(f['xy'] for f in d['traffic']['focuses'] if f['id']=='sejong');d['traffic']['focuses']=[f for f in d['traffic']['focuses'] if f['id']=='sejong']
    d['visualAcceptance']=report;write(source/'delivery.json',d);export(source,ROOT/'snapshot',review_only=True)
    sheet=Image.new('RGB',(2048,1024));sheet.paste(original);sheet.paste(Image.fromarray(result),(1024,0));sheet.save(ROOT/'comparison.png')
    review={'rect':list(RECT),'center':d['traffic']['focus'],'snapshot':'./snapshot/','before':'before.png','after':'after.png','hashes':{f:sha(ROOT/f) for f in ['before.png','after.png']},'candidateAccepted':False}
    write(ROOT/'review.json',review);write(ROOT/'report.json',report)
    html='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>세종대로 · 배경 차량 제거 비교</title>
<style>*{box-sizing:border-box}body{margin:0;background:#e9debf;color:#30291e;font:14px system-ui}header{padding:12px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}button{padding:8px;border:1px solid #62513b;background:#fff7e5;cursor:pointer}button[aria-pressed=true]{background:#dfb962}p{margin:0;width:100%;font-size:12px}canvas{display:block;width:100%;height:calc(100dvh - 150px);touch-action:none;image-rendering:pixelated}#status{padding:8px}</style>
<header><strong>세종대로 차량 제거 · LOCAL REVIEW</strong><button data-mode="before">① 기존 배경 + 차량</button><button data-mode="empty">② 정리 배경만</button><button data-mode="after">③ 정리 배경 + 차량</button><button id="motion">재생/정지</button><button data-scale="0.5">50%</button><button data-scale="1">100%</button><button id="reset">구간 중심</button><p id="notice">후보 검수 중 · 기존 지도/배포 변경 없음 · 드래그로 이동</p></header><canvas id="review" tabindex="0" aria-label="세종대로 차량 제거 비교 지도"></canvas><p id="status">불러오는 중</p><script type="module" src="../../web/pilot/road-review.js"></script></html>'''
    (ROOT/'index.html').write_text(html)
    print(report)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['inspect','prepare','build']);a=p.parse_args();globals()[a.action]()
