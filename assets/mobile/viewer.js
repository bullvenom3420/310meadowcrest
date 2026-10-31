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

    let angle = 0, vel = 0, auto = true, dragging = false, lastX = 0, lastT = 0, visible = true, raf = 0;
    const view = lookAt([0, 9.5, 46], [0, 3.6, 0], [0, 1, 0]);
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
      const proj = mat4persp((asp > 1.6 ? 21 : 30) * Math.PI / 180, asp, 1, 300);  // tighter framing on wide desktop viewers
      const R = rotY(angle);
      const vp = mul(proj, view), mvp = mul(vp, R);
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
    }
    function tick() {
      raf = 0;
      if (!dragging) { if (auto) angle += 0.002975; else { angle += vel; vel *= 0.94; if (Math.abs(vel) < 1e-5) vel = 0; } }
      draw();
      if (visible && (auto || dragging || vel)) raf = requestAnimationFrame(tick);
    }
    function kick() { if (!raf && visible) raf = requestAnimationFrame(tick); }

    canvas.addEventListener('pointerdown', e => {
      dragging = true; lastX = e.clientX; lastT = performance.now(); vel = 0; canvas.style.cursor = 'grabbing';
      if (auto) { auto = false; if (opts.onFirstTouch) opts.onFirstTouch(); }
      try { canvas.setPointerCapture(e.pointerId); } catch (_) { }
      kick();
    });
    canvas.addEventListener('pointermove', e => {
      if (!dragging) return;
      const now = performance.now(), dx = e.clientX - lastX;
      const d = dx / Math.max(200, host.clientWidth) * Math.PI * 1.6;
      angle += d; vel = d / Math.max(1, (now - lastT) / 16.7) ; lastX = e.clientX; lastT = now;
    });
    const end = () => { dragging = false; canvas.style.cursor = 'grab'; kick(); };
    canvas.addEventListener('pointerup', end); canvas.addEventListener('pointercancel', end);
    new IntersectionObserver(([en]) => { visible = en.isIntersecting; if (visible) kick(); }).observe(host);
    addEventListener('resize', () => { draw(); });
    draw(); kick();
    return { canvas };
  };
})();
