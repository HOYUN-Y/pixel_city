"""Independent landmark trial. Six single-use slots, source gates, no provider fallback."""
import argparse
import copy
import fcntl
import html
import math
import os
from pathlib import Path
import re
import shutil
import numpy as np
from PIL import Image, ImageDraw
import landmark_capture as capture

seam=capture.seam;qs=capture.qs;ROOT=capture.ROOT;CONFIG=capture.CONFIG
SOURCES=seam.P2/'configs/landmark_pilot_sources.json'
SCENES=('gwanghwamun','jongno-tower')
LIMITS={scene+'_'+kind:1 for scene in SCENES for kind in ('background','sprite','repair')}
WALK=seam.P2/'eval/vworld/projection_walk/runs/20260914T115537004661Z'


def resolve(run):
    if not run or not re.fullmatch(r'\d{8}T\d{12}Z',run):raise ValueError('Invalid run')
    return ROOT/'runs'/run


def silhouette(spec):
    mask=Image.new('L',(1024,1024));d=ImageDraw.Draw(mask)
    d.polygon([tuple(p) for p in spec['outline']],fill=255)
    for polygon in spec['holes']:d.polygon([tuple(p) for p in polygon],fill=0)
    return mask


def validate_source(spec):
    for polygon in [spec['outline'],*spec['holes']]:
        if len(polygon)<3:raise ValueError('Missing outline')
        for p in polygon:
            if len(p)!=2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<1024 for v in p):raise ValueError('Invalid source polygon')
    box=spec['context'];bounds=silhouette(spec).getbbox()
    if not bounds or len(box)!=4 or not all(isinstance(v,int) for v in box) or box[2]-box[0]!=box[3]-box[1] or not 0<=box[0]<box[2]<=1024 or not 0<=box[1]<box[3]<=1024:
        raise ValueError('Invalid square context')
    if any(bounds[i]<box[i] for i in [0,1]) or any(bounds[i]>box[i] for i in [2,3]):raise ValueError('Clipped source silhouette')
    if len(spec['roads'])!=2 or len(spec['neighbor_width'])!=2:raise ValueError('Pre-generation correspondences required')
    for p in [spec['anchor'],*spec['roads'],*spec['neighbor_width']]:
        if len(p)!=2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<1024 for v in p):raise ValueError('Invalid reference point')
    if math.dist(*spec['neighbor_width'])==0:raise ValueError('Zero reference width')


def init():
    cfg=qs.read(CONFIG);sources=qs.read(SOURCES);approved={};blocked={}
    if cfg['request_limits']!=LIMITS or cfg['size']!=1024 or cfg['width_m']!=800:raise ValueError('Approved scope changed')
    for scene in SCENES:
        spec=sources.get(scene,{})
        if not spec.get('approved'):blocked[scene]=spec.get('review','Source not reviewed');continue
        validate_source(spec)
        if not re.fullmatch(r'\d{8}T\d{12}Z/'+scene,spec['capture']):raise ValueError('Invalid capture path')
        src=ROOT/'captures'/spec['capture'];r=qs.read(src/'capture.json')
        if r['scene']!=scene or not capture.check(r['samples'])['passed']:raise ValueError('Source projection invalid')
        for file,digest in r['files'].items():
            if qs.sha(src/file)!=digest:raise ValueError('Source changed')
        approved[scene]=spec
    if not approved:raise ValueError('No visually approved source; no AI run created')
    ROOT.mkdir(parents=True,exist_ok=True)
    with (ROOT/'.approval.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (ROOT/'approved_run.json').exists():raise ValueError('Trial already initialized; never reset budget')
        folder=ROOT/'runs'/seam.stamp();folder.mkdir(parents=True)
        for scene,spec in approved.items():
            src=ROOT/'captures'/spec['capture']
            shutil.copyfile(src/'source.png',folder/(scene+'_source.png'))
            shutil.copyfile(src/'capture.json',folder/(scene+'_capture.json'))
            silhouette(spec).save(folder/(scene+'_source_mask.png'))
        shutil.copyfile(seam.P2/cfg['style_reference'],folder/'style.png')
        wm=qs.read(WALK/'manifest.json')
        if qs.sha(WALK/'traveler.png')!=wm['asset_sha256']['traveler.png']:raise ValueError('Traveler changed')
        shutil.copyfile(WALK/'traveler.png',folder/'traveler.png')
        qs.write(folder/'config.json',cfg);qs.write(folder/'sources.json',approved)
        r={'run_id':folder.name,'kind':'landmark-pilot','model':seam.api.MODEL,'request_limit':6,'limits':LIMITS,
           'requests':[],'sources':approved,'blocked_scenes':blocked,'generation_closed':False,
           'input_sha256':{p.name:qs.sha(p) for p in folder.iterdir()},'user_visual_approval':False,'status':'prepared'}
        qs.write(folder/'report.json',r);qs.write(ROOT/'approved_run.json',{'run_id':folder.name,'request_limit':6})
    print('RUN='+folder.name,flush=True)


def inputs_ok(folder,r):
    if r['model']!=seam.api.MODEL or r['request_limit']!=6 or r['limits']!=LIMITS or qs.read(ROOT/'approved_run.json')['run_id']!=folder.name:raise ValueError('Approval/model changed')
    for file,digest in r['input_sha256'].items():
        if qs.sha(folder/file)!=digest:raise ValueError('Pinned input changed')
    if qs.read(folder/'sources.json')!=r['sources']:raise ValueError('Source approval changed')


def generate(folder,r,key,scene,kind):
    if scene not in r['sources']:raise ValueError('Scene has no approved source')
    spec=r['sources'][scene];source=Image.open(folder/(scene+'_source.png')).convert('RGB')
    guide=Image.open(folder/(scene+'_source_mask.png'));style=Image.open(folder/'style.png').convert('RGB')
    label=qs.read(folder/'config.json')['scenes'][scene]['label']
    if kind=='background':
        prompt=('Use case: style-transfer. Asset: one continuous orthographic pixel-art Seoul map background plate. '
            'Image 1 is the ONLY layout/geometry reference. Image 2 is ONLY pixel style, not its layout or objects. '
            'Image 3 marks the target landmark silhouette WHITE, surrounding scenery BLACK. '
            'Render the surroundings as crisp coherent pixel art, but REMOVE the entire '+label+' landmark marked white, including its attached cast shadow. '
            'Reconstruct the small hidden background using adjacent pavement/courtyard and buildings; do not put a replacement building there. '
            'Preserve surrounding roads, ground footprint, roof direction and other building positions. '
            'Fixed parallel orthographic camera, heading 22.5 degrees and elevation 30 degrees. Constant scale at every depth. '
            'Soft diffuse daylight, restrained contact shadows only, no strong directional cast shadows. '
            'No perspective, vanishing point, foreground enlargement, distant shrinkage, text, labels, people, vehicles, new landmarks or farm objects. Opaque 1024 square.')
        refs=[source,style,guide.convert('RGB')]
    elif kind=='sprite':
        box=spec['context'];cut=source.crop(box);mask=guide.crop(box)
        cut.putalpha(mask)
        prompt=('Use case: stylized-concept. Asset: one genuinely transparent independent pixel-art '+label+' landmark. '
            'Image 1 is the actual VWorld object cutout, the ONLY structure and camera reference. '
            'Image 2 is ONLY pixel style. Image 3 is the exact silhouette/framing guide: WHITE object, BLACK transparent. '
            'Preserve the object exact position, size, proportions, roof and support geometry within this square. '
            'Image 4 is surrounding source context ONLY; never copy its buildings or ground into the sprite. '
            'Constant parallel orthographic camera, no perspective or vanishing point, no independent auto-zoom. '
            'Soft diffuse daylight, readable pixel clusters, no strong directional shadow. '
            'The empty space under Jongno Tower upper structure must be genuinely transparent, not a dark painted window. '
            'For Gwanghwamun preserve two roof levels, pale stone platform and three gate arches; do not invent extra palace buildings. '
            'No ground, scenery, labels, added objects, glow, opaque backdrop or checkerboard. Return one transparent 1024 square with exactly the reference framing.')
        refs=[cut.resize((1024,1024),Image.Resampling.NEAREST),style,mask.convert('RGB').resize((1024,1024),Image.Resampling.NEAREST),source]
    else:
        review=qs.read(folder/'review.json')['scenes'][scene];repair=review['repair']
        if repair['target'] not in ['background','sprite'] or not repair.get('reason'):raise ValueError('Observed defect required')
        target=repair['target'];base=Image.open(folder/(scene+'_'+target+'_raw.png'))
        prompt=('Use case: precise-object-edit. Image 1 is the exact candidate to repair; image 2 is the original structure reference. '
                'Keep position, framing, scale, palette and all unrelated pixels. Fix only: '+repair['reason'])
        if target=='sprite':
            prompt=('Use case: precise-object-edit. Image 1 is a WRONG candidate, style only. Image 2 is the actual VWorld camera/structure. '
                    'Image 3 is the REQUIRED exact silhouette and output placement: white object, black transparent. Image 4 is pixel style only. '
                    'Correct the candidate to match Image 2 and 3, NOT the incorrect camera, size or placement in Image 1. '
                    'Keep genuine transparency and structural gaps; no ground, backdrop, glow or shadow. Fix: '+repair['reason'])
            refs=[base,source.crop(spec['context']).resize((1024,1024),Image.Resampling.NEAREST),guide.crop(spec['context']).convert('RGB').resize((1024,1024),Image.Resampling.NEAREST),style]
        else:
            mask=repair_mask(repair);prompt+=' Image 3 is the edit guide: change WHITE only, preserve BLACK.'
            refs=[base,source,mask.convert('RGB')]
    name=scene+'_'+kind
    raw=seam.paid(folder,r,key,name,name,prompt,refs,transparent=kind=='sprite' or kind=='repair' and target=='sprite',limits=LIMITS)
    if kind=='repair':r.setdefault('repairs',{})[scene]=repair;qs.write(folder/'report.json',r)
    return raw


def repair_mask(spec):
    box=spec['edit_box']
    if len(box)!=4 or not all(isinstance(v,int) for v in box) or not 0<=box[0]<box[2]<=1024 or not 0<=box[1]<box[3]<=1024:raise ValueError('Invalid local repair')
    if (box[2]-box[0])*(box[3]-box[1])>1024*1024/4:raise ValueError('Repair is not local')
    m=Image.new('L',(1024,1024));m.paste(255,box);return m


def candidate(folder,r,scene,kind,review):
    im=Image.open(folder/(scene+'_'+kind+'_raw.png')).copy()
    fix=r.get('repairs',{}).get(scene)
    if fix and fix['target']==kind and review.get('repair_accepted'):
        raw=Image.open(folder/(scene+'_repair_raw.png'))
        if kind=='sprite':im=raw.copy()
        else:im.paste(raw,(0,0),repair_mask(fix))
    return im


def compose(folder,r,scene,review):
    spec=r['sources'][scene];box=spec['context'];side=box[2]-box[0]
    plate=candidate(folder,r,scene,'background',review).convert('RGBA')
    raw=candidate(folder,r,scene,'sprite',review).convert('RGBA')
    alpha=np.asarray(raw.getchannel('A'))
    if not np.any(alpha==0) or not np.any(alpha>=128):raise ValueError('Missing transparent object')
    offset=review.get('sprite_offset',[0,0])
    if len(offset)!=2 or not all(isinstance(v,int) and abs(v)<=16 for v in offset):raise ValueError('Unreviewed large translation')
    scale=review.get('sprite_scale',side/1024)
    if not isinstance(scale,(int,float)) or not math.isfinite(scale) or not .5*side/1024<=scale<=1.5*side/1024:raise ValueError('Invalid uniform source-fit scale')
    rendered_side=round(1024*scale)
    sprite=Image.new('RGBA',(1024,1024));sprite.paste(raw.resize((rendered_side,rendered_side),Image.Resampling.BOX),(box[0]+offset[0],box[1]+offset[1]))
    # Use generated transparency for picking/occlusion; do not punch source-shaped holes.
    hit=sprite.getchannel('A').point(lambda v:255 if v>=128 else 0)
    bbox=hit.getbbox()
    if not bbox:raise ValueError('Empty sprite')
    source_bbox=silhouette(spec).getbbox()
    delta=[(bbox[i+2]-bbox[i])/(source_bbox[i+2]-source_bbox[i])-1 for i in [0,1]]
    anchor=review.get('generated_anchor')
    anchor_error=math.dist(anchor,spec['anchor']) if anchor else None
    geometry={'size_change':delta,'anchor_error_px':anchor_error,'landmark_passed':anchor_error is not None and anchor_error<=4 and all(abs(v)<=.05 for v in delta),
              'uniform_scale':rendered_side/1024,'placement_offset':offset,'source_bbox':source_bbox,'rendered_bbox':bbox,
              'note':'Measured after documented uniform placement; matching bounding size is not proof of matching internal geometry or geographic accuracy.'}
    roads=review.get('roads',[None,None]);width=review.get('neighbor_width')
    errors=[math.dist(a,b) if b is not None else None for a,b in zip(spec['roads'],roads)]
    ratio=math.dist(*width)/math.dist(*spec['neighbor_width'])-1 if width else None
    geometry.update(road_errors_px=errors,neighbor_width_change=ratio,background_passed=len(errors)==2 and all(v is not None and v<=8 for v in errors) and ratio is not None and abs(ratio)<=.15)
    # Do not silently punch a hole in an incorrectly generated solid building.
    holes=Image.new('L',(1024,1024));d=ImageDraw.Draw(holes)
    for poly in spec['holes']:d.polygon([tuple(p) for p in poly],fill=255)
    hole=np.asarray(holes)>0
    geometry['source_void_opaque_pixels']=int(np.count_nonzero(np.asarray(hit)[hole]))
    geometry['source_void_alignment_passed']=geometry['source_void_opaque_pixels']==0
    geometry['void_passed']=not spec['holes'] or bool(review.get('void_reviewed') and review.get('void_valid'))
    geometry['overall_geometry_passed']=bool(geometry['landmark_passed'] and geometry['background_passed'] and geometry['void_passed'] and geometry['source_void_alignment_passed'])
    return plate,sprite,hit,Image.alpha_composite(plate,sprite),geometry


def build(folder,r):
    review=qs.read(folder/'review.json');scenes={};hashes={'traveler.png':qs.sha(folder/'traveler.png')};overlays={};metrics={}
    for scene,spec in r['sources'].items():
        sr=review.get('scenes',{}).get(scene,{})
        if not sr.get('publish'):continue
        needed=[scene+'_'+k for k in ['background','sprite']]
        if any(not any(q['name']==n and q['status']=='complete' for q in r['requests']) for n in needed):raise ValueError('Two complete scene assets required')
        plate,sprite,hit,final,geometry=compose(folder,r,scene,sr);metrics[scene]=geometry
        for kind,im in [('before',plate),('sprite',sprite),('hit',hit),('final',final)]:im.save(folder/(scene+'_'+kind+'.png'))
        route=copy.deepcopy(sr['route']);spots=copy.deepcopy(sr['spots'])
        overlay={'image_sha256':qs.sha(folder/(scene+'_final.png')),'spots':spots,'route':route,'occluders':[{'id':'landmark-body','polygon':spec['outline']}],
                 'landmark':{'id':scene,'mode':'independent','sprite':scene+'_sprite.png','hit':scene+'_hit.png','occluder_id':'landmark-body'},'generation_edges':[]}
        qs.write(folder/(scene+'_overlay.json'),overlay);overlays[scene]=qs.sha(folder/(scene+'_overlay.json'))
        variants={k:{'label':label,'file':scene+'_'+k+'.png','sha256':qs.sha(folder/(scene+'_'+k+'.png'))} for k,label in [('source','VWorld 정사영 원본'),('before','주변 배경만'),('final','독립 외형 합성')]}
        scenes[scene]={'label':qs.read(folder/'config.json')['scenes'][scene]['label'],'variants':variants,'overlay':scene+'_overlay.json','review':sr['summary']+' · AI 재해석·수작업 가림·실제 길찾기 아님'}
        for kind in ['source','before','sprite','hit','final']:hashes[scene+'_'+kind+'.png']=qs.sha(folder/(scene+'_'+kind+'.png'))
    if not scenes:raise ValueError('No publishable scene')
    manifest={'version':1,'kind':'landmark-pilot','run_id':folder.name,'width':1024,'height':1024,'character':'traveler.png','asset_sha256':hashes,'overlay_sha256':overlays,'scenes':scenes,'blocked_scenes':r['blocked_scenes']}
    qs.write(folder/'manifest.json',manifest);r['geometry']=metrics;r['status']='awaiting_user_review';qs.write(folder/'report.json',r)
    doc='<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>독립 랜드마크 시험</title><style>body{font:16px system-ui;background:#fbf3e4;margin:24px}img{max-width:100%;image-rendering:pixelated}section{margin-bottom:40px}</style><h1>광화문·종로타워 독립 외형 시험</h1><p>국토교통부 / VWorld · AI 재해석 · 로컬 검수용 · 사용자 미감 미승인</p><a href="report.json">프롬프트·비용</a> · <a href="verification.json">검증</a>'
    for scene,s in scenes.items():
        doc+=f'<section><h2>{html.escape(s["label"])}</h2><a href="../../../../../web/pilot/?view=landmark-pilot&run={folder.name}&scene={scene}">지도·선택·보행 시험</a><p>{html.escape(s["review"])}</p>'
        doc+=f'<p><a href="{scene}_sprite_raw.png">독립 외형 원출력</a> · <a href="{scene}_sprite.png">배치된 투명 외형</a></p>'
        if scene in r.get('repairs',{}):doc+=f'<p><a href="{scene}_repair_raw.png">보정 원출력</a></p>'
        for kind in ['source','before','final']:doc+=f'<h3>{kind}</h3><img src="{scene}_{kind}.png">'
        doc+='</section>'
    (folder/'index.html').write_text(doc,encoding='utf8');verify(folder,r)


def verify(folder,r):
    inputs_ok(folder,r)
    if len(r['requests'])>6:raise ValueError('Budget exceeded')
    for group,limit in LIMITS.items():
        if sum(q['group']==group for q in r['requests'])>limit:raise ValueError('Slot budget exceeded')
    for req in r['requests']:
        if req['status']!='complete' or qs.sha(folder/(req['name']+'_raw.png'))!=req['raw_sha256']:raise ValueError('Unresolved or changed raw output')
        for i,h in enumerate(req['reference_sha256']):
            if qs.sha(folder/f'{req["name"]}_ref{i}.png')!=h:raise ValueError('Reference changed')
    manifest=qs.read(folder/'manifest.json');review=qs.read(folder/'review.json');metrics={}
    for scene in manifest['scenes']:
        plate,sprite,hit,final,geometry=compose(folder,r,scene,review['scenes'][scene]);metrics[scene]=geometry
        for kind,expected in [('before',plate),('sprite',sprite),('hit',hit),('final',final)]:
            if Image.open(folder/(scene+'_'+kind+'.png')).tobytes()!=expected.tobytes():raise ValueError('Unexpected composition edits')
        if qs.sha(folder/(scene+'_overlay.json'))!=manifest['overlay_sha256'][scene]:raise ValueError('Overlay changed')
    for file,digest in manifest['asset_sha256'].items():
        if qs.sha(folder/file)!=digest:raise ValueError('Published asset changed')
    result={'technical_passed':True,'requests':len(r['requests']),'geometry':metrics,'user_visual_approval':False,'manifest_sha256':qs.sha(folder/'manifest.json')}
    qs.write(folder/'verification.json',result);print(result,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['init','generate','build','verify','close']);p.add_argument('--run');p.add_argument('--scene',choices=SCENES);p.add_argument('--asset',choices=['background','sprite','repair']);p.add_argument('--allow-external',action='store_true');a=p.parse_args()
    if a.command=='init':init();return
    folder=resolve(a.run)
    with (folder/'.generation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);r=qs.read(folder/'report.json');inputs_ok(folder,r)
        if a.command=='generate':
            if not a.allow_external or r['generation_closed'] or not a.scene or not a.asset:raise ValueError('Generation not authorized or closed')
            if a.scene not in r['sources']:raise ValueError('Source not approved')
            name=a.scene+'_'+a.asset
            if any(q['name']==name or q['status']!='complete' for q in r['requests']):raise ValueError('Attempted or unresolved request; no retry')
            key=os.environ.get('OPENROUTER_API_KEY','').strip()
            if not key:raise ValueError('OPENROUTER_API_KEY is missing')
            cap=seam.api.validate_capabilities(seam.api.request_json(f'/images/models/{seam.api.MODEL}/endpoints',key))
            if cap['supported_parameters'].get('input_references',{}).get('max',0)<4 or 'transparent' not in cap['supported_parameters'].get('background',{}).get('values',[]):raise ValueError('Required model capabilities missing')
            generate(folder,r,key,a.scene,a.asset)
        elif a.command=='build':build(folder,r)
        elif a.command=='verify':verify(folder,r)
        else:r['generation_closed']=True;qs.write(folder/'report.json',r)


if __name__=='__main__':main()
