"""VWorld-only 1024px/800m orthographic source gate for two landmarks."""
import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import math
import os
from pathlib import Path
import threading
import time
import seam_lab as seam

qs=seam.api.qs
vw=seam.vw
ROOT=seam.P2/'eval/vworld/landmark_pilot'
CONFIG=seam.P2/'configs/landmark_pilot.json'


def check(samples):
    try:
        if len(samples)<4:raise ValueError('Four settled samples required')
        baseline=samples[0]['expected']
        for s in samples:
            if s['viewport']!=[1024,1024] or s['drawing_buffer']!=[1024,1024]:raise ValueError('Pixel scale changed')
            if not s['orthographic'] or abs(s['width']-800)>1e-6:raise ValueError('Not the approved orthographic frame')
            m=s['matrix']
            if len(m)!=16 or not all(math.isfinite(v) for v in m) or abs(m[15]-1)>1e-9 or abs(m[11])>1e-9:raise ValueError('Invalid projection matrix')
            if len(s['lengths'])!=3 or any(not math.isfinite(v) or abs(v-128)>1 for v in s['lengths']):raise ValueError('Scale varies with depth')
            for field,tol in [('position',.01),('direction',1e-6),('up',1e-6)]:
                if len(s[field])!=3 or not all(math.isfinite(v) for v in s[field]) or math.dist(s[field],baseline[field])>tol:raise ValueError('Camera drift')
            if len(s['ground_anchor'])!=2 or any(not math.isfinite(v) or v<0 or v>1024 for v in s['ground_anchor']):raise ValueError('Missing ground anchor')
        return {'passed':True,'reference_100m_px':samples[-1]['lengths'],'ground_anchor':samples[-1]['ground_anchor']}
    except (KeyError,TypeError,ValueError) as e:return {'passed':False,'reason':str(e)}


def page(key,scene):
    cfg=qs.read(CONFIG);spec={**cfg['scenes'][scene],'id':scene,'size':1024,'meters_per_pixel':800/1024}
    source_cfg=copy.deepcopy(vw.read(vw.CONFIG));source_cfg['camera']=cfg['camera'];source_cfg['try_orthographic']=False
    original=vw.page(key,spec,source_cfg)
    start=original.index('      const applyCamera=()=>{');end=original.index('    } catch(e){fail(e)}',start)
    return original[:start]+Path(__file__).with_suffix('.js').read_text()+original[end:]


def capture(scene):
    key=os.environ.get('VWORLD_API_KEY','').strip()
    if not key:raise ValueError('VWORLD_API_KEY is missing')
    cfg=qs.read(CONFIG)
    if cfg['size']!=1024 or cfg['width_m']!=800 or cfg['camera']!={'heading_deg':22.5,'pitch_deg':-30,'range_m':900}:raise ValueError('Approved camera changed')
    content=page(key,scene).encode()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!='/':self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(content)
        def log_message(self,*_):pass
    server=ThreadingHTTPServer(('localhost',8767),Handler)
    folder=ROOT/'captures'/seam.stamp()/scene;folder.mkdir(parents=True)
    r={'scene':scene,'spec':cfg['scenes'][scene],'camera':cfg['camera'],'size':1024,'width_m':800,
       'samples':[],'visual_approved':False,'ai_requests':0,'key_persisted':False,'source':'국토교통부 / VWorld'}
    threading.Thread(target=server.serve_forever,daemon=True).start()
    print('CAPTURE='+str(folder.relative_to(seam.P2)),flush=True)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            tab=browser.new_page(viewport={'width':1024,'height':1024},device_scale_factor=1)
            tab.goto('http://localhost:8767/',wait_until='domcontentloaded',timeout=30000)
            tab.wait_for_function('()=>window.__landmark?.ready||window.__P2?.error',timeout=90000)
            if tab.evaluate('()=>window.__P2.error'):raise ValueError('VWorld initialization failed')
            tab.wait_for_timeout(12000)
            deadline=time.monotonic()+60;heights=[]
            while time.monotonic()<deadline:
                h=tab.evaluate('()=>window.__landmark.height()')
                if isinstance(h,(int,float)) and math.isfinite(h):heights.append(h)
                else:heights=[]
                if len(heights)>=3 and max(heights[-3:])-min(heights[-3:])<.1:break
                tab.wait_for_timeout(2000)
            else:raise ValueError('Terrain height unavailable')
            tab.evaluate('h=>window.__landmark.prepare(h,false)',h)
            tab.wait_for_timeout(12000)  # Building cache only; no perspective input is saved.
            tab.evaluate('h=>window.__landmark.prepare(h,true)',h)
            stable=0
            for i in range(45):
                tab.wait_for_timeout(2000);s=tab.evaluate('()=>window.__landmark.measure()');r['samples'].append(s)
                stable=stable+1 if s['tiles_loaded'] else 0
                if (i+1)%10==0:print(scene+': waiting for orthographic source',flush=True)
                if i>=29 and stable>=3:break
            r['samples'].append(tab.evaluate('()=>window.__landmark.measure()'))
            r['validation']=check(r['samples'])
            tab.screenshot(path=str(folder/'source.png'));browser.close()
    except Exception as e:
        r['error']=vw.redact(str(e),key);r['validation']={'passed':False,'reason':'Capture failed'}
    finally:
        server.shutdown();server.server_close()
        r['files']={p.name:qs.sha(p) for p in folder.glob('*.png')}
        vw.write(folder/'capture.json',vw.secret_safe(r,key))
    print(scene+': '+str(r['validation']),flush=True)
    return folder


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scene',choices=['all','gwanghwamun','jongno-tower'],default='all');p.add_argument('--allow-external',action='store_true');a=p.parse_args()
    if not a.allow_external:raise ValueError('Explicit VWorld opt-in required')
    for scene in qs.read(CONFIG)['scenes'] if a.scene=='all' else [a.scene]:capture(scene)
