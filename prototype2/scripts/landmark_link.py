"""Bounded right/left/repair/cars trial; immutable inputs and independent tower."""
import argparse
import copy
import fcntl
import html
import math
import os
import re
import shutil
import numpy as np
from PIL import Image, ImageDraw
import link_capture as capture

seam=capture.seam;qs=capture.qs;ROOT=capture.ROOT;PARENT=capture.PARENT
CONFIG=seam.P2/'configs/landmark_link.json';SIZE=(1792,1024)
LIMITS={'right':1,'left':1,'repair':1,'cars':1}

def resolve(run):
    if not run or not re.fullmatch(r'\d{8}T\d{12}Z',run):raise ValueError('Invalid run')
    return ROOT/'runs'/run

def points(points):
    return all(len(p)==2 and all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<SIZE[i] for i,v in enumerate(p)) for p in points)

def init():
    cfg=qs.read(CONFIG);src=ROOT/'captures'/cfg['capture_run'];r=qs.read(src/'capture.json')
    if not cfg['source_review']['approved'] or not capture.check(r['samples'])['passed']:raise ValueError('Reviewed aligned source required')
    if cfg['size']!=list(SIZE) or cfg['offsets']!={'right':[768,0],'left':[0,0]} or cfg['limits']!=LIMITS:raise ValueError('Scope changed')
    for ref in cfg['references'].values():
        if len(ref['roads'])!=2 or len(ref['building'])!=2 or not points(ref['roads']+ref['building']) or math.dist(*ref['building'])==0:raise ValueError('Missing source correspondences')
    if qs.sha(src/'source.png')!=r['files']['source.png']:raise ValueError('Source changed')
    pm=qs.read(PARENT/'manifest.json')
    for file in ['jongno-tower_sprite.png','jongno-tower_hit.png','traveler.png']:
        if qs.sha(PARENT/file)!=pm['asset_sha256'][file]:raise ValueError('Parent changed')
    ROOT.mkdir(parents=True,exist_ok=True)
    with (ROOT/'.approval.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (ROOT/'approved_run.json').exists():raise ValueError('Trial already initialized; never reset budget')
        folder=ROOT/'runs'/seam.stamp();folder.mkdir(parents=True)
        for file in ['source.png','capture.json']:shutil.copyfile(src/file,folder/file)
        for file in ['jongno-tower_sprite.png','jongno-tower_hit.png','jongno-tower_source_mask.png','traveler.png','style.png']:shutil.copyfile(PARENT/file,folder/file)
        shutil.copyfile(PARENT/'jongno-tower_overlay.json',folder/'parent_overlay.json')
        qs.write(folder/'config.json',cfg)
        report={'run_id':folder.name,'kind':'landmark-link','model':seam.api.MODEL,'limits':LIMITS,'request_limit':4,'requests':[],
          'generation_closed':False,'input_sha256':{p.name:qs.sha(p) for p in folder.iterdir()},'status':'prepared','user_visual_approval':False}
        qs.write(folder/'report.json',report);qs.write(ROOT/'approved_run.json',{'run_id':folder.name,'request_limit':4})
    print('RUN='+folder.name,flush=True)

def inputs_ok(folder,r):
    if r['model']!=seam.api.MODEL or r['limits']!=LIMITS or r['request_limit']!=4 or qs.read(ROOT/'approved_run.json')['run_id']!=folder.name:raise ValueError('Approval changed')
    for file,digest in r['input_sha256'].items():
        if qs.sha(folder/file)!=digest:raise ValueError('Pinned input changed')

def generate(folder,r,key,name):
    source=Image.open(folder/'source.png').convert('RGB');style=Image.open(folder/'style.png').convert('RGB')
    base=('Use case: style-transfer. One continuous crisp pixel-art Seoul map. Exact parallel orthographic geometry, heading22.5 elevation30, constant128px per100m at every depth. '
          'Image1 is ONLY geometry/layout; Image2 is ONLY pixel style, never its layout. Preserve every road centerline, street width, building footprint, roof direction, facade height and relative size at exact input pixel positions. '
          'Soft neutral diffuse daylight suitable for later dynamic sunset overlay. No strong directional cast shadows; faint contact darkening only. '
          'No perspective, horizon, distant shrinking, autozoom, invented roads/buildings, humans, cars, farm objects, labels, text or panels. Opaque1024 square. ')
    if name=='right':
        prompt=base+'Image3 marks Jongno Tower WHITE: remove that complete tower and its cast shadow, reconstruct ONLY its hidden ground/plaza. Do not replace it with another object. Preserve all surroundings.'
        refs=[source.crop((768,0,1792,1024)),style,Image.open(folder/'jongno-tower_source_mask.png').convert('RGB')]
    elif name=='left':
        if not any(q['name']=='right' and q['status']=='complete' for q in r['requests']):raise ValueError('Right tile required')
        crop=source.crop((0,0,1024,1024));known=Image.new('L',(1024,1024));known.paste(255,(768,0,1024,1024));mixed=crop.copy()
        mixed.paste(Image.open(folder/'right_raw.png').crop((0,0,256,1024)),(768,0))
        prompt=base+'Image3 contains completed neighbor art in the RIGHT256px. Image4 marks that existing overlap WHITE. Continue every roof and road coherently through the overlap without repositioning or duplicating buildings. Keep exact framing and colors.'
        refs=[crop,style,mixed,known.convert('RGB')]
    elif name=='repair':
        rev=qs.read(folder/'review.json')['repair'];box=rev['context'];mask=repair_mask(rev)
        if not rev.get('reason'):raise ValueError('Observed defect required')
        prompt='Use case: precise-object-edit. Image1 is exact edit target, Image2 aligned VWorld geometry, Image3 white-only edit region. Preserve all other pixels, fixed orthographic framing, roads and pixel palette. No blur or perspective. Fix ONLY: '+rev['reason']
        refs=[assembly(folder).crop(box),source.crop(box),mask.crop(box).convert('RGB')]
    else:
        rev=qs.read(folder/'review.json')['traffic']
        if not rev.get('generate') or not rev.get('direction_prompt'):raise ValueError('Reviewed road/direction required')
        prompt='Use case: stylized-concept. Transparent two-view pixel-art car sheet, same small cream hatchback in TWO vertical columns, one car per column. Fixed elevated parallel city camera. '+rev['direction_prompt']+' Generous transparent padding, no ground, shadow, labels, glow or other objects. Image1 is pixel style only.'
        refs=[style]
    return seam.paid(folder,r,key,name,name,prompt,refs,transparent=name=='cars',limits=LIMITS)

def repair_mask(rev):
    box=rev['context'];edit=rev['box']
    if len(box)!=4 or box[2]-box[0]!=1024 or box[3]-box[1]!=1024 or not 0<=box[0]<box[2]<=1792 or box[1]!=0 or box[3]!=1024:raise ValueError('Invalid repair context')
    if len(edit)!=4 or not all(isinstance(v,int) for v in edit) or not box[0]<=edit[0]<edit[2]<=box[2] or not 0<=edit[1]<edit[3]<=1024 or (edit[2]-edit[0])*(edit[3]-edit[1])>262144:raise ValueError('Repair exceeds local scope')
    mask=Image.new('L',SIZE);mask.paste(255,edit);return mask

def ownership(review):
    # A hard ownership boundary, not feathering: whole crossing buildings belong to one tile.
    seamline=review.get('seam',[[896,0],[896,1024]])
    if len(seamline)<2 or seamline[0][1]!=0 or seamline[-1][1]!=1024 or any(not 768<=x<=1024 or not 0<=y<=1024 for x,y in seamline) or any(a[1]>b[1] for a,b in zip(seamline,seamline[1:])):raise ValueError('Invalid ownership seam')
    m=Image.new('L',SIZE);ImageDraw.Draw(m).polygon([(1792,0),*map(tuple,seamline),(1792,1024)],fill=255);return m

def assembly(folder):
    review=qs.read(folder/'review.json') if (folder/'review.json').exists() else {}
    left=Image.new('RGB',SIZE);left.paste(Image.open(folder/'left_raw.png'),(0,0));right=Image.new('RGB',SIZE);right.paste(Image.open(folder/'right_raw.png'),(768,0))
    return Image.composite(right,left,ownership(review))

def geometry(cfg,review):
    result={}
    for tile,src in cfg['references'].items():
        out=review.get('references',{}).get(tile,{})
        roads=out.get('roads',[None,None]);width=out.get('building')
        if len(roads)!=2 or not points([p for p in roads if p is not None]) or width is not None and (len(width)!=2 or not points(width)):raise ValueError('Invalid measured correspondences')
        errors=[math.dist(a,b) if b is not None else None for a,b in zip(src['roads'],roads)]
        ratio=math.dist(*width)/math.dist(*src['building'])-1 if width else None
        passed=len(errors)==2 and all(e is not None and e<=8 for e in errors) and ratio is not None and abs(ratio)<=.15
        result[tile]={'road_error_px':errors,'neighbor_width_change':ratio,'passed':passed}
    return {'tiles':result,'passed':all(x['passed'] for x in result.values()),'note':'Manual image correspondences, not survey/geographic proof'}

def build(folder,r):
    review=qs.read(folder/'review.json');cfg=qs.read(folder/'config.json');plate=assembly(folder)
    if review.get('repair_accepted'):
        if not any(q['name']=='repair' and q['status']=='complete' for q in r['requests']):raise ValueError('Repair unavailable')
        rev=review['repair'];plate.paste(Image.open(folder/'repair_raw.png'),rev['context'][:2],repair_mask(rev).crop(rev['context']))
    plate.save(folder/'before.png');ownership(review).save(folder/'ownership.png')
    sprite=Image.new('RGBA',SIZE);sprite.paste(Image.open(folder/'jongno-tower_sprite.png'),(768,0));sprite.save(folder/'sprite.png')
    hit=Image.new('L',SIZE);hit.paste(Image.open(folder/'jongno-tower_hit.png'),(768,0));hit.save(folder/'hit.png')
    final=Image.alpha_composite(plate.convert('RGBA'),sprite);final.save(folder/'final.png')
    receiver=Image.new('RGBA',SIZE);d=ImageDraw.Draw(receiver)
    for polygon in review['receiver']:
        if len(polygon)<3 or not points(polygon):raise ValueError('Invalid ground receiver')
        d.polygon([tuple(p) for p in polygon],fill=(255,255,255,255))
    receiver.save(folder/'receiver.png')
    parent=qs.read(folder/'parent_overlay.json');overlay=copy.deepcopy(parent)
    for spot in overlay['spots']:spot['xy'][0]+=768
    for oc in overlay['occluders']:
        for p in oc['polygon']:p[0]+=768
    overlay['route']=review['route'];overlay['walk_routes']={'tower':review['route'],'connection':review['connection_route']};overlay['spots'][1:]=review['spots'];overlay['image_sha256']=qs.sha(folder/'final.png')
    overlay['landmark'].update(sprite='sprite.png',hit='hit.png')
    direction=qs.read(folder/'capture.json')['samples'][-1]['east_screen'];length=math.hypot(*direction)
    overlay['sunset']={'kind':'ground-alpha-preview','receiver':'receiver.png','anchor':[1275.1484375,608.33984375],'height':174,'direction':[v/length for v in direction]}
    overlay['generation_edges']=[[a,b] for a,b in zip(review['seam'],review['seam'][1:])]
    assets=['source.png','before.png','final.png','sprite.png','hit.png','receiver.png','traveler.png']
    traffic=review.get('traffic',{})
    if traffic.get('approved'):
        for target,spec in traffic['assets'].items():
            src=folder/spec['file'] if spec.get('generated') else seam.P2/spec['file']
            if qs.sha(src)!=spec['sha256']:raise ValueError('Car source changed')
            im=Image.open(src).convert('RGBA').crop(spec['box']);im.thumbnail(tuple(spec['size']),Image.Resampling.NEAREST);im.save(folder/target);assets.append(target)
        overlay['traffic']=traffic['overlay']
    qs.write(folder/'overlay.json',overlay)
    variants={k:{'label':label,'file':k+'.png','sha256':qs.sha(folder/(k+'.png'))} for k,label in [('source','VWorld 공통 정사영 원본'),('before','연결 배경만'),('final','종로타워 독립 합성')]}
    manifest={'version':1,'kind':'landmark-link','run_id':folder.name,'width':1792,'height':1024,'character':'traveler.png',
      'asset_sha256':{f:qs.sha(folder/f) for f in assets},'overlay_sha256':{'jongno-link':qs.sha(folder/'overlay.json')},
      'scenes':{'jongno-link':{'label':'종로타워 연결·노을','variants':variants,'overlay':'overlay.json','review':review['summary']}}}
    qs.write(folder/'manifest.json',manifest);r['geometry']=geometry(cfg,review);r['status']='awaiting_user_review';qs.write(folder/'report.json',r)
    doc='<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>종로타워 연결·노을</title><style>body{font:16px system-ui;background:#fbf3e4;margin:24px}img{max-width:100%;image-rendering:pixelated}</style><h1>종로타워 2칸 연결·노을 미리보기</h1><p>'+html.escape(review['summary'])+'</p>'
    doc+=f'<a href="../../../../../web/pilot/?view=landmark-link&run={folder.name}">지도·산책·차량·노을 시험</a> · <a href="report.json">프롬프트·비용</a> · <a href="verification.json">검증</a>'
    for kind in ['source','before','final']:doc+=f'<h2>{kind}</h2><img src="{kind}.png">'
    doc+='<h2>노을 미리보기</h2><p>브라우저 검수에서 저장한 노을 결과 · 지면에만 드리운 타워 그림자 · 실제 일조 아님</p><a href="sunset.png">노을 PNG</a>'
    doc+='<p>국토교통부 / VWorld · AI 재해석 · 노을 미리보기이며 실제 일조·실제 길찾기 아님</p>'
    (folder/'index.html').write_text(doc,encoding='utf8');verify(folder,r)

def verify(folder,r):
    inputs_ok(folder,r)
    if len(r['requests'])>4:raise ValueError('Budget exceeded')
    for group,limit in LIMITS.items():
        if sum(q['group']==group for q in r['requests'])>limit:raise ValueError('Slot exceeded')
    for q in r['requests']:
        if q['status']!='complete' or qs.sha(folder/(q['name']+'_raw.png'))!=q['raw_sha256']:raise ValueError('Unresolved/changed request')
        for i,h in enumerate(q['reference_sha256']):
            if qs.sha(folder/f'{q["name"]}_ref{i}.png')!=h:raise ValueError('Reference changed')
    m=qs.read(folder/'manifest.json')
    for file,h in {**m['asset_sha256'],'overlay.json':m['overlay_sha256']['jongno-link']}.items():
        if qs.sha(folder/file)!=h:raise ValueError('Published output changed')
    im=Image.open(folder/'sprite.png');expected=Image.new('RGBA',SIZE);expected.paste(Image.open(folder/'jongno-tower_sprite.png'),(768,0))
    if im.tobytes()!=expected.tobytes():raise ValueError('Tower was changed')
    review=qs.read(folder/'review.json');plate=assembly(folder)
    if review.get('repair_accepted'):
        rev=review['repair'];plate.paste(Image.open(folder/'repair_raw.png'),rev['context'][:2],repair_mask(rev).crop(rev['context']))
    if Image.open(folder/'before.png').convert('RGB').tobytes()!=plate.tobytes() or Image.open(folder/'final.png').convert('RGBA').tobytes()!=Image.alpha_composite(plate.convert('RGBA'),expected).tobytes():raise ValueError('Unexpected composite edit')
    hit=Image.new('L',SIZE);hit.paste(Image.open(folder/'jongno-tower_hit.png'),(768,0))
    if Image.open(folder/'hit.png').tobytes()!=hit.tobytes():raise ValueError('Tower hit mask changed')
    result={'technical_passed':True,'requests':len(r['requests']),'tower_translation_only':True,'geometry':geometry(qs.read(folder/'config.json'),qs.read(folder/'review.json')),'user_visual_approval':False,'manifest_sha256':qs.sha(folder/'manifest.json')}
    qs.write(folder/'verification.json',result);print(result,flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['init','generate','build','verify','close']);p.add_argument('--run');p.add_argument('--asset',choices=list(LIMITS));p.add_argument('--allow-external',action='store_true');a=p.parse_args()
    if a.command=='init':init();return
    folder=resolve(a.run)
    with (folder/'.generation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);r=qs.read(folder/'report.json');inputs_ok(folder,r)
        if a.command=='generate':
            if not a.allow_external or r['generation_closed'] or not a.asset:raise ValueError('Generation not authorized')
            if any(q['name']==a.asset or q['status']!='complete' for q in r['requests']):raise ValueError('No retry')
            key=os.environ.get('OPENROUTER_API_KEY','').strip()
            if not key:raise ValueError('OPENROUTER_API_KEY is missing')
            cap=seam.api.validate_capabilities(seam.api.request_json(f'/images/models/{seam.api.MODEL}/endpoints',key))
            if cap['supported_parameters'].get('input_references',{}).get('max',0)<4:raise ValueError('Four references unavailable')
            generate(folder,r,key,a.asset)
        elif a.command=='build':build(folder,r)
        elif a.command=='verify':verify(folder,r)
        else:r['generation_closed']=True;qs.write(folder/'report.json',r)

if __name__=='__main__':main()
