"""VWorld-only perspective/orthographic source comparison. Never calls AI."""
import argparse
import copy
from datetime import datetime, timezone
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import vworld_pipeline as vw

ROOT=vw.P2/'eval/vworld/projection_probe/runs'
SPEC={'id':'namsan_projection','lon':126.98808,'lat':37.55112,'size':1536,'meters_per_pixel':1600/1536}
CAMERA={'heading_deg':22.5,'pitch_deg':-30,'range_m':1800}


def page(key):
    cfg=copy.deepcopy(vw.read(vw.CONFIG));cfg['camera']=CAMERA;cfg['try_orthographic']=False
    original=vw.page(key,SPEC,cfg)
    start=original.index('      const applyCamera=()=>{')
    end=original.index('    } catch(e){fail(e)}',start)
    return original[:start]+Path(__file__).with_suffix('.js').read_text()+original[end:]


def check_samples(mode,samples,initial=None):
    if len(samples)<4:return {'passed':False,'reason':'Need three settled samples and final capture sample'}
    try:
        first=initial or samples[0]
        for s in samples:
            if s['viewport']!=[1536,1536] or s['drawing_buffer']!=[1536,1536]:raise ValueError('Unexpected pixel scale')
            values=s['lengths']
            if len(values)!=3 or not all(math.isfinite(v) and v>0 for v in values):raise ValueError('Invalid reference lengths')
            for field,tolerance in [('position',.01),('direction',1e-6),('up',1e-6)]:
                if math.dist(first[field],s[field])>tolerance:raise ValueError('Camera moved after setup')
            m=s['matrix']
            if len(m)!=16 or not all(math.isfinite(v) for v in m):raise ValueError('Invalid projection matrix')
            if mode=='orthographic':
                if not s['orthographic'] or abs(m[15]-1)>1e-9 or abs(m[11])>1e-9:raise ValueError('Orthographic camera reverted')
                if abs(s['width']-1600)>1e-6:raise ValueError('Orthographic width changed')
                if max(abs(v-96) for v in values)>1 or (max(values)-min(values))/96>.01:raise ValueError('Scale varies with depth')
            elif s['orthographic'] or abs(values[1]-96)>1 or (max(values)-min(values))/values[1]<.05:
                raise ValueError('Perspective negative control failed')
        return {'passed':True,'expected_orthographic_px':96,'final_lengths':samples[-1]['lengths'],
                'relative_spread':(max(samples[-1]['lengths'])-min(samples[-1]['lengths']))/samples[-1]['lengths'][1]}
    except (KeyError,TypeError,ValueError) as e:return {'passed':False,'reason':str(e)}


def resolve(name):
    if not name or not re.fullmatch(r'\d{8}T\d{12}Z',name):raise ValueError('Invalid run ID')
    return ROOT/name


def capture():
    key=os.environ.get('VWORLD_API_KEY','').strip()
    if not key:raise ValueError('VWORLD_API_KEY is missing')
    content=page(key).encode()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!='/':self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(content)
        def log_message(self,*_):pass
    server=ThreadingHTTPServer(('localhost',8767),Handler)
    folder=ROOT/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');folder.mkdir(parents=True)
    report={'run_id':folder.name,'spec':SPEC,'camera':CAMERA,'ai_requests':0,'key_persisted':False,'modes':{},'user_visual_approval':False,'render_review':None}
    threading.Thread(target=server.serve_forever,daemon=True).start()
    print('RUN='+folder.name,flush=True)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            tab=browser.new_page(viewport={'width':1536,'height':1536},device_scale_factor=1)
            errors=[];tab.on('pageerror',lambda e:errors.append(vw.redact(str(e),key)))
            deadline=time.monotonic()+90
            tab.goto('http://localhost:8767/',wait_until='domcontentloaded',timeout=30000)
            tab.wait_for_function('()=>window.__probe?.ready||window.__P2?.error',timeout=max(1,int((deadline-time.monotonic())*1000)))
            state=tab.evaluate('()=>window.__P2')
            if state.get('error'):raise ValueError(vw.redact(state['error'],key))
            # The SDK changes its initial camera asynchronously and terrain
            # height can be finite at a coarse LOD before final tiles arrive.
            sdk_settle=time.monotonic()+12
            height=None;heights=[]
            while time.monotonic()<deadline:
                height=tab.evaluate('()=>window.__probe.heightAtTarget()')
                loaded=tab.evaluate('()=>Boolean(ws3d.viewer.scene.globe.tilesLoaded)')
                if isinstance(height,(float,int)) and math.isfinite(height) and time.monotonic()>=sdk_settle and loaded:
                    heights.append(height)
                    if len(heights)>=3 and max(heights[-3:])-min(heights[-3:])<.1:break
                else:heights=[]
                tab.wait_for_timeout(2000)
            else:raise ValueError('Terrain height unavailable within 90 seconds; no fallback')
            report['terrain_height_m']=height
            report['terrain_height_samples']=heights[-3:]
            for mode in ['perspective','orthographic']:
                entry={'samples':[]};report['modes'][mode]=entry
                try:
                    mode_deadline=deadline if mode=='perspective' else time.monotonic()+90
                    tab.evaluate('([mode,h])=>window.__probe.prepare(mode,h)',[mode,height])
                    entry['initial']=tab.evaluate('()=>window.__probe.measure()')
                    settle=time.monotonic()+12;stable=0
                    while time.monotonic()<mode_deadline:
                        tab.wait_for_timeout(2000)
                        s=tab.evaluate('()=>window.__probe.measure()')
                        if time.monotonic()>=settle:
                            entry['samples'].append(s);stable=stable+1 if s['tiles_loaded'] else 0
                            if stable>=3:break
                        if len(entry['samples'])%5==0:print(mode+' waiting for source tiles',flush=True)
                    entry['samples'].append(tab.evaluate('()=>window.__probe.measure()'))
                    tab.screenshot(path=str(folder/f'{mode}.png'))
                    tab.evaluate('()=>window.__probe.guides(true)');tab.screenshot(path=str(folder/f'{mode}_guides.png'));tab.evaluate('()=>window.__probe.guides(false)')
                    entry['validation']=check_samples(mode,entry['samples'],entry['initial'])
                    entry['tiles_loaded']=entry['samples'][-1]['tiles_loaded']
                    print(mode+' '+json.dumps(entry['validation']),flush=True)
                except Exception as e:entry['error']=vw.redact(str(e),key);entry['validation']={'passed':False,'reason':'Capture failed'}
                vw.write(folder/'report.json',vw.secret_safe(report,key))
            report['browser_errors']=errors;browser.close()
    except Exception as e:report['error']=vw.redact(str(e),key)
    finally:
        server.shutdown();server.server_close()
        report['files']={p.name:vw.digest_bytes(p.read_bytes()) for p in folder.glob('*.png')}
        vw.write(folder/'report.json',vw.secret_safe(report,key));render(folder)
    return folder


def verify(folder):
    r=vw.read(folder/'report.json')
    for file,digest in r['files'].items():
        if vw.digest_bytes((folder/file).read_bytes())!=digest:raise ValueError('Capture hash mismatch')
    results={mode:check_samples(mode,r['modes'].get(mode,{}).get('samples',[]),r['modes'].get(mode,{}).get('initial')) for mode in ['perspective','orthographic']}
    if all(s['passed'] for s in results.values()):
        a,b=[r['modes'][m]['samples'][-1] for m in ['perspective','orthographic']]
        results['same_camera']=all(math.dist(a[f],b[f])<t for f,t in [('position',.01),('direction',1e-6),('up',1e-6)]) and a['height']==b['height']
    else:results['same_camera']=False
    results['projection_verified']=all(results[m]['passed'] for m in ['perspective','orthographic']) and results['same_camera']
    results['ai_requests']=0;results['render_review']=r.get('render_review');results['user_visual_approval']=False
    vw.write(folder/'verification.json',results);print(json.dumps(results,ensure_ascii=False))
    return results


def render(folder):
    r=vw.read(folder/'report.json');v=verify(folder)
    cards=''.join(f'<figure><h2>{label}</h2><img data-mode="{mode}" src="{mode}.png" alt="{label} 캡처"><figcaption>{html.escape(json.dumps(r["modes"].get(mode,{}).get("validation",{}),ensure_ascii=False))}</figcaption></figure>' if (folder/f'{mode}.png').exists() else f'<p>{label}: 캡처 없음</p>' for mode,label in [('perspective','원근'),('orthographic','정사영')])
    doc='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>남산 투영 비교</title>
<style>body{font:16px system-ui;background:#fbf3e4;color:#3a2a1e;margin:20px}main{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0;min-width:0;overflow:auto}img{width:100%;display:block}figcaption{overflow-wrap:anywhere}button,label{margin:8px}body.native img{width:1536px;max-width:none}@media(max-width:800px){main{grid-template-columns:1fr}}</style>
<h1>남산 원근·정사영 원본 비교</h1><p>VWorld 원본 · AI 생성 0회 · 같은 카메라와 중심 기준 축척, 전체 지리 범위는 서로 다릅니다.</p>
<label><input type="checkbox" id="guides">100m 기준선 표시</label><button id="zoom">맞춤 / 100% 전환</button><a href="report.json">캡처 기록</a> · <a href="verification.json">수치 검증</a>
STATUS<main>CARDS</main><p>국토교통부 / VWorld · 기존 지도와 기본 실행은 변경하지 않았습니다.</p>
<script>document.querySelector('#guides').onchange=e=>document.querySelectorAll('img').forEach(im=>im.src=im.dataset.mode+(e.target.checked?'_guides':'')+'.png');document.querySelector('#zoom').onclick=()=>document.body.classList.toggle('native');</script></html>'''
    review=r.get('render_review') or {}
    status='<p>투영 검증: '+('통과' if v['projection_verified'] else '실패/미완료')+' · AI 입력 승인: '+('승인' if review.get('ai_input_approved') else '미승인')+'</p>'
    status+='<p>'+html.escape(review.get('note','시각 검수 대기'))+'</p>'
    (folder/'index.html').write_text(doc.replace('STATUS',status).replace('CARDS',cards),encoding='utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['capture','verify','report']);p.add_argument('--run');p.add_argument('--allow-external',action='store_true');args=p.parse_args()
    if args.command=='capture':
        if not args.allow_external:raise ValueError('Explicit VWorld access opt-in required')
        capture()
    elif args.command=='verify':verify(resolve(args.run))
    else:render(resolve(args.run))
