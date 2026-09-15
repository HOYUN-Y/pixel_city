// Local illustrative light preview. No weather/solar API and no image generation.
export function shadowTransform(config,amount){
  if(!Number.isFinite(amount)||amount<0||amount>1)throw Error('Invalid sunset amount');
  const {anchor:[x,y],direction:[dx,dy],height}=config;
  const length=220*amount,k=length/height;
  return [.7,0,-dx*k,-dy*k,x-.7*x+dx*k*y,y+dy*k*y];
}
export function validateSunset(s,size){
  const xy=p=>Array.isArray(p)&&p.length===2&&p.every((v,i)=>Number.isFinite(v)&&v>=0&&v<=[size.width,size.height][i]);
  if(!s||s.kind!=='ground-alpha-preview'||!xy(s.anchor)||!Number.isFinite(s.height)||s.height<=0||s.height>size.height||!Array.isArray(s.direction)||s.direction.length!==2||!s.direction.every(Number.isFinite)||Math.abs(Math.hypot(...s.direction)-1)>1e-6||typeof s.receiver!=='string')throw Error('Invalid sunset configuration');
}
export class SunsetLayer{
  constructor(sprite,receiver,config,size){
    validateSunset(config,size);
    if(sprite.width!==size.width||sprite.height!==size.height||receiver.width!==size.width||receiver.height!==size.height)throw Error('Shadow mask size mismatch');
    this.sprite=sprite;this.receiver=receiver;this.config=config;this.size=size;this.amount=0;this.builds=0;this.enabled=true;
    this.mask=document.createElement('canvas');this.mask.width=size.width;this.mask.height=size.height;
  }
  set(amount){
    shadowTransform(this.config,amount);if(amount===this.amount)return;
    this.amount=amount;this.builds++;const c=this.mask.getContext('2d');c.resetTransform();c.clearRect(0,0,this.size.width,this.size.height);
    if(!amount)return;
    c.imageSmoothingEnabled=false;c.save();c.setTransform(...shadowTransform(this.config,amount));c.drawImage(this.sprite,0,0);c.restore();
    c.globalCompositeOperation='source-in';c.fillStyle='#2A2435';c.fillRect(0,0,this.size.width,this.size.height);
    c.globalCompositeOperation='destination-in';c.drawImage(this.receiver,0,0);
    c.globalCompositeOperation='destination-out';c.drawImage(this.sprite,0,0);c.globalCompositeOperation='source-over';
  }
  drawShadow(c,x,y,s){if(!this.amount||!this.enabled)return;c.save();c.globalAlpha=.28*this.amount;c.drawImage(this.mask,x,y,this.size.width*s,this.size.height*s);c.restore();}
  drawTint(c,x,y,s){if(!this.amount)return;c.save();c.fillStyle=`rgba(231,119,52,${.12*this.amount})`;c.fillRect(x,y,this.size.width*s,this.size.height*s);c.restore();}
}
export function bootSunset(map){
  const mini=document.querySelector('.minimap');mini.style.height='auto';mini.style.aspectRatio=String(map.manifest.width/map.manifest.height);
  const box=document.createElement('div');box.className='object-controls';box.innerHTML='<strong>노을 미리보기 · 실제 일조 아님</strong><label>낮 ↔ 노을 <input id="sunset-amount" type="range" min="0" max="100" value="0"></label><small>종로타워 지면 그림자만 근사 표현 · 서울 실시간 환경 아님</small>';
  document.querySelector('#inspection .inspection-body').prepend(box);
  const shadowLabel=document.createElement('label');shadowLabel.innerHTML='<input id="sunset-shadow" type="checkbox" checked> 타워 그림자 표시 (켜고 끄며 비교)';box.append(shadowLabel);
  const shadowToggle=shadowLabel.querySelector('input');shadowToggle.onchange=e=>{map.living.sunset.enabled=e.target.checked;map.update();};
  const routeLabel=document.createElement('label');routeLabel.textContent='보행 시험 코스 ';const routes=document.createElement('select');routes.id='link-walk-route';
  for(const [key,route] of Object.entries(map.overlay.walk_routes))routes.add(new Option(route.title,key));routeLabel.append(routes);box.append(routeLabel);
  routes.onchange=()=>map.setRoute(map.overlay.walk_routes[routes.value]);
  const slider=box.querySelector('input'),buttons=[...document.querySelectorAll('.daytime button')].slice(0,2),mobile=document.querySelector('.mobile-time');
  for(const b of [...buttons,mobile]){b.removeAttribute('data-soon');b.removeAttribute('aria-disabled');}
  const change=v=>{if(map.mode!=='final')return;map.living.sunset.set(v);map.update();};
  buttons[0].onclick=()=>change(0);buttons[1].onclick=()=>change(1);mobile.onclick=()=>change(map.living.sunset.amount?0:1);slider.oninput=e=>change(Number(e.target.value)/100);
  const previous=map.onFrame;map.onFrame=m=>{previous?.(m);const enabled=m.mode==='final',a=m.living.sunset.amount;slider.disabled=!enabled;routes.disabled=!enabled;shadowToggle.disabled=!enabled;shadowToggle.checked=m.living.sunset.enabled;slider.value=String(Math.round(a*100));
    [...buttons,mobile].forEach(b=>b.disabled=!enabled);buttons[0].classList.toggle('selected',a===0);buttons[1].classList.toggle('selected',a>0);
    mobile.setAttribute('aria-label',a?'노을 미리보기, 낮으로 전환':'낮 미리보기, 노을로 전환');mobile.querySelector('small').textContent=a?'노을':'낮';
  };
}
