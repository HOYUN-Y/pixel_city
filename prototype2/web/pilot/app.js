import {PilotMap} from './map.js';
import {ObjectMap} from './objects.js';
import {LabMap} from './lab.js';
import {bootLab,labPanel} from './lab-ui.js';
const objectView = new URLSearchParams(location.search).get('view') === 'objects';
const labView = ['seam-lab','projection-walk'].includes(new URLSearchParams(location.search).get('view'));
const projectionView = new URLSearchParams(location.search).get('view') === 'projection-lab';
const $=s=>document.querySelector(s), mobile=()=>innerWidth<900;
const definitions={chat:['AI 가이드','#3A2A1E',400,560],feed:['피드','#6FA657',420,560],book:['도감','#8CC5D8',440,520],spot:['명소','#F2C14E',380,600],upload:['올리기','#E8735A',380,600],post:['픽셀 엽서','#8CC5D8',400,480],route:['추천 코스','#6FA657',400,540]};
const names=['덕수궁','궁궐 산책길','도심 풍경','서울의 오후','한옥 지붕','담장 길','작은 정원'];
const state={order:[],positions:{},selected:'chat',expanded:false,filter:'all',uploadKind:'spot',opener:null};
let toastTimer,lastMobile=mobile(),windowDrag=null;
function toast(text='준비 중인 기능입니다. 전송·저장·인증은 하지 않습니다.'){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,2400);}
const soon=(label,cls='')=>`<button class="${cls}" data-soon aria-disabled="true">${label}</button>`;
const sample='<div class="sample-note">시안 예시 · 서비스 미연결 · 실제 데이터가 아닙니다</div>';
function routeCard(){return `<div class="sample-card"><div class="sample-art">AI 추천 코스 · 정적 예시</div><div class="copy"><h3>고궁 산책 · 반나절 코스</h3><p>경로·시간·거리 계산은 아직 연결하지 않았어요.</p><ol class="steps"><li>1. 궁궐 둘러보기</li><li>2. 담장 따라 걷기</li><li>3. 도심 풍경 감상하기</li></ol><div class="actions">${soon('지도에 표시','primary')}${soon('저장')}</div></div></div>`;}
function panel(key){
  if(labView&&map.overlay&&['spot','route'].includes(key))return labPanel(map,key);
  const chat=`${sample}<div class="bubble">안녕하세요! Pixel City 가이드 화면입니다.<br>지금은 지도를 둘러보실 수 있어요. AI 대화는 준비 중입니다.</div><div class="chips">${['반나절 고궁 코스','저녁 먹거리','비 오는 날 실내'].map(x=>soon(x)).join('')}</div><form class="panel-form"><input aria-label="가이드 질문" placeholder="가이드에게 물어보기 · 준비 중" autocomplete="off"><button data-soon aria-disabled="true" aria-label="질문 전송 준비 중">↑</button></form><button class="wide" data-open="route">추천 코스 시안 보기</button>`;
  if(key==='chat')return chat;
  if(key==='route')return sample+routeCard();
  if(key==='feed')return sample+`<div class="tabs">${[['all','전체'],['route','루트'],['spot','명소']].map(([k,v])=>`<button data-filter="${k}" class="${state.filter===k?'selected':''}">${v}</button>`).join('')}</div>`+
    [{type:'spot',title:'궁궐 옆, 잠깐의 산책',text:'명소 카드의 이미지와 본문 배치를 살펴보세요.'},{type:'route',title:'서울의 오후를 걷는 코스',text:'추천 경로는 연결하지 않은 디자인 예시입니다.'},{type:'spot',title:'기와지붕이 보이는 풍경',text:'실제 후기나 사용자 게시물이 아닙니다.'}].filter(f=>state.filter==='all'||state.filter===f.type).map(f=>`<article class="sample-card"><div class="sample-art">${f.type==='spot'?'SPOT':'ROUTE'} · 시안 이미지</div><div class="copy"><h3>${f.title}</h3><p>${f.text}</p><div class="actions">${soon('♡ 좋아요')}${soon('▶ 따라가기')}<button data-open="spot">상세 시안</button></div></div></article>`).join('');
  if(key==='book')return `${sample}<div class="collection-head"><div><strong>서울 픽셀 도감</strong><small>방문 인증·카드 획득은 준비 중</small></div><b>0/7</b></div><div class="card-grid">${names.map(n=>`<button data-open="spot" aria-label="${n} 카드 시안"><small>PREVIEW</small><b>▥</b><span>${n}</span></button>`).join('')}</div><button class="wide" data-open="post">✉ 오늘의 픽셀 엽서 시안</button>`;
  if(key==='spot')return `${sample}<div class="hero">명소 사진 영역 · 시안 예시</div><h2 class="spot-heading">덕수궁</h2><p class="subtle">서울의 궁궐 · 예시 명소 상세</p><div class="actions">${soon('♡ 좋아요')}${soon('방문 인증','primary')}</div><p style="margin-top:18px">이 영역에는 명소 소개와 여행자의 사진이 표시됩니다. 현재 지도 위치·영업 정보·방문 기록은 연결하지 않았습니다.</p><div class="chips"><span>#고궁</span><span>#산책</span><span>#시안예시</span></div>${soon('◎ 지도에서 보기','wide')}<hr><p class="subtle">댓글 기능 준비 중</p><form class="panel-form"><input aria-label="예시 댓글" placeholder="댓글 남기기 · 준비 중">${soon('등록')}</form>`;
  if(key==='upload')return `${sample}<div class="tabs"><button data-upload-kind="spot" class="${state.uploadKind==='spot'?'selected':''}">◎ 명소</button><button data-upload-kind="route" class="${state.uploadKind==='route'?'selected':''}">〰 루트</button></div><div class="dropzone">사진 추가 · 픽셀 변환 준비 중<br>파일을 선택하거나 전송하지 않습니다.</div>${state.uploadKind==='route'?'<ol class="steps"><li>1. 출발 장소 예시</li><li>2. 경유 장소 예시</li></ol>':''}<form><label class="field">${state.uploadKind==='route'?'루트':'장소'} 이름<input placeholder="이름을 입력하는 화면 예시"></label><label class="field">한 줄 소개<textarea rows="3" placeholder="소개 입력 화면 예시"></textarea></label><div class="chips">${['한옥','카페','야경','먹거리','사진'].map(t=>soon('#'+t)).join('')}</div>${soon('지도에 올리기','primary wide')}<p class="subtle" style="margin-top:12px">지도에 위치나 경유지를 추가하지 않습니다.</p></form>`;
  if(key==='post')return `${sample}<div class="postcard"><strong>덕수궁 · 시청</strong><small>SEOUL PIXEL CITY · PREVIEW</small></div><label class="field">엽서에 남길 한 마디<textarea rows="3" placeholder="메시지 입력 화면 예시"></textarea></label><div class="actions">${soon('이미지 저장')}${soon('친구에게 보내기')}</div>`;
  return '';
}
function topHeight(){return Math.ceil($('.toolbar').getBoundingClientRect().bottom)+18;}
function clampWindow(key){const d=definitions[key],p=state.positions[key]||{x:96,y:topHeight()+8};
  const w=Math.min(d[2],innerWidth-40),h=Math.min(d[3],Math.max(120,innerHeight-topHeight()-24));
  p.x=Math.max(10,Math.min(innerWidth-w-10,p.x));p.y=Math.max(topHeight(),Math.min(innerHeight-h-12,p.y));
  state.positions[key]=p;return{...p,w,h};}
function render(){document.documentElement.style.setProperty('--top',`${topHeight()}px`);
  $('#windows').replaceChildren();
  if(!mobile())for(const [i,key] of state.order.entries()){
    const [title,color]=definitions[key],p=clampWindow(key),node=document.createElement('section');
    node.className='floating-window'+(i===state.order.length-1?' focused':'');node.dataset.window=key;
    node.setAttribute('role','dialog');node.setAttribute('aria-label',title+' 시안');node.style.cssText=`left:${p.x}px;top:${p.y}px;width:${p.w}px;height:${p.h}px;z-index:${10+i}`;
    node.innerHTML=`<header class="window-header" data-drag="${key}" style="background:${color};color:${key==='chat'?'#FBF3E4':'#3A2A1E'}"><span class="window-dot"></span><span class="window-title">${title}</span><small>시안 예시</small><button class="window-close" data-close="${key}" aria-label="${title} 닫기">✕</button></header><div class="panel-content">${panel(key)}</div>`;
    $('#windows').append(node);
  }
  $('#sheet').classList.toggle('expanded',state.expanded);
  $('#sheet-handle').setAttribute('aria-expanded',String(state.expanded));
  $('#sheet-handle').setAttribute('aria-label',state.expanded?'하단 시트 접기':'하단 시트 펼치기');
  $('#sheet-body').innerHTML=mobile()&&state.expanded?`<div class="sheet-title"><strong>${definitions[state.selected][0]} <small>· 시안 예시</small></strong><button data-close="${state.selected}" aria-label="시트 닫기">✕</button></div><div class="panel-content">${panel(state.selected)}</div>`:'';
  document.querySelectorAll('.dock [data-open],.sheet-tabs [data-open]').forEach(b=>{const active=mobile()?state.expanded&&state.selected===b.dataset.open:state.order.includes(b.dataset.open);b.classList.toggle('selected',active);b.setAttribute('aria-expanded',String(active));});
}
function open(key,opener){if(!definitions[key])return;state.opener=opener||document.activeElement;state.selected=key;state.expanded=true;
  state.order=state.order.filter(x=>x!==key).concat(key);render();
  const target=mobile()?$('#sheet-body button'):$(`[data-window="${key}"] .window-close`);target?.focus({preventScroll:true});}
function close(key){state.order=state.order.filter(x=>x!==key);if(mobile())state.expanded=false;render();
  if(state.opener?.isConnected)state.opener.focus({preventScroll:true});else $(`[data-open="${key}"]`)?.focus({preventScroll:true});}
document.addEventListener('submit',e=>{e.preventDefault();toast();});
document.addEventListener('dragover',e=>e.preventDefault());
document.addEventListener('drop',e=>{e.preventDefault();toast('파일 업로드는 준비 중입니다. 파일을 읽거나 전송하지 않았습니다.');});
document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.hasAttribute('data-soon')){e.preventDefault();toast();return;}
  if(b.dataset.open){if(b.closest('.dock')&&state.order.includes(b.dataset.open))close(b.dataset.open);else open(b.dataset.open,b);}
  if(b.dataset.close)close(b.dataset.close);
  if(b.dataset.filter){state.filter=b.dataset.filter;render();}
  if(b.dataset.uploadKind){state.uploadKind=b.dataset.uploadKind;render();}
  if(b.hasAttribute('data-close-route'))$('#route-bar').hidden=true;
  if(b.hasAttribute('data-close-card'))$('#card-modal').close();
});
$('#sheet-handle').onclick=()=>{state.expanded=!state.expanded;render();};
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('#card-modal').open){
  if(mobile()&&state.expanded)close(state.selected);else if(state.order.length)close(state.order.at(-1));}});
document.addEventListener('pointerdown',e=>{
  const win=e.target.closest('[data-window]');if(!win)return;const key=win.dataset.window;
  state.order=state.order.filter(x=>x!==key).concat(key);
  // Focus without rerendering: don't lose text focus or the active pointer capture.
  state.order.forEach((k,i)=>{const n=$(`[data-window="${k}"]`);n.style.zIndex=10+i;n.classList.toggle('focused',k===key);});
  if(!e.target.closest('[data-drag]')||e.target.closest('button'))return;
  e.preventDefault();const p=state.positions[key];windowDrag={key,x:e.clientX-p.x,y:e.clientY-p.y};win.setPointerCapture(e.pointerId);
});
document.addEventListener('pointermove',e=>{if(!windowDrag)return;
  const {key,x,y}=windowDrag;state.positions[key]={x:e.clientX-x,y:e.clientY-y};const p=clampWindow(key),n=$(`[data-window="${key}"]`);if(n){n.style.left=p.x+'px';n.style.top=p.y+'px';}});
for(const type of ['pointerup','pointercancel','lostpointercapture'])document.addEventListener(type,()=>windowDrag=null);
addEventListener('resize',()=>{const now=mobile();if(now!==lastMobile){if(now&&state.order.length)state.selected=state.order.at(-1);state.expanded=state.order.length>0;lastMobile=now;}render();});
$('#preview-state').onchange=e=>{const v=e.target.value;if(v==='card')$('#card-modal').showModal();else if(v){open(v,e.target);if(v==='route')$('#route-bar').hidden=false;}e.target.value='';};

function failed(error){$('#map-message').hidden=false;$('#map-message h1').textContent='시험 지도를 표시할 수 없습니다';$('#map-message p').textContent=error.message;$('#map-message').dataset.state='error';for(const id of ['zoom-in','zoom-out','fit'])$('#'+id).disabled=true;}
const map=new (objectView ? ObjectMap : labView ? LabMap : PilotMap)($('#map'),m=>{
  $('#zoom-label').textContent=Math.round(m.scale*100)+'%';$('#zoom-in').disabled=!m.ready||m.scale>=m.maxScale;$('#zoom-out').disabled=!m.ready||m.scale<=m.minScale;
  const x=Math.max(0,m.center.x-m.w/(2*m.scale)),y=Math.max(0,m.center.y-m.h/(2*m.scale));
  const right=Math.min(1536,m.center.x+m.w/(2*m.scale)),bottom=Math.min(1536,m.center.y+m.h/(2*m.scale));
  $('#mini-viewport').style.cssText=`left:${x/1536*100}%;top:${y/1536*100}%;width:${(right-x)/1536*100}%;height:${(bottom-y)/1536*100}%`;
  $('#map').dataset.scale=String(m.scale);$('#map').dataset.center=JSON.stringify(m.center);$('#map').dataset.mode=m.mode;
},failed);
$('#zoom-in').onclick=()=>map.zoom(map.scale*1.25);$('#zoom-out').onclick=()=>map.zoom(map.scale/1.25);$('#fit').onclick=()=>map.fit();
$('#debug-zoom').onchange=e=>{map.setDebug(e.target.checked);$('#double-zoom').disabled=!e.target.checked;};
document.querySelectorAll('[data-scale]').forEach(b=>b.onclick=()=>map.zoom(Number(b.dataset.scale)));
$('#seam-lines').onchange=e=>{if(objectView)map.showGeometry=e.target.checked;else map.showSeams=e.target.checked;map.update();};
$('#map-mode').onchange=e=>{if(labView){map.setMode(e.target.value);return;}map.mode=e.target.value;if(map.base&&!objectView)$('#mini-image').src=new URL(map.mode==='ai'?'preview.png':map.mode==='before'?'before.png':'source.png',map.base);map.update();};
async function json(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error(objectView?'객체형 데모 에셋을 찾을 수 없습니다. 저장소의 assets/object_pilot 폴더를 확인해 주세요.':labView?'연결·남산 시험의 로컬 생성물이 없습니다. 상세 실행 안내의 산출물 경로를 확인해 주세요.':'완료된 2×2 생성 결과가 없습니다. 생성 기록을 확인해 주세요.');return r.json();}
async function boot(){try{
  if(labView){await bootLab(map,json,{open,close,render});return;}
  if(objectView){
    const base=new URL('../../assets/object_pilot/',location.href),manifest=await json(new URL('manifest.json',base));
    await map.load(manifest,base);$('#map-message').hidden=true;$('#map-message').dataset.state='ready';
    $('#mini-image').src=new URL(manifest.preview,base);$('#run-info').textContent=manifest.review_summary;
    $('#run-report').href=new URL('index.html',base);$('#run-report').hidden=false;$('#attribution').textContent=manifest.attribution;
    document.title='Pixel City · 객체형 픽셀 지도 시험';$('.pilot-badge').textContent='OBJECT PILOT';$('.minimap span').textContent='18 OBJECTS';
    const notice=document.createElement('div');notice.id='object-summary';notice.textContent=manifest.review_summary+' · ';
    const reviewLink=document.createElement('a');reviewLink.href=new URL('index.html',base);reviewLink.target='_blank';reviewLink.rel='noopener';reviewLink.textContent='AI 6종 시안 보기 ↗';notice.append(reviewLink);$('#map-stage').append(notice);
    $('.inspection-title').textContent='OBJECT & ASSET LAB';$('#map-mode').options[0].textContent='AI 에셋 후보 적용';$('#map-mode').options[1].textContent='기본 도형 비교';
    $('#seam-lines').parentElement.lastChild.textContent=' 건물 바닥 윤곽 표시';
    $('#inspection .presets + p').textContent='건물별 객체 시험 · 실제 도형/높이 유지 · 외관은 AI 재해석. 기본 100%, 검수용 200%.';
    const tools=document.createElement('div');tools.className='object-controls';
    tools.innerHTML='<label>건물 선택 <select id="object-select"><option value="0">지도에서 건물 클릭</option></select></label><div class="actions"><button id="object-hide" disabled>건물 숨기기</button><button id="object-light" disabled>창문 켜기</button></div><p id="object-info">건물을 클릭하면 ID·높이·AI 적용 여부가 표시됩니다.</p><label><input id="object-walk" type="checkbox"> 검수용 보행자 이동</label><label>보행 위치 검수 <input id="walk-phase" type="range" min="0" max="1000" value="0"></label><small>보행자는 확대된 검수 마커이며 실제 크기·경로가 아닙니다.</small>';
    $('#inspection .inspection-body').insertBefore(tools,$('#run-info'));
    for(const b of manifest.objects){const option=document.createElement('option');option.value=b.id;option.textContent=`#${b.id} · ${b.height}m${manifest.ai_building_ids.includes(b.id)?' · AI 시험':''}`;$('#object-select').append(option);}
    const card=document.createElement('aside');card.id='object-card';card.hidden=true;card.setAttribute('aria-live','polite');$('#map-stage').append(card);
    map.onSelection=b=>{
      $('#object-select').value=b?.id||0;$('#object-hide').disabled=!b;$('#object-light').disabled=!b?.has_light;
      $('#object-hide').textContent=map.hidden.has(b?.id)?'건물 복원':'건물 숨기기';$('#object-light').textContent=map.lights.has(b?.id)?'창문 끄기':'창문 켜기';
      const status=b?({baseline:'기본 도형',candidate_unreviewed:'AI 후보 · 미감 미승인',geometry_rejected:'AI 도형 불합격 · 기본 도형 표시'}[b.status]||b.status):'';
      $('#object-info').textContent=b?`#${b.id} · 스냅샷 높이 ${b.height}m · ${status}`:'건물을 클릭하세요.';
      card.hidden=!b;if(b){card.replaceChildren();const title=document.createElement('strong');title.textContent=`BUILDING #${b.id}`;const detail=document.createElement('p');detail.textContent=`${b.height}m · ${status}`;
        const actions=document.createElement('div');actions.className='actions';
        for(const [id,text,action,disabled] of [['card-hide',$('#object-hide').textContent,()=>map.toggleHidden(),false],['card-light',$('#object-light').textContent,()=>map.toggleLight(),!b.has_light],['card-clear','닫기',()=>map.select(0),false]]){const button=document.createElement('button');button.id=id;button.textContent=text;button.disabled=disabled;button.onclick=action;actions.append(button);}
        card.append(title,detail,actions);}
    };
    $('#object-select').onchange=e=>map.focus(e.target.value);
    $('#object-hide').onclick=()=>{map.toggleHidden();if(mobile())$('#inspection').open=false;};
    $('#object-light').onclick=()=>{map.toggleLight();if(mobile())$('#inspection').open=false;};
    $('#object-walk').checked=map.walking;$('#object-walk').onchange=e=>map.setWalking(e.target.checked);$('#walk-phase').oninput=e=>{$('#object-walk').checked=false;map.setPhase(Number(e.target.value)/1000);};
    document.body.dataset.tilesReady='true';return;
  }
  const root=new URL(projectionView?'../../eval/vworld/orthographic_lab/':'../../eval/vworld/openrouter/seam_zoom/',new URL('../',location.href));
  let run=new URLSearchParams(location.search).get('run');
  if(!run&&!projectionView)run=(await json(new URL('current.json',root))).run_id;
  if(!/^\d{8}T\d{12}Z$/.test(run))throw Error('올바르지 않은 실행 ID입니다.');
  const base=new URL(`runs/${run}/`,root),manifest=await json(new URL('manifest.json',base));
  if(manifest.run_id!==run)throw Error('실행 ID가 일치하지 않습니다.');
  await map.load(manifest,base);$('#map-message').hidden=true;$('#map-message').dataset.state='ready';
  if(projectionView){
    document.title='Pixel City · 정사영 남산 2×2';$('.pilot-badge').textContent='ORTHOGRAPHIC LAB';
    $('.region').textContent='남산 · N서울타워';$('#map-stage').setAttribute('aria-label','정사영 남산 픽셀 지도');
    const option=document.createElement('option');option.value='before';option.textContent='2×2 보정 전';$('#map-mode').append(option);
  }
  $('#mini-image').src=new URL('preview.png',base);$('#run-info').textContent=`실행 ${run} · 1536×1536 · ${manifest.review_summary||'사용자 품질 승인 전'}`;
  $('#run-report').href=new URL('index.html',base);$('#run-report').hidden=false;
  $('#attribution').textContent=manifest.attribution;
  await map.loading;document.body.dataset.tilesReady=String(map.ready);
}catch(error){failed(error);}}
render();document.fonts.ready.then(()=>render());boot();
