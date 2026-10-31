"""Clay + outline turntable renderer (numpy only).

python3 render.py OUTDIR [nframes] [width] [height] [only_frame...]
"""
import sys, os, math
import numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, os.path.dirname(__file__))
import house

# ------------------------------------------------------------------ geometry
def triangulate(pts):
    """Ear clipping on a planar 3D polygon. returns index triples."""
    P = np.array(pts, float)
    n = len(P)
    nrm = np.zeros(3)
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        nrm += np.cross(a, b)
    ax = np.argmax(np.abs(nrm))
    keep = [i for i in range(3) if i != ax]
    Q = P[:, keep]
    area = 0.5 * sum(Q[i, 0] * Q[(i + 1) % n, 1] - Q[(i + 1) % n, 0] * Q[i, 1] for i in range(n))
    idx = list(range(n))
    if area < 0:
        idx.reverse()
    tris = []
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        m = len(idx)
        for k in range(m):
            i0, i1, i2 = idx[(k - 1) % m], idx[k], idx[(k + 1) % m]
            a, b, c = Q[i0], Q[i1], Q[i2]
            if cross(a, b, c) <= 1e-12:
                continue
            ok = True
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                p = Q[j]
                if cross(a, b, p) >= -1e-12 and cross(b, c, p) >= -1e-12 and cross(c, a, p) >= -1e-12:
                    ok = False
                    break
            if ok:
                tris.append((i0, i1, i2))
                idx.pop(k)
                break
        else:
            # degenerate - fan the rest
            for k in range(1, len(idx) - 1):
                tris.append((idx[0], idx[k], idx[k + 1]))
            idx = idx[:3]
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris, nrm / (np.linalg.norm(nrm) + 1e-12)


MATS = {'wall': 1.00, 'roof': 0.935, 'glass': 0.86, 'void': 0.55}

def build_mesh():
    tri, fid, nrm, alb = [], [], [], []
    for k, (pts, mat) in enumerate(house.geometry()):
        ts, n = triangulate(pts)
        for t in ts:
            tri.append([pts[t[0]], pts[t[1]], pts[t[2]]])
            fid.append(k + 1)
            nrm.append(n)
            alb.append(MATS[mat])
    return (np.array(tri, float), np.array(fid, np.int32),
            np.array(nrm, float), np.array(alb, float))


# ------------------------------------------------------------------ raster
def raster(sx, sy, sd, W, H, ids, closer_is_larger=True):
    """sx,sy: (N,3) pixel coords; sd: (N,3) depth value interpolated linearly.
    returns depth buffer & id buffer (index into triangles, -1 = empty)."""
    db = np.full((H, W), -np.inf if closer_is_larger else np.inf)
    ib = np.full((H, W), -1, np.int64)
    for t in range(len(sx)):
        x0, x1, x2 = sx[t]; y0, y1, y2 = sy[t]
        xmin = max(int(math.floor(min(x0, x1, x2))), 0)
        xmax = min(int(math.ceil(max(x0, x1, x2))), W - 1)
        ymin = max(int(math.floor(min(y0, y1, y2))), 0)
        ymax = min(int(math.ceil(max(y0, y1, y2))), H - 1)
        if xmin > xmax or ymin > ymax:
            continue
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-9:
            continue
        xs = np.arange(xmin, xmax + 1) + 0.5
        ys = np.arange(ymin, ymax + 1) + 0.5
        X, Y = np.meshgrid(xs, ys)
        l0 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / den
        l1 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / den
        l2 = 1 - l0 - l1
        m = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        if not m.any():
            continue
        d = l0 * sd[t, 0] + l1 * sd[t, 1] + l2 * sd[t, 2]
        sub = db[ymin:ymax + 1, xmin:xmax + 1]
        if closer_is_larger:
            m &= d > sub
        else:
            m &= d < sub
        sub[m] = d[m]
        ib[ymin:ymax + 1, xmin:xmax + 1][m] = ids[t]
    return db, ib


# ------------------------------------------------------------------ camera
CENTER = np.array([32.9, 36.0, 11.0])

def camera(theta_deg, elev_deg, dist):
    th = math.radians(theta_deg); el = math.radians(elev_deg)
    d = np.array([math.sin(th) * math.cos(el), -math.cos(th) * math.cos(el), math.sin(el)])
    eye = CENTER + d * dist
    f = CENTER - eye; f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return eye, f, r, u


def render(theta, W=1600, H=1000, ss=2, elev=11.0, dist=172.0, fov=27.0,
           mesh=None, line_rgb=(58, 57, 54), wall_rgb=(246, 244, 239)):
    tri, fid, nrm, alb = mesh
    Ws, Hs = W * ss, H * ss
    eye, f, r, u = camera(theta, elev, dist)
    foc = (Hs / 2) / math.tan(math.radians(fov) / 2)
    cx, cy = Ws / 2, Hs * 0.53

    rel = tri - eye
    zc = rel @ f
    sx = cx + foc * (rel @ r) / zc
    sy = cy - foc * (rel @ u) / zc
    invz = 1.0 / zc
    db, ib = raster(sx, sy, invz, Ws, Hs, np.arange(len(tri)), True)

    hit = ib >= 0
    # world position of every pixel
    px = (np.arange(Ws) + 0.5 - cx) / foc
    py = (cy - (np.arange(Hs) + 0.5)) / foc
    PX, PY = np.meshgrid(px, py)
    ray = f[None, None] + PX[..., None] * r[None, None] + PY[..., None] * u[None, None]
    zview = np.where(hit, 1.0 / np.where(hit, db, 1.0), 0)
    wpos = eye + ray * zview[..., None]

    # light: fixed relative to camera (key from upper front-left)
    la = math.radians(theta - 40.0)
    L = np.array([math.sin(la) * math.cos(math.radians(62)),
                  -math.cos(la) * math.cos(math.radians(62)),
                  math.sin(math.radians(62))])
    L /= np.linalg.norm(L)

    # ---- shadow map (orthographic along -L)
    lf = -L
    lr = np.cross(lf, [0, 0, 1.0]); lr /= np.linalg.norm(lr)
    lu = np.cross(lr, lf)
    SM = 2600; ext = 75.0
    def lproj(p):
        q = p - CENTER
        return (SM / 2 + (q @ lr) / ext * SM / 2, SM / 2 - (q @ lu) / ext * SM / 2, q @ lf)
    lx, ly, ld = lproj(tri)
    sdb, _ = raster(lx, ly, ld, SM, SM, np.arange(len(tri)), False)

    def shadow_at(points, bias=0.25, soft=2):
        qx, qy, qd = lproj(points)
        acc = np.zeros(qx.shape)
        cnt = 0
        for ox in range(-soft, soft + 1):
            for oy in range(-soft, soft + 1):
                ix = np.clip((qx + ox * 2.0).astype(int), 0, SM - 1)
                iy = np.clip((qy + oy * 2.0).astype(int), 0, SM - 1)
                acc += (qd - bias <= sdb[iy, ix])
                cnt += 1
        return acc / cnt

    # ---- shading
    N = nrm[np.where(hit, ib, 0)]
    facing = np.sign(np.sum(N * (-ray), -1, keepdims=True))
    N = N * np.where(facing == 0, 1, facing)
    ndl = np.clip(N @ L, 0, None)
    sh = np.ones((Hs, Ws))
    hp = wpos[hit]
    sh[hit] = shadow_at(hp, soft=3)
    a = alb[np.where(hit, ib, 0)]
    amb = 0.70 + 0.10 * N[..., 2] + 0.06 * (N @ (-f))
    lum = a * (amb + 0.30 * ndl * (0.35 + 0.65 * sh))
    lum = np.clip(lum, 0, 1.08)
    base = np.array(wall_rgb, float) / 255.0
    col = np.clip(lum[..., None] * base[None, None] / 1.0, 0, 1)

    # ---- ground (transparent) : shadow + soft contact occlusion
    gt = np.where(ray[..., 2] < -1e-6, -eye[2] / np.minimum(ray[..., 2], -1e-6), 0)
    gp = eye + ray * gt[..., None]
    gm = (~hit) & (ray[..., 2] < 0)
    galpha = np.zeros((Hs, Ws))
    if gm.any():
        gpts = gp[gm]
        gsh = shadow_at(gpts, bias=0.3, soft=3)
        dxy = np.hypot(gpts[:, 0] - CENTER[0], gpts[:, 1] - CENTER[1])
        fade = np.clip(1 - (dxy - 45) / 40, 0, 1)
        galpha[gm] = (1 - gsh) * 0.20 * fade
    # contact occlusion: blurred silhouette of the footprint seen from camera
    foot = np.zeros((Hs, Ws), np.uint8)
    foot[hit & (wpos[..., 2] < 1.2)] = 255
    fimg = Image.fromarray(foot).filter(ImageFilter.GaussianBlur(10 * ss))
    contact = np.asarray(fimg, float) / 255.0
    galpha = np.maximum(galpha, (~hit) * contact * 0.22)

    # ---- outlines from face-id discontinuities
    face_buf = np.where(hit, fid[np.where(hit, ib, 0)], 0)
    e = np.zeros((Hs, Ws), bool)
    e[:, 1:] |= face_buf[:, 1:] != face_buf[:, :-1]
    e[1:, :] |= face_buf[1:, :] != face_buf[:-1, :]
    # thicken: 1 px at ss=2 -> ~1px final; silhouettes a bit heavier
    sil = np.zeros_like(e)
    bg = ~hit
    sil[:, 1:] |= bg[:, 1:] != bg[:, :-1]
    sil[1:, :] |= bg[1:, :] != bg[:-1, :]
    e2 = e.copy()
    e2[:-1, :] |= e[1:, :]
    e2[:, :-1] |= e[:, 1:]
    s2 = sil.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            s2 |= np.roll(np.roll(sil, dy, 0), dx, 1)
    lines = e2 | s2

    # ---- compose RGBA
    lc = np.array(line_rgb, float) / 255.0
    rgb = np.where(hit[..., None], col, lc[None, None] * 0 + 0)
    alpha = np.where(hit, 1.0, galpha)
    shadow_rgb = np.array([0.24, 0.23, 0.21])
    rgb = np.where(hit[..., None], rgb, shadow_rgb[None, None])
    la_ = 0.88
    rgb = np.where(lines[..., None], lc * la_ + rgb * (1 - la_) * hit[..., None] + lc * (1 - la_) * (~hit[..., None]), rgb)
    alpha = np.where(lines, np.maximum(alpha, la_), alpha)

    img = np.dstack([rgb * alpha[..., None], alpha])           # premultiplied
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), 'RGBA')
    im = im.resize((W, H), Image.LANCZOS)
    arr = np.asarray(im).astype(float)
    a8 = arr[..., 3:4] / 255.0
    arr[..., :3] = np.where(a8 > 0, arr[..., :3] / np.maximum(a8, 1e-6), 0)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA')


if __name__ == '__main__':
    out = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    W = int(sys.argv[3]) if len(sys.argv) > 3 else 1600
    H = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
    only = [int(v) for v in sys.argv[5:]]
    os.makedirs(out, exist_ok=True)
    mesh = build_mesh()
    print('triangles', len(mesh[0]), flush=True)
    for i in (only or range(n)):
        th = 360.0 * i / n
        im = render(th, W, H, mesh=mesh)
        im.save(os.path.join(out, 'frame-%03d.png' % i))
        print('frame', i, flush=True)
