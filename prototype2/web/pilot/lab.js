import {PilotMap} from './map.js';
import {routePoint,routePhase,hitSpot,validOverlay} from './lab-core.js';
import {LivingLayer} from './living.js';
import {labSize} from './lab-size.js';

function asset(base,file){if(!/^[a-zA-Z0-9_./-]+$/.test(file)||file.includes('..')||file.startsWith('/'))throw Error('잘못된 에셋 경로');return new URL(file,base);}
async function picture(base,file,expected){
  const r=await fetch(asset(base,file));if(!r.ok)throw Error('시험 이미지를 불러오지 못했습니다: '+file);
  const bytes=await r.arrayBuffer();if(bytes.byteLength>32*1024*1024)throw Error('시험 이미지 크기 초과');
  if(expected){const digest=await crypto.subtle.digest('SHA-256',bytes),hash=[...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('');if(hash!==expected)throw Error('시험 이미지 해시 불일치: '+file);}
  try{return await createImageBitmap(new Blob([bytes]));}catch{throw Error('시험 이미지 형식 오류: '+file);}
}

export class LabMap extends PilotMap {
  constructor(canvas,onChange,onError){
    super(canvas,onChange,onError);this.images=new Map();this.phase=0;this.playing=false;this.follow=true;this.routeVisible=true;this.pinsVisible=true;this.selected=null;this.mode='final';this.lastTick=0;
    this.actorCanvas=document.createElement('canvas');this.actorCanvas.width=48;this.actorCanvas.height=60;
    canvas.addEventListener('pointerdown',e=>{if(this.pointers.size>1)this.clickStart=null;else this.clickStart={x:e.clientX,y:e.clientY};});
    canvas.addEventListener('pointermove',e=>{if(this.clickStart&&Math.hypot(e.clientX-this.clickStart.x,e.clientY-this.clickStart.y)>5)this.clickStart=null;});
    canvas.addEventListener('pointerup',e=>{if(!this.clickStart||!this.ready||this.mode!=='final')return;this.clickStart=null;const r=canvas.getBoundingClientRect(),p=this.world(e.clientX-r.left,e.clientY-r.top);const spots=(this.overlay?.spots||[]).filter(s=>!(this.overlay.landmark?.mode==='highlight_only'&&s.id===this.overlay.landmark.id));this.select(this.living?.hit(p)||(this.pinsVisible?hitSpot(spots,p,this.scale)?.id:null)||null);});
    canvas.addEventListener('pointercancel',()=>this.clickStart=null);
    canvas.addEventListener('keydown',e=>{if(e.key==='Escape')this.select(null);});
    document.addEventListener('visibilitychange',()=>{this.lastTick=0;if(this.living)this.living.lastTick=0;if(!document.hidden)this.update();});
  }
  async loadLab(manifest,base,scene){
    if(manifest.version!==1||!manifest.scenes[scene])throw Error('지원하지 않는 시험 장면입니다.');
    this.labManifest=manifest;this.base=base;this.manifest=labSize(manifest);this.ready=false;
    const sprite=await picture(base,manifest.character,manifest.asset_sha256[manifest.character]);this.sprite=sprite;
    await this.setScene(scene);this.ready=true;this.fit();
  }
  async setScene(id){
    const token=this.loadToken=(this.loadToken||0)+1;this.ready=false;this.canvas.dataset.scene='';this.setPlaying(false);
    const scene=this.labManifest.scenes[id];if(!scene)throw Error('장면을 찾을 수 없습니다.');
    const images=new Map();await Promise.all(Object.entries(scene.variants).map(async([key,v])=>{const im=await picture(this.base,v.file,v.sha256);if(im.width!==this.manifest.width||im.height!==this.manifest.width)throw Error('지도 크기 불일치');images.set(key,im);}));
    const response=await fetch(asset(this.base,scene.overlay),{cache:'no-store'});if(!response.ok)throw Error('가림·장소 데이터가 없습니다.');
    const bytes=await response.arrayBuffer(),expected=this.labManifest.overlay_sha256?.[id];
    if(expected){const digest=await crypto.subtle.digest('SHA-256',bytes);if([...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('')!==expected)throw Error('객체 데이터 해시 불일치');}
    const overlay=validOverlay(JSON.parse(new TextDecoder().decode(bytes)),scene.variants.final.sha256,this.manifest);
    const living=await LivingLayer.load(overlay,this.base,this.labManifest.asset_sha256,picture,this.manifest);
    if(this.labManifest.kind==='projection-expand')living.trafficPlaying=false;
    if(token!==this.loadToken){for(const im of images.values())im.close();living.close();return;}
    this.living?.close();this.living=living;
    for(const im of this.images.values())im.close();
    this.images=images;this.scene=id;this.sceneData=scene;this.overlay=overlay;this.mode='final';this.phase=0;this.selected=null;
    this.masks=new Map(overlay.occluders.map(o=>{const c=document.createElement('canvas');c.width=c.height=this.manifest.width;const ctx=c.getContext('2d');ctx.beginPath();o.polygon.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();ctx.fill();return[o.id,c];}));
    this.routeCanvas=null;
    if(overlay.landmark?.mode==='highlight_only'){
      const route=document.createElement('canvas');route.width=route.height=this.manifest.width;const rc=route.getContext('2d');
      rc.beginPath();overlay.route.points.forEach((p,i)=>i?rc.lineTo(...p.xy):rc.moveTo(...p.xy));rc.lineWidth=3;rc.strokeStyle='#FFF5CB';rc.stroke();rc.lineWidth=1;rc.strokeStyle='#CE672D';rc.setLineDash([6,5]);rc.stroke();
      rc.globalCompositeOperation='destination-out';for(const m of this.masks.values())rc.drawImage(m,0,0);this.routeCanvas=route;
    }
    this.ready=true;this.update();this.onScene?.(scene);this.onSelection?.(null);
  }
  setMode(mode){if(!this.images.has(mode))return;this.mode=mode;if(mode!=='final'){this.setPlaying(false);if(this.living)this.living.trafficPlaying=false;this.select(null);}this.update();}
  select(id){this.selected=this.overlay?.spots.find(s=>s.id===id)||null;this.onSelection?.(this.selected);this.update();}
  focusSpot(id){this.select(id);if(this.selected){this.center={x:this.selected.xy[0],y:this.selected.xy[1]};this.scale=Math.max(this.scale,.75);this.update();}}
  setPlaying(value){this.playing=!!value&&this.mode==='final';this.lastTick=0;if(this.playing){if(this.overlay.route.playback==='once'&&this.phase===1)this.phase=0;this.scale=Math.max(this.scale,this.w<900?1:.75);}this.update();}
  setPhase(value){this.playing=false;this.phase=Math.max(0,Math.min(1,value));this.lastTick=0;if(this.follow){const p=routePoint(this.overlay.route.points,this.phase);this.center={x:p.xy[0],y:p.xy[1]};}this.update();}
  draw(){
    const c=this.ctx;c.setTransform(this.dpr,0,0,this.dpr,0,0);c.fillStyle='#D9CBA5';c.fillRect(0,0,this.w,this.h);
    if(!this.ready||!this.images?.size)return;
    const now=performance.now();if(this.playing&&!document.hidden){if(this.lastTick)this.phase=routePhase(this.phase,now-this.lastTick,this.overlay.route.playback);this.lastTick=now;if(this.overlay.route.playback==='once'&&this.phase===1)this.playing=false;}
    const trafficMoving=this.living?.advance(now,this.mode==='final');
    const position=routePoint(this.overlay.route.points,this.phase);
    if(this.playing&&this.follow){this.center={x:position.xy[0],y:position.xy[1]};this.clamp();}
    const ox=this.w/2-this.center.x*this.scale,oy=this.h/2-this.center.y*this.scale;
    c.imageSmoothingEnabled=false;c.drawImage(this.images.get(this.mode),ox,oy,this.manifest.width*this.scale,this.manifest.width*this.scale);
    c.save();c.beginPath();c.rect(ox,oy,this.manifest.width*this.scale,this.manifest.width*this.scale);c.clip();
    if(this.mode==='final')this.living?.drawBackground(c,ox,oy,this.scale,this.selected?.id);
    if(this.showSeams){
      const n=this.manifest.width,grid=n===2304?[768,1536]:[768];
      const lines=[...grid.flatMap(x=>[[[x,0],[x,n],'#FF4260'],[[0,x],[n,x],'#FF4260']]),
        ...(this.overlay.generation_edges||[[[896,0],[896,n]],[[0,896],[n,896]]]).map(([a,b])=>[a,b,'#31E1FF'])];
      for(const [a,b,color] of lines){c.strokeStyle=color;c.lineWidth=1.5;c.setLineDash([6,5]);c.beginPath();c.moveTo(ox+a[0]*this.scale,oy+a[1]*this.scale);c.lineTo(ox+b[0]*this.scale,oy+b[1]*this.scale);c.stroke();}c.setLineDash([]);
    }
    if(this.mode==='final'){
      this.living?.drawTraffic(c,ox,oy,this.scale);
      if(this.routeVisible){if(this.routeCanvas)c.drawImage(this.routeCanvas,ox,oy,this.manifest.width*this.scale,this.manifest.width*this.scale);else{c.strokeStyle='#FFF5CB';c.lineWidth=5;c.beginPath();this.overlay.route.points.forEach((p,i)=>{const x=ox+p.xy[0]*this.scale,y=oy+p.xy[1]*this.scale;i?c.lineTo(x,y):c.moveTo(x,y);});c.stroke();c.strokeStyle='#CE672D';c.lineWidth=2;c.setLineDash([6,5]);c.stroke();c.setLineDash([]);}}
      const actor=this.actorCanvas,ac=actor.getContext('2d',{willReadFrequently:true});ac.clearRect(0,0,48,60);ac.imageSmoothingEnabled=false;
      const bob=this.playing?Math.round(Math.sin(this.phase*100*Math.PI)):0;
      ac.save();if(position.direction<0){ac.translate(48,0);ac.scale(-1,1);}ac.drawImage(this.sprite,Math.round((48-this.sprite.width)/2),54-this.sprite.height+bob);ac.restore();
      const before=ac.getImageData(0,0,48,60).data;let visible=0,total=0;for(let i=3;i<before.length;i+=4)if(before[i]>=128)total++;
      ac.globalCompositeOperation='destination-out';for(const id of position.behind)if(this.living.occluderEnabled(id))ac.drawImage(this.masks.get(id),position.xy[0]-24,position.xy[1]-54,48,60,0,0,48,60);ac.globalCompositeOperation='source-over';
      const after=ac.getImageData(0,0,48,60).data;for(let i=3;i<after.length;i+=4)if(after[i]>=128)visible++;
      if(this.actorVisible!==false)c.drawImage(actor,ox+(position.xy[0]-24)*this.scale,oy+(position.xy[1]-54)*this.scale,48*this.scale,60*this.scale);
      this.canvas.dataset.actorVisible=String(visible);this.canvas.dataset.actorOccluded=String(total-visible);this.canvas.dataset.segment=String(position.segment);
      if(this.pinsVisible)for(const [i,s] of this.overlay.spots.entries()){
        if(this.overlay.landmark?.mode==='highlight_only'&&s.id===this.overlay.landmark.id)continue;
        const x=ox+s.xy[0]*this.scale,y=oy+s.xy[1]*this.scale;
        c.fillStyle=this.selected?.id===s.id?'#E8735A':'#F2C14E';c.strokeStyle='#3A2A1E';c.lineWidth=2;c.beginPath();c.arc(x,y,13,0,Math.PI*2);c.fill();c.stroke();
        c.fillStyle='#3A2A1E';c.font='bold 13px monospace';c.textAlign='center';c.fillText(String(i+1),x,y+5);
      }
    }
    c.restore();this.canvas.dataset.scene=this.scene;this.canvas.dataset.phase=String(this.phase);this.canvas.dataset.playing=String(this.playing);this.canvas.dataset.selected=this.selected?.id||'';
    this.canvas.dataset.towerVisible=String(this.living.towerVisible);this.canvas.dataset.towerLight=String(this.living.light);this.canvas.dataset.trafficPlaying=String(this.living.trafficPlaying);this.canvas.dataset.trafficTime=String(this.living.seconds);this.canvas.dataset.vehicles=JSON.stringify(this.mode==='final'?this.living.samples||[]:[]);
    this.onChange(this);this.onFrame?.(this);
    if((this.playing||trafficMoving)&&!document.hidden&&!this.tickTimer)this.tickTimer=setTimeout(()=>{this.tickTimer=0;this.update();},33);
  }
}
