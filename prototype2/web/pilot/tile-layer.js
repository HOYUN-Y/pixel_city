// Native world pixels; decoded detail tiles have a bounded lifetime.
export function safeAsset(base,file){
  if(typeof file!=='string'||!/^[a-zA-Z0-9_./-]+$/.test(file)||file.includes('..')||file.startsWith('/'))throw Error('잘못된 지도 파일 경로');
  return new URL(file,base);
}
export async function verifiedBytes(base,file,hash){
  if(!/^[a-f0-9]{64}$/.test(hash||''))throw Error('지도 파일 해시 누락');
  const response=await fetch(safeAsset(base,file));if(!response.ok)throw Error('지도 자료를 불러오지 못했습니다');
  const bytes=await response.arrayBuffer();if(bytes.byteLength>32*1024*1024)throw Error('지도 파일 크기 초과');
  const digest=await crypto.subtle.digest('SHA-256',bytes);
  if([...new Uint8Array(digest)].map(n=>n.toString(16).padStart(2,'0')).join('')!==hash)throw Error('지도 자료 검증 실패');
  return bytes;
}
export async function tilePicture(base,file,hash){return createImageBitmap(new Blob([await verifiedBytes(base,file,hash)]));}
export function visibleTiles(size,level,view,halo=0){
  const step=512/level,cols=Math.ceil(size.width/step),rows=Math.ceil(size.height/step),items=[];
  const x0=Math.max(0,Math.floor(view.x/step)-halo),x1=Math.min(cols-1,Math.ceil((view.x+view.width)/step)-1+halo);
  const y0=Math.max(0,Math.floor(view.y/step)-halo),y1=Math.min(rows-1,Math.ceil((view.y+view.height)/step)-1+halo);
  for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++)items.push({x,y,level,key:`${level}/${x}/${y}`,file:`tiles/${level}/${x}_${y}.png`,world:[x*step,y*step,Math.min(step,size.width-x*step),Math.min(step,size.height-y*step)]});
  return items;
}
export class TileLayer{
  constructor(manifest,base,changed,picture=tilePicture){
    this.manifest=manifest;this.base=base;this.changed=changed;this.picture=picture;
    this.cache=new Map();this.pending=new Set();this.failed=new Set();this.wanted=[];this.visible=new Set();this.closed=false;this.requests=0;
  }
  async init(){
    this.preview=await this.picture(this.base,this.manifest.preview,this.manifest.asset_sha256[this.manifest.preview]);
    if(this.preview.width!==this.manifest.width/4||this.preview.height!==this.manifest.height/4){this.preview.close();throw Error('미리보기 크기 불일치');}
  }
  close(){this.closed=true;this.preview?.close();for(const im of this.cache.values())im.close();this.cache.clear();}
  request(view,scale){
    const level=scale>.5?1:scale>.25?.5:.25;
    // The always-resident quarter preview already covers the lowest level.
    const visible=level===.25?[]:visibleTiles(this.manifest,level,view);
    this.visible=new Set(visible.map(t=>t.key));
    const neighbors=level===.25?[]:visibleTiles(this.manifest,level,view,1).filter(t=>!this.visible.has(t.key));
    this.wanted=[...visible,...neighbors].slice(0,48);
    for(const t of visible)if(this.cache.has(t.key)){const im=this.cache.get(t.key);this.cache.delete(t.key);this.cache.set(t.key,im);}
    this.pump();return visible;
  }
  pump(){
    if(this.closed)return;
    for(const t of this.wanted){
      if(this.pending.size>=4)break;
      if(this.cache.has(t.key)||this.pending.has(t.key)||this.failed.has(t.key))continue;
      this.pending.add(t.key);this.requests++;
      this.picture(this.base,t.file,this.manifest.asset_sha256[t.file]).then(im=>{
        if(im.width!==Math.round(t.world[2]*t.level)||im.height!==Math.round(t.world[3]*t.level)){im.close();throw Error('표시 타일 크기 불일치');}
        if(this.closed||!this.wanted.some(w=>w.key===t.key)){im.close();return;}
        while(this.cache.size>=48){const key=[...this.cache.keys()].find(k=>!this.visible.has(k))??this.cache.keys().next().value;this.cache.get(key).close();this.cache.delete(key);}
        this.cache.set(t.key,im);
      }).catch(()=>this.failed.add(t.key)).finally(()=>{this.pending.delete(t.key);if(!this.closed){this.changed();this.pump();}});
    }
  }
  draw(ctx,ox,oy,scale,view){
    ctx.drawImage(this.preview,ox,oy,this.manifest.width*scale,this.manifest.height*scale);
    for(const t of this.request(view,scale)){const im=this.cache.get(t.key);if(im)ctx.drawImage(im,ox+t.world[0]*scale,oy+t.world[1]*scale,t.world[2]*scale,t.world[3]*scale);}
  }
}
