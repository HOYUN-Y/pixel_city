"""Local-only polish snapshot. Reuses existing artwork and paid generation ledger."""
import argparse
import math
from copy import deepcopy
from pathlib import Path
from shutil import copyfile
from PIL import Image, ImageDraw, ImageChops
from city_snapshot import P2, read, write, sha
from dense_snapshot import export

ROOT=P2/'work/dense-polish-20260919'
GEN=P2/'work/dense-city-20260916-source'
BASE=P2/'work/dense-roads-20260917/jongno-v2-source'
NAME='gwanghwamun_polish_20260919'

def prepare_generation():
    """Only prepare the approved one replacement; existing generate.py owns billing."""
    tasks=read(GEN/'generation_tasks.json')
    if NAME in tasks: raise ValueError('Task already prepared; never replace prompt')
    task={'group':'replacement','transparent':True,'references':['gwang_dense_source.png','gwang_dense_mask.png','background_2_2_ground_v2.png'],
          'prompt':'''Use case: stylized-concept. Asset: transparent pixel-art Gwanghwamun gate sprite for an existing orthographic city map.
Image 1 is the structural reference; Image 2 is the exact silhouette/placement guide; Image 3 supplies ONLY pixel texture and palette.
Render ONLY the main gate, two dark blue tiled roofs above a broad pale stone base with THREE arches. Preserve the low, broad proportions of image 1; do not make a tall pavilion. Match the silhouette envelope in image 2: approximately x181..784, y192..603 on the 1024 square canvas (width/height about 1.47). Preserve the reference roof slope and camera orientation, fixed orthographic heading22.5/elevation30, parallel lines with no vanishing point, no dramatic perspective or enlarged near side.
Detailed crisp warm city pixel art, red/green timber, muted blue tiles, pale stone. Genuine transparent RGBA outside the gate AND inside open arches. No checkerboard, no ground, shadow, surrounding walls, trees, people, text or second gate. Keep whole sprite inside the guide envelope. Output1024x1024.'''}
    tasks[NAME]=task;write(GEN/'generation_tasks.json',tasks)
    approval=read(GEN/'authorization.json');approval['names'].append(NAME);write(GEN/'authorization.json',approval)
    ROOT.mkdir(parents=True,exist_ok=True)
    write(ROOT/'generation_authorization.json',{'user_authorized':True,'basis':'Implement approved existing-art polish plan, 2026-09-19','name':NAME,'ledger':str(GEN/'report.json'),'total_budget_usd':5,'total_call_limit':32,'reservation_usd':.75,'retries':0,'task':task})

def build():
    source=ROOT/'source';snapshot=ROOT/'snapshot'
    if source.exists() or snapshot.exists(): raise ValueError('Immutable output exists; choose a new run')
    source.mkdir(parents=True)
    d=deepcopy(read(BASE/'delivery.json'))
    for p in BASE.glob('*.png'): copyfile(p,source/p.name)
    frozen=read(P2/'work/dense-occlusion-20260917/frozen_masks.json')
    foreground=Image.new('L',(384,384));draw=ImageDraw.Draw(foreground)
    for polygon in frozen['reveal_polygons']:draw.polygon([tuple(p) for p in polygon],fill=255)
    foreground.save(source/'bosingak_foreground.png')
    d['reveal'].update(auto=True,foregroundMask='bosingak_foreground.png')
    traffic=d['traffic']
    for lane in traffic['lanes']:lane['id']='jongno-'+lane['id']
    for mask in traffic['occluders']:mask['lanes']=['jongno-'+i for i in mask['lanes']]
    sejong=read(P2/'work/dense-roads-20260917/sejong-source/delivery.json')['traffic']
    for lane in sejong['lanes']:lane['id']='sejong-'+lane['id'];traffic['lanes'].append(lane)
    traffic['focuses']=[{'id':'jongno','label':'종로','xy':traffic['focus']},{'id':'sejong','label':'세종대로','xy':sejong['focus']}]
    d['run_id']='dense-polish-20260919'
    result={'baselineDeliverySha256':sha(BASE/'delivery.json'),'backgroundUnchanged':True,'backgroundSha256':sha(source/d['background']),'userVisualApproval':False,'geometryPassed':False,'seamWarningsRetained':['0_4–0_5','1_1–1_2','1_2–1_3','1_2–2_2'],'backgroundRepair':'No confirmed new target; preserved reviewed DP composition. No extra repair request.'}
    raw=GEN/f'{NAME}_raw.png'
    if raw.exists():
        im=Image.open(raw).convert('RGBA');im.putalpha(im.getchannel('A').point(lambda p:255 if p>=128 else 0));im=im.crop(im.getbbox())
        scale=math.sqrt((113/im.width)*(77/im.height));size=(round(im.width*scale),round(im.height*scale))
        old=d['landmarks'][0]['rect'][2:];error=lambda s:abs(math.log((s[0]/s[1])/(113/77)))
        result['gwanghwamun']={'raw':str(raw),'oldSize':old,'candidateSize':size,'aspectImproved':error(size)<error(old),'selected':False}
        im=im.resize(size,Image.Resampling.NEAREST);im.save(ROOT/'gwanghwamun_candidate.png')
        if error(size)<error(old):
            l=d['landmarks'][0];l['rect']=[round((1954+2067-size[0])/2),1617-size[1],*size]
            im.save(source/l['sprite']);im.getchannel('A').save(source/l['hit']);result['gwanghwamun']['selected']=True
    else:result['gwanghwamun']={'selected':False,'reason':'No completed generation; retain baseline'}
    d['visualAcceptance']={**result,'status':'local-review-pending'};write(source/'delivery.json',d)
    export(source,snapshot,review_only=True)
    html=(P2/'web/pilot/index.html').read_text().replace('href="style.css"','href="../../web/pilot/style.css"').replace('src="app.js"','src="../../web/pilot/beta-app.js"').replace('<body>','<body data-city-base="./snapshot/">')
    (ROOT/'index.html').write_text(html)
    background=Image.open(source/d['background']).convert('RGBA')
    for title,delivery,folder in [('before',read(BASE/'delivery.json'),BASE),('after',d,source)]:
        image=background.copy()
        for l in delivery['landmarks']:
            if not l['reveal_only']:image.alpha_composite(Image.open(folder/l['sprite']).convert('RGBA'),tuple(l['rect'][:2]))
        image.convert('RGB').save(ROOT/f'{title}.png')
        image.crop((1900,1480,2130,1690)).resize((690,630),Image.Resampling.NEAREST).save(ROOT/f'gwanghwamun_{title}.png')
    before=Image.open(ROOT/'before.png');after=Image.open(ROOT/'after.png')
    outside=ImageChops.difference(before,after);l=d['landmarks'][0];old=read(BASE/'delivery.json')['landmarks'][0]
    painter=ImageDraw.Draw(outside)
    for r in [l['rect'],old['rect']]:painter.rectangle((r[0],r[1],r[0]+r[2]-1,r[1]+r[3]-1),fill=(0,0,0))
    result['outsideLandmarkChangedPixels']=sum(p!=(0,0,0) for p in outside.getdata())
    result['ledger']=read(GEN/'report.json').get('budget_accounting',{})
    write(ROOT/'report.json',result)
    print(ROOT)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare-generation',action='store_true');a=p.parse_args()
    prepare_generation() if a.prepare_generation else build()
