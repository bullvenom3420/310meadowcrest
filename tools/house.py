"""310 Meadowcrest - conceptual massing model.

All units are FEET.  Coordinate system:
  x : left -> right as seen from the street (0 = outer face of left brick wall)
  y : front -> rear  (0 = front of the covered-entry columns)
  z : up (0 = grade, first finished floor ~0.5)

Every dimension below was read from the plan set PDFs (dated 11-20-2025):
  sheet 1 front/rear elevations, sheet 3 first floor, sheet 4 second floor.
Things the drawings do not show (side elevations, exact roof intersections)
are inferred from the plan jogs and the 9:12 / 12:12 pitches noted on sheet 1.

This file has no dependencies.  geometry() returns a list of faces:
  (points[[x,y,z],...], material)   material in {'wall','roof','glass','void'}
"""

T = 0.5          # roof slab thickness (vertical, ft)
BASE = 10.6      # top of first-floor walls (10'-1" plate + floor offset)
EAVE = 10.4      # roof plane height at the eave edge
P9 = 0.75        # 9:12
P12 = 1.0        # 12:12

faces = []


def face(pts, mat):
    faces.append(([list(map(float, p)) for p in pts], mat))


# ---------------------------------------------------------------- primitives
def prism_x(x0, x1, poly_yz, mat='wall'):
    """Extrude a (y,z) polygon along x."""
    n = len(poly_yz)
    face([(x0, y, z) for y, z in poly_yz], mat)
    face([(x1, y, z) for y, z in poly_yz], mat)
    for i in range(n):
        (ya, za), (yb, zb) = poly_yz[i], poly_yz[(i + 1) % n]
        face([(x0, ya, za), (x1, ya, za), (x1, yb, zb), (x0, yb, zb)], mat)


def prism_y(y0, y1, poly_xz, mat='wall'):
    n = len(poly_xz)
    face([(x, y0, z) for x, z in poly_xz], mat)
    face([(x, y1, z) for x, z in poly_xz], mat)
    for i in range(n):
        (xa, za), (xb, zb) = poly_xz[i], poly_xz[(i + 1) % n]
        face([(xa, y0, za), (xa, y1, za), (xb, y1, zb), (xb, y0, zb)], mat)


def prism_z(z0, z1, poly_xy, mat='wall'):
    n = len(poly_xy)
    face([(x, y, z0) for x, y in poly_xy], mat)
    face([(x, y, z1) for x, y in poly_xy], mat)
    for i in range(n):
        (xa, ya), (xb, yb) = poly_xy[i], poly_xy[(i + 1) % n]
        face([(xa, ya, z0), (xb, yb, z0), (xb, yb, z1), (xa, ya, z1)], mat)


def slab(poly_xy, zfun, t=T, mat='roof'):
    """Roof slab: top surface on plane zfun(x,y), thickness t below it."""
    n = len(poly_xy)
    top = [(x, y, zfun(x, y)) for x, y in poly_xy]
    bot = [(x, y, zfun(x, y) - t) for x, y in poly_xy]
    face(top, mat)
    face(bot, mat)
    for i in range(n):
        j = (i + 1) % n
        face([bot[i], bot[j], top[j], top[i]], mat)


def profile(w0, w1, apex, apex_z, s0, s1, base=BASE, t=T, n=0):
    """Wall+gable cross-section under a two-slope roof.
    w0,w1 wall lines, apex position/height of the roof TOP surface, slopes.
    Returned polygon follows roof-underside (top - t) and is clipped at base."""
    def z(u):
        return apex_z - t - (s0 * (apex - u) if u <= apex else s1 * (u - apex))
    pts = []
    # left side
    za = z(w0)
    if za > base:
        pts += [(w0, base), (w0, za)]
    else:
        pts += [(apex - (apex_z - t - base) / s0, base)]
    if w0 < apex < w1:
        pts.append((apex, apex_z - t))
    zb = z(w1)
    if zb > base:
        pts += [(w1, zb), (w1, base)]
    else:
        pts += [(apex + (apex_z - t - base) / s1, base)]
    return pts


def side_gable(xw0, xw1, xs0, xs1, yfw, yrw, yfe, yre, ry, rz, s=P9, base=BASE,
               front_poly=None, rear_x=None, rear_poly=None):
    """Gable roof with ridge running left-right (gable ends face the sides)."""
    prism_x(xw0, xw1, profile(yfw, yrw, ry, rz, s, s, base))
    zf = lambda x, y: rz - s * (ry - y)
    zr = lambda x, y: rz - s * (y - ry)
    slab(front_poly or [(xs0, yfe), (xs1, yfe), (xs1, ry), (xs0, ry)], zf)
    r0, r1 = rear_x or (xs0, xs1)
    slab(rear_poly or [(r0, ry), (r1, ry), (r1, yre), (r0, yre)], zr)


def front_gable(xw0, xw1, xs0, xs1, y0, y1, ys0, ys1, rx, rz, s=P12, base=BASE):
    """Gable roof with ridge running front-back (gable faces the street/rear)."""
    prism_y(y0, y1, profile(xw0, xw1, rx, rz, s, s, base))
    slab([(xs0, ys0), (rx, ys0), (rx, ys1), (xs0, ys1)], lambda x, y: rz - s * (rx - x))
    slab([(rx, ys0), (xs1, ys0), (xs1, ys1), (rx, ys1)], lambda x, y: rz - s * (x - rx))


def arch_pts(x0, x1, zs, rise, n=10):
    """Points of a segmental arch from (x0,zs) over to (x1,zs)."""
    import math
    c = (x0 + x1) / 2
    hw = (x1 - x0) / 2
    if rise >= hw - 1e-6:          # semicircle
        r, cz = hw, zs
        a0 = 0.0
    else:
        r = (hw * hw + rise * rise) / (2 * rise)
        cz = zs + rise - r
        a0 = math.asin((zs - cz) / r)
    out = []
    for i in range(n + 1):
        a = a0 + (math.pi - 2 * a0) * i / n
        out.append((c + r * math.cos(a), cz + r * math.sin(a)))
    return out          # from right to left


def opening(axis, at, u0, u1, z0, z1, out, arch=0.0, mat='glass', d=0.06):
    """Window/door panel on a wall plane.
    axis 'y': wall plane y=at, panel spans x u0..u1 ; out=-1 faces street.
    axis 'x': wall plane x=at, spans y u0..u1."""
    if arch > 0:
        prof = [(u0, z0), (u1, z0)] + arch_pts(u0, u1, z1 - arch, arch)[0:]
        # arch_pts runs right->left starting at (u1, z1-arch)
    else:
        prof = [(u0, z0), (u1, z0), (u1, z1), (u0, z1)]
    c = at + out * d
    if axis == 'y':
        face([(u, c, z) for u, z in prof], mat)
    else:
        face([(c, u, z) for u, z in prof], mat)


# ---------------------------------------------------------------- the house
def build():
    faces.clear()

    # 1. FIRST FLOOR footprint (outer brick face, sheet 3) - walls to plate
    foot = [
        (0, 9.9), (2.2, 9.9), (2.2, 5.6), (11.2, 5.6), (11.2, 4.6), (22.9, 4.6),
        (22.9, 3.5), (31.1, 3.5), (31.1, 8.5), (40.6, 8.5), (40.6, 4.5), (54.0, 4.5),
        (54.0, 5.5), (63.5, 5.5), (63.5, 9.7), (65.83, 9.7), (65.83, 54.0),
        (47.5, 54.0), (47.5, 43.6), (42.4, 43.6), (42.4, 38.1), (25.0, 38.1),
        (25.0, 46.6), (23.1, 46.6), (23.1, 68.7), (0, 68.7),
    ]
    prism_z(0.0, BASE, foot)

    # 2. MAIN BLOCK - tall side-gable, ridge 34'-0" above grade (33'-6" overall
    #    above finished floor).  Front slope comes down to the 1st-floor eave,
    #    rear slope stops at the 2nd-floor rear wall (8'-1" plate).
    ry, rz = 35.07, 34.0
    front_poly = [(10.2, 3.6), (11.2, 3.6), (11.2, 4.65), (22.9, 4.65), (22.9, 3.6),
                  (55.0, 3.6), (55.0, ry), (10.2, ry)]
    side_gable(11.2, 54.0, 10.2, 55.0, 4.5, 52.4, 3.6, 53.4, ry, rz,
               front_poly=front_poly)

    # 3. WINGS - lower side gables (ridge ~29'-3"), set back to the plan jogs
    side_gable(2.2, 11.2, 1.2, 11.2, 5.6, 54.0, 4.6, 55.0, 29.8, EAVE + P9 * 25.2,
               rear_x=(2.2, 11.2))
    side_gable(54.0, 63.5, 54.0, 64.5, 5.5, 54.0, 4.5, 55.0, 29.75, EAVE + P9 * 25.25,
               rear_x=(54.0, 63.5))

    # 4. OUTER BAYS - lowest side gables (ridge ~27'-8"), the actual side walls
    side_gable(0.03, 2.2, -1.0, 2.2, 9.9, 54.0, 8.9, 55.0, 31.95, EAVE + P9 * 23.05,
               rear_poly=[(-1.0, 31.95), (2.2, 31.95), (2.2, 55.0), (0.0, 55.0),
                          (0.0, 46.6), (-1.0, 46.6)])
    side_gable(63.5, 65.80, 63.5, 66.83, 9.7, 54.0, 8.7, 55.0, 31.85, EAVE + P9 * 23.15)

    # 5. low roof over the primary bedroom behind the 2nd-floor rear wall
    slab([(47.2, 46.0), (54.0, 46.0), (54.0, 55.0), (47.2, 55.0)],
         lambda x, y: EAVE + P9 * (55.0 - y))

    # 6. GARAGE gable facing the rear, 12:12, ridge 25'-5"
    prism_y(46.6, 68.7, profile(0.0, 23.1, 11.55, 25.4, P12, P12))
    slab([(-0.9, 34.0), (11.55, 34.0), (11.55, 69.6), (-0.9, 69.6)],
         lambda x, y: 25.4 - (11.55 - x))
    slab([(11.55, 34.0), (24.0, 34.0), (24.0, 69.6), (11.55, 69.6)],
         lambda x, y: 25.4 - (x - 11.55))

    # 7. FRONT: Bed #2 bay gable (12:12, flared corners)
    prism_z(BASE, 11.7, [(11.18, 4.6), (22.92, 4.6), (22.92, 13.5), (11.18, 13.5)])
    front_gable(12.0, 22.0, 11.5, 22.5, 4.6, 13.5, 4.1, 13.5, 17.0, 17.2, base=11.7)

    # 8. FRONT: two-story stair gable (12:12, ridge 27'-1")
    front_gable(22.88, 32.42, 21.3, 34.1, 3.48, 26.5, 2.9, 26.5, 27.7, 27.1, base=0.0)

    # 9. FRONT: two-story foyer with 3:12 roof behind the entry
    prism_x(32.6, 39.3, [(8.5, 0.0), (8.5, 21.9 + 0.25 * 0.9 - T),
                          (25.0, 21.9 + 0.25 * 17.4 - T), (25.0, 0.0)])
    slab([(32.1, 7.6), (39.8, 7.6), (39.8, 25.0), (32.1, 25.0)],
         lambda x, y: 21.9 + 0.25 * (y - 7.6))

    # 10. FRONT: stone covered-entry gable (12:12, ridge 16'-6")
    front_gable(31.08, 40.62, 29.6, 42.1, 0.2, 8.5, -0.4, 8.5, 35.85, 16.5, base=0.0)

    # 11. FRONT: Media / Bed #6 dormer (12:12, ridge 25'-6")
    front_gable(44.1, 50.7, 42.6, 52.2, 7.2, 24.0, 6.7, 24.0, 47.4, 25.5, base=11.0)

    # 12. REAR: centre gable over Bed #4/#5 (12:12, ridge 28'-6")
    front_gable(21.6, 34.7, 20.4, 35.8, 42.0, 52.6, 42.0, 53.0, 28.1, 28.5, base=12.1)

    # 13. REAR: outdoor-living beam under the 2nd floor overhang
    prism_z(9.8, 12.1, [(23.1, 52.4), (47.5, 52.4), (47.5, 54.0), (23.1, 54.0)])

    # ------------------------------------------------------------ openings
    F, R = -1, 1
    # front (street side)
    opening('y', 5.6, 5.3, 8.1, 6.5, 8.5, F)                    # 2-1620 fxd
    opening('y', 4.6, 14.7, 19.6, 2.4, 11.2, F, arch=1.4)       # bed 2 arched
    opening('y', 3.5, 26.6, 28.9, 12.0, 19.0, F)                # stair tall
    opening('y', 0.2, 33.9, 37.8, 0.0, 9.4, F, arch=1.95, mat='void')  # entry arch
    opening('y', 8.5, 34.5, 37.2, 17.1, 19.5, F)                # foyer 2-1626
    opening('y', 7.2, 45.9, 48.7, 15.2, 21.2, F, arch=1.4)      # dormer arched
    opening('y', 4.5, 44.9, 49.8, 2.6, 8.6, F)                  # study 2-2660
    opening('y', 5.5, 57.4, 60.1, 6.5, 8.5, F)                  # 2-1620 fxd
    # rear
    for a, b in ((51.5, 54.4), (55.1, 58.1), (58.8, 61.7)):     # primary 3060s
        opening('y', 54.0, a, b, 2.8, 8.7, R)
    opening('y', 43.6, 43.6, 47.0, 3.5, 8.7, R)                 # 3050 fxd
    opening('y', 38.1, 25.5, 41.5, 0.5, 9.0, R)                 # 16080 slider
    opening('y', 68.7, 2.5, 20.5, 0.2, 8.6, R)                  # 18080 garage door
    opening('y', 68.7, 10.7, 12.3, 16.4, 20.1, R)               # gable vent
    opening('y', 52.6, 22.7, 27.3, 15.1, 20.3, R)               # 4050 SH
    opening('y', 52.6, 29.1, 33.6, 15.1, 20.3, R)               # 4050 SH
    opening('x', 23.1, 55.8, 58.7, 0.2, 8.2, R)                 # garage 3080 door
    # left side
    opening('x', 0.0, 38.5, 41.5, 2.5, 8.0, F)                  # 3050 SH laundry
    opening('x', 0.0, 19.4, 22.9, 4.0, 8.0, F)                  # 3650 SH
    opening('x', 0.0, 12.3, 16.3, 6.0, 8.0, F)                  # 4020 fxd
    opening('x', 0.0, 27.6, 31.6, 14.6, 19.6, F)                # 2nd flr 4050
    # right side
    opening('x', 65.83, 26.4, 30.4, 4.0, 8.0, R)                # 4040 fxd
    opening('x', 65.83, 21.8, 23.8, 4.0, 8.0, R)                # 2040 SH
    opening('x', 65.83, 30.2, 34.2, 14.6, 19.6, R)              # 2nd flr 4050
    return list(faces)


def geometry():
    return build()


if __name__ == '__main__':
    g = geometry()
    print(len(g), 'faces')
