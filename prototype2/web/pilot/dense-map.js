import {LabMap} from './lab.js';
import {TileLayer,tilePicture,verifiedBytes} from './tile-layer.js';
import {validateDense,cropHit} from './dense-core.js';
import {routePoint,routePhase} from './lab-core.js';
import {vehiclePosition} from './living-core.js';

const canvas=(w,h)=>Object.assign(document.createElement('canvas'),{width:w,height:h});
function maskCanvas(im){
  const c=canvas(im.width,im.height),ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(im,0,0);
  const pixels=ctx.getImageData(0,0,c.width,c.height);for(let i=0;i<pixels.data.length;i+=4){pixels.data[i+3]=pixels.data[i]>=128?255:0;pixels.data[i]=255;pixels.data[i+1]=198;pixels.data[i+2]=65;}ctx.putImageData(pixels,0,0);return c;
}
class CroppedObjects{
  static async load(overlay,base,hashes){
    const l=new CroppedObjects(overlay);
    try{
      const read=async f=>{if(l.images.has(f))return l.images.get(f);const im=await tilePicture(base,f,hashes[f]);l.images.set(f,im);return im;};
      for(const d of overlay.landmarks){
        const [sprite,hit]=await Promise.all([read(d.sprite),read(d.hit)]);
        if([sprite,hit].some(im=>im.width!==d.rect[2]||im.height!==d.rect[3]))throw Error('객체 영역 크기 불일치');
        const c=canvas(hit.width,hit.height),ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(hit,0,0);
        const pixels=ctx.getImageData(0,0,c.width,c.height).data,shape=maskCanvas(hit),outline=canvas(c.width+4,c.height+4),oc=outline.getContext('2d');
        for(const [x,y] of [[0,2],[4,2],[2,0],[2,4]])oc.drawImage(shape,x,y);oc.globalCompositeOperation='destination-out';oc.drawImage(shape,2,2);
        l.children.push({data:{landmark:d},sprite,pixels,shape,outline,visible:!d.reveal_only});
      }
      for(const lane of overlay.traffic.lanes)await read(lane.sprite);
      return l;
    }catch(e){l.close();throw e;}
  }
  constructor(data){this.data=data;this.children=[];this.images=new Map();this.seconds=0;this.lastTick=0;this.trafficVisible=true;this.trafficPlaying=!matchMedia('(prefers-reduced-motion: reduce)').matches;this.towerVisible=true;this.samples=[];}
  close(){for(const im of this.images.values())im.close();this.images.clear();}
  hit(p){return [...this.children].reverse().find(l=>l.visible&&cropHit(p,l.data.landmark.rect,l.pixels))?.data.landmark.id||null;}
  occluderEnabled(id){return !!this.children.find(l=>l.data.landmark.occluder_id===id&&l.visible);}
  setLandmarkVisible(id,value){const l=this.children.find(l=>l.data.landmark.id===id);if(l)l.visible=!!value;}
  advance(now){const moving=this.trafficPlaying&&this.trafficVisible&&!document.hidden;if(moving&&this.lastTick)this.seconds+=Math.min(100,now-this.lastTick)/1000;this.lastTick=moving?now:0;return moving;}
  draw(c,ox,oy,s,selected){for(const l of this.children)if(l.visible){const [x,y,w,h]=l.data.landmark.rect;c.drawImage(l.sprite,ox+x*s,oy+y*s,w*s,h*s);if(l.data.landmark.id===selected)c.drawImage(l.outline,ox+(x-2)*s,oy+(y-2)*s,(w+4)*s,(h+4)*s);}}
  drawTraffic(c,ox,oy,s){
    this.samples=[];if(!this.trafficVisible)return;
    for(const lane of this.data.traffic.lanes)for(const offset of lane.offsets){const p=vehiclePosition(lane,this.seconds,offset,this.data.traffic.speed),im=this.images.get(lane.sprite);c.save();c.globalAlpha=p.alpha;c.drawImage(im,ox+(p.xy[0]-im.width)*s,oy+(p.xy[1]-im.height)*s,im.width*2*s,im.height*2*s);c.restore();this.samples.push({lane:lane.id,xy:p.xy,alpha:p.alpha});}
  }
}
class CroppedReveal{
  static async load(data,objects,base,hashes){
    const target=objects.children.find(l=>l.data.landmark.id===data.targetId),ims=[];
    try{
      for(const f of [data.underlay,data.mask])ims.push(await tilePicture(base,f,hashes[f]));
      const [x,y,w,h]=data.rect;if(ims.some(im=>im.width!==w||im.height!==h))throw Error('재구성 패치 크기 불일치');
      const patch=canvas(w,h),c=patch.getContext('2d');c.drawImage(ims[0],0,0);const r=target.data.landmark.rect;c.drawImage(target.sprite,r[0]-x,r[1]-y);
      c.globalCompositeOperation='destination-in';c.drawImage(maskCanvas(ims[1]),0,0);
      return new CroppedReveal(data,target,patch);
    }finally{for(const im of ims)im.close();}
  }
  constructor(data,target,patch){this.data=data;this.target=target;this.patch=patch;this.opacity=.45;this.active=false;this.amount=0;this.last=0;this.reduced=matchMedia('(prefers-reduced-motion: reduce)');}
  set(active){this.active=!!active;this.last=0;if(this.reduced.matches)this.amount=this.active?1:0;}
  get moving(){return this.amount!==(this.active?1:0)&&!document.hidden;}
  hit(p){return this.active&&cropHit(p,this.target.data.landmark.rect,this.target.pixels)?this.data.targetId:null;}
  draw(c,ox,oy,s,now,selected){
    const goal=this.active?1:0;if(this.reduced.matches)this.amount=goal;else if(!document.hidden){const step=this.last?Math.min(50,now-this.last)/200:0;this.amount+=Math.sign(goal-this.amount)*Math.min(Math.abs(goal-this.amount),step);}this.last=document.hidden?0:now;
    if(!this.amount)return;const [x,y,w,h]=this.data.rect;c.save();c.globalAlpha=this.amount*(1-this.opacity);c.drawImage(this.patch,ox+x*s,oy+y*s,w*s,h*s);c.restore();
    if(selected===this.data.targetId){const r=this.target.data.landmark.rect;c.save();c.globalAlpha=this.amount;c.drawImage(this.target.outline,ox+(r[0]-2)*s,oy+(r[1]-2)*s,(r[2]+4)*s,(r[3]+4)*s);c.restore();}
  }
}

// Old manifests retain the existing LabMap implementation without conversion.
export class DenseMap extends LabMap{
  async loadLab(m,base,scene){
    if(m.kind!=='city-dense-pilot'){this.dense=false;return super.loadLab(m,base,scene);}
    this.ready=false;this.dense=true;this.base=base;this.manifest=m;this.labManifest=m;this.scene='seoul-dense';
    const o=JSON.parse(new TextDecoder().decode(await verifiedBytes(base,m.overlay,m.asset_sha256[m.overlay])));validateDense(m,o);
    this.overlay=o;this.tiles=new TileLayer(m,base,()=>this.update());
    try{
      await this.tiles.init();this.living=await CroppedObjects.load(o,base,m.asset_sha256);
      this.reveal=await CroppedReveal.load(o.reveal,this.living,base,m.asset_sha256);
      this.sprite=await tilePicture(base,m.character,m.asset_sha256[m.character]);
    }catch(e){this.tiles.close();this.living?.close();throw e;}
    this.actorCanvas=canvas(96,120);this.scale=m.initialView.scale;this.center={x:m.initialView.center[0],y:m.initialView.center[1]};this.minScale=Math.min(.125,this.w/m.width,this.h/m.height);this.maxScale=1;this.ready=true;this.update();
  }
  setMode(mode){if(!this.dense)return super.setMode(mode);}
  setRoute(route){if(!this.dense)return super.setRoute(route);this.setPlaying(false);this.overlay.route=route;this.setPhase(0);}
  draw(){
    if(!this.dense)return super.draw();
    const c=this.ctx;c.setTransform(this.dpr,0,0,this.dpr,0,0);c.fillStyle='#D9CBA5';c.fillRect(0,0,this.w,this.h);if(!this.ready)return;
    const now=performance.now();if(this.playing&&!document.hidden){if(this.lastTick)this.phase=routePhase(this.phase,now-this.lastTick,this.overlay.route.playback);this.lastTick=now;if(this.phase===1)this.playing=false;}
    const position=routePoint(this.overlay.route.points,this.phase),trafficMoving=this.living.advance(now);
    if(this.playing&&this.follow){this.center={x:position.xy[0],y:position.xy[1]};this.clamp();}
    const s=this.scale,ox=this.w/2-this.center.x*s,oy=this.h/2-this.center.y*s;
    c.imageSmoothingEnabled=false;this.tiles.draw(c,ox,oy,s,{x:-ox/s,y:-oy/s,width:this.w/s,height:this.h/s});
    c.save();c.beginPath();c.rect(ox,oy,this.manifest.width*s,this.manifest.height*s);c.clip();
    if(this.routeVisible){c.strokeStyle='#F2C14E';c.lineWidth=2;c.setLineDash([5,4]);c.beginPath();this.overlay.route.points.forEach((p,i)=>i?c.lineTo(ox+p.xy[0]*s,oy+p.xy[1]*s):c.moveTo(ox+p.xy[0]*s,oy+p.xy[1]*s));c.stroke();c.setLineDash([]);}
    this.living.draw(c,ox,oy,s,this.selected?.id);this.reveal.draw(c,ox,oy,s,now,this.selected?.id);this.living.drawTraffic(c,ox,oy,s);
    if(this.actorVisible){
      const ac=this.actorCanvas.getContext('2d');ac.clearRect(0,0,96,120);ac.imageSmoothingEnabled=false;ac.save();if(position.direction<0){ac.translate(96,0);ac.scale(-1,1);}ac.drawImage(this.sprite,48-this.sprite.width,108-this.sprite.height*2,this.sprite.width*2,this.sprite.height*2);ac.restore();
      ac.globalCompositeOperation='destination-out';for(const l of this.living.children)if(l.visible&&position.behind.includes(l.data.landmark.occluder_id)){const r=l.data.landmark.rect;ac.drawImage(l.shape,r[0]-position.xy[0]+48,r[1]-position.xy[1]+108);}ac.globalCompositeOperation='source-over';
      c.drawImage(this.actorCanvas,ox+(position.xy[0]-48)*s,oy+(position.xy[1]-108)*s,96*s,120*s);
    }
    c.restore();this.rain?.draw(c,this.w,this.h,now);
    Object.assign(this.canvas.dataset,{scene:this.scene,phase:String(this.phase),playing:String(this.playing),selected:this.selected?.id||'',trafficPlaying:String(this.living.trafficPlaying),trafficTime:String(this.living.seconds),vehicles:JSON.stringify(this.living.samples),reveal:String(this.reveal.active),revealAmount:String(this.reveal.amount),tileCache:String(this.tiles.cache.size),tilePending:String(this.tiles.pending.size),tileFailed:String(this.tiles.failed.size),tileRequests:String(this.tiles.requests)});
    this.onChange(this);this.onFrame?.(this);
    if((this.playing||trafficMoving||this.rain?.moving||this.reveal.moving)&&!document.hidden&&!this.tickTimer)this.tickTimer=setTimeout(()=>{this.tickTimer=0;this.update();},33);
  }
}
