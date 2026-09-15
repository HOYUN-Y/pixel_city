// A bounded reconstructed patch blended over the original map, never a whole-map fade.
export class RevealLayer {
  static async load(data,base,hashes,picture,size,living){
    if(!data)return null;
    const target=living.children.find(c=>c.data.landmark.id===data.targetId);
    if(!target||!target.data.landmark.reveal_only)throw Error('가림 해제 대상 불일치');
    const images=[];
    try{
      for(const file of [data.underlay,data.mask]){if(!hashes[file])throw Error('가림 해제 해시 누락');const im=await picture(base,file,hashes[file]);if(im.width!==size.width||im.height!==size.height)throw Error('가림 해제 크기 불일치');images.push(im);}
      const c=document.createElement('canvas');c.width=size.width;c.height=size.height;
      const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(images[1],0,0);
      const mask=ctx.getImageData(0,0,size.width,size.height);
      for(let i=0;i<mask.data.length;i+=4)mask.data[i+3]=mask.data[i]>=128?255:0;
      ctx.putImageData(mask,0,0);
      const layer=new RevealLayer(data,c,target.hitPixels,size);
      layer.patch=document.createElement('canvas');layer.patch.width=c.width;layer.patch.height=c.height;
      const pc=layer.patch.getContext('2d');pc.drawImage(images[0],0,0);pc.drawImage(target.images.get(target.data.landmark.sprite),0,0);pc.globalCompositeOperation='destination-in';pc.drawImage(c,0,0);
      layer.outline=target.outline;return layer;
    }finally{for(const im of images)im.close();}
  }
  constructor(data,mask,hit,size){this.data=data;this.mask=mask;this.hitPixels=hit;this.size=size;this.active=false;this.amount=0;this.last=0;this.opacity=.45;this.query=matchMedia('(prefers-reduced-motion: reduce)');}
  set(active){this.active=!!active;this.last=0;if(this.query.matches)this.amount=this.active?1:0;}
  get moving(){return this.amount!==(this.active?1:0)&&!document.hidden;}
  hit(p){return this.active&&p.x>=0&&p.y>=0&&p.x<this.size.width&&p.y<this.size.height&&this.hitPixels[(Math.floor(p.y)*this.size.width+Math.floor(p.x))*4]>=128?this.data.targetId:null;}
  draw(c,ox,oy,scale,now,selected){
    const goal=this.active?1:0;
    if(this.query.matches)this.amount=goal;
    else if(!document.hidden){const step=this.last?Math.min(50,now-this.last)/200:0;this.amount+=Math.sign(goal-this.amount)*Math.min(Math.abs(goal-this.amount),step);}
    this.last=document.hidden?0:now;
    if(!this.amount)return;
    c.save();c.globalAlpha=this.amount*(1-this.opacity);c.drawImage(this.patch,ox,oy,this.size.width*scale,this.size.height*scale);c.restore();
    if(selected===this.data.targetId){c.save();c.globalAlpha=this.amount;c.drawImage(this.outline,ox,oy,this.size.width*scale,this.size.height*scale);c.restore();}
  }
}
