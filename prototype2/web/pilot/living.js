import {vehiclePosition,validateLiving} from './living-core.js';

function canvas(w=1536,h=1536){const c=document.createElement('canvas');c.width=w;c.height=h;return c;}

export class LivingLayer {
  static async load(overlay,base,hashes,picture){
    validateLiving(overlay);const layer=new LivingLayer(overlay);
    const files=new Set(overlay.traffic?.lanes.map(l=>l.sprite)||[]);
    if(overlay.landmark)for(const key of ['background','sprite','hit','light'])files.add(overlay.landmark[key]);
    try{
      for(const file of files){if(!hashes[file])throw Error('객체 이미지 해시 누락');layer.images.set(file,await picture(base,file,hashes[file]));}
      if(overlay.landmark){
        for(const key of ['background','sprite','hit','light']){const im=layer.images.get(overlay.landmark[key]);if(im.width!==1536||im.height!==1536)throw Error('랜드마크 크기 불일치');}
        const hit=canvas(),ctx=hit.getContext('2d',{willReadFrequently:true});ctx.drawImage(layer.images.get(overlay.landmark.hit),0,0);layer.hitPixels=ctx.getImageData(0,0,1536,1536).data;
        const shape=canvas(),sc=shape.getContext('2d');const pixels=sc.createImageData(1536,1536);
        for(let i=0;i<pixels.data.length;i+=4){pixels.data[i]=255;pixels.data[i+1]=198;pixels.data[i+2]=65;pixels.data[i+3]=layer.hitPixels[i]>=128?255:0;}sc.putImageData(pixels,0,0);
        layer.outline=canvas();const oc=layer.outline.getContext('2d');for(const [x,y] of [[-2,0],[2,0],[0,-2],[0,2]])oc.drawImage(shape,x,y);oc.globalCompositeOperation='destination-out';oc.drawImage(shape,0,0);
      }
      for(const o of overlay.traffic?.occluders||[]){const c=canvas(),ctx=c.getContext('2d');ctx.beginPath();o.polygon.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();ctx.fill();layer.masks.push(c);}
      return layer;
    }catch(e){layer.close();throw e;}
  }
  constructor(overlay){this.data=overlay;this.images=new Map();this.masks=[];this.towerVisible=true;this.light=false;this.trafficVisible=true;this.trafficPlaying=!!overlay.traffic&&!matchMedia('(prefers-reduced-motion: reduce)').matches;this.seconds=0;this.lastTick=0;this.scratch=canvas(64,64);}
  close(){for(const im of this.images.values())im.close();this.images.clear();}
  hit(p){return this.towerVisible&&p.x>=0&&p.y>=0&&p.x<1536&&p.y<1536&&this.hitPixels?.[(Math.floor(p.y)*1536+Math.floor(p.x))*4]>=128?this.data.landmark.id:null;}
  occluderEnabled(id){return !(this.data.landmark?.occluder_id===id&&!this.towerVisible);}
  advance(now,active){const moving=active&&!document.hidden&&this.trafficVisible&&this.trafficPlaying&&!!this.data.traffic;if(moving&&this.lastTick)this.seconds+=Math.min(100,now-this.lastTick)/1000;this.lastTick=moving?now:0;return moving;}
  drawBackground(c,ox,oy,scale,selected){
    const l=this.data.landmark;if(!l)return;
    const draw=im=>c.drawImage(im,ox,oy,1536*scale,1536*scale);
    draw(this.images.get(l.background));if(this.towerVisible){draw(this.images.get(l.sprite));if(this.light)draw(this.images.get(l.light));if(selected===l.id)draw(this.outline);}
  }
  drawTraffic(c,ox,oy,scale){
    this.samples=[];if(!this.data.traffic||!this.trafficVisible)return;
    const ac=this.scratch.getContext('2d',{willReadFrequently:true});
    for(const lane of this.data.traffic.lanes)for(const offset of lane.offsets){
      const p=vehiclePosition(lane,this.seconds,offset,this.data.traffic.speed),im=this.images.get(lane.sprite);
      ac.clearRect(0,0,64,64);ac.imageSmoothingEnabled=false;ac.drawImage(im,Math.round((64-im.width)/2),Math.round((64-im.height)/2));
      const count=()=>{const a=ac.getImageData(0,0,64,64).data;let n=0;for(let i=3;i<a.length;i+=4)if(a[i]>=128)n++;return n;};
      const total=count();ac.globalCompositeOperation='destination-out';for(const m of this.masks)ac.drawImage(m,p.xy[0]-32,p.xy[1]-32,64,64,0,0,64,64);ac.globalCompositeOperation='source-over';
      const visible=count();c.save();c.globalAlpha=p.alpha;c.drawImage(this.scratch,ox+(p.xy[0]-32)*scale,oy+(p.xy[1]-32)*scale,64*scale,64*scale);c.restore();
      this.samples.push({lane:lane.id,xy:p.xy,visible,occluded:total-visible,alpha:p.alpha});
    }
  }
}
