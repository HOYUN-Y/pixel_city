"""Offline interaction assets only. No AI, HTTP, default pointer or source edits."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import re
import shutil
import numpy as np
from PIL import Image,ImageDraw
import qwen_style as qs

ROOT=qs.P2/'eval/vworld/projection_walk/runs'
CONFIG=qs.P2/'configs/projection_walk.json'

def validate(cfg):
    xy=lambda p:isinstance(p,list) and len(p)==2 and all(isinstance(x,(int,float)) and 0<=x<=1536 for x in p)
    if cfg['route']['playback']!='once' or len(cfg['spots'])!=3:raise ValueError('Wrong walk configuration')
    for polygon in [cfg['tower_polygon']]+[o['polygon'] for o in cfg['occluders']]:
        if len(polygon)<3 or not all(xy(p) for p in polygon):raise ValueError('Invalid polygon')
    ids={o['id'] for o in cfg['occluders']}
    for p in cfg['route']['points']:
        if not xy(p['xy']) or any(i not in ids for i in p.get('behind',[])):raise ValueError('Invalid route')

def build():
    cfg=qs.read(CONFIG);validate(cfg)
    parent=qs.P2/'eval/vworld/orthographic_lab/runs'/cfg['parent_run']
    char=qs.P2/'eval/vworld/seam_lab/runs'/cfg['character_run']/'traveler.png'
    if qs.sha(parent/'mosaic.png')!=cfg['image_sha256'] or qs.sha(char)!=cfg['character_sha256']:raise ValueError('Pinned parent or character changed')
    folder=ROOT/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');folder.mkdir(parents=True)
    for src,dst in [('mosaic.png','final.png'),('before.png','before.png'),('source.png','source.png')]:shutil.copyfile(parent/src,folder/dst)
    shutil.copyfile(char,folder/'traveler.png');qs.write(folder/'config.json',cfg)
    mask=Image.new('L',(1536,1536));ImageDraw.Draw(mask).polygon([tuple(p) for p in cfg['tower_polygon']],fill=255);mask.save(folder/'tower_hit.png')
    overlay={k:cfg[k] for k in ['image_sha256','occluders','route','spots']}
    overlay['landmark']={'id':'tower','mode':'highlight_only','hit':'tower_hit.png','occluder_id':'tower-base'}
    qs.write(folder/'overlay.json',overlay)
    variants={k:{'label':label,'file':file,'sha256':qs.sha(folder/file)} for k,file,label in [('source','source.png','정사영 원본'),('before','before.png','보정 전'),('final','final.png','상호작용 시험')]}
    manifest={'version':1,'run_id':folder.name,'character':'traveler.png','parent_run':cfg['parent_run'],'ai_requests':0,'user_visual_approval':False,
              'asset_sha256':{p.name:qs.sha(p) for p in folder.glob('*.png')},'overlay_sha256':{'namsan':qs.sha(folder/'overlay.json')},
              'scenes':{'namsan':{'label':'남산 · N서울타워','variants':variants,'overlay':'overlay.json','review':'정사영 산책 · 수작업 경로/가림 · 실제 길찾기 아님 · 화풍 잠정 사용'}}}
    qs.write(folder/'manifest.json',manifest)
    im=Image.open(folder/'final.png').convert('RGB');d=ImageDraw.Draw(im)
    d.line([tuple(p['xy']) for p in cfg['route']['points']],fill='#ff4260',width=2)
    for i,p in enumerate(cfg['route']['points']):d.text(tuple(p['xy']),str(i),fill='#ffffff')
    for o in cfg['occluders']:d.line([tuple(p) for p in o['polygon']+[o['polygon'][0]]],fill='#20e0ff',width=2)
    im.crop((510,510,1130,835)).resize((1240,650),Image.Resampling.NEAREST).save(folder/'route_review.png')
    Image.open(folder/'final.png').crop((510,510,1130,835)).resize((1240,650),Image.Resampling.NEAREST).save(folder/'detail.png')
    (folder/'index.html').write_text(f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>정사영 남산 산책</title>
<style>body{{font:16px system-ui;background:#fbf3e4;color:#3a2a1e;margin:24px}}img{{max-width:100%;image-rendering:pixelated}}</style>
<h1>정사영 남산 산책 시험</h1><p><a href="../../../../../web/pilot/?view=projection-walk&run={folder.name}">타워 선택·산책 시작</a> · <a href="verification.json">검증 기록</a> · <a href="config.json">수작업 좌표</a></p>
<p>추가 AI 생성 0회. 기존 그림을 변경하지 않고 타워 선택 윤곽과 기존 캐릭터를 표시합니다. 기본 정지, 45초 단회 재생. 실제 거리·고도·길찾기 정보가 아닙니다.</p><p>캐릭터 재생/정지·처음으로·따라가기·위치 슬라이더는 지도 검수에서 조작합니다. 타워를 클릭하면 정보를 표시합니다. 원본·보정 전 비교에서는 상호작용이 꺼집니다.</p>
<h2>수작업 경로·가림 검수</h2><img src="route_review.png"><p>분홍: 경로 · 하늘색: 가림 윤곽. 가려진 부분의 길 연결은 시각 시험용 추정입니다.</p><p>국토교통부 / VWorld · 기존 AI 재해석 · 사용자 미감 검수 대기 · 로컬 검수용</p></html>''',encoding='utf8')
    verify(folder);print('RUN='+folder.name,flush=True);return folder

def verify(folder):
    cfg=qs.read(folder/'config.json');validate(cfg);m=qs.read(folder/'manifest.json')
    for name,digest in m['asset_sha256'].items():
        if qs.sha(folder/name)!=digest:raise ValueError('Asset hash mismatch')
    if qs.sha(folder/'final.png')!=cfg['image_sha256']:raise ValueError('Background modified')
    if qs.sha(folder/'traveler.png')!=cfg['character_sha256']:raise ValueError('Character modified')
    if qs.sha(folder/'overlay.json')!=m['overlay_sha256']['namsan']:raise ValueError('Overlay changed')
    overlay=qs.read(folder/'overlay.json')
    if any(overlay[k]!=cfg[k] for k in ['image_sha256','occluders','route','spots']):raise ValueError('Configuration/overlay mismatch')
    mask=np.asarray(Image.open(folder/'tower_hit.png'))
    expected=Image.new('L',(1536,1536));ImageDraw.Draw(expected).polygon([tuple(p) for p in cfg['tower_polygon']],fill=255)
    if not np.array_equal(mask,np.asarray(expected)):raise ValueError('Configuration/mask mismatch')
    if not mask[630,781] or mask[735,700] or mask[600,900]:raise ValueError('Tower/orange mast/background hit mismatch')
    qs.write(folder/'verification.json',{'passed':True,'background_byte_identical':True,'ai_requests':0,'user_visual_approval':False,'final_sha256':cfg['image_sha256'],'config_sha256':qs.sha(folder/'config.json'),'manifest_sha256':qs.sha(folder/'manifest.json')})

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['build','verify']);p.add_argument('--run');a=p.parse_args()
    if a.command=='build':build()
    else:
        if not a.run or not re.fullmatch(r'\d{8}T\d{12}Z',a.run):raise ValueError('Invalid run ID')
        verify(ROOT/a.run)
