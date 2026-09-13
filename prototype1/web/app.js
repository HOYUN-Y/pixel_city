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

/* ---------- 지형 (poc/terrain.py가 만든 표고 격자) ----------
 * ENU 축정렬 직사각 격자다. 좌표계 변환은 파이썬이 이미 끝냈고 여기선 이중선형만 한다.
 * terrain.json이 없으면 TERR=null -> zAt()이 전부 0 -> 지형 도입 전 평지 동작.
 * 되돌리기가 `rm web/data/terrain.json` 한 줄인 것이 이 구조 덕이다.
 */
let TERR = null, TEXAG = 1;

function zAt(e, n) {
  const g = TERR;
  if (!g) return 0;
  const fi = (e - g.e0) / g.step, fj = (n - g.n0) / g.step;
  if (fi < 0 || fj < 0 || fi > g.nx - 1 || fj > g.ny - 1) return 0;
  // 마지막 행·열에서 i+1이 격자를 넘지 않도록 클램프. 빼면 메시 외곽이 0으로 주저앉는다
  const i = Math.min(Math.floor(fi), g.nx - 2), j = Math.min(Math.floor(fj), g.ny - 2);
  const u = fi - i, v = fj - j, z = g.z, w = g.nx;
  return TEXAG / Q * (
    (z[j * w + i] * (1 - u) + z[j * w + i + 1] * u) * (1 - v) +
    (z[(j + 1) * w + i] * (1 - u) + z[(j + 1) * w + i + 1] * u) * v);
}

function checkTerrainGolden(g) {
  const bad = g.golden.filter(p => Math.abs(zAt(p.e, p.n) / TEXAG - p.z) > 1e-3);
  if (bad.length) {
    console.error('[pixel_city] 지형 이식 불일치 — terrain.py와 결과가 다르다', bad);
    return false;
  }
  console.log(`[pixel_city] 지형 골든 값 ${g.golden.length}건 일치 `
    + `(격자 ${g.nx}x${g.ny} / datum ${g.z0}m / 기복 ${g.zmin}~${g.zmax}m / exag ${g.exag})`);
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
// h는 "지면 위 높이". z를 주면 그 값을 기준면으로 쓰고(건물 = 평면 기초),
// 안 주면 지형을 샘플한다(도로·POI 등 지면 밀착 요소가 편집 없이 지형을 탄다).
// ponytail: 카메라 앵커는 z=0 평면 고정. 최대 줌에서 남산에 가면 지형이 화면 위로
// ~400 아트픽셀 벗어난다. 고치려면 앵커·visible()의 oy·screenToWorld 3곳을 동시에
// 수정해야 하고, 문서용 축척(전체/넓게)에서는 25~50픽셀이라 무해하다.
const sy = (e, n, h, z) =>
  Math.round(projV(e, n, h + (z === undefined ? zAt(e, n) : z), s())
             - projV(view.cx, view.cy, 0, s()) + OH / 2);
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
  // 지형 음영 — 맨땅·공원·문화재구역 각각의 표고 램프 (기존 색에서 파생).
  // style.json에 색을 넣지 않는 이유는 그 경로가 export.py -> meta.json 재생성을
  // 요구하고, 수집 캐시가 없어 지금 돌릴 수 없기 때문이다. 처마 파생색과 같은 패턴이다.
  // ⚠️ nearest()가 채널당 5비트로 버킷팅하므로(>>3) 모든 채널에서 8 미만 차이인 색 둘은
  // LUT가 구분하지 못한다. GSHADE_K 간격을 좁히면 램프끼리 뭉친다
  // (selfcheck가 '엉뚱한 색으로 스냅'으로 잡는다. 현재 간격에서는 충돌 0).
  TSHADE = [C.ground, C.park, C.heri].map(base => GSHADE_K.map(f => {
    const fr = Array.isArray(f) ? f : [f, f, f];   // 채널별 배율 (스칼라도 허용)
    const c = base.map((v, i) => Math.max(0, Math.min(255, Math.round(v * fr[i]))));
    add(c);
    return rgb(c);
  }));
  buildVariants(add);                 // 건물 변주색도 여기서 등록한다
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

/* 벽에 그릴 가로선 개수. 0 = 없음 / 1 = 파라펫 1줄 / n>1 = n층 (선은 n-1개).
 *
 * 층당 아트픽셀 = (층고 × cosΦ) / s(). 줌별로 2.6/s() 이고 실측 판정은:
 *   줌2 1.3px 불가 · 줌3 2.6px 모아레(sy의 Math.round가 2/3/2/3px로 흩뿌린다) · 줌4 5.2px 가능
 * 그래서 줌3은 파라펫 1줄만, 줌4에서만 층 띠를 그린다. 가드 하나가 둘을 분기시킨다.
 */
function floorBands(b) {
  if (s() > 1.0) return 0;                                   // 줌 0~2: 비용 0
  if (b.fl < 3) return 1;                                    // 저층은 띠가 의미 없다
  return (b.h / b.fl) * Math.cos(PHI) / s() >= BAND_MIN_PX ? b.fl : 1;
}

function walls(en, h0, h1, litC, darkC, z, bands) {
  const sa = Math.sin(ALPHA), ca = Math.cos(ALPHA);
  for (let i = 0; i < en.length - 1; i++) {
    const [e1, n1] = en[i], [e2, n2] = en[i + 1];
    const nx = n2 - n1, nz = -(e2 - e1);
    if (nx * sa + nz * ca <= 0) continue;                    // 후면 제거
    const lit = Math.abs(nx) / (Math.hypot(nx, nz) + 1e-9) > 0.5;
    poly([[sx(e1, n1), sy(e1, n1, h0, z)], [sx(e2, n2), sy(e2, n2, h0, z)],
          [sx(e2, n2), sy(e2, n2, h1, z)], [sx(e1, n1), sy(e1, n1, h1, z)]],
         lit ? litC : darkC, null);
    // ponytail: 띠는 lit 면에만, 색은 그 건물의 dark 재사용 -> 팔레트 추가 0색, 비용 절반.
    // 어두운 면까지 필요하면 dark×0.8을 재질별로 등록해야 한다(+색) — 그때 올린다.
    // 간격은 sy()의 Math.round 때문에 +-1 아트픽셀 흔들린다. 고치려면 sy를 우회해야 하고
    // 그건 파이썬 렌더러와의 패리티를 깬다.
    if (!bands || !lit) continue;
    octx.strokeStyle = darkC; octx.lineWidth = 1;
    octx.beginPath();
    for (let k = 1; k <= (bands === 1 ? 1 : bands - 1); k++) {
      const hb = bands === 1 ? h0 + (h1 - h0) * 0.92 : h0 + (h1 - h0) * k / bands;
      octx.moveTo(sx(e1, n1) + 0.5, sy(e1, n1, hb, z) + 0.5);
      octx.lineTo(sx(e2, n2) + 0.5, sy(e2, n2, hb, z) + 0.5);
    }
    octx.stroke();
  }
}

/* ---------- 건물 색 변주 ----------
 *
 * 지붕은 **주용도 세분류**, 벽은 **재질 x 연령**. 둘을 분리한 게 핵심이다 —
 * 팔레트는 덧셈(+75색)으로 늘고 외형은 곱셈(실재 조합 83개)으로 는다.
 * 묶어두면 같은 변주에 630색이 필요하다.
 *
 * 실측 6,985동: 최대 셀 점유 **44.5% -> 13.4%**, 갈리는 조합 **8 -> 83개**.
 * 축을 이렇게 고른 근거는 poc/style.json의 `_variant_note`와 WORKLOG 09-13에 있다.
 *
 * **결측은 전부 오늘 색으로 떨어진다** — 지붕은 대분류, 벽은 kind 기본색, 연령은
 * 중립 밴드(배율 1.0). 이 되돌리기 동치를 selfcheck가 지킨다.
 */
let VAR = null;                 // 캐시된 변주 색. buildVariants()가 채운다

// ↓ 셋 다 iso2.py의 wall_mat / wood_use / age_band와 **같은 규칙**이어야 한다
function wallMat(strct) {
  if (strct.includes('목')) return null;                    // 목조는 kind가 처리
  if (/철근콘크리트|철골철근|철골콘크리트/.test(strct)) return '콘크리트';
  if (/벽돌|조적|블록|석/.test(strct)) return '조적';
  return '기타';
}
function woodUse(prpos) {
  const p = prpos || '';
  return p.includes('주택') ? '주거' : (p.includes('근린생활') ? '근생' : '기타');
}
function ageBand(year, breaks) {                            // 결측(0)은 중립 = 오늘 색
  const b = breaks || [1966, 1989];
  if (!year) return 1;
  return year < b[0] ? 0 : (year >= b[1] ? 2 : 1);
}

function variant(b) {
  // b.wm은 목조면 주용도 구분(주거/근생/기타), 아니면 재질(콘크리트/조적/기타)이다.
  // 로드 시 kind에 따라 갈라 구워두므로 여기선 그대로 쓴다.
  if (b.kind) return [b.kind === 2 ? '궁궐' : '한옥', b.wm, b.ab];
  return [b.rg, b.wm, b.ab];
}

/* 프레임마다 rgb() 문자열을 만들지 않도록 로드 시 한 번 구워둔다.
 * 기존 drawBuilding은 건물당 3~4회 템플릿 문자열을 만들었다 (프레임당 약 28,000회). */
function buildVariants(add) {
  const K = C.age_k || [1, 1, 1];
  const mulc = (c, k) => c.map(v => Math.max(0, Math.min(255, Math.round(v * k))));
  VAR = { roof: {}, wall: {}, wood: {} };
  const reg = c => { add(c); return rgb(c); };

  // 지붕 — 주용도 세분류. 폴백은 대분류(오늘 색)
  for (const [k, c] of Object.entries(C.roof_g || {})) VAR.roof[k] = reg(c);
  for (const [k, t] of Object.entries(C.use)) VAR.roof['대분류:' + k] = reg(t[0]);
  VAR.roof['대분류:'] = reg(C.default[0]);

  // 벽 — 재질 x 연령
  for (const [k, [lit, dark]] of Object.entries(C.wall_m || {}))
    VAR.wall[k] = K.map(f => [reg(mulc(lit, f)), reg(mulc(dark, f))]);
  // 목조 벽 — 주용도 x 연령 (한옥은 재질 축이 없다)
  for (const [kind, byUse] of Object.entries(C.wood_wall || {})) {
    VAR.wood[kind] = {};
    for (const [u, [lit, dark]] of Object.entries(byUse))
      VAR.wood[kind][u] = K.map(f => [reg(mulc(lit, f)), reg(mulc(dark, f))]);
  }
  // 폴백 — 변주가 없을 때 쓰는 오늘 색
  VAR.fb = {};
  for (const [k, t] of Object.entries(C.use)) VAR.fb[k] = [reg(t[1]), reg(t[2])];
  VAR.fb[''] = [reg(C.default[1]), reg(C.default[2])];
  VAR.fbWood = { 한옥: [reg(C.hanok[1]), reg(C.hanok[2])],
                 궁궐: [reg(C.palace[1]), reg(C.palace[2])] };
  // 목조 지붕은 용도로 변하지 않는다 (기와는 기와). 처마 파생색까지 미리 굽는다
  const woodRoof = t => [reg(t[0]), reg(t[0].map(v => Math.round(v * 0.72))),
                                    reg(t[0].map(v => Math.round(v * 0.62)))];
  VAR.fbRoofWood = { 한옥: woodRoof(C.hanok), 궁궐: woodRoof(C.palace) };
}

/* -> [지붕, 밝은벽, 어두운벽] **rgb 문자열**. 예전에는 색 배열을 돌려줬다. */
function palette(b) {
  const [rg, wm, ab] = variant(b);
  if (b.kind) {
    const kn = b.kind === 2 ? '궁궐' : '한옥';
    const w = VAR.wood[kn] && VAR.wood[kn][wm];
    const [roof, e72, e62] = VAR.fbRoofWood[kn];
    return [roof, ...(w ? w[ab] : VAR.fbWood[kn]), e72, e62];
  }
  const roof = VAR.roof[rg] || VAR.roof['대분류:' + (D.city.uses[b.use] || '')]
                            || VAR.roof['대분류:'];
  const w = VAR.wall[wm];
  return [roof, ...(w ? w[ab] : (VAR.fb[D.city.uses[b.use]] || VAR.fb['']))];
}

function drawBuilding(b) {
  const pal = palette(b), [roof, lit, dark] = pal;
  // ponytail: 건물은 중심 표고(b.z)에 평면으로 앉는다. 경사면에서 내리막쪽이 최대
  // ±7m 떠 보이지만, 정점별 표고를 주면 바닥이 비평면이 되어 지붕이 기운다
  // (90m 격자 최대 경사에서 7~13 아트픽셀). 평평한 게 기운 것보다 훨씬 낫다.
  const en = b.en, h = b.h, z = b.z;
  if (b.kind) {                                   // 목조: 낮은 기둥 + 크게 내민 처마
    const body = h * 0.5, e72 = pal[3], e62 = pal[4];
    walls(en, 0, body, lit, dark, z);             // 한옥은 1~2층이라 띠를 안 그린다
    const ev = b.eave || (b.eave = expand(en, EAVE));
    walls(ev, body, h, roof, e72, z);
    poly(ev.map(p => [sx(p[0], p[1]), sy(p[0], p[1], h, z)]), roof, e62);
  } else {
    walls(en, 0, h, lit, dark, z, floorBands(b));
    poly(en.map(p => [sx(p[0], p[1]), sy(p[0], p[1], h, z)]), roof, dark);
  }
}

function visible(b) {                             // s=1 기준 아트픽셀 AABB로 컬링
  const k = 1 / s(), m = 24;
  const ox = -projU(view.cx, view.cy, 1) * k + OW / 2;
  const oy = -projV(view.cx, view.cy, 0, 1) * k + OH / 2;
  return b.u1 * k + ox > -m && b.u0 * k + ox < OW + m
      && b.v1 * k + oy > -m && b.v0 * k + oy < OH + m;
}

/* ---------- 지형 메시 ----------
 * 표고 격자를 쿼드로 깐다. 경사로 음영 5단을 골라 언덕이 읽히게 한다.
 *
 * 순서: t = e·sinα + n·cosα 가 클수록 멀다. α=22.5°에서 sinα·cosα 둘 다 양수라
 * t는 e·n 양쪽에 단조 증가한다 -> **인덱스 내림차순이 곧 먼 것부터**다. 정렬이 필요 없다.
 */
/* 음영 상수는 terrain.json에서 온다 (정본은 poc/style.json). 하드코딩하지 않는 이유는
 * 파이썬 렌더러와 같은 숫자를 읽게 하려는 것이다 — style.json -> meta.json 경로는
 * export.py 재실행을 요구하는데 수집 캐시가 없어 지금 돌릴 수 없다.
 * gain은 남산 셀 220개 실측으로 맞췄다: 단일셀 기울기 g6은 인접 단계차 0.39로
 * 패치워크처럼 읽히고, 3x3 평활 g4는 0.20이면서 분포와 평균(2.0)을 유지한다. */
let GSHADE_K = [[1, 1, 1], [1, 1, 1], [1, 1, 1]];   // terrain.json이 덮어쓴다 (채널별 배율)
let GNEUTRAL = 2;                                  // 램프 안에서 배율 1.0인 칸 (평지)
let GLIGHT = [1.0, 0.35];                          // 광원 방향 (e, n)
let GSHADE_GAIN = 3;                               // 경사 -> 단계 (보조 신호)
let GZBAND = 50;
let BAND_MIN_PX = 3;                               // 층당 이 아트픽셀 미만이면 층 띠 대신 파라펫 1줄                                   // 표고 몇 m마다 한 단계 (주 신호)
let TSHADE = [];        // TSHADE[지표][단계] = rgb 문자열. buildPalette()가 채운다
let TCELL = null;       // Int16Array(i, j, 단계, 지표) x N. 먼 것부터. 로드 시 1회 계산

/* 셀별 음영 단계와 지표를 미리 굽는다.
 *
 * 단계 = GNEUTRAL + round(표고/GZBAND) - round(경사*GSHADE_GAIN), 램프 범위로 clamp.
 *
 * **표고 밴드가 주 신호다.** 경사만 쓰면 균일 사면이 균일 톤이 되어 산이 평지와 같은
 * 색으로 칠해진다 — 실측으로 확인했다: 남산 종단면 232m->31m 구간에서 단계가 2·3
 * 두 개만 쓰이고 단계 2의 휘도는 평지 공원과 완전히 동일했다. 지도가 산을 보여주는
 * 방식은 표고별 색조이고, 경사는 국지적 형태(능선·골)를 얹는 보조 신호다.
 *
 * neutral 단계(배율 1.0 = 평지)는 건너뛴다 — 기존 폴리곤 렌더(크리스프한 공원 경계)를
 * 덮지 않고 기복이 있는 곳만 덮는다. GZBAND(60m)가 도심 대역폭(41.5m)보다 커서
 * 평지 도심은 대부분 여기 남고, 90m 블록은 기복이 있는 곳에만 나타난다.
 *
 * 지표를 보는 이유: 남산은 전체가 공원 폴리곤(가장 큰 것이 한 변 979m)에 덮여 있어
 * 맨땅 음영으로 덮으면 산이 초록에서 회색으로 바뀐다. 셀이 공원 안인지 보고
 * 공원색 램프를 쓰면 초록을 유지한 채 기복이 읽힌다.
 */
function buildTerrainCells() {
  if (!TERR) return 0;
  const { nx, ny, step, e0, n0, z } = TERR, k = TEXAG / Q;
  // 인덱스를 격자 안으로 물린 접근자 — 3x3 스텐실이 경계를 넘지 않게
  const zc = (i, j) => z[Math.min(ny - 1, Math.max(0, j)) * nx
                       + Math.min(nx - 1, Math.max(0, i))] * k;
  // 폴리곤 ENU bbox를 미리 잡아 점-다각형 판정 횟수를 줄인다.
  // render()의 그리는 순서(heri -> park -> temple)와 같게 두고 마지막 일치를 쓴다
  const zones = [];
  for (const [cover, key] of [[2, 'heri'], [1, 'park'], [2, 'temple']])
    for (const r of (D.L[key] || [])) {
      let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
      for (const [e, n] of r) {
        x0 = Math.min(x0, e); y0 = Math.min(y0, n);
        x1 = Math.max(x1, e); y1 = Math.max(y1, n);
      }
      zones.push([cover, x0, y0, x1, y1, r]);
    }
  const out = [];
  for (let j = ny - 2; j >= 0; j--)                // 먼 것부터 (t = e·sinα + n·cosα 내림차순)
    for (let i = nx - 2; i >= 0; i--) {
      const grad = ((zc(i + 2, j) + zc(i + 2, j + 1) - zc(i - 1, j) - zc(i - 1, j + 1)) / 2 * GLIGHT[0]
                  + (zc(i, j + 2) + zc(i + 1, j + 2) - zc(i, j - 1) - zc(i + 1, j - 1)) / 2 * GLIGHT[1])
                  / (3 * step);
      const zmid = (zc(i, j) + zc(i + 1, j) + zc(i, j + 1) + zc(i + 1, j + 1)) / 4;
      const lv = Math.max(0, Math.min(GSHADE_K.length - 1,
        GNEUTRAL + Math.round(zmid / GZBAND) - Math.round(grad * GSHADE_GAIN)));
      if (lv === GNEUTRAL) continue;
      const ce = e0 + (i + 0.5) * step, cn = n0 + (j + 0.5) * step;
      let cover = 0;
      for (const [ci, x0, y0, x1, y1, r] of zones)
        if (ce >= x0 && ce <= x1 && cn >= y0 && cn <= y1 && pointInPoly(ce, cn, r)) cover = ci;
      out.push(i, j, lv, cover);
    }
  TCELL = new Int16Array(out);
  return TCELL.length / 4;
}

function drawTerrain() {
  if (!TCELL || !TSHADE.length) return;
  const { step, e0, n0 } = TERR;
  for (let p = 0; p < TCELL.length; p += 4) {
    const e = e0 + TCELL[p] * step, n = n0 + TCELL[p + 1] * step;
    const e1 = e + step, n1 = n + step;
    poly([[sx(e, n), sy(e, n, 0)], [sx(e1, n), sy(e1, n, 0)],
          [sx(e1, n1), sy(e1, n1, 0)], [sx(e, n1), sy(e, n1, 0)]],
         TSHADE[TCELL[p + 3]][TCELL[p + 2]], null);
  }
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

  // 지면 — 격자 밖 배경. zAt이 격자 밖에서 0이므로 지형 메시와 이가 맞는다
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
  // 지표 폴리곤 위에 얹는다 — 경사 있는 셀만 덮으므로 평지의 크리스프한 경계는 남는다
  drawTerrain();
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
    label(nm, toScr(sx(p[0], p[1])), toScr(sy(p[0], p[1], b.h, b.z)) - 3, '#eef2f8', '#000');
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
    const pts = src.map(p => [sx(p[0], p[1]), sy(p[0], p[1], b.h, b.z)]);
    // 표고 b.z는 양쪽에 같이 들어가 소거된다 -> drop은 지형 도입 전과 동일하다
    const drop = sy(src[0][0], src[0][1], 0, b.z)
               - sy(src[0][0], src[0][1], b.h, b.z);         // 지붕→지면
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
    const ci = D.city, gi = D.B.indexOf(b);
    // 색의 근거를 그대로 보여준다 — "왜 이 색인가"에 답할 수 있어야 한다
    row('주용도', (ci.prp && ci.prp[ci.prpos[gi]]) || D.city.uses[b.use] || '—');
    row('용도 대분류', D.city.uses[b.use] || '—');
    row('구조', (ci.str && ci.str[ci.strct[gi]]) || KIND_NM[b.kind]);
    row('지상층수', `${b.fl}층`);
    // 높이의 출처를 밝힌다 — 36%는 실측(buld_hg), 나머지는 층고 곡선 추정이다
    row(ci.meas && ci.meas[gi] ? '높이 (실측)' : '높이 (추정)', `${b.h.toFixed(1)} m`);
    const yr = ci.yr && ci.yr[gi];
    row('사용승인', yr ? `${yr}년` : '기록 없음');
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
  // cache:'no-cache'는 캐시를 버리는 게 아니라 **재검증**을 강제한다 (If-Modified-Since).
  // 안 바뀐 파일은 304로 돌아와 비용이 거의 없고, 바뀐 파일은 반드시 새로 받는다.
  // 이게 없으면 export.py를 돌려도 브라우저가 옛 JSON을 계속 쓴다 — 실제로 겪었다.
  // 페이지 URL에 ?v=N을 붙여도 app.js가 fetch하는 data/*.json은 뚫리지 않는다.
  const grab = n => fetch(`data/${n}.json`, { cache: 'no-cache' });
  const [meta, city, L, poi] = await Promise.all(
    ['meta', 'city', 'layers', 'poi'].map(n => grab(n).then(r => r.json())));
  // 지형은 없어도 돈다 — 404면 평지로 되돌아간다 (되돌리기 안전망)
  const terr = await grab('terrain').then(r => r.ok ? r.json() : null)
                                    .catch(() => null);
  Object.assign(D, { meta, city, L, poi, terrain: terr });

  const st = meta.style;
  ALPHA = st.alpha_deg * Math.PI / 180;
  PHI = st.phi_deg * Math.PI / 180;
  EAVE = st.eave;
  C = st.colors;
  PIX_ON = st.pixel_size || 3;
  if (st.band_min_px != null) BAND_MIN_PX = st.band_min_px;
  PIX = PIX_ON;
  checkGolden(meta.golden);
  if (terr) {
    TERR = terr; TEXAG = terr.exag ?? 1;
    if (terr.shade) GSHADE_K = terr.shade;          // 파이썬과 같은 상수를 쓴다
    if (terr.light) GLIGHT = terr.light;
    if (terr.gain != null) GSHADE_GAIN = terr.gain;
    if (terr.zband != null) GZBAND = terr.zband;
    if (terr.neutral != null) GNEUTRAL = terr.neutral;
    checkTerrainGolden(terr);
  }
  else console.warn('[pixel_city] terrain.json 없음 — 평지로 렌더한다');
  console.log(`[pixel_city] 팔레트 ${buildPalette()}색`);

  // 링 디코딩 + 컬링용 AABB(s=1 기준) 사전계산
  const nameOf = new Map(city.names);
  D.B = city.rings.map((r, i) => {
    const en = decRing(r);
    let u0 = 1e9, u1 = -1e9, v0 = 1e9, v1 = -1e9, ce = 0, cn = 0;
    const h = city.h[i] / Q;
    for (const p of en) { ce += p[0]; cn += p[1]; }
    const z = zAt(ce / en.length, cn / en.length);   // 기초 표고. expand와 같은 중심 계산
    for (const [e, n] of en) {
      const u = projU(e, n, 1);
      u0 = Math.min(u0, u); u1 = Math.max(u1, u);
      // AABB에 표고를 굽는다. 컬링 마진을 넓히는 쪽은 최대 줌에서 ~420 아트픽셀이
      // 필요해 컬링이 무력화된다 — 여기서 굽는 것이 정확하고 더 짧다
      v0 = Math.min(v0, projV(e, n, h + z, 1)); v1 = Math.max(v1, projV(e, n, z, 1));
    }
    const kind = city.kind[i];
    // 변주 축을 로드 시 굽는다 — iso2.variant()와 같은 규칙.
    // 값이 없으면(-1) 그대로 undefined/null로 두어 palette()가 오늘 색으로 폴백한다.
    const prp = city.prp ? city.prp[city.prpos[i]] : null;
    const str = city.str ? city.str[city.strct[i]] : null;
    return { en, h, z, kind, use: city.use[i], nm: nameOf.get(i) || '',
             // 층수는 이제 데이터에서 온다. 예전엔 h/층고로 역산했는데
             // (실측 6,991동 전부 일치) 층고 상수에 대한 숨은 결합이었다
             // 층수는 데이터에서 온다. 아래 역산은 city.fl이 없는 옛 데이터용 폴백이다
             // (높이가 실측이면 역산이 애초에 안 맞으므로 폴백은 근사일 뿐이다)
             fl: city.fl ? city.fl[i] : Math.max(1, Math.round(
                   h / (kind === 2 ? (st.palace_floor_h || 8.25)
                      : kind === 1 ? st.wood_floor_h : st.floor_h))),
             rg: prp && (st.colors.roof_g || {})[prp] ? prp : null,
             wm: kind ? woodUse(prp) : wallMat(str || ''),
             ab: ageBand(city.yr ? city.yr[i] : 0, st.age_break),
             u0, u1, v0, v1 };
  });
  for (const k of ['heri', 'park', 'temple', 'river']) D.L[k] = D.L[k].map(decRing);
  D.L.road = D.L.road.map(([w, r]) => [w, decRing(r)]).sort((a, b) => a[0] - b[0]);
  if (TERR) console.log(`[pixel_city] 지형 음영 셀 ${buildTerrainCells()}개 `
    + `(격자 ${(TERR.nx - 1) * (TERR.ny - 1)}칸 중 경사 있는 것만)`);

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
  // 팔레트 색은 '시각적으로 같은 색'으로 스냅돼야 한다. 인덱스 0만 보던 것을 전수로 바꿨다.
  // 자기 자신을 요구하지 않는 이유: nearest()가 채널당 5비트로 버킷팅하므로(>>3) 모든
  // 채널이 8 미만 차이인 색끼리는 원리상 구분되지 않고, 그건 육안으로도 같은 색이다.
  // 잡아야 하는 것은 '멀리 있는 색으로 스냅되는 것'이다 — 새 색을 추가할 때 그게 사고다.
  let dup = 0;
  for (let i = 0; i < PAL_RGB.length; i += 3) {
    const j = nearest(PAL_RGB[i], PAL_RGB[i + 1], PAL_RGB[i + 2]) * 3;
    const d = Math.hypot(PAL_RGB[i] - PAL_RGB[j], PAL_RGB[i + 1] - PAL_RGB[j + 1],
                         PAL_RGB[i + 2] - PAL_RGB[j + 2]);
    if (j !== i) dup++;
    console.assert(d < 14, '팔레트 색이 엉뚱한 색으로 스냅된다', i / 3,
                   [PAL_RGB[i], PAL_RGB[i + 1], PAL_RGB[i + 2]], '->',
                   [PAL_RGB[j], PAL_RGB[j + 1], PAL_RGB[j + 2]]);
  }
  // 참고: 근사 중복 2건은 지형 도입 전부터 있다 (문교사회용 처마 파생 ~ 한옥 벽,
  // 주거용 파생 ~ 공업용 파생). 채널당 4 이하 차이라 화면에서 구분되지 않는다.
  if (dup) console.log(`[pixel_city] 팔레트 근사 중복 ${dup}건 (5비트 버킷 공유, 무해)`);
  if (TERR) {
    for (const g of TERR.golden)
      console.assert(Math.abs(zAt(g.e, g.n) / TEXAG - g.z) < 1e-3, '지형 골든', g);
    console.assert(zAt(1e9, 1e9) === 0, '격자 밖은 0');
    // 마지막 격자점 클램프 — 빼면 메시 외곽이 0으로 주저앉는다
    const le = TERR.e0 + (TERR.nx - 1) * TERR.step, ln = TERR.n0 + (TERR.ny - 1) * TERR.step;
    console.assert(Math.abs(zAt(le, ln) - TEXAG / Q * TERR.z[TERR.nx * TERR.ny - 1]) < 1e-9,
                   '마지막 격자점 클램프');
    // drop 불변식: 표고는 지붕→지면 낙차를 오염시키지 않는다 (반올림 ±1 허용)
    const dz = sy(459, -1691, 0, zAt(459, -1691)) - sy(459, -1691, 100, zAt(459, -1691));
    console.assert(Math.abs(dz - (sy(0, 0, 0, 0) - sy(0, 0, 100, 0))) <= 1, 'drop 오염');
    console.assert(sy(459, -1691, 0) < sy(0, 0, 0, 0) - 10, '남산이 화면에서 솟는다');
    console.assert(TSHADE.length === 3 && TSHADE[0].length === GSHADE_K.length, '지형 음영 미등록');
    const nf = GSHADE_K[GNEUTRAL];
    console.assert((Array.isArray(nf) ? nf : [nf]).every(v => v === 1),
                   'neutral 칸의 배율이 1.0이 아니다 — 평지가 원래 색으로 안 남는다');
    console.assert(TCELL && TCELL.length % 4 === 0, '지형 셀 미계산');
  }
  // 계층 2 — 층 띠 게이트. 줌 0~2에서 켜지면 저줌 비용이 새는 것이고,
  // 줌 4에서 안 켜지면 기능이 죽은 것이다. 둘 다 조용히 지나가면 안 된다.
  {
    const zi0 = view.zi, probe = { h: 30, fl: 10, kind: 0 };
    view.zi = 0; console.assert(floorBands(probe) === 0, '줌0에서 띠가 켜졌다');
    view.zi = 2; console.assert(floorBands(probe) === 0, '줌2에서 띠가 켜졌다');
    view.zi = 3; console.assert(floorBands(probe) === 1, '줌3은 파라펫 1줄이어야 한다');
    view.zi = 4; console.assert(floorBands(probe) === 10, '줌4에서 층 띠가 안 켜졌다');
    console.assert(floorBands({ h: 6, fl: 2, kind: 0 }) === 1, '저층은 파라펫만');
    view.zi = zi0;
  }
  // 계층 1 — 색 변주
  {
    const sp = paletteSpread();
    console.assert(PAL_RGB.length / 3 <= 160, `팔레트 예산 초과 ${PAL_RGB.length / 3}`);
    console.assert(sp.cells >= 40, `색 변주가 데이터로 안 갈린다 (${sp.cells}종)`);
    console.assert(sp.topShare <= 0.15, `한 색이 건물의 ${(sp.topShare*100).toFixed(1)}%를 덮는다`);
    // ★ 되돌리기 동치 — 속성이 전부 결측이면 오늘과 같은 색이어야 한다
    const bare = { kind: 0, use: D.city.uses.indexOf('상업용'), rg: null, wm: null, ab: 1 };
    console.assert(palette(bare)[0] === rgb(C.use['상업용'][0]), '폴백이 오늘 색과 다르다');
    // 분류 함수가 iso2.py와 같은 규칙인지
    console.assert(wallMat('철근콘크리트구조') === '콘크리트' && wallMat('벽돌구조') === '조적'
                && wallMat('일반철골구조') === '기타' && wallMat('일반목구조') === null, 'wallMat');
    console.assert(woodUse('단독주택') === '주거' && woodUse('제2종근린생활시설') === '근생'
                && woodUse(null) === '기타', 'woodUse');
    console.assert(ageBand(0, [1966, 1989]) === 1 && ageBand(1950, [1966, 1989]) === 0
                && ageBand(2010, [1966, 1989]) === 2, 'ageBand');
  }
  console.log('[pixel_city] selfcheck ok');
  return true;
}
/* 오프스크린 영역의 고유색 수. 색 변주 작업의 before/after를 숫자로 비교하려고 둔다.
 * 화면 캔버스가 아니라 off를 읽는다 — 블릿·DPR 배율이 색을 섞지 않은 상태여야 한다. */
function countColors(x = 0, y = 0, w = OW, h = OH) {
  const d = octx.getImageData(x, y, w, h).data, seen = new Set();
  for (let i = 0; i < d.length; i += 4) seen.add((d[i] << 16) | (d[i + 1] << 8) | d[i + 2]);
  return seen.size;
}

/* 건물이 실제로 몇 가지 색으로 갈리는지. "8팔레트 문제"의 직접 지표다. */
function paletteSpread() {
  // 지붕만 세면 안 된다 — 한옥은 기와가 전부 같은 색이라 벽 변주가 안 잡힌다.
  // 건물을 실제로 구분하는 건 (지붕, 밝은벽, 어두운벽) 조합이다.
  const hist = new Map();
  for (const b of D.B) {
    const k = palette(b).slice(0, 3).map(c => Array.isArray(c) ? c.join(',') : c).join('|');
    hist.set(k, (hist.get(k) || 0) + 1);
  }
  const top = Math.max(...hist.values());
  return { cells: hist.size, top, topShare: +(top / D.B.length).toFixed(3) };
}

window.pixelCitySelfCheck = pixelCitySelfCheck;
// 디버그 훅 — 콘솔에서 좌표 변환과 판정을 직접 확인할 수 있다
window.pixelCity = { pick, sx, sy, zAt, palette, countColors, paletteSpread,
                     s: () => s(), view, get PIX() { return PIX; },
                     get OW() { return OW; }, get OH() { return OH; }, D };
