"""1792x1024 source aligned to the existing Jongno Tower trial. No AI calls."""
import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import threading
import landmark_capture as parent

seam=parent.seam;qs=parent.qs;vw=parent.vw
ROOT=seam.P2/'eval/vworld/landmark_link'
PARENT=parent.ROOT/'runs/20260914T144245416491Z'

def baseline():
    r=qs.read(PARENT/'jongno-tower_capture.json')
    if not parent.check(r['samples'])['passed'] or qs.sha(PARENT/'jongno-tower_source.png')!=r['files']['source.png']:raise ValueError('Parent source changed')
    return r['samples'][-1]

def check(samples):
    try:
        if len(samples)<4:raise ValueError('Four settled samples required')
        expected=samples[0]['expected']
        for s in samples:
            if s['viewport']!=[1792,1024] or s['drawing_buffer']!=[1792,1024]:raise ValueError('Pixel scale changed')
            if not s['orthographic'] or not math.isfinite(s['width']) or abs(s['width']-1400)>1e-6:raise ValueError('Projection changed')
            m=s['matrix']
            if len(m)!=16 or not all(math.isfinite(v) for v in m) or abs(m[15]-1)>1e-9 or abs(m[11])>1e-9:raise ValueError('Invalid projection')
            for k,tol in [('position',.01),('direction',1e-6),('up',1e-6)]:
                if len(s[k])!=3 or not all(math.isfinite(v) for v in s[k]) or math.dist(s[k],expected[k])>tol:raise ValueError('Camera drift')
            for key,n,limit,target in [('lengths',3,1,128),('alignment_errors',9,1,0)]:
                if len(s[key])!=n or any(not math.isfinite(v) or abs(v-target)>limit for v in s[key]):raise ValueError('Source alignment failed')
        return {'passed':True,'max_alignment_error_px':max(max(s['alignment_errors']) for s in samples),'reference_100m_px':samples[-1]['lengths']}
    except (KeyError,TypeError,ValueError) as e:return {'passed':False,'reason':str(e)}

def page(key):
    cfg=copy.deepcopy(vw.read(vw.CONFIG));cfg['camera']={'heading_deg':22.5,'pitch_deg':-30,'range_m':900}
    spec={**qs.read(parent.CONFIG)['scenes']['jongno-tower'],'id':'jongno-link','size':1024,'meters_per_pixel':800/1024}
    original=vw.page(key,spec,cfg);start=original.index('      const applyCamera=()=>{');end=original.index('    } catch(e){fail(e)}',start)
    return original[:start]+'const BASE='+json.dumps(baseline())+';\n'+Path(__file__).with_suffix('.js').read_text()+original[end:]

def capture():
    key=os.environ.get('VWORLD_API_KEY','').strip()
    if not key:raise ValueError('VWORLD_API_KEY is missing')
    content=page(key).encode()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!='/':self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(content)
        def log_message(self,*_):pass
    server=ThreadingHTTPServer(('localhost',8767),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    folder=ROOT/'captures'/seam.stamp();folder.mkdir(parents=True)
    r={'run_id':folder.name,'samples':[],'size':[1792,1024],'parent_offset':[768,0],'width_m':1400,'visual_approved':False,'ai_requests':0,'key_persisted':False,'source':'국토교통부 / VWorld'}
    print('CAPTURE='+folder.name,flush=True)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True);p=browser.new_page(viewport={'width':1792,'height':1024},device_scale_factor=1)
            p.goto('http://localhost:8767/',wait_until='domcontentloaded',timeout=30000)
            p.wait_for_function('()=>window.__link?.ready||window.__P2?.error',timeout=90000)
            if p.evaluate('()=>window.__P2.error'):raise ValueError('VWorld initialization failed')
            p.wait_for_timeout(12000)
            for xy in [[512,600],[1280,600]]:
                p.evaluate('xy=>window.__link.warm(xy)',xy);p.wait_for_timeout(12000);print('Warmed building cache; no perspective output',flush=True)
            p.evaluate('()=>window.__link.prepare()');stable=0
            for i in range(45):
                p.wait_for_timeout(2000);s=p.evaluate('()=>window.__link.measure()');r['samples'].append(s);stable=stable+1 if s['tiles_loaded'] else 0
                if (i+1)%10==0:print('Waiting for source geometry',flush=True)
                if i>=29 and stable>=3:break
            r['samples'].append(p.evaluate('()=>window.__link.measure()'));r['validation']=check(r['samples']);p.screenshot(path=str(folder/'source.png'));browser.close()
    except Exception as e:r['error']=vw.redact(str(e),key);r['validation']={'passed':False,'reason':'Capture failed'}
    finally:
        server.shutdown();server.server_close();r['files']={p.name:qs.sha(p) for p in folder.glob('*.png')};qs.write(folder/'capture.json',vw.secret_safe(r,key))
    print(r['validation'],flush=True)
    return folder

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--allow-external',action='store_true');a=p.parse_args()
    if not a.allow_external:raise ValueError('Explicit VWorld opt-in required')
    capture()
