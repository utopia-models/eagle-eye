"""Build the Eagle Eye icon set from the sand renderer.  python build.py <out-dir>

Every size is a LANCZOS downscale of a 1024 render, so the grains average into solid gold at small sizes.
Safe zones are fitted from the mask itself (the glyph's farthest pixel from the centre), not guessed:
  Android adaptive foreground  -> inside the 66/108 dp safe circle (radius 0.3056 of the canvas)
  PWA maskable                 -> inside the 80% safe circle (radius 0.40)
"""
import os, sys, numpy as np
from PIL import Image
from sand import Mask, render, save_rgb, INK
import icon

OUT = sys.argv[1]
INK8 = tuple(int(round(c * 255)) for c in INK)


def p(*a):
    f = os.path.join(OUT, *a); os.makedirs(os.path.dirname(f), exist_ok=True); return f


def max_radius(m: Mask):
    a = np.asarray(m.im.resize((1000, 1000)), dtype=np.float32)
    ys, xs = np.nonzero(a > 40)
    return float(np.hypot(xs + 0.5 - 500, ys + 0.5 - 500).max())


def mask_at(scale):
    m = Mask(); icon.wedjat(m, scale, 500, 500); return m


S0 = 3.7
R0 = max_radius(mask_at(S0))
fit = lambda r: S0 * r / R0


def small(im, s):
    """small renders: downscale, then lift saturation/brightness and sharpen so 48-192 px stays gold, not brown"""
    from PIL import ImageEnhance, ImageFilter
    t = im.resize((s, s), Image.LANCZOS)
    if s <= 256:
        rgb = t.convert("RGB") if t.mode != "RGBA" else t
        base = ImageEnhance.Brightness(ImageEnhance.Color(t.convert("RGB")).enhance(1.25)).enhance(1.12)
        base = base.filter(ImageFilter.UnsharpMask(radius=1.0, percent=60, threshold=2))
        if t.mode == "RGBA":
            base.putalpha(t.getchannel("A")); return base
        return base
    return t


def opaque(scale, px=1024):
    return Image.fromarray((np.clip(render(mask_at(scale), px), 0, 1) * 255 + .5).astype(np.uint8), "RGB")


def transparent(m, px=1024):
    lit, a = render(m, px, bg=False)
    rgb = np.clip(lit / np.maximum(a[..., None], 1e-4), 0, 1)
    return Image.fromarray(np.dstack([(rgb * 255 + .5).astype(np.uint8), (a * 255 + .5).astype(np.uint8)]), "RGBA")


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
mk = opaque(sm)
for s in (192, 512):
    small(mk, s).save(p("pwa", f"icon-{s}-maskable.png"))

# 3. Android adaptive: foreground (sand, transparent), background (ink), monochrome (flat silhouette)
sf = fit(285)
fg = transparent(mask_at(sf))
fg.save(p("android", "adaptive-foreground.png"))
Image.new("RGB", (1024, 1024), INK8).save(p("android", "adaptive-background.png"))
mono = mask_at(sf).im.resize((1024, 1024), Image.LANCZOS)
Image.merge("RGBA", (Image.new("L", (1024, 1024), 255),) * 3 + (mono,)).save(p("android", "adaptive-monochrome.png"))

# 4. splash mark: transparent sand eye, tightly framed (Expo splash `image`, backgroundColor #0a0a09)
sp = transparent(mask_at(fit(420)))
sp.save(p("splash", "splash-icon-1024.png"))
sp.resize((512, 512), Image.LANCZOS).save(p("splash", "splash-mark-512.png"))

# 5. favicon: the flat-gold wedjat on an ink tile (reads on light and dark tabs)
icon.fav()
fav = Image.open("fav-r3.png")
f16 = icon.fav16(); f32 = fav.resize((32, 32), Image.LANCZOS); f48 = fav.resize((48, 48), Image.LANCZOS)
f16.save(p("web", "favicon-16.png")); f32.save(p("web", "favicon-32.png")); f48.save(p("web", "favicon-48.png"))
f48.save(p("web", "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)], append_images=[f16, f32])
Image.open("fav-mark.png").save(p("web", "favicon-mark-transparent.png"))

print(f"R0={R0:.0f} master_scale={S0} maskable_scale={sm:.2f} fg_scale={sf:.2f} splash_scale={fit(420):.2f}")
