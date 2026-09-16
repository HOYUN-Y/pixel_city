import {RainLayer} from './rain.js';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $=s=>document.querySelector(s), STORE='pixel-city.collection.v1';

export async function bootCity(map,json,{open,close,render,toast}){
  const base=new URL(document.body.dataset.cityBase||'../../assets/city_pilot/',location.href);
  const [manifest,data]=await Promise.all([json(new URL('manifest.json',base)),json(new URL('places.json',base))]);
  await map.loadLab(manifest,base,'jongno-link');
  map.pinsVisible=false;map.routeVisible=false;map.actorVisible=false;map.follow=false;
  map.rain=new RainLayer(()=>map.update());
  let saved=new Set(),storageAvailable=true;
  try{const value=JSON.parse(localStorage.getItem(STORE)||'[]');if(Array.isArray(value))saved=new Set(value.filter(id=>data.landmarks.some(l=>l.id===id)));}catch{storageAvailable=false;}
  const state={selected:data.landmarks.find(l=>l.name==='종로타워'),query:'',draft:'',messages:[],pending:false,guide:'설정 확인 중'};
  const place=l=>data.places.find(p=>p.id===(l?.placeId||l?.parentPlaceId))||(l?.contentId?l:null);
  const source=p=>p?`<p class="subtle">한국관광공사 TourAPI · 콘텐츠 ${esc(p.contentId)}<br>수정 ${esc(p.modifiedAt||'미제공')} · 수집 ${esc(p.collectedAt)}<br><a href="${esc(p.sourceUrl)}" target="_blank" rel="noopener noreferrer">데이터 출처 ↗</a></p>`:'';
  const revealControls=()=>state.selected?.mapSpotId==='bosingak'&&map.reveal?`<p class="sample-note">AI 재구성 · 추정 배치<br>가려진 배경과 보신각 외관을 재구성한 시험입니다. 실측 높이·실제 가림 관계는 미검증입니다.</p><div class="actions"><button data-city-reveal>${map.reveal.active?'원래 지도 복원':'가림 해제 보기'}</button>${map.reveal.active?'<button data-reveal-opacity="0.25">전경 25%</button><button data-reveal-opacity="0.45">45%</button><button data-reveal-opacity="0.65">65%</button>':''}</div>`:'';
  const selected=()=>{const l=state.selected,p=place(l);return `<h2>${esc(l?.name||'장소 선택')}</h2><p>${esc(l?.status||p?.address||'')}</p>${l?.parentPlaceId?'<p class="sample-note">상위 시설 자료입니다. 개별 장소 정보가 아닙니다.</p>':''}<p>${esc(p?.overview||l?.note||'이번 TourAPI 수집에서 상세 정보를 확인하지 못했습니다.')}</p>${source(p)}<div class="actions">${l?.id?.startsWith('landmark-')?`<button data-collect="${esc(l.id)}">${saved.has(l.id)?'도감에서 빼기':'도감에 담기'}</button>`:''}${l?.mapSpotId?`<button data-city-focus="${esc(l.mapSpotId)}">지도에서 보기</button>`:'<span class="subtle">지도 앵커 미검증 · 이동 보류</span>'}</div><button class="wide" data-open="chat">이 장소에 대해 질문하기</button>`;};
  map.beta={panel(key){
    if(key==='spot')return revealControls()+selected();
    if(key==='book')return `<div class="collection-head"><strong>서울 픽셀 도감</strong><b>${saved.size}/8</b></div><p class="subtle">직접 담은 카드만 이 브라우저에 저장합니다. 방문 인증·동기화가 아닙니다.${storageAvailable?'':' 저장소를 사용할 수 없어 임시 표시만 가능합니다.'}</p><div class="card-grid">${data.landmarks.map(l=>`<button data-city-place="${esc(l.id)}"><small>${saved.has(l.id)?'COLLECTED':'DISCOVER'}</small><b>${saved.has(l.id)?'◆':'◇'}</b><span>${esc(l.name)}</span></button>`).join('')}</div><button class="wide" data-open="places">주변 장소 36곳 둘러보기</button>`;
    if(key==='places'){const q=state.query.toLowerCase(),items=data.places.filter(p=>(p.name+' '+p.address+' '+p.overview).toLowerCase().includes(q));return `<form data-city-search class="panel-form"><input name="q" aria-label="주변 장소 검색" value="${esc(state.query)}" placeholder="장소 이름·키워드"><button>검색</button></form><p class="subtle">수집본 ${items.length}/36곳 · 현재 영업 여부 미확인</p>${items.map(p=>`<button class="wide city-place" data-city-place="${esc(p.id)}"><strong>${esc(p.name)}</strong><small>${esc(p.address)}</small></button>`).join('')}`;}
    if(key==='chat')return `<p class="sample-note">자료 기반 AI 가이드 · ${esc(state.guide)}</p><p class="subtle">선택: ${esc(state.selected?.name||'없음')}<br>전송 시 질문·최근 대화·관련 관광 자료가 OpenRouter/OpenAI로 전달됩니다. 개인정보를 입력하지 마세요. 실시간 영업·길찾기는 제공하지 않습니다.</p><div class="city-messages" aria-live="polite">${state.messages.map(m=>`<div class="bubble ${m.role==='user'?'city-user':''}">${esc(m.content)}${m.sources?.map(s=>`<small><a href="${esc(s.sourceUrl)}" target="_blank" rel="noopener noreferrer">${esc(s.name)} · TourAPI ${esc(s.contentId)}</a><br>수정 ${esc(s.modifiedAt)} · 수집 ${esc(s.collectedAt)}</small>`).join('')||''}</div>`).join('')}</div><form data-city-guide class="panel-form"><input name="message" maxlength="800" aria-label="가이드 질문" value="${esc(state.draft)}" placeholder="선택한 장소에 대해 물어보세요" required ${state.pending?'disabled':''}><button ${state.pending?'disabled':''}>${state.pending?'…':'전송'}</button></form>`;
    return null;
  }};
  map.onSelection=spot=>{if(!spot)return;const l=data.landmarks.find(l=>l.mapSpotId===spot.id);if(l){state.selected=l;open('spot');}};
  document.addEventListener('input',e=>{if(e.target.closest('[data-city-guide]'))state.draft=e.target.value;if(e.target.closest('[data-city-search]'))state.query=e.target.value;});
  document.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    if(b.dataset.cityPlace){state.selected=data.landmarks.find(l=>l.id===b.dataset.cityPlace)||data.places.find(p=>p.id===b.dataset.cityPlace);if(state.selected?.mapSpotId!=='bosingak')map.reveal?.set(false);map.update();open('spot');}
    if(b.dataset.cityFocus){map.zoom(1);map.focusSpot(b.dataset.cityFocus);if(innerWidth<900)close?.();}
    if(b.hasAttribute('data-city-reveal')&&map.reveal){map.reveal.set(!map.reveal.active);map.zoom(1);map.focusSpot('bosingak');render();if(innerWidth<900)close?.();map.update();}
    if(b.dataset.revealOpacity&&map.reveal){map.reveal.opacity=Number(b.dataset.revealOpacity);toast(`전경 불투명도 ${Math.round(map.reveal.opacity*100)}%`);map.update();}
    if(b.dataset.collect){const id=b.dataset.collect;saved.has(id)?saved.delete(id):saved.add(id);try{localStorage.setItem(STORE,JSON.stringify([...saved]));}catch{storageAvailable=false;toast('저장 공간을 사용할 수 없어 이번 화면에서만 유지됩니다.');}render();}
  });
  document.addEventListener('submit',async e=>{
    const form=e.target;if(!form.matches('[data-city-guide],[data-city-search]'))return;e.preventDefault();e.stopImmediatePropagation();
    if(form.matches('[data-city-search]')){state.query=new FormData(form).get('q').trim();render();return;}
    if(state.pending)return;const message=String(new FormData(form).get('message')||'').trim();if(!message)return;
    const history=state.messages.filter(m=>!m.error).slice(-4).map(({role,content})=>({role,content}));state.messages.push({role:'user',content:message});state.pending=true;state.draft='';render();
    try{const response=await fetch('/api/guide',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,selectedPlaceId:place(state.selected)?.id||null,history}),signal:AbortSignal.timeout(35000)});const reply=await response.json();if(!response.ok)throw Error(reply.error||'가이드를 잠시 사용할 수 없습니다.');state.messages.push({role:'assistant',content:reply.answer,sources:reply.sources});}
    catch{state.messages.push({role:'assistant',content:'가이드를 지금 사용할 수 없습니다. 예산·서버 설정 또는 연결 상태를 확인해 주세요. 지도와 도감은 계속 사용할 수 있습니다.',error:true});}
    finally{state.pending=false;render();}
  },true);
  if($('#inspection'))$('#inspection').hidden=true;$('#map-message').hidden=true;$('#map-message').dataset.state='ready';
  $('.brand .region').textContent='광화문 · 종로';$('.search small').textContent='· 자료 기반';$('#map-stage').setAttribute('aria-label','광화문·종로 픽셀 지도');
  $('#mini-image').src=new URL(manifest.minimap||manifest.preview||'final.png',base);$('.minimap span').textContent=map.dense?'SEOUL · PIXEL CITY':'JONGNO · PIXEL CITY';$('.pilot-badge').textContent='FEEDBACK BETA';
  if(map.dense){$('.brand .region').textContent='경복궁 · 광화문 · 종각';$('#map-stage').setAttribute('aria-label','경복궁·광화문·종각 고밀도 픽셀 지도');}
  $('.daytime').hidden=true;const rain=$('.toolbar-right > button');rain.removeAttribute('data-soon');rain.removeAttribute('aria-disabled');rain.textContent='☂ 날씨 미리보기: 꺼짐';rain.setAttribute('aria-label','날씨 미리보기 변경');
  const levels=['off','light','heavy'],labels=['꺼짐','약한 비','강한 비'];
  const mobileRain=$('.mobile-time');mobileRain.removeAttribute('data-soon');mobileRain.removeAttribute('aria-disabled');mobileRain.setAttribute('aria-label','날씨 미리보기 변경');mobileRain.textContent='☂ 꺼짐';
  rain.onclick=mobileRain.onclick=()=>{const i=(levels.indexOf(map.rain.level)+1)%3;map.rain.set(levels[i]);for(const button of [rain,mobileRain]){button.textContent='☂ '+labels[i];button.dataset.rain=levels[i];}map.update();};
  const controls=document.createElement('div');controls.className='city-controls';controls.innerHTML='<button data-open="places">주변 장소</button><button id="city-traffic">차량 일시정지</button><button id="city-road">차량 구간 보기</button><button id="city-walk">보행 시험</button>';
  $('#map-stage').append(controls);
  if(map.dense){const nav=document.createElement('nav');nav.className='city-landmarks';nav.setAttribute('aria-label','지도 명소 바로가기');nav.innerHTML=[['gwanghwamun','광화문'],['bosingak','보신각'],['jongno-tower','종로타워']].map(([id,label])=>`<button data-city-focus="${id}">${label}</button>`).join('');$('#map-stage').append(nav);}
  $('#city-traffic').textContent=map.living.trafficPlaying?'차량 일시정지':'차량 재생';$('#city-traffic').onclick=()=>{map.living.trafficPlaying=!map.living.trafficPlaying;$('#city-traffic').textContent=map.living.trafficPlaying?'차량 일시정지':'차량 재생';map.update();};
  $('#city-road').onclick=()=>{const p=map.dense?map.overlay.traffic.focus:[880,245];map.zoom(1);map.center={x:p[0],y:p[1]};map.update();};
  $('#city-walk').onclick=()=>{map.actorVisible=!map.actorVisible;map.routeVisible=map.actorVisible;map.setPlaying(map.actorVisible);$('#city-walk').textContent=map.actorVisible?'보행 중지':'보행 시험';};
  $('#attribution').textContent='국토교통부 / VWorld 기반 AI 재해석 · 관광 정보: 한국관광공사 TourAPI · 실제 길찾기 아님';
  document.body.dataset.tilesReady='true';document.body.dataset.cityReady='true';document.title='Pixel City · 종로 산책';render();map.update();
  fetch('/api/guide').then(r=>r.ok?r.json():{enabled:false}).then(s=>{state.guide=s.enabled?'질문을 입력해 주세요':'서버 가이드 비활성 · 도감 이용 가능';render();}).catch(()=>{state.guide='서버 가이드 비활성 · 도감 이용 가능';render();});
}
