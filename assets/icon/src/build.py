"""Build the Eagle Eye icon set for one concept.  python build.py <out-dir> [concept-id]   (default: wadjet)

Concept ids live in concepts.py (A watch · B wadjet-gold · C horus · D iris · E agents · F aten · wadjet = round 1).
Every size is a LANCZOS downscale of a 1024 render, so the grains average into solid gold at small sizes.
Safe zones are fitted from the mask itself (the glyph's farthest pixel from the centre), not guessed:
  Android adaptive foreground  -> inside the 66/108 dp safe circle (radius 0.3056 of the canvas)
  PWA maskable                 -> inside the 80% safe circle (radius 0.40)
A gold-tile concept (B) is a sand field with the glyph cut out: its adaptive background is the sand field and its
foreground is the ink glyph.
"""
import os, sys, numpy as np
from PIL import Image
from sand import Mask, render, INK
import concepts as C

OUT = sys.argv[1]
CON = C.ALL[sys.argv[2] if len(sys.argv) > 2 else "wadjet"]
INK8 = C.INK8
GOLD = CON.tile == "gold"


def p(*a):
    f = os.path.join(OUT, *a); os.makedirs(os.path.dirname(f), exist_ok=True); return f


def max_radius(m: Mask):
    a = np.asarray(m.im.resize((1000, 1000)), dtype=np.float32)
    ys, xs = np.nonzero(a > 40)
    return float(np.hypot(xs + 0.5 - 500, ys + 0.5 - 500).max())


def mask_at(scale):
    m = Mask(); CON.glyph(m, scale, 500, 500); return m


S0 = CON.S0
R0 = max_radius(mask_at(S0))
fit = lambda r: S0 * r / R0


def small(im, s):
    """small renders: downscale, then lift saturation/brightness and sharpen so 48-192 px stays gold, not brown"""
    from PIL import ImageEnhance, ImageFilter
    t = im.resize((s, s), Image.LANCZOS)
    if s <= 256:
        base = ImageEnhance.Brightness(ImageEnhance.Color(t.convert("RGB")).enhance(1.25)).enhance(1.12)
        base = base.filter(ImageFilter.UnsharpMask(radius=1.0, percent=60, threshold=2))
        if t.mode == "RGBA":
            base.putalpha(t.getchannel("A")); return base
        return base
    return t


def to8(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255 + .5).astype(np.uint8), "RGB")


def opaque(scale, px=1024):
    return to8(C.master(CON, scale, px))


def transparent(m, px=1024):
    if GOLD:  # the ink glyph, flat
        a = m.im.resize((px, px), Image.LANCZOS)
        im = Image.new("RGBA", (px, px), INK8 + (0,)); im.putalpha(a); return im
    if CON.kind == "flat":
        col, a = C.flat(m, px, bg=False)
    else:
        lit, a = render(m, px, bg=False, density=CON.density, bloom=CON.bloom)
        col = np.clip(lit / np.maximum(a[..., None], 1e-4), 0, 1)
        if CON.plate:  # beaten gold under the grains: composite over the plate, alpha = the glyph
            g = np.asarray(m.im.resize((px, px), Image.LANCZOS), dtype=np.float32) / 255.0
            plate = C.gold_plate(np.zeros((px, px, 3)), m, px)
            under = np.clip(plate / np.maximum(g[..., None], 1e-4), 0, 1)
            col = 1 - (1 - col * a[..., None]) * (1 - under)   # the same screen blend as the master
            a = np.maximum(a * (1 - g), g)
    return Image.fromarray(np.dstack([(col * 255 + .5).astype(np.uint8), (a * 255 + .5).astype(np.uint8)]), "RGBA")


if __name__ == "__main__":
    # 1. master + iOS (RGB, no alpha) + apple-touch + PWA "any"
    master = opaque(S0)
    master.save(p("icon-1024.png"))
    master.save(p("ios", "AppIcon-1024.png"))
    small(master, 180).save(p("web", "apple-touch-icon.png"))
    for s in (192, 512):
        small(master, s).save(p("pwa", f"icon-{s}.png"))
    master.resize((512, 512), Image.LANCZOS).save(p("android", "play-store-512.png"))

    # 2. PWA maskable: glyph inside the 80% safe circle
    sm = min(S0, fit(392))
    mk = master if sm == S0 else opaque(sm)
    for s in (192, 512):
        small(mk, s).save(p("pwa", f"icon-{s}-maskable.png"))

    # 3. Android adaptive: foreground (glyph, transparent), background, monochrome (flat silhouette)
    sf = fit(285)
    fg = transparent(mask_at(sf))
    fg.save(p("android", "adaptive-foreground.png"))
    if GOLD:
        bgm = Mask(); bgm.d.rectangle([0, 0, bgm.S, bgm.S], fill=255)
        to8(C.gold_plate(render(bgm, 1024, density=CON.density, bloom=CON.bloom, scatter=0.0), bgm, 1024)).save(p("android", "adaptive-background.png"))
    else:
        Image.new("RGB", (1024, 1024), INK8).save(p("android", "adaptive-background.png"))
    mono = mask_at(sf).im.resize((1024, 1024), Image.LANCZOS)
    Image.merge("RGBA", (Image.new("L", (1024, 1024), 255),) * 3 + (mono,)).save(p("android", "adaptive-monochrome.png"))

    # 4. splash mark: the glyph, transparent, tightly framed (Expo splash `image`, backgroundColor #0a0a09)
    sp = transparent(mask_at(fit(420))) if not GOLD else C.fav_image(CON)
    sp.save(p("splash", "splash-icon-1024.png"))
    sp.resize((512, 512), Image.LANCZOS).save(p("splash", "splash-mark-512.png"))

    # 5. favicon: the flat small-size mark on its tile (reads on light and dark tabs); site/favicon.svg is drawn from it
    fav = C.fav_image(CON)
    f16, f32, f48 = (C.fav_small(CON, s) for s in (16, 32, 48))
    f16.save(p("web", "favicon-16.png")); f32.save(p("web", "favicon-32.png")); f48.save(p("web", "favicon-48.png"))
    f48.save(p("web", "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)], append_images=[f16, f32])
    fav.save(p("web", "favicon-1024.png"))

    print(f"{CON.id}: R0={R0:.0f} master_scale={S0} maskable_scale={sm:.2f} fg_scale={sf:.2f}")
