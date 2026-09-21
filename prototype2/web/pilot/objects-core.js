// Pure fixed-camera compositing. Depth is encoded camera distance, not roof height.
export function decodeDepth(data) {
  const result = new Uint32Array(data.length / 4);
  for (let i = 0; i < result.length; i++) result[i] = data[i * 4] * 65536 + data[i * 4 + 1] * 256 + data[i * 4 + 2];
  return result;
}

export function compose(size, ground, groundDepth, objects, {mode = 'ai', hidden = new Set(), lights = new Set()} = {}) {
  const pixels = new Uint8ClampedArray(ground);
  const depth = new Uint32Array(groundDepth);
  const ids = new Uint32Array(size * size);
  for (const object of objects) {
    if (hidden.has(object.id)) continue;
    const source = mode === 'source' ? object.basePixels : mode === 'previous' && object.previousPixels ? object.previousPixels : object.spritePixels;
    const [width, height] = object.size, [left, top] = object.xy;
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
      const from = y * width + x, px = left + x, py = top + y;
      if (px < 0 || py < 0 || px >= size || py >= size || source[from * 4 + 3] < 128) continue;
      const to = py * size + px, z = object.depthValues[from];
      if (z < depth[to] || (z === depth[to] && ids[to] && object.id > ids[to])) continue;
      depth[to] = z; ids[to] = object.id;
      const glow = lights.has(object.id) && mode === 'ai' ? object.lightPixels[from * 4 + 3] / 255 : 0;
      for (let c = 0; c < 3; c++) pixels[to * 4 + c] = source[from * 4 + c] * (1 - glow) + object.lightPixels[from * 4 + c] * glow;
      pixels[to * 4 + 3] = 255;
    }
  }
  return {pixels, depth, ids};
}

export function projectPoint(e, n, h, camera) {
  const a = camera.alpha_deg * Math.PI / 180, p = camera.phi_deg * Math.PI / 180;
  return [(e * Math.cos(a) - n * Math.sin(a)) / camera.scale + camera.cx,
    -((e * Math.sin(a) + n * Math.cos(a)) * Math.sin(p) + h * Math.cos(p)) / camera.scale + camera.cy];
}

export function cameraDepth(e, n, h, camera, encoding) {
  const a = camera.alpha_deg * Math.PI / 180, p = camera.phi_deg * Math.PI / 180;
  const distance = -(e * Math.sin(a) + n * Math.cos(a)) * Math.cos(p) + h * Math.sin(p);
  return Math.round((distance + encoding.offset) * encoding.scale);
}

export function containsPoint(point, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [x, y] = point, [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
