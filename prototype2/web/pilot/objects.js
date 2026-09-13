import {PilotMap} from './map.js';
import {compose, decodeDepth, projectPoint, cameraDepth, containsPoint} from './objects-core.js';

export class ObjectMap extends PilotMap {
  constructor(canvas, onChange, onError) {
    super(canvas, onChange, onError);
    this.objects = []; this.hidden = new Set(); this.lights = new Set(); this.selected = 0;
    this.dirty = true; this.showGeometry = false; this.phase = 0;
    this.walking = !matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.walkStart = performance.now(); this.walkPhase = 0;
    canvas.addEventListener('pointerdown', e => {
      if (this.pointers.size !== 1) {if (this.press) this.press.dragged = true; return;}
      this.press = {id: e.pointerId, x: e.clientX, y: e.clientY, dragged: false};
    });
    canvas.addEventListener('pointermove', e => {
      if (this.press && Math.hypot(e.clientX - this.press.x, e.clientY - this.press.y) > 5) this.press.dragged = true;
    });
    canvas.addEventListener('pointerup', e => {
      if (this.press?.id === e.pointerId && !this.press.dragged && this.ready) {
        const rect = canvas.getBoundingClientRect(), point = this.world(e.clientX - rect.left, e.clientY - rect.top);
        const x = Math.floor(point.x / this.manifest.art_pixel), y = Math.floor(point.y / this.manifest.art_pixel);
        this.select(x >= 0 && y >= 0 && x < this.size && y < this.size ? this.composite.ids[y * this.size + x] : 0);
      }
      this.press = null;
    });
    canvas.addEventListener('pointercancel', () => {this.press = null;});
    canvas.addEventListener('keydown', e => {if (e.key === 'Escape') this.select(0);});
    document.addEventListener('visibilitychange', () => {if (!document.hidden) this.update();});
  }

  async pixels(file, width, height) {
    if (!/^[a-zA-Z0-9_]+\.png$/.test(file)) throw Error('올바르지 않은 에셋 경로입니다.');
    const image = new Image();
    image.src = new URL(file, this.base);
    try {await image.decode();} catch {throw Error(`객체 에셋을 불러오지 못했습니다: ${file}`);}
    if (image.naturalWidth !== width || image.naturalHeight !== height) throw Error(`에셋 크기 오류: ${file}`);
    const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
    const context = canvas.getContext('2d', {willReadFrequently: true}); context.drawImage(image, 0, 0);
    return context.getImageData(0, 0, width, height).data;
  }

  async load(manifest, base) {
    if (manifest.version !== 1 || manifest.kind !== 'object_pilot' || manifest.width !== 1536 || manifest.height !== 1536 || manifest.art_pixel !== 3 || manifest.camera.size !== 512)
      throw Error('지원하지 않는 객체 장면입니다.');
    if (manifest.objects.length !== 18 || new Set(manifest.objects.map(b => b.id)).size !== 18) throw Error('건물 목록이 올바르지 않습니다.');
    this.manifest = manifest; this.base = base; this.size = 512;
    for (const b of manifest.objects) {
      if (!Number.isInteger(b.id) || b.id <= 0 || !b.xy.every(Number.isInteger) || !b.size.every(n => Number.isInteger(n) && n > 0 && n <= 512))
        throw Error('건물 에셋 정보가 올바르지 않습니다.');
    }
    const [ground, groundBase, z] = await Promise.all([manifest.ground, manifest.ground_base, manifest.ground_depth].map(p => this.pixels(p, 512, 512)));
    this.groundPixels = ground; this.groundBasePixels = groundBase; this.groundDepth = decodeDepth(z);
    this.objects = await Promise.all(manifest.objects.map(async b => {
      const [spritePixels, basePixels, depthPixels, lightPixels] = await Promise.all([b.sprite, b.base, b.depth, b.light].map(p => this.pixels(p, ...b.size)));
      return {...b, spritePixels, basePixels, lightPixels, depthValues: decodeDepth(depthPixels)};
    }));
    this.buffer = document.createElement('canvas'); this.buffer.width = this.buffer.height = 512;
    this.bufferContext = this.buffer.getContext('2d');
    const building = this.objects.find(b => b.id === 4577), ring = building.footprint;
    const lo = [Math.min(...ring.map(p => p[0])) - 6, Math.min(...ring.map(p => p[1])) - 6];
    const hi = [Math.max(...ring.map(p => p[0])) + 6, Math.max(...ring.map(p => p[1])) + 6];
    this.walkRoute = [lo, [hi[0], lo[1]], hi, [lo[0], hi[1]]];
    this.ready = true; this.loading = Promise.resolve(); this.fit(); this.refresh();
    this.canvas.dataset.objectCount = this.objects.length;
  }

  select(id) {
    this.selected = this.objects.some(b => b.id === Number(id)) ? Number(id) : 0;
    this.canvas.dataset.selected = this.selected; this.refresh(); this.onSelection?.(this.objects.find(b => b.id === this.selected));
  }
  focus(id) {
    const b = this.objects.find(b => b.id === Number(id));
    if (b) this.center = {x: (b.xy[0] + b.size[0] / 2) * 3, y: (b.xy[1] + b.size[1] / 2) * 3};
    this.select(id);
  }
  refresh() {this.dirty = true; this.update();}
  toggleHidden() {if (!this.selected) return; this.hidden.has(this.selected) ? this.hidden.delete(this.selected) : this.hidden.add(this.selected); this.select(this.selected);}
  toggleLight() {if (!this.objects.find(b => b.id === this.selected)?.has_light) return; this.lights.has(this.selected) ? this.lights.delete(this.selected) : this.lights.add(this.selected); this.select(this.selected);}
  setWalking(enabled) {this.walking = enabled; this.walkStart = performance.now(); this.walkPhase = this.phase; this.update();}
  setPhase(value) {this.walking = false; this.phase = value; this.update();}

  rebuild() {
    this.composite = compose(this.size, this.mode === 'source' ? this.groundBasePixels : this.groundPixels, this.groundDepth, this.objects,
      {mode: this.mode, hidden: this.hidden, lights: this.lights});
    const pixels = new Uint8ClampedArray(this.composite.pixels), ids = this.composite.ids;
    if (this.selected && !this.hidden.has(this.selected)) {
      for (let y = 1; y < 511; y++) for (let x = 1; x < 511; x++) {
        const i = y * 512 + x;
        if (ids[i] === this.selected && [ids[i - 1], ids[i + 1], ids[i - 512], ids[i + 512]].some(id => id !== this.selected))
          pixels.set([255, 206, 79, 255], i * 4);
      }
    }
    this.bufferContext.putImageData(new ImageData(pixels, 512, 512), 0, 0);
    this.canvas.dataset.lit = [...this.lights].join(',');
    this.canvas.dataset.hiddenObjects = [...this.hidden].join(',');
    this.dirty = false; this.lastMode = this.mode;
  }

  drawWalker(c, ox, oy, step) {
    if (this.walking) this.phase = (this.walkPhase + (performance.now() - this.walkStart) / 24000) % 1;
    const position = this.phase * 4, index = Math.floor(position) % 4, fraction = position - Math.floor(position);
    const a = this.walkRoute[index], b = this.walkRoute[(index + 1) % 4];
    const e = a[0] + (b[0] - a[0]) * fraction, n = a[1] + (b[1] - a[1]) * fraction;
    // A deliberately enlarged diagnostic marker, not a real route/person-scale claim.
    const pattern = ['  hh ', ' hhhh', '  ss ', ' bbbb', '  bb ', '  bb ', ' l l '];
    const palette = {h: '#483427', s: '#edbd84', b: '#ed7854', l: '#394754'};
    const cam = this.manifest.camera, feet = projectPoint(e, n, 0, cam);
    let shown = 0, occluded = 0;
    const collision = this.objects.some(o => containsPoint([e, n], o.footprint));
    for (let y = 0; y < pattern.length; y++) for (let x = 0; x < pattern[y].length; x++) {
      const key = pattern[y][x]; if (key === ' ') continue;
      const px = Math.round(feet[0]) + x - 2, py = Math.round(feet[1]) + y - pattern.length;
      if (px < 0 || py < 0 || px >= 512 || py >= 512) continue;
      const h = (pattern.length - y) * cam.scale / Math.cos(cam.phi_deg * Math.PI / 180);
      const z = cameraDepth(e, n, h, cam, this.manifest.depth_encoding);
      if (collision || z < this.composite.depth[py * 512 + px]) {occluded++; continue;}
      c.fillStyle = palette[key]; c.fillRect(ox + px * step, oy + py * step, step, step); shown++;
    }
    this.canvas.dataset.walkerVisible = shown; this.canvas.dataset.walkerOccluded = occluded;
    this.canvas.dataset.walkerPhase = this.phase.toFixed(4);
  }

  draw() {
    const c = this.ctx; c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    c.fillStyle = '#D9CBA5'; c.fillRect(0, 0, this.w, this.h);
    if (!this.ready) return;
    if (this.dirty || this.lastMode !== this.mode) this.rebuild();
    const ox = this.w / 2 - this.center.x * this.scale, oy = this.h / 2 - this.center.y * this.scale;
    const step = this.scale * this.manifest.art_pixel;
    c.imageSmoothingEnabled = false; c.drawImage(this.buffer, ox, oy, 512 * step, 512 * step);
    this.drawWalker(c, ox, oy, step);
    if (this.showGeometry) {
      c.save(); c.strokeStyle = '#df3d67'; c.lineWidth = 1;
      for (const b of this.objects) {
        if (this.hidden.has(b.id)) continue;
        c.beginPath();
        for (const [i, p] of b.footprint.entries()) {
          const [x, y] = projectPoint(...p, 0, this.manifest.camera);
          i ? c.lineTo(ox + x * step, oy + y * step) : c.moveTo(ox + x * step, oy + y * step);
        }
        c.closePath(); c.stroke();
      }
      c.restore();
    }
    this.onChange(this);
    if (this.walking && !document.hidden) this.update();
  }
}
