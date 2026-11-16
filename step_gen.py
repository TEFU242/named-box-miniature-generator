#!/usr/bin/env python3
"""RoofLamp STEP 產生器（build123d / OpenCascade，精確 B-rep，不是網格）。
用法：echo '<json>' | python step_gen.py out.step
json: {"kind":"lamp","p":{...}} 或 {"kind":"brick","p":{...}}
座標：Z 向上，+X 右，前牆朝 −Y（對應網頁 3D 的 +Z 前牆）。
"""
import sys, json, math
from build123d import (Box, Cylinder, Pos, Axis, Align, Vector, Wire, Face, Solid,
                       export_step, Compound)

MIN = Align.MIN


def dedupe(pts):
    out = []
    for q in pts:
        if not out or math.hypot(q[0] - out[-1][0], q[1] - out[-1][1]) > 1e-6:
            out.append(q)
    if len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-6:
        out.pop()
    return out


def prism_y(pts, length):
    """XZ 輪廓沿 Y 擠出，Y 置中。"""
    pts = dedupe(pts)
    face = Face(Wire.make_polygon([Vector(x, 0, z) for x, z in pts], close=True))
    return Solid.extrude(face, Vector(0, length, 0)).translate((0, -length / 2, 0))


def prism_x(pts, length):
    """YZ 輪廓沿 X 擠出，X 置中。"""
    pts = dedupe(pts)
    face = Face(Wire.make_polygon([Vector(0, y, z) for y, z in pts], close=True))
    return Solid.extrude(face, Vector(length, 0, 0)).translate((-length / 2, 0, 0))


def outer_solid(roof, W, D, H, R, L):
    if roof == 'flat':
        return prism_y([(-W / 2, 0), (W / 2, 0), (W / 2, H), (-W / 2, H)], D)
    if roof == 'shed':
        return prism_y([(-W / 2, 0), (W / 2, 0), (W / 2, H), (-W / 2, H + R)], D)
    if roof == 'gable':
        return prism_y([(-W / 2, 0), (W / 2, 0), (W / 2, H), (0, H + R), (-W / 2, H)], D)
    a = prism_y([(-W / 2, 0), (W / 2, 0), (W / 2, H), (0, H + R), (-W / 2, H)], D)
    b = prism_x([(-D / 2, 0), (D / 2, 0), (D / 2, H), (L / 2, H + R), (-L / 2, H + R), (-D / 2, H)], W)
    return a & b


def win_layout(L, t, n, ww0):
    if not n:
        return []
    span = L - 2 * t
    ww = min(ww0, (span - (n + 1) * 3) / n)
    if ww < 2:
        return []
    gap = (span - n * ww) / (n + 1)
    return [(-span / 2 + gap * (i + 1) + ww * i + ww / 2, ww) for i in range(n)]


SQ3 = math.sqrt(3)


def lamp_grid(n, m, span, span_s, d_req, shape, layout):
    vext = 2 / SQ3 if shape == 'hex' else 1
    hon = layout == 'honey'
    gap = 1.6
    pts = []
    if hon:
        h = 0.5 if m > 1 else 0
        rk = 1 if shape == 'square' else SQ3 / 2
        k = (m - 1) * rk
        d = min(d_req, (span - 2 - (n - 1 + h) * gap) / (n + h), (span_s - 2 - k * gap) / (k + vext))
        pa = d + gap
        pb = pa * rk
        for j in range(m):
            for i in range(n):
                pts.append(((i - (n - 1) / 2) * pa + (pa / 2 if j % 2 else 0) - (pa / 4 if m > 1 else 0),
                            (j - (m - 1) / 2) * pb))
    else:
        d = min(d_req, (span_s - 2) / vext, span - 2,
                span / n - 3 if n > 1 else 1e9, (span_s / m - 3) / vext if m > 1 else 1e9)
        for j in range(m):
            for i in range(n):
                pts.append((0 if n == 1 else -span / 2 + span * (i + 0.5) / n,
                            0 if m == 1 else -span_s / 2 + span_s * (j + 0.5) / m))
    return d, pts


def lamp_list(p, t):
    """回傳 [(x, z, d, shape, rot)]，座標與網頁 3D 相同（z 為網頁 Z）。"""
    if not p.get('lampOn', True) or p['lampD'] <= 0:
        return []
    n = max(1, int(round(p.get('lampN', 1))))
    m = max(1, int(round(p.get('lampRows', 1))))
    along_x = p['width'] >= p['depth']
    Lw, S = (p['width'], p['depth']) if along_x else (p['depth'], p['width'])
    shape = p.get('lampShape', 'circle')
    layout = p.get('lampLayout', 'grid')
    d, pts = lamp_grid(n, m, Lw - 2 * t, S - 2 * t, p['lampD'], shape, layout)
    if d <= 1:
        return []
    ax = max(0, (p['width'] - 2 * t - d) / 2)
    az = max(0, (p['depth'] - 2 * t - d) / 2)
    b = {'center': (0, 0), 'front': (0, .6 * az), 'back': (0, -.6 * az),
         'left': (-.6 * ax, 0), 'right': (.6 * ax, 0)}.get(p.get('lampPos', 'center'), (p.get('lampX', 0), p.get('lampZ', 0)))
    single = layout != 'honey' or (n == 1 and m == 1)
    out = []
    for a, c in pts:
        if single:
            if n == 1:
                a = b[0] if along_x else b[1]
            if m == 1:
                c = b[1] if along_x else b[0]
        out.append((a, c, d, shape, 0) if along_x else (c, a, d, shape, 90))
    return out


def lamp_cutter(x, z, d, shape, rot, h, zc):
    """通孔刀具：中心 (x, -z, zc)，高度 h。"""
    if shape == 'square':
        return Pos(x, -z, zc) * Box(d, d, h)
    if shape == 'hex':
        R = d / SQ3
        off = 0 if rot else math.pi / 2  # 尖角朝向行方向（rot=0 時沿 Y）
        pts = [Vector(R * math.cos(off + k * math.pi / 3), R * math.sin(off + k * math.pi / 3), 0) for k in range(6)]
        face = Face(Wire.make_polygon(pts, close=True))
        return Solid.extrude(face, Vector(0, 0, h)).translate((x, -z, zc - h / 2))
    return Pos(x, -z, zc) * Cylinder(d / 2, h)


def make_lamp(p):
    w, d, H, t = p['width'], p['depth'], p['wallH'], p['wall']
    if p.get('plateMode'):  # 牆高 < 3mm：平板
        plate = Box(w, d, t, align=(Align.CENTER, Align.CENTER, MIN))
        for x, z, dia, shp, rot in lamp_list(p, t):
            plate = plate - lamp_cutter(x, z, dia, shp, rot, t * 3, t / 2)
        return plate
    roof = p['roof']
    R = 0 if roof == 'flat' else p['rise']
    swap = w > d
    W, D = (d, w) if swap else (w, d)
    run = W if roof == 'shed' else W / 2
    sl = R / run if run else 0
    v = t * math.sqrt(1 + sl * sl)
    L = D if roof == 'gable' else max(0, (D - W) * p['ridge'] / 100)

    outer = outer_solid(roof, W, D, H, R, L)
    big = Box(W - 2 * t, D - 2 * t, H + R + 40, align=(Align.CENTER, Align.CENTER, MIN)).translate((0, 0, -20))
    inner = outer.translate((0, 0, -v)) & big
    shell = outer - inner
    if swap:
        shell = shell.rotate(Axis.Z, 90)

    n_rows = max(1, int(round(p.get('winRows', 1))))
    gap = p.get('winGap', 4)
    sill = min(p['winSill'], max(0, H - 4))
    wh = max(1.5, min(p['winH'], (H - sill - 1.5 - (n_rows - 1) * gap) / n_rows))
    rows = []
    for i in range(n_rows):
        y0 = sill + i * (wh + gap)
        y1 = y0 + wh
        if y1 > H - 1.5 + 1e-6:
            break
        rows.append((-2 if (i == 0 and sill <= 0.01) else y0, y1))
    walls = [('nFront', w, 'x', -1), ('nBack', w, 'x', 1), ('nLeft', d, 'y', -1), ('nRight', d, 'y', 1)]
    for key, Lw, axis, sgn in walls:
        for c, ww in win_layout(Lw, t, int(p.get(key, 0)), p['winW']):
            for z0, z1 in rows:
                zc, zh = (z0 + z1) / 2, z1 - z0
                if axis == 'x':
                    cut = Pos(c, sgn * d / 2, zc) * Box(ww, t * 4, zh)
                else:
                    cut = Pos(sgn * w / 2, c, zc) * Box(t * 4, ww, zh)
                shell = shell - cut

    top = H + R
    for x, z, dia, shp, rot in lamp_list(p, t):
        shell = shell - lamp_cutter(x, z, dia, shp, rot, top * 3, top / 2)
    return shell


def rnd(i, j):
    s = math.sin(i * 12.9898 + j * 78.233) * 43758.5453
    return s - math.floor(s)


def make_brick(p):
    pw, ph, relief, base = p['pw'], p['ph'], p['relief'], p['pbase']
    L, Hb, m = 18.0, 5.4, 1.0
    solid = Box(pw, ph, base, align=(MIN, MIN, MIN))
    rows = int(math.ceil(ph / (Hb + m)))
    for r in range(rows):
        off = (r % 2) * (L + m) / 2
        col = -1
        x = -off
        while x < pw:
            col += 1
            x0, x1 = max(0, x), min(pw, x + L)
            y0, y1 = r * (Hb + m), min(ph, r * (Hb + m) + Hb)
            if x1 - x0 >= 1.0 and y1 - y0 >= 1.0:
                h = relief * (0.85 + 0.15 * rnd(col, r))
                b = Box(x1 - x0, y1 - y0, h, align=(MIN, MIN, MIN)).translate((x0, y0, base))
                try:
                    cm = min(0.3, h * 0.45, (x1 - x0) * 0.2, (y1 - y0) * 0.2)
                    b = b.chamfer(cm, None, b.faces().sort_by(Axis.Z)[-1].edges())
                except Exception:
                    pass
                solid = solid + b
            x += L + m
    return solid


def main():
    out = sys.argv[1]
    req = json.load(sys.stdin)
    kind, p = req['kind'], req['p']
    part = make_lamp(p) if kind == 'lamp' else make_brick(p)
    export_step(part, out)


if __name__ == '__main__':
    main()
