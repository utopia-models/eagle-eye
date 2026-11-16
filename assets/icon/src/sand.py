"""Eagle Eye icon: the live.utopiamodels.ai sand material, ported from live.js's grain shader to numpy.

Grain = round soft point, alpha pow(1-r,1.6); colour mix(GOLD1,GOLD2,seed), a pearl sheen (blue-violet) mixed in,
one grain in five a pearl glint; additive blending (SRC_ALPHA, ONE) on ink. The pupil is the molten sun disk:
grains on a swirl, brighter toward the rim. Geometry = a mask (white = sand), drawn by each candidate.
"""
import math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

INK = np.array([10, 10, 9]) / 255.0
GOLD1 = np.array([212, 169, 78]) / 255.0
GOLD2 = np.array([240, 210, 138]) / 255.0
GOLD3 = np.array([255, 244, 214]) / 255.0
EXPOSURE = 1.6
DEEP = np.array([120, 78, 22]) / 255.0
LIGHT = (0.32, 0.22)
SPARK = 0.12
SAT = 1.35


# ---------------- geometry helpers (all in a 1000-unit square, y down) ----------------
def cubic(p0, p1, p2, p3, n=200):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = map(np.array, (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def path(*segs):
    """segs: list of (p0,p1,p2,p3) cubics or (p0,p1) lines; returns Nx2 polyline."""
    pts = []
    for s in segs:
        if len(s) == 4:
            pts.append(cubic(*s))
        else:
            pts.append(np.linspace(np.array(s[0]), np.array(s[1]), 60))
    return np.concatenate(pts)


class Mask:
    """A supersampled mask canvas. Units are 0..1000; pixels = S."""

    def __init__(self, S=4000):
        self.S = S
        self.k = S / 1000.0
        self.im = Image.new("L", (S, S), 0)
        self.d = ImageDraw.Draw(self.im)
        self.pupil = None  # (cx, cy, r) in units

    def _p(self, pts):
        return [(float(x) * self.k, float(y) * self.k) for x, y in pts]

    def fill(self, pts, v=255):
        self.d.polygon(self._p(pts), fill=v)

    def stroke(self, pts, w, taper=None, v=255):
        """round-capped stroke of width w (units); taper=(w0,w1) tapers along the path."""
        pts = np.asarray(pts)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        L = np.concatenate([[0], np.cumsum(seg)])
        total = L[-1]
        n = max(2, int(total * self.k / 2))
        ts = np.linspace(0, total, n)
        xs = np.interp(ts, L, pts[:, 0]); ys = np.interp(ts, L, pts[:, 1])
        for i, (x, y) in enumerate(zip(xs, ys)):
            ww = w if taper is None else taper[0] + (taper[1] - taper[0]) * (i / (n - 1))
            r = ww / 2 * self.k
            self.d.ellipse([x * self.k - r, y * self.k - r, x * self.k + r, y * self.k + r], fill=v)

    def disk(self, cx, cy, r, v=255):
        k = self.k
        self.d.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k], fill=v)

    def array(self):
        return np.asarray(self.im, dtype=np.float32) / 255.0


# ---------------- the sand renderer ----------------
def render(mask: Mask, out_px=1024, density=1.0, seed=7, bloom=0.9, scatter=0.05, bg=True, glow_bg=0.0, grain_scale=1.0):
    """Returns float RGB (out_px^2) on ink (bg=True) or (rgb_premult, alpha) on transparent (bg=False)."""
    rng = np.random.default_rng(seed)
    SS = 2  # supersample the splat buffer
    W = out_px * SS
    m = mask.array()
    # downsample the mask to the splat grid for sampling probabilities
    mm = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((W, W), Image.LANCZOS), dtype=np.float32) / 255.0
    # grain field: a dense core along each stroke (48 px legibility) thinning to scattered grains at the edges and
    # a few loose grains drifting just outside (the live mark's open, airy edge)
    inner = ndimage.distance_transform_edt(mm > 0.5) / (SS * out_px / 1024)       # depth into the stroke, icon px
    core = np.clip(inner / 14.0, 0, 1) ** 0.6
    pmap = mm * (0.6 + 0.4 * core)
    halo = ndimage.gaussian_filter(mm, 3.5 * SS * out_px / 1024) * (1 - mm)
    area = pmap.sum()
    N = int(area * 0.056 * density)
    Nh = int(N * scatter)
    idx = np.concatenate([rng.choice(pmap.size, size=N, p=pmap.ravel() / pmap.sum()),
                          rng.choice(halo.size, size=Nh, p=halo.ravel() / halo.sum())]) if Nh else rng.choice(pmap.size, size=N, p=pmap.ravel() / pmap.sum())
    N = idx.size
    gy, gx = np.divmod(idx, W)
    x = gx + rng.random(N); y = gy + rng.random(N)
    sd = rng.random(N)          # vSeed
    sz = rng.random(N)          # aS.y -> size
    ph = rng.random(N)

    # brightness per grain: most grains mid gold, a tail of dim amber, ~7% sparkles (the live site's glints)
    B = 0.62 + 0.62 * rng.random(N) ** 1.5
    spark = rng.random(N) < SPARK
    B = np.where(spark, 1.9 + 1.0 * rng.random(N), B)
    # one light, the live site's head light: from the upper left, warm; plus a lift on the silhouette's rim
    ux = x / W; uy = y / W
    light = 0.78 + 0.42 * np.clip(1.15 - 0.9 * np.hypot(ux - LIGHT[0], uy - LIGHT[1]), 0, 1)
    edge = ndimage.gaussian_filter(mm, 2.5 * SS * out_px / 1024)
    e = edge[np.clip(y.astype(int), 0, W - 1), np.clip(x.astype(int), 0, W - 1)]
    rim = 0.30 * np.clip((1 - e) * 2.0, 0, 1)
    B = B * light + rim
    if mask.pupil is not None:  # the molten sun disk: a swirl still-frame, brighter toward its rim
        cx, cy, r = [v * W / 1000.0 for v in mask.pupil]
        dx = x - cx; dy = y - cy; rr = np.hypot(dx, dy) / r
        inp = rr < 1.04
        ang = np.arctan2(dy, dx) + 0.9 * (1 - np.clip(rr, 0, 1)) ** 1.5
        x = np.where(inp, cx + rr * r * np.cos(ang), x); y = np.where(inp, cy + rr * r * np.sin(ang), y)
        swirl = 0.5 + 0.5 * np.sin(ang * 3 + rr * 9)
        swirl = 0.5 + 0.5 * np.sin(ang * 2 + rr * 11)
        B = np.where(inp, B * (1.38 + 0.62 * np.clip((rr - 0.4) / 0.6, 0, 1) ** 1.3) * (0.88 + 0.24 * swirl), B)
    # colour ramp by brightness: deep amber -> GOLD1 -> GOLD2 -> GOLD3
    stops = np.array([0.35, 0.85, 1.6, 2.5])
    cols = np.stack([DEEP, GOLD1, GOLD2, GOLD3])
    col = np.stack([np.interp(B, stops, cols[:, c]) for c in range(3)], -1)
    # pearl: one grain in five carries the live shader's blue-violet glint (subtle so gold leads at 48 px)
    t = 4.2
    pm = 0.5 + 0.5 * np.sin(t * 0.31 + sd * 9.0)
    pearl = np.array([0.72, 0.84, 1.0])[None] * (1 - pm[:, None]) + np.array([0.88, 0.80, 1.0])[None] * pm[:, None]
    glint = (np.mod(sd * 7.13, 1.0) >= 0.8) & (B > 0.9)
    col = np.where(glint[:, None], col * 0.35 + pearl * 0.65 * np.clip(B, 0, 1.8)[:, None], col)
    alpha = B
    # splat: grain radius in splat px (point size 1..2.6 css px at the live site; scaled to the icon)
    rad = (1.1 + 1.7 * sz) * SS * grain_scale * (out_px / 1024) * np.where(B > 1.9, 1.4, 1.0)
    acc = np.zeros((W, W, 3), np.float32)
    # bucket by integer radius for vectorized stamping
    for R in np.unique(np.ceil(rad).astype(int)):
        sel = np.ceil(rad).astype(int) == R
        if not sel.any():
            continue
        oy, ox = np.mgrid[-R:R + 1, -R:R + 1]
        for dyo, dxo in zip(oy.ravel(), ox.ravel()):
            px = np.floor(x[sel]).astype(int) + dxo; py = np.floor(y[sel]).astype(int) + dyo
            d = np.hypot(px + 0.5 - x[sel], py + 0.5 - y[sel]) / rad[sel]
            w = np.clip(1 - d, 0, None) ** 1.6 * alpha[sel] * 0.85
            ok = (px >= 0) & (px < W) & (py >= 0) & (py < W) & (w > 0)
            for c in range(3):
                np.add.at(acc[:, :, c], (py[ok], px[ok]), (col[sel][ok, c] * w[ok]).astype(np.float32))
    # tone: hue-preserving shoulder (scale by the max channel so dense sand stays gold, never white)
    def shoulder(img, k=1.0):
        mx = img.max(-1, keepdims=True)
        return img * (1 - np.exp(-mx * k)) / np.maximum(mx, 1e-6)
    lit = shoulder(acc * EXPOSURE, 1.0)
    if bloom:  # the warm glow the additive sand throws, tinted amber
        b1 = np.stack([ndimage.gaussian_filter(lit[:, :, c], 10 * SS * out_px / 1024) for c in range(3)], -1)
        b2 = np.stack([ndimage.gaussian_filter(lit[:, :, c], 60 * SS * out_px / 1024) for c in range(3)], -1)
        lit = lit + bloom * 0.35 * b1 * np.array([1.0, 0.78, 0.40]) + bloom * 0.11 * b2 * np.array([1.0, 0.70, 0.30])
    lit = lit.reshape(out_px, SS, out_px, SS, 3).mean(axis=(1, 3))
    lit = shoulder(lit, 1.05) * 1.08
    lum = lit.mean(-1, keepdims=True)
    lit = np.clip(lum + (lit - lum) * SAT, 0, None)
    if bg:
        base = np.broadcast_to(INK, lit.shape).copy()
        if glow_bg:
            yy, xx = np.mgrid[0:out_px, 0:out_px] / out_px
            g = np.exp(-((xx - 0.5) ** 2 + (yy - 0.5) ** 2) / 0.09) * glow_bg
            base = base + g[..., None] * np.array([0.10, 0.075, 0.035])
        return np.clip(base + lit * (1 - base), 0, 1)
    a = np.clip(lit.max(axis=-1) * 1.25, 0, 1)
    return lit, a


def save_rgb(arr, path):
    Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(path)
