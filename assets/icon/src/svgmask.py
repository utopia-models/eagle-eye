"""Vector export of a concept's favicon: the same drawing calls as sand.Mask (fill, stroke, disk), written as SVG.

  python svgmask.py <concept-id> <out.svg>

v=255 draws gold, v=0 draws ink, in order, on an ink rounded tile (or gold, for a gold-tile concept).
A stroke becomes one outline polygon (offset along the normals) with round caps, so tapers survive.
"""
import sys
import numpy as np
import concepts as C


class SvgMask:
    def __init__(self, S=1000):
        self.S = S; self.k = 1.0; self.els = []; self.pupil = None

    def _col(self, v, fg, bg):
        return fg if v else bg

    def fill(self, pts, v=255):
        pts = np.asarray(pts, float)
        if len(pts) > 60:
            pts = pts[::4]   # 1000-unit canvas: every 4th sample is still sub-pixel at 512 px
        d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"
        self.els.append(("path", d, v))

    def disk(self, cx, cy, r, v=255):
        self.els.append(("circle", (cx, cy, r), v))

    def stroke(self, pts, w, taper=None, v=255):
        pts = np.asarray(pts, float)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        keep = np.concatenate([[True], seg > 1e-6]); pts = pts[keep]
        n = len(pts)
        ws = np.full(n, w, float) if taper is None else np.linspace(taper[0], taper[1], n)
        t = np.gradient(pts, axis=0); t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
        nrm = np.stack([-t[:, 1], t[:, 0]], -1)
        left = pts + nrm * ws[:, None] / 2; right = pts - nrm * ws[:, None] / 2
        self.fill(np.concatenate([left, right[::-1]]), v)
        self.disk(*pts[0], ws[0] / 2, v); self.disk(*pts[-1], ws[-1] / 2, v)

    def svg(self, gold_tile=False, size=32):
        gold, ink = "#e2b860", "#0a0a09"
        fg, bg = (ink, gold) if gold_tile else (gold, ink)
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" width="{size}" height="{size}">',
               f'<rect width="1000" height="1000" rx="215" fill="{bg}"/>']
        for kind, a, v in self.els:
            c = fg if v else bg
            if kind == "path":
                out.append(f'<path d="{a}" fill="{c}"/>')
            else:
                out.append(f'<circle cx="{a[0]:.1f}" cy="{a[1]:.1f}" r="{a[2]:.1f}" fill="{c}"/>')
        out.append("</svg>")
        return "\n".join(out) + "\n"


def export(cid):
    c = C.ALL[cid]
    import icon
    real = C.Mask
    C.Mask = icon.Mask = SvgMask
    try:
        m = c.fav()
    finally:
        C.Mask = icon.Mask = real
    return m.svg(gold_tile=(c.tile == "gold"))


if __name__ == "__main__":
    open(sys.argv[2], "w").write(export(sys.argv[1]))
    print("ok", sys.argv[2])
