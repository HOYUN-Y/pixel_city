export class RainLayer {
  constructor(update){this.level='off';this.elapsed=0;this.last=0;this.query=matchMedia('(prefers-reduced-motion: reduce)');this.query.addEventListener('change',()=>{this.last=0;update();});document.addEventListener('visibilitychange',()=>this.last=0);}
  set(level){this.level=['off','light','heavy'].includes(level)?level:'off';this.last=0;}
  get moving(){return this.level!=='off'&&!this.query.matches&&!document.hidden;}
  draw(c,w,h,now){
    if(this.level==='off')return;
    if(this.moving&&this.last)this.elapsed+=Math.min(now-this.last,100);this.last=this.moving?now:0;
    c.save();c.fillStyle=this.level==='heavy'?'rgba(50,75,110,.14)':'rgba(60,90,120,.06)';c.fillRect(0,0,w,h);
    if(!this.query.matches){c.strokeStyle='rgba(205,226,242,.65)';c.lineWidth=1;const n=this.level==='heavy'?180:65;
      c.beginPath();for(let i=0;i<n;i++){const x=((i*137.31-this.elapsed*.035)%w+w)%w,y=(i*83.77+this.elapsed*.45)%h;c.moveTo(x,y);c.lineTo(x-3,y+9);}c.stroke();}
    c.restore();
  }
}
