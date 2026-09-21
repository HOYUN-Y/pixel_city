// Opt-in local experience. No generation, route animation, or automatic guide calls.
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function thumbnail(l,base,caption=false){
  if(!l)return '';
  const image=l.thumbnail?`<img src="${esc(new URL(l.thumbnail,base))}" alt="${esc(l.name)} 지도 그림" width="160" height="100">`:'';
  return `<figure class="discovery-thumb${image?'':' missing'}">${image}<span class="thumb-fallback">${image?'이미지를 불러오지 못했습니다':'지도 연결 준비 중'}</span>${caption&&l.thumbnailCaption?`<figcaption>${esc(l.thumbnailCaption)}</figcaption>`:''}</figure>`;
}
export function setupDiscovery(map,data,base,state,saved,{open,close,render}){
  const linked=data.landmarks.filter(l=>l.mapSpotId);
  if(linked.some(l=>!map.overlay.spots.some(s=>s.id===l.mapSpotId)))throw Error('명소 연결 자료가 불완전합니다.');
  let bookFilter='all',choosing=false;
  map.beta.landmarkTitle=`명소 ${data.landmarks.length}곳 · 지도 연결 ${linked.length}곳`;
  map.living.trafficVisible=false;map.living.trafficPlaying=false;
  document.querySelector('.city-controls')?.remove();document.querySelector('.city-landmarks')?.remove();
  const entry=document.querySelector('.layers button');entry.removeAttribute('data-soon');entry.removeAttribute('aria-disabled');entry.dataset.open='landmarks';entry.textContent=`명소 ${linked.length}곳`;
  document.querySelector('.layers').setAttribute('aria-label','지도 메뉴');
  const oldPanel=map.beta.panel;
  map.beta.panel=key=>{
    if(key==='landmarks')return `<p class="subtle">원하는 명소를 골라 둘러보세요. 지도 연결 ${linked.length}/${data.landmarks.length}곳 · 자동 방문 처리는 없습니다.</p><div class="discovery-list">${data.landmarks.map(l=>`<button data-discovery-place="${esc(l.id)}" aria-pressed="${state.selected?.id===l.id}">${thumbnail(l,base)}<span><strong>${esc(l.name)}</strong><small>${esc(l.discoveryNote||'지도 연결 준비 중 · 설명 보기')}</small><small>${saved.has(l.id)?'도감에 담음':'미수집'}</small></span></button>`).join('')}</div>`;
    const html=oldPanel(key);
    if(key!=='book')return html;
    const template=document.createElement('template');template.innerHTML=html;
    const grid=template.content.querySelector('.card-grid');
    grid.insertAdjacentHTML('beforebegin',`<div class="actions" aria-label="도감 필터"><button data-book-filter="all" aria-pressed="${bookFilter==='all'}">전체</button><button data-book-filter="saved" aria-pressed="${bookFilter==='saved'}">수집함</button></div>`);
    for(const b of template.content.querySelectorAll('[data-city-place]')){const l=data.landmarks.find(l=>l.id===b.dataset.cityPlace);if(l){if(bookFilter==='saved'&&!saved.has(l.id)){b.remove();continue;}b.querySelector('b')?.remove();b.insertAdjacentHTML('afterbegin',thumbnail(l,base));}}
    if(!grid.children.length)grid.insertAdjacentHTML('afterend','<p class="sample-note">아직 담은 명소가 없습니다. 명소 상세에서 도감에 담아 보세요.</p>');
    return template.innerHTML;
  };
  function focus(id){
    const spot=map.overlay.spots.find(s=>s.id===id);if(!spot)return;
    const object=map.overlay.landmarks.find(l=>l.id===id),points=spot.hitPolygon||[[spot.xy[0]-40,spot.xy[1]-40],[spot.xy[0]+40,spot.xy[1]+40]];
    const rect=object?.rect??[Math.min(...points.map(p=>p[0])),Math.min(...points.map(p=>p[1])),Math.max(...points.map(p=>p[0]))-Math.min(...points.map(p=>p[0])),Math.max(...points.map(p=>p[1]))-Math.min(...points.map(p=>p[1]))];
    const canvas=map.canvas.getBoundingClientRect(),toolbar=document.querySelector('.toolbar').getBoundingClientRect();
    const panel=document.querySelector(innerWidth<900?'#sheet':'.floating-window')?.getBoundingClientRect();
    const left=innerWidth<900?20:Math.max(20,(panel?.right??0)-canvas.left+24),right=map.w-(innerWidth<900?20:180);
    const top=toolbar.bottom-canvas.top+24,bottom=innerWidth<900?Math.min(map.h-24,(panel?.top??map.h)-canvas.top-20):map.h-70;
    map.scale=Math.max(map.minScale,Math.min(1,(right-left-48)/rect[2],(bottom-top-48)/rect[3]));
    map.center={x:rect[0]+rect[2]/2-((left+right)/2-map.w/2)/map.scale,y:rect[1]+rect[3]/2-((top+bottom)/2-map.h/2)/map.scale};map.update();
  }
  function choose(l,pan){choosing=true;try{map.select(l?.mapSpotId??null);}finally{choosing=false;}state.selected=l;open('spot');if(pan&&l?.mapSpotId)requestAnimationFrame(()=>focus(l.mapSpotId));}
  map.onSelection=spot=>{if(choosing)return;if(!spot){state.selected=null;close();return;}const l=data.landmarks.find(l=>l.mapSpotId===spot.id);if(l){state.selected=l;open('spot');}};
  document.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    if(b.dataset.bookFilter){e.stopImmediatePropagation();bookFilter=b.dataset.bookFilter==='saved'?'saved':'all';render();document.querySelector(`[data-book-filter="${bookFilter}"]`)?.focus();return;}
    const id=b.dataset.discoveryPlace||b.dataset.cityPlace,focusId=b.dataset.cityFocus;
    if(!id&&!focusId&&b.id!=='bosingak-marker')return;
    e.stopImmediatePropagation();
    const target=focusId||(b.id==='bosingak-marker'?'bosingak':null);
    const l=data.landmarks.find(l=>l.id===id||(target&&l.mapSpotId===target))||data.places.find(p=>p.id===id);
    if(l)choose(l,true);
  },true);
  document.addEventListener('error',e=>{if(e.target.matches?.('.discovery-thumb img')){e.target.closest('figure').classList.add('missing');e.target.hidden=true;}},true);
  // Retain the existing hidden-landmark marker and add keyboard-accessible static anchors.
  const previousFrame=map.onFrame,pins=map.overlay.spots.filter(s=>s.hitPolygon||s.selectionMode==='location-only').map(s=>{
    const b=document.createElement('button');b.className='discovery-marker';b.dataset.cityFocus=s.id;b.textContent='⌖ '+s.title+(s.selectionMode==='location-only'?' · 위치':'');b.setAttribute('aria-label',s.title+(s.selectionMode==='location-only'?' 위치 안내':' 선택'));document.querySelector('#map-stage').append(b);return {s,b};
  });
  map.onFrame=()=>{
    previousFrame?.();const occupied=[];
    // Keep labels at their true anchors. Hide overlapping secondary labels at low
    // zoom rather than moving location cues; every place remains in the list.
    const visiblePins=[...pins].sort((a,b)=>Number(b.s.id===map.selected?.id)-Number(a.s.id===map.selected?.id));
    for(const {s,b} of visiblePins){
      const x=map.w/2+(s.xy[0]-map.center.x)*map.scale,y=map.h/2+(s.xy[1]-map.center.y)*map.scale;
      b.hidden=x<20||x>map.w-20||y<20||y>map.h-20;b.style.left=x+'px';b.style.top=y+'px';b.setAttribute('aria-pressed',String(map.selected?.id===s.id));
      if(b.hidden)continue;
      const r=b.getBoundingClientRect();
      b.hidden=occupied.some(a=>r.left<a.right+4&&r.right>a.left-4&&r.top<a.bottom+4&&r.bottom>a.top-4);
      if(!b.hidden)occupied.push(r);
    }
  };
  state.selected=null;render();
}
