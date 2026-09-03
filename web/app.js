/* pixel_city 뷰어 — 공공 공간데이터를 브라우저에서 아이소메트릭 픽셀로 그린다.
 *
 * 투영·처마·음영 로직은 poc/iso2.py를 이식한 것이다. 두 렌더러가 어긋나지 않도록
 * 상수는 poc/style.json 하나에서 오고, 로드 시 골든 값으로 투영을 대조한다.
 */
'use strict';

const D = {};                 // meta / city / layers / poi
let ALPHA, PHI, EAVE, C;
const Q = 10;                 // 0.1m 양자화 (meta.q로 덮어씀)

const rgb = a => `rgb(${a[0]},${a[1]},${a[2]})`;
const mul = (a, k) => `rgb(${a.map(v => Math.round(v * k)).join(',')})`;

/* ---------- 투영 (iso2.py proj/depth와 동일해야 한다) ---------- */
function projU(e, n, s) { return (e * Math.cos(ALPHA) - n * Math.sin(ALPHA)) / s; }
function projV(e, n, h, s) {
  return -((e * Math.sin(ALPHA) + n * Math.cos(ALPHA)) * Math.sin(PHI) + h * Math.cos(PHI)) / s;
}

function checkGolden(golden) {
  const bad = [];
  for (const g of golden) {
    const u = projU(g.e, g.n, 1), v = projV(g.e, g.n, g.h, 1);
    if (Math.abs(u - g.u) > 1e-6 || Math.abs(v - g.v) > 1e-6) bad.push({ g, u, v });
  }
  if (bad.length) {
    console.error('[pixel_city] 투영 이식 불일치 — 파이썬 렌더러와 결과가 다르다', bad);
    return false;
  }
  console.log(`[pixel_city] 투영 골든 값 ${golden.length}건 일치`);
  return true;
}

/* ---------- 디코딩 ---------- */
function decRing(a) {                       // [x0,y0,dx,dy,...] -> [[e,n],...] 미터
  let x = a[0], y = a[1];
  const out = [[x / Q, y / Q]];
  for (let i = 2; i < a.length; i += 2) {
    x += a[i]; y += a[i + 1];
    out.push([x / Q, y / Q]);
  }
  return out;
}

/* 중심 기준 확대 — 처마 근사 (iso2.expand) */
function expand(en, k) {
  let cx = 0, cy = 0;
  for (const p of en) { cx += p[0]; cy += p[1]; }
  cx /= en.length; cy /= en.length;
  return en.map(p => [cx + (p[0] - cx) * k, cy + (p[1] - cy) * k]);
}

/* ---------- 뷰 상태 ---------- */
const SCALES = [7.0, 3.5, 1.75, 0.875, 0.45];   // m/px. 인접 단계가 정확히 2배
const view = { cx: 0, cy: 0, zi: 1 };
const layers = { poi: true, subway: true, green: true, label: true };
let canvas, ctx, W = 0, H = 0, DPR = 1;

const s = () => SCALES[view.zi];
// 월드(미터) -> 화면(px)
const sx = (e, n) => Math.round(projU(e, n, s()) - projU(view.cx, view.cy, s()) + W / 2);
const sy = (e, n, h) => Math.round(projV(e, n, h, s()) - projV(view.cx, view.cy, 0, s()) + H / 2);

/* ---------- 그리기 ---------- */
function poly(pts, fill, stroke) {
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  ctx.closePath();
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
}

function walls(en, h0, h1, litC, darkC) {
  const sa = Math.sin(ALPHA), ca = Math.cos(ALPHA);
  for (let i = 0; i < en.length - 1; i++) {
    const [e1, n1] = en[i], [e2, n2] = en[i + 1];
    const nx = n2 - n1, nz = -(e2 - e1);
    if (nx * sa + nz * ca <= 0) continue;                    // 후면 제거
    const lit = Math.abs(nx) / (Math.hypot(nx, nz) + 1e-9) > 0.5;
    poly([[sx(e1, n1), sy(e1, n1, h0)], [sx(e2, n2), sy(e2, n2, h0)],
          [sx(e2, n2), sy(e2, n2, h1)], [sx(e1, n1), sy(e1, n1, h1)]],
         lit ? litC : darkC, null);
  }
}

function palette(b) {
  if (b.kind === 2) return C.palace;
  if (b.kind === 1) return C.hanok;
  return C.use[D.city.uses[b.use]] || C.default;
}

function drawBuilding(b) {
  const [roof, lit, dark] = palette(b);
  const en = b.en, h = b.h;
  if (b.kind) {                                   // 목조: 낮은 기둥 + 크게 내민 처마
    const body = h * 0.5;
    walls(en, 0, body, rgb(lit), rgb(dark));
    const ev = b.eave || (b.eave = expand(en, EAVE));
    walls(ev, body, h, rgb(roof), mul(roof, 0.72));
    poly(ev.map(p => [sx(p[0], p[1]), sy(p[0], p[1], h)]), rgb(roof), mul(roof, 0.62));
  } else {
    walls(en, 0, h, rgb(lit), rgb(dark));
    poly(en.map(p => [sx(p[0], p[1]), sy(p[0], p[1], h)]), rgb(roof), rgb(dark));
  }
}

function visible(b) {                             // s=1 기준 화면 AABB로 컬링
  const k = 1 / s(), m = 64;
  const ox = -projU(view.cx, view.cy, 1) * k + W / 2;
  const oy = -projV(view.cx, view.cy, 0, 1) * k + H / 2;
  return b.u1 * k + ox > -m && b.u0 * k + ox < W + m
      && b.v1 * k + oy > -m && b.v0 * k + oy < H + m;
}

function drawLines(list, color, widthOf) {
  ctx.strokeStyle = color; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  for (const it of list) {
    const [w, en] = widthOf ? it : [null, it];
    ctx.lineWidth = widthOf ? Math.max(1, (w / Q) / s()) : 1.5;
    ctx.beginPath();
    en.forEach((p, i) => i ? ctx.lineTo(sx(p[0], p[1]), sy(p[0], p[1], 0))
                           : ctx.moveTo(sx(p[0], p[1]), sy(p[0], p[1], 0)));
    ctx.stroke();
  }
}

function render() {
  const t0 = performance.now();
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = rgb(C.bg);
  ctx.fillRect(0, 0, W, H);
  labelBoxes = [];

  // 지면
  const E = 4000;
  poly([[sx(-E, -E), sy(-E, -E, 0)], [sx(E, -E), sy(E, -E, 0)],
        [sx(E, E), sy(E, E, 0)], [sx(-E, E), sy(-E, E, 0)]], rgb(C.ground), null);

  if (layers.green) {
    for (const g of D.L.heri) poly(g.map(p => [sx(p[0], p[1]), sy(p[0], p[1], 0)]),
                                   rgb(C.heri), rgb(C.heri_edge));
    for (const g of D.L.park) poly(g.map(p => [sx(p[0], p[1]), sy(p[0], p[1], 0)]),
                                   rgb(C.park), rgb(C.park_edge));
    for (const g of D.L.temple) poly(g.map(p => [sx(p[0], p[1]), sy(p[0], p[1], 0)]),
                                     rgb(C.heri), rgb(C.heri_edge));
  }
  drawLines(D.L.road, rgb(C.road), true);
  drawLines(D.L.river, rgb(C.river), false);

  let drawn = 0;
  for (const b of D.B) if (visible(b)) { drawBuilding(b); drawn++; }

  if (layers.subway) drawSubway();
  if (layers.poi) drawPOI();
  if (layers.label) drawLabels();

  document.getElementById('stat').textContent =
    `건물 ${D.B.length.toLocaleString()}동 중 ${drawn.toLocaleString()} 표시 · `
    + `${s().toFixed(2)} m/px · ${Math.round(performance.now() - t0)}ms`;
}

function drawSubway() {
  const sub = D.poi.subway, lc = D.meta.style.subway_lines;
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  for (const [ln, pts] of Object.entries(sub.lines)) {
    if (pts.length < 2) continue;
    ctx.strokeStyle = lc[ln] || '#888';
    ctx.lineWidth = Math.max(2, 9 / s());
    ctx.globalAlpha = 0.85;
    ctx.beginPath();
    pts.forEach((p, i) => { const x = sx(p[0] / Q, p[1] / Q), y = sy(p[0] / Q, p[1] / Q, 0);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  for (const st of sub.stations) {
    const x = sx(st.x / Q, st.y / Q), y = sy(st.x / Q, st.y / Q, 0);
    const r = Math.max(4, 16 / s());
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
    ctx.strokeStyle = lc[st.lines[0]] || '#666';
    ctx.lineWidth = Math.max(2, r * 0.42); ctx.stroke();
    if (s() <= 3.5) label(st.name, x, y - r - 4, '#fff', '#000');
  }
}

const POI_KINDS = ['museum', 'market', 'tourinfo'];

function drawPOI() {
  for (const k of POI_KINDS) {
    const col = rgb(D.meta.style.poi[k].color);
    for (const p of D.poi[k]) {
      const x = sx(p.x / Q, p.y / Q), y = sy(p.x / Q, p.y / Q, 0);
      if (x < -20 || x > W + 20 || y < -20 || y > H + 20) continue;
      const r = Math.max(3, 11 / s());
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.moveTo(x, y); ctx.lineTo(x - r, y - r * 1.7);
      ctx.lineTo(x + r, y - r * 1.7); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,.55)'; ctx.lineWidth = 1; ctx.stroke();
      if (s() <= 1.75 && p.name) label(p.name, x, y - r * 1.7 - 3, col, '#000');
    }
  }
}

/* 라벨 겹침 회피 — 먼저 그린 것이 이긴다. render()마다 초기화된다. */
let labelBoxes = [];

function label(text, x, y, fg, bg) {
  ctx.font = '11px -apple-system, sans-serif';
  ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
  const w = ctx.measureText(text).width, box = [x - w / 2 - 2, y - 13, x + w / 2 + 2, y + 2];
  for (const o of labelBoxes)
    if (box[0] < o[2] && box[2] > o[0] && box[1] < o[3] && box[3] > o[1]) return false;
  labelBoxes.push(box);
  ctx.lineWidth = 3; ctx.strokeStyle = bg; ctx.strokeText(text, x, y);
  ctx.fillStyle = fg; ctx.fillText(text, x, y);
  return true;
}

function drawLabels() {
  if (s() > 1.75) return;                        // 확대했을 때만
  // 높은 건물이 우선. 궁궐·전각은 낮아도 관광 대상이라 끌어올린다.
  const cand = [];
  for (const [i, nm] of D.city.names) {
    const b = D.B[i];
    if (visible(b)) cand.push([b.kind === 2 ? b.h + 40 : b.h, nm, b]);
  }
  cand.sort((a, b) => b[0] - a[0]);
  for (const [, nm, b] of cand) {
    const p = b.en[0];
    label(nm, sx(p[0], p[1]), sy(p[0], p[1], b.h) - 3, '#eef2f8', '#000');
  }
}

/* ---------- 클릭 판정 ---------- */
function pointInPoly(px, py, pts) {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, yi] = pts[i], [xj, yj] = pts[j];
    if ((yi > py) !== (yj > py) && px < (xj - xi) * (py - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function pick(px, py) {
  for (const k of POI_KINDS) {                    // POI가 건물보다 우선
    for (const p of D.poi[k]) {
      const x = sx(p.x / Q, p.y / Q), y = sy(p.x / Q, p.y / Q, 0);
      const r = Math.max(6, 11 / s());
      if (px > x - r && px < x + r && py > y - r * 1.9 && py < y + 4)
        return { type: 'poi', kind: k, data: p };
    }
  }
  for (const st of D.poi.subway.stations) {
    const x = sx(st.x / Q, st.y / Q), y = sy(st.x / Q, st.y / Q, 0);
    const r = Math.max(6, 16 / s());
    if (Math.hypot(px - x, py - y) < r) return { type: 'subway', data: st };
  }
  for (let i = D.B.length - 1; i >= 0; i--) {     // 가까운 건물부터 (그린 순서 역순)
    const b = D.B[i];
    if (!visible(b)) continue;
    const src = b.kind ? (b.eave || (b.eave = expand(b.en, EAVE))) : b.en;
    const pts = src.map(p => [sx(p[0], p[1]), sy(p[0], p[1], b.h)]);
    if (pointInPoly(px, py, pts)) return { type: 'building', data: b };
  }
  return null;
}

/* ---------- 정보 패널 ---------- */
const KIND_NM = ['일반', '한옥 · 목조', '궁궐 · 전각'];
const POI_LABEL = { mus_typ: '유형', opr_tel: '전화', opr_url: '홈페이지', new_adr: '주소',
                    category: '분류', items: '취급품목', adr_road: '주소', homepage: '홈페이지',
                    des_inf: '설명', add_inf: '위치', sws_tme: '운영 시작', swe_tme: '운영 종료' };

function showInfo(hit) {
  const box = document.getElementById('info');
  if (!hit) { box.classList.remove('on'); return; }
  const h2 = box.querySelector('h2'), dl = box.querySelector('dl');
  dl.innerHTML = '';
  const row = (k, v) => {
    if (!v) return;
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd');
    if (/^https?:\/\//.test(v)) {
      const a = document.createElement('a');
      a.href = v; a.target = '_blank'; a.rel = 'noopener'; a.textContent = v;
      dd.appendChild(a);
    } else dd.textContent = v;
    dl.append(dt, dd);
  };
  if (hit.type === 'building') {
    const b = hit.data;
    h2.textContent = b.nm || '(이름 없는 건물)';
    row('용도', D.city.uses[b.use] || '—');
    row('구조', KIND_NM[b.kind]);
    row('지상층수', `${b.fl}층`);
    row('추정 높이', `${b.h.toFixed(1)} m`);
  } else if (hit.type === 'subway') {
    h2.textContent = `${hit.data.name}역`;
    row('노선', hit.data.lines.map(l => `${l}호선`).join(', '));
    row('출처', '프로토타입 상수');
  } else {
    h2.textContent = hit.data.name || D.meta.style.poi[hit.kind].label;
    row('분류', D.meta.style.poi[hit.kind].label);
    for (const [k, v] of Object.entries(hit.data))
      if (POI_LABEL[k]) row(POI_LABEL[k], v);
  }
  box.classList.add('on');
}

/* ---------- 입력 ---------- */
function resize() {
  DPR = Math.min(2, window.devicePixelRatio || 1);
  W = canvas.clientWidth; H = canvas.clientHeight;
  canvas.width = W * DPR; canvas.height = H * DPR;
  render();
}

function setZoom(zi, ax, ay) {
  zi = Math.max(0, Math.min(SCALES.length - 1, zi));
  if (zi === view.zi) return;
  // 커서 아래 지점을 고정한 채 확대
  const before = screenToWorld(ax ?? W / 2, ay ?? H / 2);
  view.zi = zi;
  const after = screenToWorld(ax ?? W / 2, ay ?? H / 2);
  view.cx += before.e - after.e; view.cy += before.n - after.n;
  syncZoomUI(); render(); writeHash();
}

/* 화면 -> 월드(지면 h=0). 투영식을 역으로 푼다. */
function screenToWorld(px, py) {
  const k = s();
  const du = (px - W / 2) * k + projU(view.cx, view.cy, 1);
  const dv = -((py - H / 2) * k + projV(view.cx, view.cy, 0, 1)) / Math.sin(PHI);
  const ca = Math.cos(ALPHA), sa = Math.sin(ALPHA);
  return { e: du * ca + dv * sa, n: -du * sa + dv * ca };
}

function syncZoomUI() {
  document.querySelectorAll('#zoom button').forEach((b, i) =>
    b.setAttribute('aria-pressed', i === view.zi));
}

function writeHash() {
  const lon = D.meta.origin.lon0 + view.cx / D.meta.origin.mlon;
  const lat = D.meta.origin.lat0 + view.cy / D.meta.origin.mlat;
  history.replaceState(null, '', `#@${lon.toFixed(5)},${lat.toFixed(5)},${view.zi}`);
}

function readHash() {
  const m = location.hash.match(/^#@(-?[\d.]+),(-?[\d.]+),(\d+)/);
  if (!m) return false;
  view.cx = (parseFloat(m[1]) - D.meta.origin.lon0) * D.meta.origin.mlon;
  view.cy = (parseFloat(m[2]) - D.meta.origin.lat0) * D.meta.origin.mlat;
  view.zi = Math.max(0, Math.min(SCALES.length - 1, parseInt(m[3], 10)));
  return true;
}

function bindInput() {
  let drag = null, moved = 0;
  canvas.addEventListener('pointerdown', e => {
    drag = { x: e.clientX, y: e.clientY }; moved = 0;
    canvas.classList.add('drag'); canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove', e => {
    if (!drag) return;
    const a = screenToWorld(e.clientX, e.clientY), b = screenToWorld(drag.x, drag.y);
    moved += Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y);
    view.cx -= a.e - b.e; view.cy -= a.n - b.n;
    drag = { x: e.clientX, y: e.clientY };
    render();
  });
  canvas.addEventListener('pointerup', e => {
    canvas.classList.remove('drag');
    if (drag && moved < 5) showInfo(pick(e.clientX, e.clientY));
    drag = null; writeHash();
  });
  canvas.addEventListener('wheel', e => {
    e.preventDefault();
    setZoom(view.zi + (e.deltaY < 0 ? 1 : -1), e.clientX, e.clientY);
  }, { passive: false });

  document.getElementById('info').querySelector('.close')
    .addEventListener('click', () => showInfo(null));
  for (const k of Object.keys(layers)) {
    const el = document.getElementById('ly-' + k);
    el.addEventListener('change', () => { layers[k] = el.checked; render(); });
  }
  addEventListener('resize', resize);
  // 이미 열린 상태에서 공유 링크를 받았을 때. writeHash는 replaceState라 이걸 트리거하지 않는다.
  addEventListener('hashchange', () => { if (readHash()) { syncZoomUI(); render(); } });
}

/* ---------- 시작 ---------- */
async function main() {
  const [meta, city, L, poi] = await Promise.all(
    ['meta', 'city', 'layers', 'poi'].map(n => fetch(`data/${n}.json`).then(r => r.json())));
  Object.assign(D, { meta, city, L, poi });

  const st = meta.style;
  ALPHA = st.alpha_deg * Math.PI / 180;
  PHI = st.phi_deg * Math.PI / 180;
  EAVE = st.eave;
  C = st.colors;
  checkGolden(meta.golden);

  // 링 디코딩 + 컬링용 AABB(s=1 기준) 사전계산
  const nameOf = new Map(city.names);
  D.B = city.rings.map((r, i) => {
    const en = decRing(r);
    let u0 = 1e9, u1 = -1e9, v0 = 1e9, v1 = -1e9;
    const h = city.h[i] / Q;
    for (const [e, n] of en) {
      const u = projU(e, n, 1);
      u0 = Math.min(u0, u); u1 = Math.max(u1, u);
      v0 = Math.min(v0, projV(e, n, h, 1)); v1 = Math.max(v1, projV(e, n, 0, 1));
    }
    const kind = city.kind[i];
    const fh = kind === 2 ? st.wood_floor_h * st.palace_scale
             : kind === 1 ? st.wood_floor_h : st.floor_h;
    return { en, h, kind, use: city.use[i], nm: nameOf.get(i) || '',
             fl: Math.max(1, Math.round(h / fh)), u0, u1, v0, v1 };
  });
  for (const k of ['heri', 'park', 'temple', 'river']) D.L[k] = D.L[k].map(decRing);
  D.L.road = D.L.road.map(([w, r]) => [w, decRing(r)]).sort((a, b) => a[0] - b[0]);

  const zb = document.getElementById('zoom');
  SCALES.forEach((sc, i) => {
    const b = document.createElement('button');
    b.textContent = ['전체', '넓게', '보통', '확대', '최대'][i];
    b.onclick = () => setZoom(i);
    zb.appendChild(b);
  });

  canvas = document.getElementById('map');
  ctx = canvas.getContext('2d');
  if (!readHash()) { view.cx = 0; view.cy = 0; view.zi = 1; }
  syncZoomUI(); bindInput(); resize();
  document.getElementById('load').remove();
}

main().catch(e => {
  console.error(e);
  document.getElementById('load').textContent = '데이터를 불러오지 못했습니다: ' + e.message;
});
