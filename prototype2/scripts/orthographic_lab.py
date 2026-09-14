"""Approved six-request Namsan orthographic trial; no default-map changes."""
import argparse
import fcntl
import html
import math
import os
from pathlib import Path
import re
import statistics
import numpy as np
from PIL import Image, ImageDraw
import seam_lab as seam
import projection_probe as probe

qs=seam.api.qs
ROOT=qs.P2/'eval/vworld/orthographic_lab'
SOURCE_RUN='20260914T091414062775Z'
LIMITS={'namsan':4,'seam':1,'tower':1}
CORE=(192,256,1344,1408)
TOWER=(736,624,832,864)
# Manually identified before generation, in the original 1536px source.
REFERENCE={
 'tower':[[778,648],[778,815]],
 'buildings':[
  {'id':'far_west_roof','depth':'far','line':[[514,362],[555,350]]},
  {'id':'far_east_roof','depth':'far','line':[[751,402],[784,394]]},
  {'id':'mid_west_roof','depth':'middle','line':[[397,644],[445,629]]},
  {'id':'mid_summit_base','depth':'middle','line':[[755,832],[807,812]]},
  {'id':'near_west_roof','depth':'near','line':[[340,1231],[374,1220]]},
  {'id':'near_east_roof','depth':'near','line':[[781,1326],[811,1317]]}],
 'roads':[[438,776],[557,781],[861,797],[978,806],[1154,871],[1223,887],[448,1110],[952,1271]]}

def project(p):return [(p[0]-CORE[0])*4/3,(p[1]-CORE[1])*4/3]

def init():
    ROOT.mkdir(parents=True,exist_ok=True)
    with (ROOT/'.approval.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (ROOT/'approved_run.json').exists():raise ValueError('Trial already initialized; reuse its run, never reset budget')
        source_folder=probe.resolve(SOURCE_RUN)
        original=qs.read(source_folder/'report.json')
        # Verify without modifying the original probe record.
        for name,digest in original['files'].items():
            if qs.sha(source_folder/name)!=digest:raise ValueError('Probe source hash changed')
        a,b=[original['modes'][m] for m in ['perspective','orthographic']]
        if not all(probe.check_samples(m,x['samples'],x['initial'])['passed'] for m,x in [('perspective',a),('orthographic',b)]):raise ValueError('Projection probe failed')
        if not all(math.dist(a['initial'][f],b['initial'][f])<t for f,t in [('position',.01),('direction',1e-6),('up',1e-6)]):raise ValueError('Probe camera mismatch')
        cfg=qs.read(qs.CONFIG);style=qs.P2/cfg['style_reference']
        if qs.sha(style)!=cfg['style_sha256']:raise ValueError('Style hash changed')
        folder=ROOT/'runs'/seam.stamp();folder.mkdir(parents=True)
        Image.open(source_folder/'orthographic.png').save(folder/'input.png')
        Image.open(style).save(folder/'style.png')
        Image.open(folder/'input.png').crop(CORE).resize((1536,1536),Image.Resampling.LANCZOS).save(folder/'source.png')
        report={'run_id':folder.name,'status':'prepared','model':seam.api.MODEL,'limits':LIMITS,'request_limit':6,'requests':[],
                'source_probe_run':SOURCE_RUN,'source_sha256':qs.sha(folder/'input.png'),'style_sha256':qs.sha(folder/'style.png'),
                'source_approval':{'approved_by':'user','scope':'experimental AI input only','note':'Incomplete facade textures acknowledged; not approval for production or user approval of generated art.'},
                'source_render_review':original['render_review'],'reference_source':REFERENCE,'reference_method':'manual visual annotation before generation; approximate image coordinates, not geographic truth',
                'source_core':CORE,'source_to_output_scale':4/3,'reference_100m_px':128,'user_visual_approval':False,'repairs':{}}
        qs.write(folder/'report.json',report);qs.write(ROOT/'approved_run.json',{'run_id':folder.name,'request_limit':6})
        annotate(folder,'source.png',report,None,'source_review.png')
        print('RUN='+folder.name,flush=True)
        return folder

def load(run):
    if not run or not re.fullmatch(r'\d{8}T\d{12}Z',run):raise ValueError('Invalid run ID')
    if qs.read(ROOT/'approved_run.json')['run_id']!=run:raise ValueError('Unapproved run')
    folder=ROOT/'runs'/run
    return folder,qs.read(folder/'report.json')

def inputs_ok(folder,r):
    if r['limits']!=LIMITS or r['request_limit']!=6 or r['model']!=seam.api.MODEL:raise ValueError('Budget/model changed')
    if qs.sha(folder/'input.png')!=r['source_sha256'] or qs.sha(folder/'style.png')!=r['style_sha256']:raise ValueError('Input hash changed')
    if r['reference_source']!=REFERENCE:raise ValueError('Pre-generation reference changed')

def generate(folder,r,key):
    if r['requests']:raise ValueError('Scene already attempted; no retry')
    source=Image.open(folder/'input.png').convert('RGB');style=Image.open(folder/'style.png').convert('RGB')
    canvas=Image.new('RGB',(1792,1792));known=Image.new('L',canvas.size)
    for i in range(4):
        crop,mixed,mask=seam.context_tile(source,canvas,known,i)
        prompt=('Use case: style-transfer / contextual continuation. Image 1 is the ONLY geometry and scene reference, '
          'an ORTHOGRAPHIC parallel-projection map of mountainous Namsan, Seoul. Image 2 is ONLY pixel-art style, '
          'never its layout or objects. Image 3 contains previous generated pixels at their correct coordinates; '
          'Image 4 is a context mask: WHITE is previous art to preserve, BLACK is the area to redraw. '
          'Image 5 is a close detail of the same source tower, ONLY for its shape IF already present in Image 1. '
          'Output one continuous crisp pixel-art map, unchanged camera angle, framing and constant world scale. '
          'No perspective convergence, no vanishing point, no horizon, no shrinking distant buildings or enlarged foreground. '
          'Keep every building position, footprint width, roof direction, relative height and winding road alignment. '
          'Keep the actual hill slope, ridge, forest layering and summit elevation; do not flatten the hill. '
          'Keep exactly the source tower size and position, its slender white shaft, observation deck, antenna and base. '
          'Do not enlarge it as a hero landmark, duplicate it, or confuse it with the separate orange mast. '
          'Use clear square pixel clusters, fresh greens, readable cool roofs, restrained consistent shadows, warm paving only where paving exists. '
          'Continue roof edges, paths, tree crowns and palette across the context boundary. No farms, extra buildings, '
          'characters, panels, guide marks, captions or labels. Unknown facade texture may be simplified, never change its building mass.')
        raw=seam.paid(folder,r,key,'namsan',f'namsan_{i}',prompt,[crop,style,mixed,mask.convert('RGB'),source.crop(TOWER)],limits=LIMITS)
        seam.commit_tile(canvas,known,raw,i).save(folder/f'namsan_{i}_locked.png')
    canvas.crop((128,128,1664,1664)).save(folder/'before.png')
    r['status']='awaiting_review';qs.write(folder/'report.json',r)
    publish(folder,r)

def repair(folder,r,key,kind):
    spec=qs.read(folder/'review.json')['repair_requests'][kind]
    if not spec.get('needed') or not spec.get('reason'):raise ValueError('Repair needs recorded visual defect')
    box,edit=spec['context_box'],spec['edit_box']
    if len(box)!=4 or box[2]-box[0]!=1024 or box[3]-box[1]!=1024 or not(0<=box[0]<box[2]<=1536 and 0<=box[1]<box[3]<=1536):raise ValueError('Invalid context')
    if not(box[0]<=edit[0]<edit[2]<=box[2] and box[1]<=edit[1]<edit[3]<=box[3]):raise ValueError('Invalid repair mask')
    base=Image.open(folder/'before.png').convert('RGB');mask=Image.new('L',(1024,1024))
    ImageDraw.Draw(mask).rectangle((edit[0]-box[0],edit[1]-box[1],edit[2]-box[0]-1,edit[3]-box[1]-1),fill=255)
    prompt=('Use case: precise-object-edit. Image 1 is the current pixel map, Image 2 is exact orthographic source geometry at the same coordinates, '
            'Image 3 is an EDIT GUIDE: change only WHITE, preserve BLACK. Image 4 is original tower detail only. '
            'Keep constant orthographic scale, camera, slopes, palette and pixel clusters. No perspective, enlargement, extra objects or labels. '
            +spec['reason'])
    raw=seam.paid(folder,r,key,kind,kind+'_repair',prompt,[base.crop(box),Image.open(folder/'source.png').crop(box),mask.convert('RGB'),Image.open(folder/'input.png').crop(TOWER)],limits=LIMITS)
    candidate=base.copy();candidate.paste(raw.convert('RGB'),box[:2],mask);candidate.save(folder/f'{kind}_candidate.png')
    r['repairs'][kind]={**spec,'candidate':f'{kind}_candidate.png','accepted':False}
    qs.write(folder/'report.json',r)

def geometry(r,review):
    ref=r['reference_source'];out=review.get('final',{});errors=[];widths=[];missing=[]
    def point(p):
        if len(p)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1536 for v in p):raise ValueError('Invalid annotation')
        return p
    try:
        roads=out['roads'];tower=out['tower'];buildings=out['buildings']
        if len(roads)!=8 or len(tower)!=2 or len(buildings)!=6:raise ValueError('Missing annotations')
        for i,(a,b) in enumerate(zip(ref['roads']+ref['tower'],roads+tower)):
            if b is None:missing.append('point_'+str(i));continue
            errors.append(math.dist(project(a),point(b)))
        for a,b in zip(ref['buildings'],buildings):
            if a['id']!=b['id']:raise ValueError('Building identity missing')
            if b.get('line') is None:missing.append(a['id']);continue
            if len(b['line'])!=2:raise ValueError('Building identity missing')
            line=[point(p) for p in b['line']]
            widths.append({'id':a['id'],'depth':a['depth'],'relative_change':math.dist(*line)/(math.dist(*a['line'])*4/3)-1})
        tower_change=math.dist(*tower)/(math.dist(*ref['tower'])*4/3)-1 if all(p is not None for p in tower) else None
        median=statistics.median(errors) if errors else None;maximum=max(errors) if errors else None
        passed=not missing and median is not None and median<=8 and maximum<=16 and all(abs(x['relative_change'])<=.15 for x in widths) and tower_change is not None and abs(tower_change)<=.10
        return {'measured':not missing,'passed':passed,'missing':missing,'point_errors_px':errors,'median_px':median,'max_px':maximum,'building_widths':widths,'tower_height_change':tower_change,'method':'manual correspondences; proxy only, not proof of exact orthographic AI output'}
    except (KeyError,TypeError,ValueError) as e:return {'measured':False,'passed':False,'reason':str(e),'method':'unidentified objects are not a pass'}

def annotate(folder,name,r,review,output):
    im=Image.open(folder/name).convert('RGB');d=ImageDraw.Draw(im)
    data=review if review else {'tower':[project(p) for p in REFERENCE['tower']], 'roads':[project(p) for p in REFERENCE['roads']],
             'buildings':[{**b,'line':[project(p) for p in b['line']]} for b in REFERENCE['buildings']]}
    for i,p in enumerate(data.get('roads',[])):
        if p is not None:d.ellipse((p[0]-5,p[1]-5,p[0]+5,p[1]+5),outline='#ff4260',width=2);d.text((p[0]+8,p[1]),f'R{i+1}',fill='#ff4260')
    for i,b in enumerate(data.get('buildings',[])):
        if b.get('line') and all(p is not None for p in b['line']):
            d.line([tuple(p) for p in b['line']],fill='#20e0ff',width=3);d.text(tuple(b['line'][0]),f'B{i+1}',fill='#ffff00')
    if data.get('tower') and all(p is not None for p in data['tower']):d.line([tuple(p) for p in data['tower']],fill='#ffff00',width=3)
    im.save(folder/output)

def verify(folder,r):
    inputs_ok(folder,r)
    req=r['requests']
    if len(req)>6 or any(sum(x['group']==g for x in req)>n for g,n in LIMITS.items()):raise ValueError('Budget exceeded')
    if len({x['name'] for x in req})!=len(req):raise ValueError('Duplicate request')
    if any(x['status']!='complete' for x in req):raise ValueError('Unresolved request')
    for x in req:
        if qs.sha(folder/(x['name']+'_raw.png'))!=x['raw_sha256']:raise ValueError('Raw changed')
    canvas=Image.new('RGB',(1792,1792));known=Image.new('L',canvas.size)
    for i in range(4):
        locked=seam.commit_tile(canvas,known,Image.open(folder/f'namsan_{i}_raw.png'),i)
        if not np.array_equal(np.asarray(locked),np.asarray(Image.open(folder/f'namsan_{i}_locked.png'))):raise ValueError('Context lock differs')
    if not np.array_equal(np.asarray(canvas.crop((128,128,1664,1664))),np.asarray(Image.open(folder/'before.png'))):raise ValueError('Assembly differs')
    base=np.asarray(Image.open(folder/'before.png'))
    for x in r['repairs'].values():
        mask=np.zeros((1536,1536),bool);a,b,c,d=x['edit_box'];mask[b:d,a:c]=True
        if not np.array_equal(base[~mask],np.asarray(Image.open(folder/x['candidate']))[~mask]):raise ValueError('Repair changed protected pixels')
    review=qs.read(folder/'review.json') if (folder/'review.json').exists() else {}
    expected=Image.open(folder/'before.png').convert('RGB')
    for kind,spec in r['repairs'].items():
        if spec.get('accepted')!=review.get('repair_decisions',{}).get(kind,{}).get('accepted',False):raise ValueError('Republish changed review')
        if spec.get('accepted'):
            box=spec['edit_box'];expected.paste(Image.open(folder/spec['candidate']).crop(box),box[:2])
    if qs.sha(folder/'mosaic.png')!=r['final_sha256'] or not np.array_equal(np.asarray(expected),np.asarray(Image.open(folder/'mosaic.png'))):raise ValueError('Final composition changed')
    source=Image.open(folder/'input.png').crop(CORE).resize((1536,1536),Image.Resampling.LANCZOS)
    if not np.array_equal(np.asarray(source),np.asarray(Image.open(folder/'source.png'))):raise ValueError('Source alignment changed')
    for name,directory in [('mosaic.png','tiles'),('before.png','before_tiles'),('source.png','source_tiles')]:
        native=Image.open(folder/name)
        for z in range(4):
            factor=2**(3-z);level=native if z==3 else native.resize((math.ceil(1536/factor),)*2,Image.Resampling.BOX)
            for y in range(math.ceil(level.height/256)):
                for x in range(math.ceil(level.width/256)):
                    tile=Image.open(folder/directory/str(z)/str(x)/f'{y}.png')
                    if not np.array_equal(np.asarray(tile),np.asarray(level.crop((x*256,y*256,min(level.width,(x+1)*256),min(level.height,(y+1)*256))))):raise ValueError('Zoom pyramid differs')
    result={'technical_passed':True,'requests':len(req),'geometry':geometry(r,review),'visual_review':review.get('note','pending'),'user_visual_approval':False}
    qs.write(folder/'verification.json',result);return result

def publish(folder,r):
    review=qs.read(folder/'review.json') if (folder/'review.json').exists() else {}
    final=Image.open(folder/'before.png').convert('RGB')
    for kind,spec in r['repairs'].items():
        decision=review.get('repair_decisions',{}).get(kind,{})
        spec['accepted']=decision.get('accepted',False);spec['review_note']=decision.get('reason','not reviewed')
        if spec['accepted']:
            box=spec['edit_box'];final.paste(Image.open(folder/spec['candidate']).crop(box),box[:2])
    final.save(folder/'mosaic.png')
    for name,target in [('mosaic.png','tiles'),('before.png','before_tiles'),('source.png','source_tiles')]:seam.legacy.pyramid(Image.open(folder/name),folder/target)
    final.resize((384,384),Image.Resampling.BOX).save(folder/'preview.png')
    if review.get('final'):annotate(folder,'mosaic.png',r,review['final'],'final_review.png')
    r['final_sha256']=qs.sha(folder/'mosaic.png');r['status']='awaiting_user_review';qs.write(folder/'report.json',r)
    v=verify(folder,r)
    manifest={'version':1,'run_id':folder.name,'status':'awaiting_user_review','width':1536,'height':1536,'tile_size':256,'max_native_zoom':3,
        'tiles':'tiles','source_tiles':'source_tiles','before_tiles':'before_tiles','preview':'preview.png','mosaic':'mosaic.png','source':'source.png',
        'generation_frontiers':[896,896],'review_targets':[{'label':'N서울타워','xy':project([778,732])},{'label':'중앙 연결','xy':[896,896]}],
        'review_summary':'정사영 남산 2×2 · AI 재해석 · 구조 '+('통과' if v['geometry']['passed'] else '미통과/미검증')+' · 사용자 미감 승인 전',
        'attribution':'국토교통부 / VWorld · AI 재해석 · 로컬 검수용 · 실제 좌표 정합 미검증'}
    qs.write(folder/'manifest.json',manifest)
    cards=''.join(f'<figure><h2>{label}</h2><img src="{name}"></figure>' for name,label in [('source.png','정사영 원본'),('before.png','2×2 보정 전'),('mosaic.png','최종 후보'),('source_review.png','원본 기준점'),('final_review.png','결과 대응점')] if (folder/name).exists())
    prompts=''.join('<h3>'+html.escape(x['name'])+'</h3><pre>'+html.escape(x['prompt'])+'</pre>' for x in r['requests'])
    doc=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>정사영 남산 2×2</title>
<style>body{{font:16px system-ui;background:#fbf3e4;color:#3a2a1e;margin:20px}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:16px}}figure{{margin:0}}img{{width:100%;image-rendering:pixelated}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}</style>
<h1>정사영 남산 2×2 — 사용자 검수용</h1><p>{html.escape(manifest['review_summary'])}</p>
<p><a href="../../../../../web/pilot/?view=projection-lab&run={folder.name}">지도에서 이동·줌·원본 비교</a> · <a href="mosaic.png">최종 PNG</a> · <a href="report.json">프롬프트·비용 기록</a> · <a href="verification.json">검증</a></p>
<p>정사영 원본의 중앙 영역을 4/3 확대했습니다. 원본의 100m 투영 길이는 이 배율에서 128px이나 AI의 정확한 축척 보장을 뜻하지 않습니다. 외벽은 AI 추정이며 사용자 미감 승인 전입니다.</p>
<p>{html.escape(str(review.get('note','검수 대기')))}</p><p><a href="../../../seam_lab/runs/20260914T084137369841Z/index.html">이전 원근 결과 참고 — 좌표 일치 비교 아님</a></p><main>{cards}</main><h2>실제 요청 프롬프트</h2>{prompts}<p>{manifest['attribution']}</p></html>'''
    (folder/'index.html').write_text(doc,encoding='utf8');print(str(folder/'index.html'),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['init','generate','repair','publish','verify']);p.add_argument('--run');p.add_argument('--kind',choices=['seam','tower']);p.add_argument('--allow-external',action='store_true');a=p.parse_args()
    if a.command=='init':init();return
    folder,r=load(a.run)
    with (folder/'.generation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);r=qs.read(folder/'report.json');inputs_ok(folder,r)
        if a.command=='verify':print(verify(folder,r));return
        if a.command=='publish':publish(folder,r);return
        if (folder/'review.json').exists() and qs.read(folder/'review.json').get('generation_closed'):raise ValueError('Trial generation closed; unused budget is not new authorization')
        if not a.allow_external:raise ValueError('--allow-external required')
        key=os.environ.get('OPENROUTER_API_KEY','').strip()
        if not key:raise ValueError('OPENROUTER_API_KEY missing')
        cap=seam.api.validate_capabilities(seam.api.request_json(f'/images/models/{seam.api.MODEL}/endpoints',key))
        if cap['supported_parameters'].get('input_references',{}).get('max',0)<5:raise ValueError('Five references unsupported')
        r['capability']=cap;qs.write(folder/'report.json',r)
        if a.command=='generate':generate(folder,r,key)
        else:repair(folder,r,key,a.kind)

if __name__=='__main__':main()
