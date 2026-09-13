// Fixed local-image coordinates, not geographic coordinates. No API or POI layer.
export class PilotMap {
  constructor(canvas, onChange, onError) {
    this.canvas=canvas; this.ctx=canvas.getContext('2d'); this.onChange=onChange; this.onError=onError;
    this.scale=.5; this.maxScale=1; this.minScale=.125; this.center={x:768,y:768};
    this.mode='ai'; this.levels={ai:new Map(),source:new Map()}; this.pointers=new Map();
    this.frame=0; this.showSeams=false; this.ready=false;
    canvas.addEventListener('wheel',e=>{e.preventDefault();if(!this.ready)return;
      const delta=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?this.h:1);
      this.zoom(this.scale*Math.exp(-Math.max(-120,Math.min(120,delta))*.002),e.clientX,e.clientY);
    },{passive:false});
    canvas.addEventListener('pointerdown',e=>{if(!this.ready||(e.pointerType==='mouse'&&e.button!==0))return;
      this.pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});canvas.setPointerCapture(e.pointerId);canvas.classList.add('dragging');});
    canvas.addEventListener('pointermove',e=>this.move(e));
    for(const type of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(type,e=>{
      this.pointers.delete(e.pointerId);if(!this.pointers.size)canvas.classList.remove('dragging');});
    canvas.addEventListener('keydown',e=>{if(!this.ready)return;
      if(['+','=','-','0','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))e.preventDefault();
      if(e.key==='+'||e.key==='=')this.zoom(this.scale*1.25);
      if(e.key==='-')this.zoom(this.scale/1.25);if(e.key==='0')this.fit();
      const delta={ArrowLeft:[-60,0],ArrowRight:[60,0],ArrowUp:[0,-60],ArrowDown:[0,60]}[e.key];
      if(delta){this.center.x+=delta[0]/this.scale;this.center.y+=delta[1]/this.scale;this.update();}
    });
    addEventListener('resize',()=>this.resize());this.resize();
  }
  async load(manifest, base) {
    if(manifest.width!==1536||manifest.height!==1536||manifest.tile_size!==256||manifest.max_native_zoom!==3)
      throw Error('지원하지 않는 시험 지도 크기입니다.');
    if(manifest.status!=='awaiting_user_review')throw Error('완료된 2×2 출력이 아닙니다.');
    this.manifest=manifest;this.base=base;
    await Promise.all(['ai','source'].map(mode=>this.loadLevel(mode,0)));
    this.ready=true;this.fit();
    this.loading=Promise.all(['ai','source'].flatMap(mode=>[1,2,3].map(z=>this.loadLevel(mode,z))))
      .catch(error=>{this.ready=false;this.onError(error);});
  }
  async loadLevel(mode,z) {
    const m=this.manifest,factor=2**(m.max_native_zoom-z),w=Math.ceil(m.width/factor),h=Math.ceil(m.height/factor);
    const buffer=document.createElement('canvas');buffer.width=w;buffer.height=h;const ctx=buffer.getContext('2d');
    const path=mode==='ai'?m.tiles:m.source_tiles;
    if(!['tiles','source_tiles'].includes(path))throw Error('잘못된 타일 경로입니다.');
    await Promise.all(Array.from({length:Math.ceil(h/256)},(_,y)=>Array.from({length:Math.ceil(w/256)},(_,x)=>new Promise((resolve,reject)=>{
      const image=new Image();image.onload=()=>{const ew=Math.min(256,w-x*256),eh=Math.min(256,h-y*256);
        if(image.naturalWidth!==ew||image.naturalHeight!==eh){reject(Error('타일 크기가 올바르지 않습니다.'));return;}
        ctx.drawImage(image,x*256,y*256);resolve();};
      image.onerror=()=>reject(Error(`지도 타일을 불러오지 못했습니다 (${mode} / ${z}/${x}/${y}).`));
      image.src=new URL(`${path}/${z}/${x}/${y}.png`,this.base).href;
    }))).flat());
    this.levels[mode].set(z,buffer);this.update();
  }
  resize(){const rect=this.canvas.getBoundingClientRect();this.w=rect.width;this.h=rect.height;
    this.dpr=Math.min(3,devicePixelRatio||1);this.canvas.width=Math.round(this.w*this.dpr);this.canvas.height=Math.round(this.h*this.dpr);this.update();}
  fit(){if(!this.manifest)return;const mobile=this.w<900;
    const availableW=Math.max(1,this.w-(mobile?28:180)),availableH=Math.max(1,this.h-(mobile?240:180));
    this.scale=Math.max(this.minScale,Math.min(1,availableW/1536,availableH/1536));this.center={x:768,y:768};this.update();}
  world(x,y){return{x:this.center.x+(x-this.w/2)/this.scale,y:this.center.y+(y-this.h/2)/this.scale};}
  zoom(value,x=this.w/2,y=this.h/2){if(!this.manifest)return;const anchor=this.world(x,y);
    this.scale=Math.max(this.minScale,Math.min(this.maxScale,value));
    this.center={x:anchor.x-(x-this.w/2)/this.scale,y:anchor.y-(y-this.h/2)/this.scale};this.update();}
  setDebug(enabled){this.maxScale=enabled?2:1;this.zoom(this.scale);}
  move(e){if(!this.pointers.has(e.pointerId))return;
    const before=[...this.pointers.values()];this.pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});const after=[...this.pointers.values()];
    if(before.length===1){this.center.x-=(after[0].x-before[0].x)/this.scale;this.center.y-=(after[0].y-before[0].y)/this.scale;}
    else if(before.length===2){const mid=p=>({x:(p[0].x+p[1].x)/2,y:(p[0].y+p[1].y)/2});
      const distance=p=>Math.hypot(p[0].x-p[1].x,p[0].y-p[1].y),a=mid(before),b=mid(after),anchor=this.world(a.x,a.y);
      this.scale=Math.max(this.minScale,Math.min(this.maxScale,this.scale*distance(after)/Math.max(1,distance(before))));
      this.center={x:anchor.x-(b.x-this.w/2)/this.scale,y:anchor.y-(b.y-this.h/2)/this.scale};}
    this.update();
  }
  clamp(){if(!this.manifest)return;
    for(const [axis,screen,size] of [['x',this.w,this.manifest.width],['y',this.h,this.manifest.height]]){
      const half=screen/(2*this.scale);this.center[axis]=size<=half*2?size/2:Math.max(half,Math.min(size-half,this.center[axis]));}
  }
  update(){this.clamp();if(!this.frame)this.frame=requestAnimationFrame(()=>{this.frame=0;this.draw();});}
  draw(){const c=this.ctx;c.setTransform(this.dpr,0,0,this.dpr,0,0);c.fillStyle='#D9CBA5';c.fillRect(0,0,this.w,this.h);
    if(!this.manifest)return;const levels=this.levels[this.mode];
    const target=Math.max(0,Math.min(3,3+Math.ceil(Math.log2(this.scale))));
    // Retain a decoded lower-resolution world image until the desired level is ready.
    const z=[...levels.keys()].filter(k=>k<=target).sort((a,b)=>b-a)[0];
    const ox=this.w/2-this.center.x*this.scale,oy=this.h/2-this.center.y*this.scale;
    if(z!==undefined){c.imageSmoothingEnabled=false;c.drawImage(levels.get(z),ox,oy,1536*this.scale,1536*this.scale);}
    if(this.showSeams){c.save();c.beginPath();c.rect(ox,oy,1536*this.scale,1536*this.scale);c.clip();
      c.strokeStyle='#FF4260';c.lineWidth=2;c.setLineDash([6,5]);c.beginPath();
      c.moveTo(ox+768*this.scale,oy);c.lineTo(ox+768*this.scale,oy+1536*this.scale);
      c.moveTo(ox,oy+768*this.scale);c.lineTo(ox+1536*this.scale,oy+768*this.scale);c.stroke();c.setLineDash([]);
      for(const [i,p] of this.manifest.review_targets.entries()){const x=ox+p.xy[0]*this.scale,y=oy+p.xy[1]*this.scale;
        c.fillStyle='#3A2A1E';c.fillRect(x-10,y-10,20,20);c.fillStyle='#F2C14E';c.font='12px monospace';c.fillText(String(i+1),x-4,y+4);}
      c.restore();}
    this.onChange(this);
  }
}
