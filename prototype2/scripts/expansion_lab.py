"""Bounded 5+2+1 OpenRouter extension; old outputs and default pointers are immutable."""
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
import expansion_capture as capture
import seam_lab as seam

qs = seam.api.qs
ROOT = capture.ROOT
CONFIG = seam.P2/'configs/namsan_expansion.json'
PARENT = seam.P2/'eval/vworld/orthographic_lab/runs/20260914T093846326385Z'
WALK = seam.P2/'eval/vworld/projection_walk/runs/20260914T115537004661Z'
CARS = seam.P2/'eval/vworld/seam_lab/runs/20260914T084137369841Z'
PARENT_SHA = 'dec645180d953343109a486af7517ea6df4a5cd386dce41608ded4a3685913d7'
LIMITS = {'map':5, 'repair':2, 'cars':1}
ORDER = {'B':(768,0), 'C':(1536,0), 'D':(0,768), 'E':(0,1536), 'A':(0,0)}
CORE = (128,128,2432,2432)


def reference_views():
    """Offline inspection crops for manual pre-generation annotations."""
    cfg=qs.read(CONFIG);folder=ROOT/'captures'/cfg['capture_run']
    source=Image.open(folder/'source.png')
    for name,(x,y) in ORDER.items():
        source.crop((x,y,x+768,y+768)).save(folder/('reference_'+name+'.png'))


def resolve(run):
    if not run or not re.fullmatch(r'\d{8}T\d{12}Z',run):
        raise ValueError('Invalid run')
    return ROOT/'runs'/run


def init():
    cfg = qs.read(CONFIG)
    src = ROOT/'captures'/cfg['capture_run']
    meta = qs.read(src/'capture.json')
    if not capture.check(meta['samples'])['passed'] or not cfg['source_review']['approved']:
        raise ValueError('Aligned, visually reviewed source required before initialization')
    if cfg['limits']!=LIMITS or cfg['final_size']!=[2304,2304] or cfg['parent_offset']!=[768,768] or cfg['old_edge_edit_limit_px']!=128:
        raise ValueError('Approved extension scope changed')
    if qs.sha(src/'source.png') != cfg['source_sha256'] or qs.sha(PARENT/'mosaic.png') != PARENT_SHA:
        raise ValueError('Source or parent changed')
    if set(cfg['references']) != set(ORDER):
        raise ValueError('Pre-generation correspondences required for all five tiles')
    for ref in cfg['references'].values():
        if len(ref['roads'])!=2 or len(ref['building'])!=2:
            raise ValueError('Two road points and one building width required')
        for point in ref['roads']+ref['building']:
            if len(point)!=2 or not all(isinstance(v,(float,int)) and math.isfinite(v) and 0<=v<=2304 for v in point):raise ValueError('Invalid reference coordinate')
        if math.dist(*ref['building'])==0:raise ValueError('Zero building width')
    ROOT.mkdir(parents=True,exist_ok=True)
    with (ROOT/'.approval.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (ROOT/'approved_run.json').exists():
            raise ValueError('Trial already initialized; never reset request budget')
        folder = ROOT/'runs'/seam.stamp()
        folder.mkdir(parents=True)
        for file,digest in meta['files'].items():
            if qs.sha(src/file)!=digest: raise ValueError('Capture changed')
        for file in ['input.png','source.png','capture.json']:
            shutil.copyfile(src/file,folder/file)
        shutil.copyfile(PARENT/'mosaic.png',folder/'parent.png')
        shutil.copyfile(PARENT/'style.png',folder/'style.png')
        qs.write(folder/'config.json',cfg)
        qs.write(folder/'report.json',{'run_id':folder.name,'kind':'projection-expand','model':seam.api.MODEL,
            'request_limit':8,'limits':LIMITS,'requests':[],'config':cfg,'generation_closed':False,
            'input_sha256':{p.name:qs.sha(p) for p in folder.iterdir()},'status':'prepared','user_visual_approval':False})
        qs.write(ROOT/'approved_run.json',{'run_id':folder.name,'request_limit':8})
        print('RUN='+folder.name,flush=True)
        return folder


def inputs_ok(folder,r):
    if qs.read(ROOT/'approved_run.json')['run_id']!=folder.name or r['limits']!=LIMITS or r['request_limit']!=8 or r['model']!=seam.api.MODEL:
        raise ValueError('Approval/model changed')
    for file,digest in r['input_sha256'].items():
        if qs.sha(folder/file)!=digest: raise ValueError('Pinned input changed')
    if (folder/'config.json').exists() and qs.read(folder/'config.json')!=r['config']:
        raise ValueError('Pre-generation configuration changed')


def assembly(folder,r):
    canvas=Image.new('RGB',(2560,2560));known=Image.new('L',canvas.size)
    owner=np.zeros((2560,2560),dtype=np.uint8)
    canvas.paste(Image.open(folder/'parent.png'),(896,896))
    known.paste(255,(896,896,2432,2432));owner[896:2432,896:2432]=1
    for i,(name,(x,y)) in enumerate(ORDER.items()):
        req=next((a for a in r['requests'] if a['name']=='map_'+name),None)
        if not req: break
        if req['status']!='complete' or qs.sha(folder/(req['name']+'_raw.png'))!=req['raw_sha256']:
            raise ValueError('Incomplete or changed request; no retry')
        raw=Image.open(folder/(req['name']+'_raw.png')).convert('RGB')
        box=(x,y,x+1024,y+1024);mask=known.crop(box)
        canvas.paste(Image.composite(canvas.crop(box),raw,mask),(x,y))
        part=owner[y:y+1024,x:x+1024];part[np.asarray(mask)==0]=i+2
        known.paste(255,box)
    return canvas,known,owner


def generate(folder,r,key):
    source=Image.open(folder/'input.png').convert('RGB');style=Image.open(folder/'style.png').convert('RGB')
    for name,(x,y) in ORDER.items():
        if any(a['name']=='map_'+name for a in r['requests']):
            assembly(folder,r)  # Completed outputs may be resumed; never request them twice.
            continue
        canvas,known,_=assembly(folder,r);box=(x,y,x+1024,y+1024)
        crop=source.crop(box);mask=known.crop(box)
        mixed=Image.composite(canvas.crop(box),crop,mask)
        prompt=('Use case: style-transfer. Extend one continuous orthographic pixel-art Seoul map. '
          'Image 1 is the ONLY exact building, road and terrain geometry reference. Image 2 is ONLY pixel style, never its farm layout or objects. '
          'Image 3 is previously completed map art at exact aligned coordinates. Image 4 is a preservation guide: WHITE is locked previous art, BLACK is the new area. '
          'Continue roofs, roads, walls and trees through every boundary, including buildings cut by the boundary. '
          'Preserve parallel projection, framing, footprint, building count, roof direction and relative height. Same constant scale at every depth; '
          'no vanishing point, horizon, enlarged foreground or distant shrinkage. Preserve hill slopes, ridges and winding roads. '
          'Match existing green palette, clear pixel clusters, roof detail and restrained shadows. No new landmarks, vehicles, people, labels, text, farmland or divided panels. '
          'Return one opaque 1024 square map tile.')
        if r['config']['source_review'].get('allow_inferred_buildings'):
            prompt+=(' The user approved an experimental continuation despite incomplete 3D source. Where ONLY aerial roofs are present, '
                     'infer restrained low/mid-rise walls under those existing roofs to match the neighboring pixel city. '
                     'Keep the visible roof footprint, road corridors and blocks anchored. These heights are artistic estimates, not real measurements. '
                     'Do not add landmark towers or invented roads, and do not make the distant area a flat photo-texture.')
        else:
            prompt+=' Do not invent 3D masses where the source is unreadable.'
        seam.paid(folder,r,key,'map','map_'+name,prompt,[crop,style,mixed,mask.convert('RGB')],limits=LIMITS)
        canvas,_,_=assembly(folder,r);canvas.crop(CORE).save(folder/'progress.png')
    canvas,known,owner=assembly(folder,r)
    if known.crop(CORE).getextrema()!=(255,255): raise ValueError('Missing final coverage')
    canvas.crop(CORE).save(folder/'before.png');Image.fromarray(owner[128:2432,128:2432]).save(folder/'ownership.png')
    r['status']='awaiting_review';qs.write(folder/'report.json',r)


def protected():
    # Old local x>=128 AND y>=128, including all tower/walk pixels.
    m=np.zeros((2304,2304),dtype=bool);m[896:2304,896:2304]=True
    return m


def edit_mask(spec):
    box=spec['context_box'];edit=spec['edit_box']
    if len(box)!=4 or box[2]-box[0]!=1024 or box[3]-box[1]!=1024 or not (0<=box[0]<box[2]<=2304 and 0<=box[1]<box[3]<=2304):
        raise ValueError('Invalid repair context')
    if not (box[0]<=edit[0]<edit[2]<=box[2] and box[1]<=edit[1]<edit[3]<=box[3]):
        raise ValueError('Invalid repair edit box')
    mask=np.zeros((2304,2304),dtype=np.uint8);mask[edit[1]:edit[3],edit[0]:edit[2]]=255
    if np.any(mask[protected()]):raise ValueError('Repair touches protected parent interior')
    return Image.fromarray(mask)


def repair(folder,r,key,name):
    if name not in ['repair_1','repair_2']:raise ValueError('Invalid repair slot')
    spec=qs.read(folder/'review.json')['repairs'][name]
    if not spec['needed'] or not spec['reason']:raise ValueError('Visual defect required')
    mask=edit_mask(spec);box=spec['context_box']
    base=Image.open(folder/'before.png').convert('RGB')
    prompt=('Use case: precise-object-edit. Image 1 is the exact pixel-art target; image 2 is aligned VWorld source geometry; '
            'image 3 is the edit guide: modify WHITE only, preserve BLACK. Keep constant orthographic scale, palette, buildings and roads. '
            'No blur, new objects, new landmarks, text or perspective. Repair only this observed defect: '+spec['reason'])
    raw=seam.paid(folder,r,key,'repair',name,prompt,[base.crop(box),Image.open(folder/'source.png').crop(box),mask.crop(box).convert('RGB')],limits=LIMITS)
    candidate=base.copy();candidate.paste(raw.convert('RGB'),box[:2],mask.crop(box));candidate.save(folder/(name+'_candidate.png'))
    r.setdefault('repairs',{})[name]=spec;qs.write(folder/'report.json',r)


def cars(folder,r,key):
    spec=qs.read(folder/'review.json')['traffic']
    if not spec['generate'] or not spec['direction_prompt']:raise ValueError('Source-selected road and direction required')
    prompt=('Use case: stylized-concept. Transparent two-view pixel-art car sheet. Exactly two vertical columns, one isolated cream city hatchback in each, '
            'same car, fixed elevated city-map camera, crisp pixel clusters, clear front and rear. '+spec['direction_prompt']+
            ' Generous transparent padding, no ground, cast shadow, labels, grid, glow, scenery or extra cars. Image 1 is only palette/pixel style. Genuine alpha background.')
    seam.paid(folder,r,key,'cars','cars',prompt,[Image.open(folder/'before.png').resize((1024,1024),Image.Resampling.BOX)],transparent=True,limits=LIMITS)


def edges(owner):
    out=[]
    for vertical in [True,False]:
        a=owner if vertical else owner.T
        changes=a[:,1:]!=a[:,:-1]
        for x in np.flatnonzero(changes.any(axis=0)):
            ys=np.flatnonzero(changes[:,x]);splits=np.split(ys,np.flatnonzero(np.diff(ys)>1)+1)
            for part in splits:
                line=[[int(x+1),int(part[0])],[int(x+1),int(part[-1]+1)]]
                out.append(line if vertical else [p[::-1] for p in line])
    return out


def geometry(r,review):
    rows=[]
    for name,ref in r['config']['references'].items():
        found=review.get('geometry',{}).get(name,{})
        roads=found.get('roads',[None,None]);building=found.get('building')
        errors=[math.dist(a,b) if b is not None else None for a,b in zip(ref['roads'],roads)]
        ratio=math.dist(*building)/math.dist(*ref['building'])-1 if building else None
        measured=len(errors)==2 and all(v is not None for v in errors) and ratio is not None
        rows.append({'tile':name,'road_errors_px':errors,'building_width_change':ratio,'measured':measured,
                     'passed':measured and max(errors)<=8 and abs(ratio)<=.15})
    return {'tiles':rows,'passed':set(r['config']['references'])==set(ORDER) and all(a['passed'] for a in rows),'method':'Manual image correspondences; not geographic proof'}


def build(folder,r):
    old_manifest=qs.read(WALK/'manifest.json')
    for file,digest in old_manifest['asset_sha256'].items():
        if qs.sha(WALK/file)!=digest:raise ValueError('Walk parent asset changed')
    if qs.sha(WALK/'overlay.json')!=old_manifest['overlay_sha256']['namsan']:
        raise ValueError('Walk parent overlay changed')
    canvas,known,owner=assembly(folder,r)
    if known.crop(CORE).getextrema()!=(255,255):raise ValueError('Five complete map tiles required')
    before=canvas.crop(CORE);before.save(folder/'before.png');final=before.copy()
    review=qs.read(folder/'review.json')
    for name,spec in r.get('repairs',{}).items():
        if review.get('decisions',{}).get(name,{}).get('accepted'):
            mask=edit_mask(spec);box=spec['context_box']
            final.paste(Image.open(folder/(name+'_raw.png')).convert('RGB'),box[:2],mask.crop(box))
    final.save(folder/'final.png')
    overlay=copy.deepcopy(qs.read(WALK/'overlay.json'))
    shift=lambda p:[v+768 for v in p]
    for s in overlay['spots']:s['xy']=shift(s['xy'])
    for p in overlay['route']['points']:p['xy']=shift(p['xy'])
    for o in overlay['occluders']:o['polygon']=[shift(p) for p in o['polygon']]
    overlay['image_sha256']=qs.sha(folder/'final.png');overlay['generation_edges']=edges(owner[128:2432,128:2432])
    hit=Image.new('L',(2304,2304));hit.paste(Image.open(WALK/'tower_hit.png'),(768,768));hit.save(folder/'tower_hit.png')
    shutil.copyfile(WALK/'traveler.png',folder/'traveler.png')
    traffic=review.get('traffic',{})
    if traffic.get('accepted'):
        if traffic['generate']:
            raw=Image.open(folder/'cars_raw.png').convert('RGBA')
            for i,name in enumerate(['car_se.png','car_nw.png']):
                im=raw.crop((i*512,0,(i+1)*512,1024));box=im.getchannel('A').point(lambda v:255 if v>=128 else 0).getbbox()
                if not box:raise ValueError('Empty car sprite')
                im=im.crop(box);im.thumbnail((traffic['sprite_max_px'],)*2,Image.Resampling.BOX)
                im.putalpha(im.getchannel('A').point(lambda v:255 if v>=128 else 0));im.save(folder/name)
        else:
            for name in ['car_se.png','car_nw.png']:
                if qs.sha(CARS/name)!=qs.read(CARS/'manifest.json')['asset_sha256'][name]:raise ValueError('Car parent changed')
                shutil.copyfile(CARS/name,folder/name)
        overlay['traffic']={'lanes':traffic['lanes'],'speed':28,'occluders':traffic['occluders']}
    qs.write(folder/'overlay.json',overlay)
    files=['source.png','before.png','final.png','tower_hit.png','traveler.png']+(['car_se.png','car_nw.png'] if overlay.get('traffic') else [])
    variants={k:{'label':label,'file':k+'.png','sha256':qs.sha(folder/(k+'.png'))} for k,label in [('source','정사영 원본'),('before','확장 보정 전'),('final','3×3 확장 시험')]}
    manifest={'version':1,'kind':'projection-expand','run_id':folder.name,'width':2304,'height':2304,'parent_run':PARENT.name,
        'character':'traveler.png','asset_sha256':{f:qs.sha(folder/f) for f in files},'overlay_sha256':{'namsan':qs.sha(folder/'overlay.json')},
        'scenes':{'namsan':{'label':'남산 · 도심 3×3 확장','variants':variants,'overlay':'overlay.json','review':review['summary']+' · 수작업 경로·실제 교통 아님'}}}
    qs.write(folder/'manifest.json',manifest)
    r['status']='awaiting_user_review';r['geometry']=geometry(r,review);r['final_sha256']=qs.sha(folder/'final.png')
    qs.write(folder/'report.json',r)
    doc='<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>남산 3×3 확장</title><style>body{font:16px system-ui;background:#fbf3e4;margin:24px}img{max-width:100%;image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
    doc+=f'<h1>남산 3×3 확장 시험</h1><a href="../../../../../web/pilot/?view=projection-expand&run={folder.name}">지도·차량 시험 열기</a><p>{html.escape(review["summary"])}</p><p>국토교통부 / VWorld · AI 재해석 · 로컬 검수용</p>'
    doc+='<p><a href="report.json">프롬프트·비용</a> · <a href="verification.json">검증</a> · <a href="review.json">수작업 검수</a></p>'
    for f in ['source','before','final']:doc+=f'<h2>{f}</h2><img src="{f}.png">'
    (folder/'index.html').write_text(doc,encoding='utf8')
    verify(folder,r)


def verify(folder,r):
    inputs_ok(folder,r)
    for req in r['requests']:
        if req['status']!='complete' or qs.sha(folder/(req['name']+'_raw.png'))!=req['raw_sha256']:raise ValueError('Raw request unresolved/changed')
        for i,h in enumerate(req['reference_sha256']):
            if qs.sha(folder/f'{req["name"]}_ref{i}.png')!=h:raise ValueError('Request reference changed')
    if len(r['requests'])>8 or any(sum(q['group']==k for q in r['requests'])>n for k,n in LIMITS.items()):raise ValueError('Budget exceeded')
    before,known,_=assembly(folder,r);before=before.crop(CORE)
    if known.crop(CORE).getextrema()!=(255,255) or not np.array_equal(np.asarray(before),np.asarray(Image.open(folder/'before.png'))):raise ValueError('Assembly mismatch')
    review=qs.read(folder/'review.json');expected=before.copy()
    for name,spec in r.get('repairs',{}).items():
        if review.get('decisions',{}).get(name,{}).get('accepted'):
            box=spec['context_box'];expected.paste(Image.open(folder/(name+'_raw.png')).convert('RGB'),box[:2],edit_mask(spec).crop(box))
    final=np.asarray(Image.open(folder/'final.png'))
    if not np.array_equal(final,np.asarray(expected)):raise ValueError('Unexpected final edits')
    old=np.asarray(Image.open(folder/'parent.png'))
    if not np.array_equal(final[896:,896:],old[128:,128:]):raise ValueError('Protected interior changed')
    m=qs.read(folder/'manifest.json')
    for file,digest in m['asset_sha256'].items():
        if qs.sha(folder/file)!=digest:raise ValueError('Published asset changed')
    if qs.sha(folder/'overlay.json')!=m['overlay_sha256']['namsan']:raise ValueError('Overlay changed')
    result={'technical_passed':True,'protected_parent_identical':True,'full_coverage':True,'requests':len(r['requests']),
            'geometry':geometry(r,review),'user_visual_approval':False,'manifest_sha256':qs.sha(folder/'manifest.json')}
    qs.write(folder/'verification.json',result)
    print(result,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['references','init','generate','repair','cars','build','verify','close'])
    p.add_argument('--run');p.add_argument('--name');p.add_argument('--allow-external',action='store_true');a=p.parse_args()
    if a.command=='references':reference_views();return
    if a.command=='init':init();return
    folder=resolve(a.run)
    with (folder/'.generation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        r=qs.read(folder/'report.json');inputs_ok(folder,r)
        if a.command in ['generate','repair','cars']:
            if not a.allow_external or r['generation_closed']:raise ValueError('External generation not authorized or closed')
            key=os.environ.get('OPENROUTER_API_KEY','').strip()
            if not key:raise ValueError('OPENROUTER_API_KEY is missing')
            if any(q['status']!='complete' for q in r['requests']):raise ValueError('Unresolved billing; no retry')
            cap=seam.api.validate_capabilities(seam.api.request_json(f'/images/models/{seam.api.MODEL}/endpoints',key))
            if cap['supported_parameters'].get('input_references',{}).get('max',0)<4:raise ValueError('Four references required')
            if a.command=='cars' and 'transparent' not in cap['supported_parameters'].get('background',{}).get('values',[]):raise ValueError('Transparent output unsupported')
            if a.command=='generate':generate(folder,r,key)
            elif a.command=='repair':repair(folder,r,key,a.name)
            else:cars(folder,r,key)
        elif a.command=='build':build(folder,r)
        elif a.command=='verify':verify(folder,r)
        else:r['generation_closed']=True;qs.write(folder/'report.json',r)


if __name__=='__main__':main()
