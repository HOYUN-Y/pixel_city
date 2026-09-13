const $=s=>document.querySelector(s);
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export function labPanel(map,key){
  const note='<div class="sample-note">이미지 좌표 기반 시험 · 실제 길찾기·고도 정보 아님</div>';
  if(key==='spot'){
    const s=map.selected||map.overlay.spots[0];
    return `${note}<h2>${escape(s.title)}</h2><p>${escape(s.description)}</p><button class="wide" data-lab-focus="${escape(s.id)}">◎ 지도에서 보기</button><button class="wide" data-lab-tour>시험 코스 보기</button>`;
  }
  return `${note}<h2>${escape(map.overlay.route.title)}</h2><p>그림 속 경로를 따라 이동하는 가림 시험입니다. 실제 접근 가능 여부·거리·시간은 제공하지 않습니다.</p><ol class="steps">${map.overlay.spots.map(s=>`<li><button data-lab-focus="${escape(s.id)}">${escape(s.title)}</button></li>`).join('')}</ol><div class="actions"><button data-lab-start>캐릭터 따라가기</button><button data-lab-route>경로 표시/숨김</button></div>`;
}

export async function bootLab(map,json,{open,close,render}){
  const root=new URL('../../eval/vworld/seam_lab/',location.href);
  const params=new URLSearchParams(location.search),run=params.get('run')||(await json(new URL('current.json',root))).run_id;
  if(!/^\d{8}T\d{12}Z$/.test(run))throw Error('올바르지 않은 시험 실행 ID입니다.');
  const base=new URL(`runs/${run}/`,root),manifest=await json(new URL('manifest.json',base));
  if(manifest.run_id!==run)throw Error('실행 ID 불일치');
  const scene=params.get('scene')||'downtown';await map.loadLab(manifest,base,scene);
  document.title='Pixel City · 연결·지형·상호작용 시험';$('.pilot-badge').textContent='SEAM LAB';
  const box=document.createElement('div');box.className='object-controls lab-controls';
  box.innerHTML='<label>시험 장면 <select id="lab-scene"></select></label><label>장소 <select id="lab-spot"><option value="">장소 선택</option></select></label><div class="actions"><button id="lab-tour">시험 코스</button><button id="lab-next">다음 장소</button></div><label><input id="lab-pins" type="checkbox" checked> 장소 표시</label><label><input id="lab-route" type="checkbox" checked> 시험 경로 표시</label><div class="actions"><button id="lab-play">캐릭터 재생</button><button id="lab-pause">일시정지</button></div><label><input id="lab-follow" type="checkbox" checked> 캐릭터 따라가기</label><label>이동·가림 검수 <input id="lab-phase" type="range" min="0" max="1000" value="0"></label><small id="lab-actor-status"></small>';
  $('#inspection .inspection-body').prepend(box);$('.inspection-title').textContent='CONTEXT · TERRAIN · INTERACTION LAB';
  $('#inspection .presets + p').textContent='분홍: 원래 격자 · 파랑: 실제 생성 경계. 가림은 최종 후보에만 적용한 수작업 마스크입니다.';
  for(const [id,s] of Object.entries(manifest.scenes)){const o=new Option(s.label,id);$('#lab-scene').add(o);}
  const notice=document.createElement('aside');notice.id='object-summary';notice.className='lab-summary';$('#map-stage').append(notice);
  let next=0;
  function syncScene(){
    const s=map.sceneData;$('#lab-scene').value=map.scene;$('.region').textContent=s.label;
    $('#map-mode').replaceChildren(...Object.entries(s.variants).map(([id,v])=>new Option(v.label,id)));$('#map-mode').value=map.mode;
    $('#lab-spot').replaceChildren(new Option('장소 선택',''),...map.overlay.spots.map(p=>new Option(p.title,p.id)));
    $('#mini-image').src=new URL(s.variants[map.mode].file,base);$('.minimap span').textContent=s.label;
    notice.replaceChildren();const text=document.createElement('span');text.textContent=s.review+' ';const link=document.createElement('a');link.href=new URL('index.html',base);link.target='_blank';link.rel='noopener';link.textContent='비교·검수 기록 ↗';notice.append(text,link);
    $('#run-info').textContent=`${run} · ${s.review}`;$('#attribution').textContent='국토교통부 / VWorld · AI 재해석 · 이미지 좌표/수작업 가림 · 로컬 검수';
    next=0;render();
  }
  map.onScene=syncScene;map.onSelection=spot=>{$('#lab-spot').value=spot?.id||'';if(spot){$('#inspection').open=false;open('spot');}else close('spot');};
  map.onFrame=m=>{const enabled=m.mode==='final';for(const id of ['lab-play','lab-pause','lab-phase','lab-spot','lab-tour','lab-next','lab-pins','lab-route','lab-follow'])$('#'+id).disabled=!enabled;
    $('#lab-phase').value=String(Math.round(m.phase*1000));$('#lab-play').textContent=m.playing?'재생 중':'캐릭터 재생';
    $('#lab-actor-status').textContent=enabled?`보이는 픽셀 ${m.canvas.dataset.actorVisible} · 가린 픽셀 ${m.canvas.dataset.actorOccluded}`:'비교 모드: 캐릭터·장소·가림 비활성';
    const preview=new URL(m.sceneData.variants[m.mode].file,base).href;if($('#mini-image').src!==preview)$('#mini-image').src=preview;
  };
  $('#lab-scene').onchange=async e=>{try{await map.setScene(e.target.value);map.fit();const u=new URL(location.href);u.searchParams.set('scene',map.scene);u.searchParams.set('run',run);history.replaceState(null,'',u);}catch(err){map.onError(err);}};
  $('#lab-spot').onchange=e=>{if(e.target.value)map.focusSpot(e.target.value);};
  $('#lab-next').onclick=()=>map.focusSpot(map.overlay.spots[next++%3].id);
  $('#lab-tour').onclick=()=>{$('#inspection').open=false;open('route');};
  function play(){close('spot');close('route');if(innerWidth<900)$('#inspection').open=false;map.setPlaying(true);}
  $('#lab-play').onclick=play;$('#lab-pause').onclick=()=>map.setPlaying(false);
  $('#lab-phase').oninput=e=>map.setPhase(Number(e.target.value)/1000);
  $('#lab-follow').onchange=e=>map.follow=e.target.checked;
  $('#lab-route').onchange=e=>{map.routeVisible=e.target.checked;map.update();};
  $('#lab-pins').onchange=e=>{map.pinsVisible=e.target.checked;map.update();};
  document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;
    if(b.dataset.labFocus){map.focusSpot(b.dataset.labFocus);close('spot');close('route');if(innerWidth<900)$('#inspection').open=false;}
    if(b.hasAttribute('data-lab-tour'))open('route');
    if(b.hasAttribute('data-lab-start'))play();
    if(b.hasAttribute('data-lab-route')){$('#lab-route').checked=!map.routeVisible;map.routeVisible=!map.routeVisible;map.update();}
  });
  // Reuse the existing top-level place filter; other service features stay inert.
  const pinButton=$('.layers button');pinButton.removeAttribute('data-soon');pinButton.removeAttribute('aria-disabled');pinButton.onclick=()=>{$('#lab-pins').checked=!map.pinsVisible;map.pinsVisible=!map.pinsVisible;map.update();};
  $('#run-report').href=new URL('index.html',base);$('#run-report').hidden=false;
  $('#map-message').hidden=true;$('#map-message').dataset.state='ready';document.body.dataset.tilesReady='true';syncScene();map.update();
}
