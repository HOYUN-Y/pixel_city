// Public entry: no run selector, source viewer, raw asset links or debug zoom.
import {DenseMap} from './dense-map.js';
import {bootCity} from './city.js';
const $=s=>document.querySelector(s), mobile=()=>innerWidth<900;
const titles={chat:'AI 가이드',book:'서울 픽셀 도감',places:'주변 장소',spot:'명소',feed:'피드',upload:'올리기'};
let active=null,opener=null;
const toast=text=>{$('#toast').textContent=text||'준비 중인 기능입니다. 전송하거나 저장하지 않습니다.';$('#toast').hidden=false;setTimeout(()=>$('#toast').hidden=true,3000);};
const map=new DenseMap($('#map'),m=>{
  $('#zoom-label').textContent=Math.round(m.scale*100)+'%';$('#zoom-in').disabled=!m.ready||m.scale>=m.maxScale;$('#zoom-out').disabled=!m.ready||m.scale<=m.minScale;
  const w=m.manifest?.width||1792,h=m.manifest?.height||1024,x=Math.max(0,m.center.x-m.w/(2*m.scale)),y=Math.max(0,m.center.y-m.h/(2*m.scale));
  $('#mini-viewport').style.cssText=`left:${x/w*100}%;top:${y/h*100}%;width:${Math.max(0,Math.min(w,m.center.x+m.w/(2*m.scale))-x)/w*100}%;height:${Math.max(0,Math.min(h,m.center.y+m.h/(2*m.scale))-y)/h*100}%`;
  $('#map').dataset.scale=String(m.scale);$('#map').dataset.center=JSON.stringify(m.center);
},fail);
function fail(e){$('#map-message').hidden=false;$('#map-message h1').textContent='지도를 불러오지 못했습니다';$('#map-message p').textContent=e.message;}
function render(){
  const top=Math.ceil($('.toolbar').getBoundingClientRect().bottom)+12;document.documentElement.style.setProperty('--top',top+'px');
  $('#windows').replaceChildren();$('#sheet-body').replaceChildren();$('#sheet').classList.toggle('expanded',!!active&&mobile());$('#sheet-handle').setAttribute('aria-expanded',String(!!active&&mobile()));
  if(!active)return;
  const title=titles[active],panel=map.beta?.panel(active)??'<p class="sample-note">시안 예시 · 준비 중인 기능입니다. 실제 게시·업로드는 하지 않습니다.</p>';
  if(mobile())$('#sheet-body').innerHTML=`<div class="sheet-title"><strong>${title}</strong><button data-beta-close aria-label="패널 닫기">✕</button></div><div class="panel-content">${panel}</div>`;
  else{const win=document.createElement('section');win.className='floating-window focused';win.setAttribute('role','dialog');win.setAttribute('aria-label',title);win.style.cssText=`left:24px;top:${top}px;width:440px;height:${Math.min(600,innerHeight-top-24)}px;z-index:12`;win.innerHTML=`<header class="window-header" style="background:#8cc5d8"><span class="window-dot"></span><span class="window-title">${title}</span><small>FEEDBACK BETA</small><button class="window-close" data-beta-close aria-label="패널 닫기">✕</button></header><div class="panel-content">${panel}</div>`;$('#windows').append(win);}
}
function open(key){if(!titles[key])return;opener=document.activeElement;active=key;render();$('[data-beta-close]')?.focus();}
function close(){active=null;render();if(opener?.isConnected)opener.focus();}
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.hasAttribute('data-soon'))return toast();if(b.dataset.open)open(b.dataset.open);if(b.hasAttribute('data-beta-close'))close();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')close();});
$('#sheet-handle').onclick=()=>active?close():open('book');
$('#zoom-in').onclick=()=>map.zoom(map.scale*1.25);$('#zoom-out').onclick=()=>map.zoom(map.scale/1.25);$('#fit').onclick=()=>map.fit();
addEventListener('resize',render);
async function json(url){const r=await fetch(url);if(!r.ok)throw Error('지도 자료가 없습니다.');return r.json();}
bootCity(map,json,{open,close,render,toast}).catch(fail);
