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

/* ---------- 뷰 상태 ----------
 *
 * 픽셀아트의 핵심은 **고정된 픽셀 격자**다. 화면 해상도에 직접 그리면 Canvas가
 * 도형을 안티앨리어싱해 가장자리가 뭉개진다(imageSmoothingEnabled는 이미지 확대에만 걸린다).
 * 그래서 1/PIX 크기 오프스크린 캔버스에 그린 뒤 정수배 NEAREST로 확대해 붙인다.
 * poc/iso2.py가 Image.NEAREST로 하는 것과 같은 방식이다.
 *
 * 좌표계가 둘이다:
 *   - 아트 픽셀 : 오프스크린. sx/sy가 돌려주는 값. s()는 "미터 / 아트픽셀"
 *   - 화면 픽셀 : 아트 픽셀 x PIX. 입력 이벤트와 라벨이 쓴다
 */
// 미터/화면px. PIX와 무관하게 프레이밍이 같도록 화면 기준으로 정의한다
const SCALES = [8 / 3, 4 / 3, 2 / 3, 1 / 3, 1 / 6];
const view = { cx: 0, cy: 0, zi: 1 };
const layers = { poi: true, subway: true, green: true, label: true };
let canvas, ctx, W = 0, H = 0, DPR = 1;
let off, octx, OW = 0, OH = 0;                  // 오프스크린(아트 픽셀)
let PIX = 3;                                    // 아트픽셀 1개가 화면에서 차지하는 px
let PIX_ON = 3;                                 // 픽셀화 켰을 때의 배율 (style.json)

// 미터/아트픽셀. PIX=1이면 화면 해상도에 그대로 그린다(= 픽셀화 이전 렌더)
const s = () => SCALES[view.zi] * PIX;
// 월드(미터) -> 아트 픽셀
const sx = (e, n) => Math.round(projU(e, n, s()) - projU(view.cx, view.cy, s()) + OW / 2);
const sy = (e, n, h) => Math.round(projV(e, n, h, s()) - projV(view.cx, view.cy, 0, s()) + OH / 2);
// 아트 픽셀 -> 화면 픽셀
const toScr = v => v * PIX;

/* ---------- 팔레트 양자화 ----------
 *
 * 오프스크린 캔버스도 도형을 안티앨리어싱하므로 경계 픽셀이 중간색으로 섞인다.
 * (실측: 팔레트가 ~50색인데 화면에는 6,593색이 나왔다)
 * 렌더 후 모든 픽셀을 팔레트의 가장 가까운 색으로 스냅해 경계를 딱 떨어지게 만든다.
 *
 * 파이썬 렌더러(poc/iso2.py)는 PIL이 폴리곤을 안티앨리어싱하지 않아 이 과정이 필요 없다.
 * 브라우저 전용 보정이다.
 *
 * 디더링은 넣지 않는다 — 모든 면이 단색이라 계조가 없어 디더링할 대상이 없다.
 * 벽면 질감은 Phase 2-D 스프라이트가 맡는다.
 */
let PAL_RGB = null;                 // Uint8Array(n*3)
let PAL_LUT = null;                 // Int16Array(32768). 15비트 RGB -> 팔레트 인덱스

const hex2rgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));

function buildPalette() {
  const seen = new Set(), out = [];
  const add = c => {
    if (!c) return;
    const k = c.join(',');
    if (!seen.has(k)) { seen.add(k); out.push(c); }
  };
  for (const k of ['bg', 'ground', 'road', 'heri', 'heri_edge', 'park', 'park_edge', 'river'])
    add(C[k]);
  const triple = t => {
    t.forEach(add);
    // 처마에 쓰는 파생색도 팔레트에 포함해야 스냅이 정확하다
    add(t[0].map(v => Math.round(v * 0.72)));
    add(t[0].map(v => Math.round(v * 0.62)));
  };
  Object.values(C.use).forEach(triple);
  [C.palace, C.hanok, C.default].forEach(triple);
  for (const v of Object.values(D.meta.style.poi)) add(v.color);
  for (const v of Object.values(D.meta.style.subway_lines)) add(hex2rgb(v));
  add([255, 255, 255]);

  PAL_RGB = new Uint8Array(out.length * 3);
  out.forEach((c, i) => PAL_RGB.set(c, i * 3));
  PAL_LUT = new Int16Array(32768).fill(-1);
  return out.length;
}

function nearest(r, g, b) {
  const key = ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3);
  let idx = PAL_LUT[key];
  if (idx >= 0) return idx;
  let best = 0, bd = Infinity;
  for (let i = 0, n = PAL_RGB.length; i < n; i += 3) {
    const dr = r - PAL_RGB[i], dg = g - PAL_RGB[i + 1], db = b - PAL_RGB[i + 2];
    const d = dr * dr + dg * dg + db * db;
    if (d < bd) { bd = d; best = i / 3; }
  }
  PAL_LUT[key] = best;
  return best;
}

function quantize() {
  const img = octx.getImageData(0, 0, OW, OH), d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const j = nearest(d[i], d[i + 1], d[i + 2]) * 3;
    d[i] = PAL_RGB[j]; d[i + 1] = PAL_RGB[j + 1]; d[i + 2] = PAL_RGB[j + 2];
  }
  octx.putImageData(img, 0, 0);
}


/* ---------- 그리기 (전부 오프스크린 octx에) ---------- */
function poly(pts, fill, stroke) {
  octx.beginPath();
  octx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) octx.lineTo(pts[i][0], pts[i][1]);
  octx.closePath();
  if (fill) { octx.fillStyle = fill; octx.fill(); }
  if (stroke) { octx.strokeStyle = stroke; octx.lineWidth = 1; octx.stroke(); }
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

function visible(b) {                             // s=1 기준 아트픽셀 AABB로 컬링
  const k = 1 / s(), m = 24;
  const ox = -projU(view.cx, view.cy, 1) * k + OW / 2;
  const oy = -projV(view.cx, view.cy, 0, 1) * k + OH / 2;
  return b.u1 * k + ox > -m && b.u0 * k + ox < OW + m
      && b.v1 * k + oy > -m && b.v0 * k + oy < OH + m;
}

function drawLines(list, color, widthOf) {
  octx.strokeStyle = color; octx.lineCap = 'butt'; octx.lineJoin = 'miter';
  for (const it of list) {
    const [w, en] = widthOf ? it : [null, it];
    octx.lineWidth = Math.max(1, Math.round(widthOf ? (w / Q) / s() : 2));
    octx.beginPath();
    en.forEach((p, i) => i ? octx.lineTo(sx(p[0], p[1]), sy(p[0], p[1], 0))
                           : octx.moveTo(sx(p[0], p[1]), sy(p[0], p[1], 0)));
    octx.stroke();
  }
}

function render() {
  const t0 = performance.now();
  octx.setTransform(1, 0, 0, 1, 0, 0);
  octx.fillStyle = rgb(C.bg);
  octx.fillRect(0, 0, OW, OH);

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

  if (PIX > 1) quantize();          // 안티앨리어싱된 경계를 팔레트로 스냅

  // 아트 픽셀 -> 화면. 정수배 NEAREST 확대라 픽셀 경계가 살아남는다
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = rgb(C.bg);
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(off, 0, 0, OW, OH, 0, 0, OW * PIX * DPR, OH * PIX * DPR);

  // 라벨은 화면 해상도로 (같이 확대하면 읽을 수 없다)
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  labelBoxes = [];
  if (layers.label) drawLabels();
  if (layers.subway) labelSubway();
  if (layers.poi) labelPOI();

  document.getElementById('stat').textContent =
    `건물 ${D.B.length.toLocaleString()}동 중 ${drawn.toLocaleString()} 표시 · `
    + `${(s() / PIX).toFixed(2)} m/화면px · `
    + (PIX > 1 ? `픽셀 ${PIX}배 · ${PAL_RGB.length / 3}색` : '픽셀화 꺼짐')
    + ` · ${Math.round(performance.now() - t0)}ms`;
}

/* 지하철·POI는 물리적 대상이 아니라 기호다. 월드 크기가 아니라
 * 화면(아트픽셀) 크기를 고정해야 확대해도 굵어지지 않는다. */
const SYM = { line: 2, station: 4, poi: 4 };

function drawSubway() {
  const sub = D.poi.subway, lc = D.meta.style.subway_lines;
  octx.lineCap = 'butt'; octx.lineJoin = 'miter';
  for (const [ln, pts] of Object.entries(sub.lines)) {
    if (pts.length < 2) continue;
    octx.strokeStyle = lc[ln] || '#888';
    octx.lineWidth = SYM.line;
    octx.beginPath();
    pts.forEach((p, i) => { const x = sx(p[0] / Q, p[1] / Q), y = sy(p[0] / Q, p[1] / Q, 0);
      i ? octx.lineTo(x, y) : octx.moveTo(x, y); });
    octx.stroke();
  }
  for (const st of sub.stations) {
    const x = sx(st.x / Q, st.y / Q), y = sy(st.x / Q, st.y / Q, 0);
    const r = SYM.station;
    // 픽셀아트답게 원 대신 사각형
    octx.fillStyle = lc[st.lines[0]] || '#666';
    octx.fillRect(x - r, y - r, r * 2, r * 2);
    octx.fillStyle = '#fff';
    octx.fillRect(x - r + 1, y - r + 1, r * 2 - 2, r * 2 - 2);
  }
}

function labelSubway() {
  if (s() / PIX > 4 / 3) return;
  for (const st of D.poi.subway.stations) {
    label(st.name, toScr(sx(st.x / Q, st.y / Q)),
          toScr(sy(st.x / Q, st.y / Q, 0) - SYM.station) - 3, '#fff', '#000');
  }
}

const POI_KINDS = ['museum', 'market', 'tourinfo'];

function drawPOI() {
  for (const k of POI_KINDS) {
    const col = rgb(D.meta.style.poi[k].color);
    octx.fillStyle = col;
    for (const p of D.poi[k]) {
      const x = sx(p.x / Q, p.y / Q), y = sy(p.x / Q, p.y / Q, 0);
      if (x < -8 || x > OW + 8 || y < -8 || y > OH + 8) continue;
      const r = SYM.poi;
      // 픽셀 삼각형 — 한 줄씩 사각형으로 쌓는다
      for (let i = 0; i < r * 2; i++) {
        const half = Math.max(1, Math.round(r * (1 - i / (r * 2))));
        octx.fillRect(x - half, y - r * 2 + i, half * 2, 1);
      }
    }
  }
}

function labelPOI() {
  if (s() / PIX > 2 / 3) return;
  for (const k of POI_KINDS) {
    const col = rgb(D.meta.style.poi[k].color);
    for (const p of D.poi[k]) {
      if (!p.name) continue;
      const x = sx(p.x / Q, p.y / Q), y = sy(p.x / Q, p.y / Q, 0);
      if (x < 0 || x > OW || y < 0 || y > OH) continue;
      label(p.name, toScr(x), toScr(y - SYM.poi * 2) - 3, col, '#000');
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
  if (s() / PIX > 2 / 3) return;                 // 확대했을 때만
  // 높은 건물이 우선. 궁궐·전각은 낮아도 관광 대상이라 끌어올린다.
  const cand = [];
  for (const [i, nm] of D.city.names) {
    const b = D.B[i];
    if (visible(b)) cand.push([b.kind === 2 ? b.h + 40 : b.h, nm, b]);
  }
  cand.sort((a, b) => b[0] - a[0]);
  for (const [, nm, b] of cand) {
    const p = b.en[0];
    label(nm, toScr(sx(p[0], p[1])), toScr(sy(p[0], p[1], b.h)) - 3, '#eef2f8', '#000');
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

function pick(spx, spy) {
  const px = spx / PIX, py = spy / PIX;          // 화면 -> 아트 픽셀
  for (const k of POI_KINDS) {                    // POI가 건물보다 우선
    for (const p of D.poi[k]) {
      const x = sx(p.x / Q, p.y / Q), y = sy(p.x / Q, p.y / Q, 0);
      const r = SYM.poi;
      if (px > x - r && px < x + r && py > y - r * 2.2 && py < y + 3)
        return { type: 'poi', kind: k, data: p };
    }
  }
  for (const st of D.poi.subway.stations) {
    const x = sx(st.x / Q, st.y / Q), y = sy(st.x / Q, st.y / Q, 0);
    const r = Math.max(6, 16 / s());
    if (Math.hypot(px - x, py - y) < r) return { type: 'subway', data: st };
  }
  // 압출은 화면상 수직 이동이라 실루엣 = 지붕 폴리곤을 아래로 쓸어내린 영역이다.
  // 지붕만 검사하면 벽면 클릭이 빠지므로 높이 구간을 몇 단계 샘플링한다.
  for (let i = D.B.length - 1; i >= 0; i--) {     // 가까운 건물부터 (그린 순서 역순)
    const b = D.B[i];
    if (!visible(b)) continue;
    const src = b.kind ? (b.eave || (b.eave = expand(b.en, EAVE))) : b.en;
    const pts = src.map(p => [sx(p[0], p[1]), sy(p[0], p[1], b.h)]);
    const drop = sy(src[0][0], src[0][1], 0) - sy(src[0][0], src[0][1], b.h);  // 지붕→지면
    const steps = Math.min(6, Math.max(1, Math.ceil(drop / 6)));
    for (let k = 0; k <= steps; k++)
      if (pointInPoly(px, py - drop * k / steps, pts))
        return { type: 'building', data: b };
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
  canvas.width = Math.round(W * DPR); canvas.height = Math.round(H * DPR);
  OW = Math.ceil(W / PIX); OH = Math.ceil(H / PIX);
  if (!off) off = document.createElement('canvas');
  off.width = OW; off.height = OH;
  octx = off.getContext('2d', { alpha: false });
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
function screenToWorld(spx, spy) {
  const k = s();
  const px = spx / PIX, py = spy / PIX;          // 화면 -> 아트 픽셀
  const du = (px - OW / 2) * k + projU(view.cx, view.cy, 1);
  const dv = -((py - OH / 2) * k + projV(view.cx, view.cy, 0, 1)) / Math.sin(PHI);
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
    canvas.classList.add('drag');
    // 합성 이벤트나 일부 입력에서 던질 수 있다. 실패해도 팬·클릭은 계속돼야 한다.
    try { canvas.setPointerCapture(e.pointerId); } catch { /* 무시 */ }
  });
  canvas.addEventListener('pointermove', e => {
    if (!drag) return;
    const a = screenToWorld(e.clientX, e.clientY), b = screenToWorld(drag.x, drag.y);
    moved += Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y);
    view.cx -= a.e - b.e; view.cy -= a.n - b.n;
    drag = { x: e.clientX, y: e.clientY };
    render();
  });
  // 포인터 이벤트는 팬만 맡고, 선택은 click으로 처리한다.
  // pointerup에 선택을 걸면 포인터 캡처 상황에 따라 누락될 수 있다.
  canvas.addEventListener('pointerup', () => {
    canvas.classList.remove('drag'); drag = null; writeHash();
  });
  canvas.addEventListener('pointercancel', () => {
    canvas.classList.remove('drag'); drag = null;
  });
  canvas.addEventListener('click', e => {
    if (moved < 5) showInfo(pick(e.clientX, e.clientY));
    moved = 0;
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
  const px = document.getElementById('ly-pixelate');
  px.addEventListener('change', () => { PIX = px.checked ? PIX_ON : 1; resize(); });
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
  PIX_ON = st.pixel_size || 3;
  PIX = PIX_ON;
  checkGolden(meta.golden);
  console.log(`[pixel_city] 팔레트 ${buildPalette()}색`);

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

/* ---------- 자체 검증 (콘솔에서 pixelCitySelfCheck() 호출) ---------- */
function pixelCitySelfCheck() {
  const sq = [[0, 0], [10, 0], [10, 10], [0, 10]];
  console.assert(pointInPoly(5, 5, sq) === true, 'pointInPoly 내부');
  console.assert(pointInPoly(15, 5, sq) === false, 'pointInPoly 외부');
  const ex = expand([[0, 0], [10, 0], [10, 10], [0, 10]], 2);
  console.assert(Math.abs(ex[0][0] + 5) < 1e-9 && Math.abs(ex[2][0] - 15) < 1e-9, 'expand');
  console.assert(OW > 0 && OH > 0 && off.width === OW, '오프스크린 크기');
  const w = screenToWorld(W / 2, H / 2);
  console.assert(Math.hypot(w.e - view.cx, w.n - view.cy) < s() * 2, '화면중심 역투영');
  console.assert(PAL_RGB && PAL_RGB.length % 3 === 0, '팔레트 구성');
  const i0 = nearest(PAL_RGB[0], PAL_RGB[1], PAL_RGB[2]);
  console.assert(i0 === 0, '팔레트 색은 자기 자신으로 스냅');
  console.log('[pixel_city] selfcheck ok');
  return true;
}
window.pixelCitySelfCheck = pixelCitySelfCheck;
// 디버그 훅 — 콘솔에서 좌표 변환과 판정을 직접 확인할 수 있다
window.pixelCity = { pick, sx, sy, s: () => s(), view, get PIX() { return PIX; },
                     get OW() { return OW; }, get OH() { return OH; }, D };
