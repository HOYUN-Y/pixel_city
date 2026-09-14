// Pure image-coordinate interactions. No geographic or physical-height claims.
export function routePhase(phase,elapsed,playback='loop') {
  const next=phase+Math.max(0,Math.min(elapsed,100))/45000;
  return playback==='once'?Math.min(1,next):next%1;
}
export function routePoint(points, phase) {
  const lengths=points.slice(1).map((p,i)=>Math.hypot(p.xy[0]-points[i].xy[0],p.xy[1]-points[i].xy[1]));
  const total=lengths.reduce((a,b)=>a+b,0);let distance=Math.max(0,Math.min(1,phase))*total;
  for(let i=0;i<lengths.length;i++){
    if(distance<=lengths[i]||i===lengths.length-1){const t=lengths[i]?distance/lengths[i]:0,a=points[i],b=points[i+1];
      return {xy:a.xy.map((v,k)=>v+(b.xy[k]-v)*t),behind:a.behind||[],segment:i,direction:b.xy[0]>=a.xy[0]?1:-1};}
    distance-=lengths[i];
  }
  return {xy:points[0].xy,behind:[],segment:0,direction:1};
}

export function hitSpot(spots, point, scale) {
  return [...spots].reverse().find(s=>Math.hypot((s.xy[0]-point.x)*scale,(s.xy[1]-point.y)*scale)<=22)||null;
}

export function validOverlay(data, hash, size={width:1536,height:1536}) {
  if(data.image_sha256!==hash)throw Error('장소·가림 데이터가 선택한 이미지와 맞지 않습니다.');
  const ids=new Set();
  const xy=p=>Array.isArray(p)&&p.length===2&&p.every((v,i)=>Number.isFinite(v)&&v>=0&&v<=[size.width,size.height][i]);
  for(const s of data.spots){if(ids.has(s.id)||!xy(s.xy))throw Error('잘못된 장소 데이터');ids.add(s.id);}
  if(data.spots.length!==3||data.route.points.length<2)throw Error('불완전한 시험 코스');
  if(data.route.playback!==undefined&&!['once','loop'].includes(data.route.playback))throw Error('잘못된 재생 방식');
  const masks=new Set(data.occluders.map(o=>o.id));
  for(const p of data.route.points){if(!xy(p.xy)||(p.behind||[]).some(id=>!masks.has(id)))throw Error('잘못된 경로 또는 가림 참조');}
  for(const o of data.occluders){if(o.polygon.length<3||o.polygon.some(p=>!xy(p)))throw Error('잘못된 가림 윤곽');}
  if(data.generation_edges!==undefined&&(!Array.isArray(data.generation_edges)||data.generation_edges.some(line=>!Array.isArray(line)||line.length!==2||line.some(p=>!xy(p)))))throw Error('잘못된 생성 경계');
  return data;
}
