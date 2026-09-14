export function vehiclePosition(lane, seconds, offset, speed=28) {
  const length=Math.hypot(lane.end[0]-lane.start[0],lane.end[1]-lane.start[1]);
  const phase=((seconds*speed/length+offset)%1+1)%1;
  return {xy:lane.start.map((v,i)=>v+(lane.end[i]-v)*phase),phase,alpha:Math.min(1,phase*length/12,(1-phase)*length/12)};
}

export function validateLiving(overlay) {
  const xy=p=>Array.isArray(p)&&p.length===2&&p.every(v=>Number.isFinite(v)&&v>=0&&v<=1536);
  const t=overlay.traffic;
  if(t){
    if(t.lanes.length!==2||!Number.isFinite(t.speed)||t.speed<=0)throw Error('잘못된 차량 설정');
    for(const l of t.lanes)if(!xy(l.start)||!xy(l.end)||Math.hypot(l.end[0]-l.start[0],l.end[1]-l.start[1])<100||l.offsets.length!==2||l.offsets.some(v=>!Number.isFinite(v)||v<0||v>=1))throw Error('잘못된 차량 경로');
    for(const o of t.occluders)if(o.polygon.length<3||o.polygon.some(p=>!xy(p)))throw Error('잘못된 차량 가림');
  }
  if(overlay.landmark&&(!overlay.spots.some(s=>s.id===overlay.landmark.id)||!overlay.occluders.some(o=>o.id===overlay.landmark.occluder_id)))throw Error('랜드마크 참조 불일치');
}
