export function landmarks(overlay) { return overlay.landmarks ?? (overlay.landmark ? [overlay.landmark] : []); }

export function vehiclePosition(lane, seconds, offset, speed=28) {
  const length=Math.hypot(lane.end[0]-lane.start[0],lane.end[1]-lane.start[1]);
  const phase=((seconds*speed/length+offset)%1+1)%1;
  return {xy:lane.start.map((v,i)=>v+(lane.end[i]-v)*phase),phase,alpha:Math.min(1,phase*length/12,(1-phase)*length/12)};
}

export function validateLiving(overlay, size={width:1536,height:1536}) {
  const xy=p=>Array.isArray(p)&&p.length===2&&p.every((v,i)=>Number.isFinite(v)&&v>=0&&v<=[size.width,size.height][i]);
  const t=overlay.traffic;
  if(t){
    if(t.lanes.length!==2||!Number.isFinite(t.speed)||t.speed<=0)throw Error('잘못된 차량 설정');
    for(const l of t.lanes)if(!xy(l.start)||!xy(l.end)||Math.hypot(l.end[0]-l.start[0],l.end[1]-l.start[1])<100||![1,2].includes(l.offsets.length)||l.offsets.some(v=>!Number.isFinite(v)||v<0||v>=1))throw Error('잘못된 차량 경로');
    for(const o of t.occluders)if(o.polygon.length<3||o.polygon.some(p=>!xy(p)))throw Error('잘못된 차량 가림');
  }
  if(overlay.landmarks!==undefined&&(!Array.isArray(overlay.landmarks)||overlay.landmark))throw Error('랜드마크 형식 중복');
  const ids=new Set(), masks=new Set();
  for(const l of landmarks(overlay)){
    if(ids.has(l.id)||masks.has(l.occluder_id)||!overlay.spots.some(s=>s.id===l.id)||!overlay.occluders.some(o=>o.id===l.occluder_id))throw Error('랜드마크 참조 불일치');
    if(l.mode!==undefined&&!['separated','highlight_only','independent'].includes(l.mode))throw Error('랜드마크 모드 불일치');
    if(overlay.landmarks&&l.mode!=='independent')throw Error('복수 랜드마크는 독립 모드만 지원');
    ids.add(l.id);masks.add(l.occluder_id);
  }
}
