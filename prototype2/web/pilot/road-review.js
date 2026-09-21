// Local comparison only; no guide calls or public manifest changes.
import {CroppedObjects} from './dense-map.js';
import {tilePicture,verifiedBytes} from './tile-layer.js';
const c=document.querySelector('#review'),ctx=c.getContext('2d'),status=document.querySelector('#status');
try{
  const cfg=await(await fetch('./review.json')).json(),base=new URL(cfg.snapshot,location.href);
  const m=await(await fetch(new URL('manifest.json',base))).json();
  if(!m.reviewOnly)throw Error('Local review snapshot required');
  const o=JSON.parse(new TextDecoder().decode(await verifiedBytes(base,m.overlay,m.asset_sha256[m.overlay])));
  const objects=await CroppedObjects.load(o,base,m.asset_sha256);
  const before=await tilePicture(new URL('./',location.href),cfg.before,cfg.hashes[cfg.before]);
  const after=await tilePicture(new URL('./',location.href),cfg.after,cfg.hashes[cfg.after]);
  let mode=cfg.candidateAccepted?'after':'before',scale=innerWidth<600?.5:1,center=[...cfg.center],drag=null,raf=0;
  const update=()=>{if(!raf)raf=requestAnimationFrame(draw);};
  function draw(now){
    raf=0;const r=c.getBoundingClientRect(),dpr=devicePixelRatio||1;
    if(c.width!==Math.round(r.width*dpr)||c.height!==Math.round(r.height*dpr)){c.width=Math.round(r.width*dpr);c.height=Math.round(r.height*dpr);}
    ctx.setTransform(dpr,0,0,dpr,0,0);ctx.imageSmoothingEnabled=false;ctx.fillStyle='#e9debf';ctx.fillRect(0,0,r.width,r.height);
    const ox=r.width/2-center[0]*scale,oy=r.height/2-center[1]*scale;
    ctx.drawImage(mode==='before'?before:after,ox+cfg.rect[0]*scale,oy+cfg.rect[1]*scale,1024*scale,1024*scale);
    ctx.save();ctx.beginPath();ctx.rect(ox+cfg.rect[0]*scale,oy+cfg.rect[1]*scale,1024*scale,1024*scale);ctx.clip();
    objects.draw(ctx,ox,oy,scale,null);objects.trafficVisible=mode!=='empty';const moving=objects.advance(now);objects.drawTraffic(ctx,ox,oy,scale);ctx.restore();
    for(const b of document.querySelectorAll('button[data-mode]'))b.setAttribute('aria-pressed',String(b.dataset.mode===mode));
    Object.assign(c.dataset,{ready:'true',mode,scale:String(scale),time:String(objects.seconds),vehicles:JSON.stringify(objects.samples),playing:String(objects.trafficPlaying)});
    document.querySelector('#motion').textContent=objects.trafficPlaying?'차량 일시정지':'차량 재생';
    status.textContent=`${Math.round(scale*100)}% · ${mode==='empty'?0:2}대 · 원본 도로 위 정지 차량 제거 시험`;
    if(moving&&!document.hidden)update();
  }
  document.querySelector('#notice').textContent=cfg.candidateAccepted?'로컬 비교 후보 · 사용자 미승인 · 기존 지도/배포 변경 없음':'보정 후보 미채택 · ②③은 문제 확인용 · 기존 지도/배포 변경 없음';
  for(const b of document.querySelectorAll('button[data-mode]'))b.onclick=()=>{mode=b.dataset.mode;objects.lastTick=0;update();};
  for(const b of document.querySelectorAll('button[data-scale]'))b.onclick=()=>{scale=Number(b.dataset.scale);update();};
  document.querySelector('#motion').onclick=()=>{objects.trafficPlaying=!objects.trafficPlaying;objects.lastTick=0;update();};
  document.querySelector('#reset').onclick=()=>{center=[...cfg.center];update();};
  c.onpointerdown=e=>{drag=[e.clientX,e.clientY,...center];c.setPointerCapture(e.pointerId);};
  c.onpointermove=e=>{if(!drag)return;center=[Math.max(cfg.rect[0],Math.min(cfg.rect[2],drag[2]-(e.clientX-drag[0])/scale)),Math.max(cfg.rect[1],Math.min(cfg.rect[3],drag[3]-(e.clientY-drag[1])/scale))];update();};
  c.onpointerup=c.onpointercancel=()=>{drag=null;};
  document.addEventListener('visibilitychange',()=>{objects.lastTick=0;update();});new ResizeObserver(update).observe(c);update();
}catch(e){status.textContent='검수 화면 로딩 실패: '+e.message;throw e;}
