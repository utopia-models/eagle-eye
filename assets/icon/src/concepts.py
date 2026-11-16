"""Eagle Eye icon concepts A-F. Each concept is a geometry (a Mask drawn in 1000 units, centred on 500,500)
plus how it is lit (the live.utopiamodels.ai sand, or flat gold) and its small-size favicon mask.

build.py takes a concept id:  python build.py <out-dir> <id>   (ids: watch wadjet-gold horus iris agents aten wadjet)
"""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from sand import Mask, path, render, INK, GOLD1, GOLD2, GOLD3
import icon

GOLD_FLAT = (226, 184, 96)
INK8 = tuple(int(round(c * 255)) for c in INK)


def T(pts, s, cx=500, cy=500):
    return [(cx + x * s, cy + y * s) for x, y in pts]


def arc_pts(cx, cy, r, a0, a1, n=240):
    a = np.linspace(a0, a1, n)
    return np.stack([cx + r * np.cos(a), cy + r * np.sin(a)], -1)


def lens(cx, cy, half_w, half_h, n=200):
    """pointed almond (vesica): the intersection of two circles; sharp corners at (+-half_w, 0)"""
    # circle through (+-half_w,0) and (0,-half_h): centre (0, d), radius R
    R = (half_w ** 2 + half_h ** 2) / (2 * half_h); d = R - half_h
    a = math.asin(half_w / R)
    top = np.stack([cx + R * np.sin(np.linspace(-a, a, n)), cy + d - R * np.cos(np.linspace(-a, a, n))], -1)
    bot = np.stack([cx + R * np.sin(np.linspace(a, -a, n)), cy - d + R * np.cos(np.linspace(a, -a, n))], -1)
    return np.concatenate([top, bot])


def almond(cx, cy, w, h, n=120):
    """soft almond: two cubics (the live dashboard's lid shape)"""
    up = path(((cx - w, cy), (cx - w * .45, cy - h * 1.32), (cx + w * .45, cy - h * 1.32), (cx + w, cy)))
    lo = path(((cx + w, cy), (cx + w * .45, cy + h * 1.32), (cx - w * .45, cy + h * 1.32), (cx - w, cy)))
    return up, lo


# ------------------------------------------------------------------ concepts
class Concept:
    id = ""; letter = ""; name = ""; symbol = ""; psych = ""
    kind = "sand"          # sand | flat
    tile = "ink"           # ink | gold   (gold = ink glyph cut out of a gold-sand field)
    S0 = 1.0               # master scale
    density = 1.0
    bloom = 0.9
    plate = False          # beaten gold under the sand, so the glyph reads solid at 48 px

    def glyph(self, m: Mask, s, cx=500, cy=500, v=255):
        raise NotImplementedError

    def fav(self) -> Mask:
        m = Mask(); self.glyph(m, self.S0 * 1.18); return m


class Watch(Concept):
    id, letter, name = "watch", "A", "The Watch"
    symbol = "The live Eagle Eye itself: the iris is the lane rings, so the icon is the product's own eye."
    psych = "Familiarity: the icon matches the screen you open, so recognition costs nothing; the round iris reads calm."
    S0 = 1.0

    def glyph(self, m, s, cx=500, cy=500, v=255):
        k = s
        up, lo = almond(cx, cy, 395 * k, 215 * k)
        m.stroke(up, 30 * k, v=v); m.stroke(lo, 30 * k, v=v)
        R = 178 * k
        # outer ring: three lanes (hunts), inner ring: two lanes (roosts), gaps between lanes
        for (r0, r1, segs, dens) in [(0.66, 0.97, [(-1.75, 0.55), (0.70, 2.30), (2.45, 4.38)], 235),
                                     (0.36, 0.58, [(-0.40, 2.70), (2.95, 5.75)], 255)]:
            for a0, a1 in segs:
                outer = arc_pts(cx, cy, r1 * R, a0, a1); inner = arc_pts(cx, cy, r0 * R, a1, a0)
                m.fill(np.concatenate([outer, inner]), v=int(dens * v / 255))
        m.stroke(arc_pts(cx, cy, R, 0, 2 * math.pi), 20 * k, v=v)           # the bright rim
        m.stroke(arc_pts(cx, cy, 0.30 * R, 0, 2 * math.pi), 14 * k, v=v)   # pupil rim
        m.disk(cx, cy, 0.25 * R, v=0)                                       # the black pupil
        if v:
            m.disk(cx - 0.11 * R, cy - 0.12 * R, 0.07 * R, v=v)            # catch-light

    def fav(self):
        m = Mask(); cx = cy = 500
        up, lo = almond(cx, cy, 455, 225)
        m.stroke(up, 70); m.stroke(lo, 70)
        m.disk(cx, cy, 250); m.disk(cx, cy, 108, v=0)
        return m


class WadjetGold(Concept):
    id, letter, name = "wadjet-gold", "B", "Gold Amulet"
    symbol = "The wedjat amulet as Egyptians wore it: the Eye of Horus struck into a gold plate, protection carried on you."
    psych = "A bright gold tile is the one warm block on a cool home screen, so it is found first; the dark cut-out eye is a strong focal point."
    tile = "gold"; S0 = 3.55; density = 0.95; bloom = 0.35

    def glyph(self, m, s, cx=500, cy=500, v=255):
        icon.wedjat(m, s, cx, cy, v=v)

    def fav(self):
        return icon.favicon_mask()


class Horus(Concept):
    id, letter, name = "horus", "C", "Horus"
    symbol = "Horus the falcon, whose cheek marking IS the wedjat: the brow, almond eye, kohl tail, teardrop and spiral cut into the god's own head."
    psych = "A profile face is read faster than any abstract mark (faces are processed first); facing right reads as forward motion."
    S0 = 1.0; plate = True; bloom = 0.6
    OX, OY = -112, -30          # centres the bust's bounding box on the tile

    def head(self, s, cx, cy):
        P = lambda x, y: (cx + x * s, cy + y * s)
        return path(
            (P(-200, 390), P(-232, 230), P(-268, 40), P(-238, -100)),       # nape, sloping forward
            (P(-238, -100), P(-192, -212), P(-60, -266), P(90, -260)),      # low flat crown
            (P(90, -260), P(170, -256), P(232, -236), P(268, -204)),        # forehead to the cere
            (P(268, -204), P(400, -226), P(522, -150), P(526, -30)),        # long upper mandible
            (P(526, -30), P(528, 50), P(496, 116), P(440, 146)),            # the hook
            (P(440, 146), P(458, 96), P(452, 50), P(420, 36)),              # back under the tip
            (P(420, 36), P(402, 28), P(386, 50), P(366, 52)),               # the tomial notch (the falcon's tooth)
            (P(366, 52), P(318, 56), P(268, 60), P(225, 72)),               # gape
            (P(225, 72), P(215, 150), P(160, 225), P(110, 280)),            # throat
            (P(110, 280), P(85, 320), P(85, 355), P(100, 390)),             # front of the neck
            (P(100, 390), P(-20, 412), P(-110, 412), P(-200, 390)))         # the bust's curved foot

    def marks(self, m, s, cx, cy, v, thick=1.0, spiral=True, brow=True, tail=True, eye_k=1.0):
        P = lambda x, y: (cx + x * s, cy + y * s)
        ex, ey, hw, hh = 140, -102, 112 * eye_k, 56 * eye_k      # the almond eye, front corner toward the beak
        eye = lens(cx + ex * s, cy + ey * s, hw * s, hh * s)
        if brow:
            m.stroke(path((P(250, -178), P(172, -226), P(20, -226), P(-120, -182))), None,
                     taper=(36 * s * thick, 18 * s * thick), v=0)                                 # the brow
        if tail:
            m.stroke(path((P(ex - hw + 10, ey + 2), P(-40, ey + 6), P(-130, ey + 6), P(-205, ey - 6))), None,
                     taper=(40 * s * thick, 22 * s * thick), v=0)                                 # the kohl tail
        # the teardrop (the falcon's malar stripe): hangs from the lower lid with a gold gap, flaring as it falls
        m.stroke(path((P(ex - 8, ey + hh + 30), P(ex - 18, ey + hh + 80), P(ex - 40, ey + hh + 130), P(ex - 78, ey + hh + 182))), None,
                 taper=(30 * s * thick, 74 * s * thick), v=0)
        if spiral:
            m.stroke(path((P(ex - 62, ey + hh - 12), P(ex - 92, ey + 120), P(ex - 200, ey + 170), P(ex - 255, ey + 120)),
                          (P(ex - 255, ey + 120), P(ex - 300, ey + 80), P(ex - 260, ey + 30), P(ex - 215, ey + 58))),
                     36 * s * thick, v=0)                                                          # the spiral
        m.fill(eye, v=0)
        pr = 33 * s * (1.0 if eye_k > 1 else min(thick, 1.25))
        px_, py_ = cx + (ex + 6) * s, cy + (ey - 4) * s
        m.disk(px_, py_, pr, v=v)                                                                  # the gold pupil, sealed in the almond
        return (px_, py_, pr)

    def glyph(self, m, s, cx=500, cy=500, v=255):
        cx, cy = cx + self.OX * s, cy + self.OY * s
        m.fill(self.head(s, cx, cy), v=v)
        pu = self.marks(m, s, cx, cy, v)
        if v:
            m.pupil = pu

    FAV16 = """
................
................
....GGGGGGG.....
..GGGGGGGGGGG...
.GGGGGGGGGGGGG..
.GGGG.....GGGGG.
.GGG...GG..GGGG.
.GGGG.....GGGGG.
.GGGGGGGGGGG.GG.
.GGGGG.GGGG...G.
.GGGG..GGG......
.GGGG.GGG.......
.GGGGGGGG.......
.GGGGGGG........
..GGGGGG........
................
"""

    def fav(self):
        m = Mask(); s = 1.08                       # the whole head on an ink margin: skull, hooked beak and jaw all read
        cx, cy = 500 - 145 * s, 500 - 73 * s
        m.fill(self.head(s, cx, cy))
        self.marks(m, s, cx, cy, 255, thick=1.5, spiral=False, brow=False, tail=False, eye_k=1.32)
        return m


class Iris(Concept):
    id, letter, name = "iris", "D", "The Lens"
    symbol = "One unbroken line and a pupil: the eye reduced to its idea, the watch that never blinks."
    psych = "Minimal and geometric: the pointed corners read as precision and engineering, the lone pupil is the single focal point."
    kind = "flat"; S0 = 1.0

    def glyph(self, m, s, cx=500, cy=500, v=255):
        m.fill(lens(cx, cy, 400 * s, 205 * s), v=v)
        m.fill(lens(cx, cy, 400 * s - 92 * s, 205 * s - 46 * s), v=0)
        m.disk(cx, cy, 112 * s, v=v)
        m.disk(cx - 38 * s, cy - 40 * s, 24 * s, v=0)   # one ink glint so the pupil is an eye, not a dot

    def fav(self):
        m = Mask(); cx = cy = 500
        m.fill(lens(cx, cy, 470, 250)); m.fill(lens(cx, cy, 470 - 150, 250 - 75), v=0)
        m.disk(cx, cy, 140)
        return m


class Agents(Concept):
    id, letter, name = "agents", "E", "Constellation"
    symbol = "Every agent is a star on the lid and the eye is drawn by them: literally one eye on every agent."
    psych = "Gestalt closure: the mind joins the dots into an eye, and that small act of completion makes the mark memorable."
    S0 = 1.0
    N_UP, N_LO = 7, 5

    def nodes(self, s, cx, cy, w=370, h=190):
        up, lo = almond(cx, cy, w * s, h * s, n=400)
        def pick(curve, n, ends):
            L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(curve, axis=0), axis=1))])
            ts = np.linspace(0, L[-1], n + 2)[1:-1] if not ends else np.linspace(0, L[-1], n)
            return np.stack([np.interp(ts, L, curve[:, 0]), np.interp(ts, L, curve[:, 1])], -1)
        return up, lo, np.concatenate([pick(up, self.N_UP, True), pick(lo, self.N_LO, False)])

    def glyph(self, m, s, cx=500, cy=500, v=255):
        up, lo, pts = self.nodes(s, cx, cy)
        m.stroke(up, 8 * s, v=int(110 * v / 255)); m.stroke(lo, 8 * s, v=int(110 * v / 255))  # the faint lid line
        for x, y in pts:                                                                      # each agent looks in
            m.stroke(np.array([[x, y], [cx + (x - cx) * 0.36, cy + (y - cy) * 0.36]]), 5 * s, v=int(70 * v / 255))
        for i, (x, y) in enumerate(pts):
            m.disk(x, y, (34 if i in (0, self.N_UP - 1) else 30) * s, v=v)
        m.disk(cx, cy, 92 * s, v=v)
        if v:
            m.pupil = (cx, cy, 92 * s)

    def fav(self):
        m = Mask(); cx = cy = 500
        self.N_UP, self.N_LO = 5, 3
        up, lo, pts = self.nodes(1.0, cx, cy, 430, 235)
        self.N_UP, self.N_LO = 7, 5
        for x, y in pts:
            m.disk(x, y, 62)
        m.disk(cx, cy, 120)
        return m


class Aten(Concept):
    id, letter, name = "aten", "F", "Ouroboros Sun"
    symbol = "The eye inside the sun disk of Ra, ringed by the serpent that eats its tail (first drawn on Tutankhamun's shrine): a watch with no end."
    psych = "The circle is the calmest shape and frames the eye as protected, not prying; the serpent's head gives the ring one point of tension."
    S0 = 1.0

    def glyph(self, m, s, cx=500, cy=500, v=255):
        R = 395 * s
        # the serpent ring: tapers from tail to head, head overlapping its own tail at the top right
        a0, a1 = -math.pi / 2 + 0.75, -math.pi / 2 + 0.75 + 2 * math.pi - 0.30
        m.stroke(arc_pts(cx, cy, R, a0, a1, 600), None, taper=(26 * s, 74 * s), v=v)
        hx, hy = cx + R * math.cos(a1), cy + R * math.sin(a1)
        ang = a1 + math.pi / 2
        head = [(hx + math.cos(ang) * 92 * s, hy + math.sin(ang) * 92 * s),
                (hx + math.cos(ang + 1.75) * 56 * s, hy + math.sin(ang + 1.75) * 56 * s),
                (hx + math.cos(ang - 1.75) * 56 * s, hy + math.sin(ang - 1.75) * 56 * s)]
        m.fill(head, v=v); m.disk(hx, hy, 50 * s, v=v)
        m.disk(hx + math.cos(ang) * 30 * s + math.cos(ang - 1.57) * 22 * s, hy + math.sin(ang) * 30 * s + math.sin(ang - 1.57) * 22 * s, 11 * s, v=0)  # its eye
        icon.wedjat(m, 2.85 * s, cx - 10 * s, cy + 10 * s, v=v)

    def fav(self):
        m = Mask(); cx = cy = 500
        m.stroke(arc_pts(cx, cy, 440, 0, 2 * math.pi), 80)
        up, lo = almond(cx, cy + 10, 280, 140)
        m.stroke(up, 70); m.stroke(lo, 70)
        m.disk(cx - 10, cy - 5, 95)
        return m


class Wadjet(Concept):
    id, letter, name = "wadjet", "-", "Wadjet in sand (round 1)"
    symbol = "The Eye of Horus in the live sand."
    psych = ""
    S0 = 3.7

    def glyph(self, m, s, cx=500, cy=500, v=255):
        icon.wedjat(m, s, cx, cy, v=v)

    def fav(self):
        return icon.favicon_mask()


ALL = {c.id: c for c in [Watch(), WadjetGold(), Horus(), Iris(), Agents(), Aten(), Wadjet()]}
ORDER = ["watch", "wadjet-gold", "horus", "iris", "agents", "aten"]


# ------------------------------------------------------------------ renderers
def mask_at(c: Concept, scale, invert=False):
    m = Mask()
    if invert:  # gold tile: the whole field is sand, the glyph is cut out of it
        m.d.rectangle([0, 0, m.S, m.S], fill=255)
        c.glyph(m, scale, v=0); m.pupil = None
    else:
        c.glyph(m, scale)
    return m


def flat(m: Mask, px=1024, bg=True, glow=True):
    """flat gold, lit top-left to bottom-right (GOLD3 -> GOLD2 -> GOLD1), with the amber glow the sand throws"""
    a = np.asarray(m.im.resize((px, px), Image.LANCZOS), dtype=np.float32) / 255.0
    yy, xx = np.mgrid[0:px, 0:px] / px
    t = np.clip((xx * 0.45 + yy * 0.75 - 0.15) / 0.95, 0, 1)[..., None]
    col = GOLD2 * (1 - t) + GOLD1 * t + (GOLD3 - GOLD2) * np.clip(0.35 - t, 0, 1) * 1.6
    if not bg:
        return np.clip(col, 0, 1), a
    out = np.broadcast_to(INK, (px, px, 3)).copy()
    if glow:
        from scipy import ndimage
        g = ndimage.gaussian_filter(a, px * 0.03)
        out = out + g[..., None] * np.array([0.30, 0.20, 0.07]) * 0.55
    return np.clip(out * (1 - a[..., None]) + col * a[..., None], 0, 1)


def gold_plate(rgb, m: Mask, px):
    """beaten gold under the sand (screen blend), so the plate reads as solid gold at 48 px and the grains as its shine"""
    a = np.asarray(m.im.resize((px, px), Image.LANCZOS), dtype=np.float32)[..., None] / 255.0
    yy, xx = np.mgrid[0:px, 0:px] / px
    t = np.clip(xx * 0.4 + yy * 0.7, 0, 1)[..., None]
    base = (GOLD2 * (1 - t) + GOLD1 * t) * 0.72 * a
    return 1 - (1 - rgb) * (1 - base)


def master(c: Concept, scale=None, px=1024):
    """opaque RGB float master for a concept"""
    s = c.S0 if scale is None else scale
    if c.tile == "gold":
        m = mask_at(c, s, invert=True)
        return gold_plate(render(m, px, density=c.density, bloom=c.bloom, scatter=0.0), m, px)
    if c.kind == "flat":
        return flat(mask_at(c, s), px)
    m = mask_at(c, s)
    out = render(m, px, density=c.density, bloom=c.bloom)
    return gold_plate(out, m, px) if c.plate else out


def fav_image(c: Concept, px=1024):
    """the small-size favicon: flat gold glyph on an ink tile (or ink glyph on a gold tile for gold-tile concepts)"""
    a = c.fav().im.resize((px, px), Image.LANCZOS)
    tile = Image.new("L", (px, px), 0)
    ImageDraw.Draw(tile).rounded_rectangle([0, 0, px - 1, px - 1], int(px * 0.215), fill=255)
    if c.tile == "gold":
        fg, bgc = INK8, GOLD_FLAT
    else:
        fg, bgc = GOLD_FLAT, INK8
    im = Image.new("RGBA", (px, px), bgc + (255,))
    im.paste(Image.new("RGBA", (px, px), fg + (255,)), (0, 0), a)
    im.putalpha(tile)
    return im


def fav_small(c: Concept, size):
    """16/32/48: area-average the 1024 favicon, then pull the glyph's alpha toward crisp pixels"""
    if size == 16 and getattr(c, "FAV16", None):        # drawn on the pixel grid
        im = Image.new("RGBA", (16, 16), INK8 + (255,))
        for y, r in enumerate(c.FAV16.strip().splitlines()):
            for x, ch in enumerate(r):
                if ch == "G": im.putpixel((x, y), GOLD_FLAT + (255,))
        for x, y in [(0, 0), (15, 0), (0, 15), (15, 15)]: im.putpixel((x, y), (0, 0, 0, 0))
        return im
    if size == 16 and c.id in ("wadjet", "wadjet-gold"):   # the wedjat's 16 px is hand-drawn on the pixel grid
        im = icon.fav16()
        if c.tile == "gold":
            px = im.load()
            for y in range(16):
                for x in range(16):
                    r, g, b, a = px[x, y]
                    if a: px[x, y] = (INK8 + (255,)) if (r, g, b) == GOLD_FLAT else (GOLD_FLAT + (255,))
        return im
    big = c.fav().im
    a = np.asarray(big.resize((size, size), Image.LANCZOS), dtype=np.float32) / 255.0
    a = np.clip((a - 0.06) / 0.88, 0, 1)    # a light pull toward crisp edges; more thins the ink cuts into rings
    fg, bgc = (INK8, GOLD_FLAT) if c.tile == "gold" else (GOLD_FLAT, INK8)
    rgb = np.array(bgc)[None, None] * (1 - a[..., None]) + np.array(fg)[None, None] * a[..., None]
    t = Image.new("L", (size * 8, size * 8), 0)
    ImageDraw.Draw(t).rounded_rectangle([0, 0, size * 8 - 1, size * 8 - 1], int(size * 8 * 0.215), fill=255)
    out = Image.fromarray((rgb + .5).astype(np.uint8), "RGB").convert("RGBA")
    out.putalpha(t.resize((size, size), Image.LANCZOS))
    return out
