"""Eagle Eye icon, round 2+: the wedjat refined per the three critics (legibility, brand, Horus)."""
import sys, numpy as np
from sand import Mask, path, render, save_rgb

G = dict(sw=15.0, pupil_r=17.5, pupil=(98, 52), brow=(15.0, 8.0), drop=(15.0, 21.0), coil=13.0)
CX, CY = 113, 62  # centre of the glyph in mark units (extents incl. stroke ~ x 20..202, y 2..124)


def wedjat(m: Mask, s, cx=500, cy=500, v=255, g=G, simple=False):
    ox, oy = cx - CX * s, cy - CY * s
    T = lambda pts: [(ox + x * s, oy + y * s) for x, y in pts]
    sw = g["sw"] * s
    # almond eye: pointed inner corner, fuller lids than the site mark so the white of the eye survives 48 px
    upper = path(((28, 66), (60, 28), (130, 22), (172, 58)))
    lower = path(((172, 58), (132, 82), (70, 92), (28, 66)))
    m.stroke(T(np.concatenate([upper, lower])), sw, v=v)
    # pupil: solid, raised so the upper lid cuts across its top; the molten sun disk
    pc = T([g["pupil"]])[0]
    m.disk(pc[0], pc[1], g["pupil_r"] * s, v)
    if v == 255:
        m.pupil = (pc[0], pc[1], g["pupil_r"] * s)
    if simple:
        return m
    # brow: arcs over the lid from the inner corner, tapering toward the temple
    m.stroke(T(path(((32, 34), (66, 6), (132, -2), (182, 14)))), None, taper=(g["brow"][0] * s, g["brow"][1] * s), v=v)
    # the line to the temple
    m.stroke(T(path(((166, 59), (178, 60.5), (190, 60.5), (199, 59)))), sw * 1.12, v=v)
    # the teardrop: as thick as the lid, flared at its foot
    m.stroke(T(path(((86, 82), (84, 96), (82, 106), (77, 118)))), None, taper=(g["drop"][0] * s, g["drop"][1] * s), v=v)
    # the spiral: an open coil
    m.stroke(T(path(((114, 82), (120, 110), (146, 126), (170, 120)), ((170, 120), (194, 113), (194, 84), (172, 82)),
                    ((172, 82), (156, 81), (152, 100), (164, 104)))), g["coil"] * s, v=v)
    return m


def master(scale=3.7, cy=500):
    m = Mask(); wedjat(m, scale, 500, cy); return m


def favicon_mask():
    """16/32 px wedjat, flat gold: eye, lid-cut pupil, teardrop, short straight tail; no brow, no coil."""
    m = Mask()
    s = 860 / 194.0  # glyph x 7..201 incl. stroke -> 86% of the tile
    ox, oy = 500 - 105 * s, 500 - 66 * s
    T = lambda pts: [(ox + x * s, oy + y * s) for x, y in pts]
    upper = path(((24, 62), (58, 22), (136, 18), (172, 56)))
    lower = path(((172, 56), (134, 82), (66, 92), (24, 62)))
    m.stroke(T(np.concatenate([upper, lower])), 17 * s)
    pc = T([(98, 46)])[0]; m.disk(pc[0], pc[1], 17 * s)
    m.stroke(T([(166, 57), (198, 57)]), 17 * s)                          # short straight tail
    m.stroke(T(path(((74, 80), (71, 94), (67, 104), (60, 114)))), None, taper=(17 * s, 20 * s))  # teardrop, inner third, slanted
    return m


def fav():
    from PIL import Image
    import numpy as np
    m = favicon_mask()
    a = np.asarray(m.im.resize((1024, 1024), Image.LANCZOS))
    rgba = np.zeros((1024, 1024, 4), np.uint8); rgba[..., :3] = (226, 184, 96); rgba[..., 3] = a
    Image.fromarray(rgba, "RGBA").save("fav-mark.png")
    tile = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    from PIL import ImageDraw
    ImageDraw.Draw(tile).rounded_rectangle([0, 0, 1023, 1023], 220, fill=(10, 10, 9, 255))
    tile.alpha_composite(Image.fromarray(rgba, "RGBA")); tile.save("fav-r3.png"); print("ok fav")


if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "r2"
    m = master()
    m.im.resize((1024, 1024)).save(f"mask-{tag}.png")
    save_rgb(render(m, 1024), f"cand-{tag}.png")
    print("ok", tag)


FAV16 = """
................
................
................
...GGGGGGGG.....
.GGGGGGGGGGGG...
GG..GGGG....GG..
GG..GGGG.....GGG
GG..GGGG.....GGG
GG..........GG..
.GGGGGGGGGGGG...
...GGGGGGGG.....
....GG..........
....GG..........
....GG..........
................
................
"""


def fav16():
    """16 px favicon drawn on the pixel grid: 2 px strokes, a 4 px opening, 4 px lid-cut pupil, vertical inner-third teardrop, 2 px tail stub."""
    from PIL import Image
    rows = [r for r in FAV16.strip().splitlines()]
    im = Image.new("RGBA", (16, 16), (10, 10, 9, 255))
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch == "G": im.putpixel((x, y), (226, 184, 96, 255))
    for x, y in [(0, 0), (15, 0), (0, 15), (15, 15)]: im.putpixel((x, y), (0, 0, 0, 0))  # rounded tile corners
    return im
