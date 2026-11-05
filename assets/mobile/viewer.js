/* 310 Meadowcrest - tiny self-contained WebGL viewer (no libraries, works offline).
   Usage: MeadowcrestViewer(containerElement, window.MEADOWCREST_MODEL, {onFirstTouch}) */
(function () {
  function b64(s) { const bin = atob(s); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return new Float32Array(u.buffer); }
  function mat4persp(fov, asp, n, f) { const t = 1 / Math.tan(fov / 2); return [t / asp, 0, 0, 0, 0, t, 0, 0, 0, 0, (f + n) / (n - f), -1, 0, 0, 2 * f * n / (n - f), 0]; }
  function mul(a, b) { const o = new Array(16); for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) { let s = 0; for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k]; o[c * 4 + r] = s; } return o; }
  function lookAt(e, t, u) {
    let zx = e[0] - t[0], zy = e[1] - t[1], zz = e[2] - t[2]; let l = Math.hypot(zx, zy, zz); zx /= l; zy /= l; zz /= l;
    let xx = u[1] * zz - u[2] * zy, xy = u[2] * zx - u[0] * zz, xz = u[0] * zy - u[1] * zx; l = Math.hypot(xx, xy, xz); xx /= l; xy /= l; xz /= l;
    const yx = zy * xz - zz * xy, yy = zz * xx - zx * xz, yz = zx * xy - zy * xx;
    return [xx, yx, zx, 0, xy, yy, zy, 0, xz, yz, zz, 0, -(xx * e[0] + xy * e[1] + xz * e[2]), -(yx * e[0] + yy * e[1] + yz * e[2]), -(zx * e[0] + zy * e[1] + zz * e[2]), 1];
  }
  function rotY(a) { const c = Math.cos(a), s = Math.sin(a); return [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1]; }
  function prog(gl, vs, fs) {
    const p = gl.createProgram();
    for (const [type, src] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]]) {
      const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      gl.attachShader(p, s);
    }
    gl.linkProgram(p); if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    return p;
  }
  function buf(gl, data) { const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW); return b; }

  window.MeadowcrestViewer = function (host, model, opts) {
    opts = opts || {};
    const canvas = document.createElement('canvas');
    canvas.style.cssText = 'display:block;width:100%;height:100%;touch-action:pan-y;cursor:grab';
    host.appendChild(canvas);
    const gl = canvas.getContext('webgl', { antialias: true, alpha: true, premultipliedAlpha: true });
    if (!gl) { canvas.remove(); return null; }

    const pos = b64(model.pos), nrm = b64(model.nrm), col = b64(model.col), lin = b64(model.lines);
    const meshP = prog(gl,
      'attribute vec3 p;attribute vec3 n;attribute vec3 c;uniform mat4 mvp;uniform mat4 rot;varying vec3 v;' +
      'void main(){vec3 N=normalize((rot*vec4(n,0.)).xyz);vec3 L=normalize(vec3(-0.45,0.75,0.55));' +
      'float d=abs(dot(N,L));float sky=0.62+0.18*N.y;vec3 rim=vec3(0.73,0.71,1.0)*0.10*max(0.,dot(N,normalize(vec3(0.6,0.3,-0.7))));' +
      'v=c*(sky+0.42*d)+rim;gl_Position=mvp*vec4(p,1.);}',
      'precision mediump float;varying vec3 v;void main(){gl_FragColor=vec4(min(v,vec3(1.)),1.);}');
    const lineP = prog(gl,
      'attribute vec3 p;uniform mat4 mvp;void main(){gl_Position=mvp*vec4(p,1.);gl_Position.z-=0.0004*gl_Position.w;}',
      'precision mediump float;void main(){gl_FragColor=vec4(0.17,0.165,0.19,1.);}');
    const shP = prog(gl,
      'attribute vec2 p;uniform mat4 mvp;varying vec2 q;void main(){q=p;gl_Position=mvp*vec4(p.x*17.,0.02,p.y*15.,1.);}',
      'precision mediump float;varying vec2 q;void main(){float r=length(q);gl_FragColor=vec4(0.,0.,0.,0.5*smoothstep(1.,0.15,r));}');
    const bP = buf(gl, pos), bN = buf(gl, nrm), bC = buf(gl, col), bL = buf(gl, lin);
    const bS = buf(gl, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]));
    const nTri = pos.length / 3, nLin = lin.length / 3;

    /* ---- pets: animated sprites (dog in the Bed 2 window, cat on the roof) ---- */
    const spriteP = prog(gl,
      'attribute vec3 p;attribute vec2 t;uniform mat4 mvp;varying vec2 v;void main(){v=t;gl_Position=mvp*vec4(p,1.);}',
      'precision mediump float;uniform sampler2D tex;varying vec2 v;void main(){vec4 c=texture2D(tex,v);if(c.a<0.02)discard;gl_FragColor=c;}');
    const FT = 0.3048, W3 = (x, y, z) => [(x - 32.9) * FT, z * FT, -(y - 34.3) * FT];
    const bUV = buf(gl, new Float32Array([0, 1, 1, 1, 0, 0, 1, 0]));
    const pets = { ready: false, dog: null, cat: null };
    function quadBuf(x0, x1, z0, z1, y) { const a = W3(x0, y, z0), b = W3(x1, y, z0), c = W3(x0, y, z1), d = W3(x1, y, z1); return buf(gl, new Float32Array([...a, ...b, ...c, ...d])); }
    function makeTex(cv) { const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, cv); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE); return t; }
    function frames(markup, vb, pxW, pxH, tailClass, ox, oy, angles) {
      return Promise.all(angles.map(a => new Promise(ok => {
        const m = markup.replace('<g class="' + tailClass + '">', '<g class="' + tailClass + '" transform="rotate(' + a.toFixed(2) + ' ' + ox + ' ' + oy + ')">');
        const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="' + vb + '" width="' + pxW + '" height="' + pxH + '">' + m + '</svg>';
        const im = new Image(); im.onload = () => { const cv = document.createElement('canvas'); cv.width = pxW; cv.height = pxH; cv.getContext('2d').drawImage(im, 0, 0, pxW, pxH); ok(makeTex(cv)); };
        im.onerror = () => ok(null); im.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
      })));
    }
    if (opts.petsMarkup) {
      const src = opts.petsMarkup;
      const dogM = src.slice(src.indexOf('<g class="pet-dog"'), src.indexOf('<!-- cat lying')).replace(/ clip-path="[^"]*"/, '');
      const catM = src.slice(src.indexOf('<g class="pet-cat"'));
      const dogAngles = Array.from({ length: 12 }, (_, i) => 1 + 21 * Math.sin(i / 12 * Math.PI * 2));
      const catKeys = [[0, 0], [.4, -24], [.55, -6], [.7, -18], [1, 0]];
      const catAngles = Array.from({ length: 16 }, (_, i) => { const t = i / 16; let k = 0; while (catKeys[k + 1][0] < t) k++; const [t0, a0] = catKeys[k], [t1, a1] = catKeys[k + 1]; const u = (t - t0) / (t1 - t0); return a0 + (a1 - a0) * (0.5 - 0.5 * Math.cos(Math.PI * u)); });
      Promise.all([frames(dogM, '525 650 72 119', 288, 476, 'dog-tail', 575, 760, dogAngles), frames(catM, '978 598 86 64', 344, 256, 'cat-tail', 1036, 637, catAngles)]).then(([d, c]) => {
        if (d.some(x => !x) || c.some(x => !x)) return;
        pets.dog = { tex: d, buf: quadBuf(14.77, 19.52, 2.49, 10.56, 4.44), period: 840 };
        pets.cat = { tex: c, w: 50.14 - 44.63, z0: 9.62 + 0.5, z1: 13.96 + 0.5, cx: 47.39, y: 4.8, period: 2600 };
        pets.ready = true; kick();
      });
    }
    function drawPets(vp, R) {
      if (!pets.ready) return;
      const now = performance.now();
      gl.useProgram(spriteP); gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      const tl = gl.getAttribLocation(spriteP, 't'); gl.bindBuffer(gl.ARRAY_BUFFER, bUV); gl.enableVertexAttribArray(tl); gl.vertexAttribPointer(tl, 2, gl.FLOAT, false, 0, 0);
      // dog: fixed in the window plane, turns with the house
      const d = pets.dog; gl.uniformMatrix4fv(gl.getUniformLocation(spriteP, 'mvp'), false, mul(vp, R));
      gl.bindTexture(gl.TEXTURE_2D, d.tex[Math.floor(now / d.period * d.tex.length) % d.tex.length]);
      let pl = attr(spriteP, 'p', d.buf, 3); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      // cat: stays on its roof spot but always turns to face the viewer
      const c = pets.cat, cxm = W3(c.cx, c.y, 0), hw = c.w * FT / 2;
      const T = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, cxm[0], 0, cxm[2], 1];
      const quad = new Float32Array([-hw, c.z0 * FT, 0, hw, c.z0 * FT, 0, -hw, c.z1 * FT, 0, hw, c.z1 * FT, 0]);
      if (!c.buf) c.buf = buf(gl, quad);
      gl.uniformMatrix4fv(gl.getUniformLocation(spriteP, 'mvp'), false, mul(mul(vp, R), mul(T, rotY(-angle))));
      gl.bindTexture(gl.TEXTURE_2D, c.tex[Math.floor(now / c.period * c.tex.length) % c.tex.length]);
      pl = attr(spriteP, 'p', c.buf, 3); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      gl.disableVertexAttribArray(pl); gl.disableVertexAttribArray(tl); gl.disable(gl.BLEND);
    }

    let angle = 0, vel = 0, auto = true, dragging = false, lastX = 0, lastT = 0, visible = true, raf = 0;
    /* zoom: k = 1 shows the whole house; smaller k moves the camera closer. ox/oy/oz shift the aim point.
       A tap or pinch aims at the spot on the house under your finger (found by casting a ray into the
       house's bounding box) and the camera moves straight toward it, so that spot stays under your finger. */
    let zoom = 1, zoomTo = 1, ox = 0, oy = 0, oz = 0, oxTo = 0, oyTo = 0, ozTo = 0, fovY = 30 * Math.PI / 180, aspNow = 1;
    const ZMIN = 0.28, ZMAX = 1.15, TY = 3.6, DY = 5.9, DZ = 46, DL = Math.hypot(DY, DZ), UY = DZ / DL, UZ = -DY / DL;
    const BOX = [[-10.3, 0, -10.8], [10.3, 10.4, 10.6]];               // the house's extents in model space
    function viewMat() { const k = zoom, tx = ox, ty = TY + oy, tz = oz; return lookAt([tx, ty + DY * k, tz + DZ * k], [tx, ty, tz], [0, 1, 0]); }
    const halfH = k => DL * k * Math.tan(fovY / 2);
    function clampPan(k) {
      if (k >= 1 - 1e-3) { oxTo = 0; oyTo = 0; ozTo = 0; return; }
      const hh = halfH(k), hw = hh * aspNow;
      // keep the aim point on the house: within its width and depth, no lower than the doorsills, no higher than the ridge
      const mx = Math.max(0, 12.2 - 0.5 * hw); oxTo = Math.max(-mx, Math.min(mx, oxTo));
      oyTo = Math.max(0.6 - TY, Math.min(Math.max(0.6 - TY, 10.4 - TY - 0.5 * hh), oyTo));
      ozTo = Math.max(-11, Math.min(11, ozTo));
    }
    function hitPoint(nx, ny, k) {                                     // world point under canvas position nx, ny
      const t = Math.tan(fovY / 2), T = [oxTo, TY + oyTo, ozTo], E = [T[0], T[1] + DY * k, T[2] + DZ * k];
      const d = [nx * t * aspNow, -DY / DL + ny * t * UY, -DZ / DL + ny * t * UZ];   // forward + right*x + up*y
      const c = Math.cos(angle), sn = Math.sin(angle);
      const toM = v => [c * v[0] - sn * v[2], v[1], sn * v[0] + c * v[2]];      // world -> model (undo the turn)
      const e = toM(E), dm = toM(d); let t0 = 0, t1 = Infinity;
      for (let i = 0; i < 3; i++) {
        if (Math.abs(dm[i]) < 1e-9) { if (e[i] < BOX[0][i] || e[i] > BOX[1][i]) { t1 = -1; break; } continue; }
        let a = (BOX[0][i] - e[i]) / dm[i], b = (BOX[1][i] - e[i]) / dm[i]; if (a > b) [a, b] = [b, a];
        t0 = Math.max(t0, a); t1 = Math.min(t1, b);
      }
      const tt = t0 <= t1 && t0 > 0 ? t0 : k * DL;                     // missed the house: use the aim-point depth
      return [E[0] + tt * d[0], E[1] + tt * d[1], E[2] + tt * d[2]];
    }
    function zoomAt(z, nx, ny) {                                       // nx, ny: -1..1 across the canvas
      const k0 = zoomTo, k1 = Math.max(ZMIN, Math.min(ZMAX, z)), f = 1 - k1 / k0, P = hitPoint(nx, ny, k0);
      oxTo += (P[0] - oxTo) * f; oyTo += (P[1] - TY - oyTo) * f; ozTo += (P[2] - ozTo) * f;
      zoomTo = k1; clampPan(k1); updBtns(); kick();
    }
    function size() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.max(1, Math.round(host.clientWidth * dpr)), h = Math.max(1, Math.round(host.clientHeight * dpr));
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
      gl.viewport(0, 0, w, h);
      return w / h;
    }
    function attr(p, name, b, n) { const l = gl.getAttribLocation(p, name); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.enableVertexAttribArray(l); gl.vertexAttribPointer(l, n, gl.FLOAT, false, 0, 0); return l; }
    function draw() {
      const asp = size();
      fovY = (asp > 1.6 ? 21 : 30) * Math.PI / 180; aspNow = asp;   // tighter framing on wide desktop viewers
      const proj = mat4persp(fovY, asp, 0.5, 300);
      const R = rotY(angle);
      zoom += (zoomTo - zoom) * 0.2; ox += (oxTo - ox) * 0.2; oy += (oyTo - oy) * 0.2; oz += (ozTo - oz) * 0.2;
      if (Math.abs(zoomTo - zoom) < 1e-4 && Math.abs(oxTo - ox) < 1e-3 && Math.abs(oyTo - oy) < 1e-3 && Math.abs(ozTo - oz) < 1e-3) { zoom = zoomTo; ox = oxTo; oy = oyTo; oz = ozTo; }
      const vp = mul(proj, viewMat()), mvp = mul(vp, R);
      gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      // ground shadow (rotates with the house)
      gl.disable(gl.DEPTH_TEST); gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      gl.useProgram(shP); gl.uniformMatrix4fv(gl.getUniformLocation(shP, 'mvp'), false, mvp);
      const ls = attr(shP, 'p', bS, 2); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); gl.disableVertexAttribArray(ls);
      gl.disable(gl.BLEND); gl.enable(gl.DEPTH_TEST);
      // house
      gl.useProgram(meshP);
      gl.uniformMatrix4fv(gl.getUniformLocation(meshP, 'mvp'), false, mvp);
      gl.uniformMatrix4fv(gl.getUniformLocation(meshP, 'rot'), false, R);
      const a1 = attr(meshP, 'p', bP, 3), a2 = attr(meshP, 'n', bN, 3), a3 = attr(meshP, 'c', bC, 3);
      gl.drawArrays(gl.TRIANGLES, 0, nTri);
      gl.disableVertexAttribArray(a2); gl.disableVertexAttribArray(a3); gl.disableVertexAttribArray(a1);
      // outlines
      gl.useProgram(lineP); gl.uniformMatrix4fv(gl.getUniformLocation(lineP, 'mvp'), false, mvp);
      const a4 = attr(lineP, 'p', bL, 3); gl.drawArrays(gl.LINES, 0, nLin); gl.disableVertexAttribArray(a4);
      drawPets(vp, R);
    }
    function tick() {
      raf = 0;
      if (!dragging) { if (auto) angle += 0.0017; else { angle += vel; vel *= 0.94; if (Math.abs(vel) < 1e-5) vel = 0; } }
      draw();
      if (visible && (auto || dragging || vel || pets.ready || zoom !== zoomTo || ox !== oxTo || oy !== oyTo || oz !== ozTo)) raf = requestAnimationFrame(tick);
    }
    function kick() { if (!raf && visible) raf = requestAnimationFrame(tick); }

    const ptrs = new Map(); let pinch0 = 0, zoom0 = 1, down = null, pinched = false;
    function updBtns() { if (!zoomBtns) return; for (const [b, off] of [[zoomBtns.inBtn, zoomTo <= ZMIN + 1e-3], [zoomBtns.outBtn, zoomTo >= 1 - 1e-3]]) { b.disabled = off; b.style.opacity = off ? '.35' : '1'; b.style.cursor = off ? 'default' : 'pointer'; } }
    const ndc = (x, y) => { const r = canvas.getBoundingClientRect(); return [((x - r.left) / r.width) * 2 - 1, 1 - ((y - r.top) / r.height) * 2]; };
    const firstTouch = () => { if (auto) { auto = false; if (opts.onFirstTouch) opts.onFirstTouch(); } };
    canvas.addEventListener('pointerdown', e => {
      ptrs.set(e.pointerId, [e.clientX, e.clientY]);
      try { canvas.setPointerCapture(e.pointerId); } catch (_) { }
      firstTouch();
      if (ptrs.size === 2) { const [p, q] = [...ptrs.values()]; pinch0 = Math.hypot(p[0] - q[0], p[1] - q[1]) || 1; zoom0 = zoomTo; dragging = false; pinched = true; down = null; }
      else { dragging = true; lastX = e.clientX; lastT = performance.now(); vel = 0; canvas.style.cursor = 'grabbing'; down = [e.clientX, e.clientY, lastT]; pinched = false; }
      kick();
    });
    canvas.addEventListener('pointermove', e => {
      if (!ptrs.has(e.pointerId)) return;
      ptrs.set(e.pointerId, [e.clientX, e.clientY]);
      if (ptrs.size === 2) { const [p, q] = [...ptrs.values()], [nx, ny] = ndc((p[0] + q[0]) / 2, (p[1] + q[1]) / 2);
        zoomAt(zoom0 * pinch0 / (Math.hypot(p[0] - q[0], p[1] - q[1]) || 1), nx, ny); return; }
      if (!dragging) return;
      const now = performance.now(), dx = e.clientX - lastX;
      const d = dx / Math.max(200, host.clientWidth) * Math.PI * 1.6;
      angle += d; vel = d / Math.max(1, (now - lastT) / 16.7) ; lastX = e.clientX; lastT = now;
    });
    const end = e => {
      // a quick tap or click (no drag, no pinch) zooms in on that spot
      if (e.type === 'pointerup' && down && !pinched && ptrs.size === 1 && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 8 && performance.now() - down[2] < 400) {
        const [nx, ny] = ndc(e.clientX, e.clientY); vel = 0; zoomAt(zoomTo * 0.6, nx, ny); }
      ptrs.delete(e.pointerId); down = null;
      if (ptrs.size === 1) { const [p] = [...ptrs.values()]; lastX = p[0]; lastT = performance.now(); dragging = true; } else { dragging = false; canvas.style.cursor = 'grab'; }
      kick();
    };
    canvas.addEventListener('pointerup', end); canvas.addEventListener('pointercancel', end);
    // trackpad pinch (and ctrl + wheel) zooms at the pointer; a plain wheel still scrolls the page
    canvas.addEventListener('wheel', e => { if (!e.ctrlKey) return; e.preventDefault(); firstTouch(); const [nx, ny] = ndc(e.clientX, e.clientY); zoomAt(zoomTo * Math.exp(e.deltaY * 0.01), nx, ny); }, { passive: false });
    // zoom buttons
    let zoomBtns = null;
    (function () {
      const bar = document.createElement('div');
      bar.style.cssText = 'position:absolute;right:max(14px,env(safe-area-inset-right,0px));bottom:14px;display:flex;flex-direction:column;gap:8px;z-index:2';
      const mk = (label, txt, dz) => { const b = document.createElement('button'); b.type = 'button'; b.setAttribute('aria-label', label); b.textContent = txt;
        b.style.cssText = 'width:44px;height:44px;border-radius:50%;border:1px solid rgba(245,239,232,.28);background:rgba(19,18,27,.55);color:#f5efe8;font:300 22px/1 Geist,system-ui,sans-serif;cursor:pointer;-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)';
        b.addEventListener('click', () => { firstTouch(); zoomAt(dz > 1 && zoomTo * dz >= 0.97 ? 1 : zoomTo * dz, 0, 0); }); bar.appendChild(b); return b; };
      const inBtn = mk('Zoom in', '+', 0.65), outBtn = mk('Zoom out', '−', 1 / 0.65);
      if (getComputedStyle(host).position === 'static') host.style.position = 'relative';
      host.appendChild(bar); zoomBtns = { inBtn, outBtn }; outBtn.disabled = true; outBtn.style.opacity = '.35';
    })();
    new IntersectionObserver(([en]) => { visible = en.isIntersecting; if (visible) kick(); }).observe(host);
    addEventListener('resize', () => { draw(); });
    draw(); kick();
    return { canvas };
  };
})();
