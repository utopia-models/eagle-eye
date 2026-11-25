#!/usr/bin/env python3
"""human_motion.py: a visible cursor and human mouse/scroll motion for Playwright captures (knowledge#18869 items 3 + 6).
Eagle's capture_browser.py (Ra) imports it:  `import human_motion as hm; await hm.install_cursor(page); await hm.move(page, x, y); await hm.click(page, x, y); await hm.scroll(page, 900)`.
Motion model (the rubric Gemini grades, item 6): curved Bezier paths with overshoot and a micro-correction, Fitts-law duration, jitter, a hover
beat before every click, off-centre click points, variable eased scroll steps with reading pauses, idle drift. No fixed speed, no teleports."""
import asyncio
import math
import random

CURSOR_JS = """(() => {
  if (window.__hmCursor) return;
  const c = document.createElement('div'); window.__hmCursor = c;
  c.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:22px;z-index:2147483647;pointer-events:none;transform:translate(-3px,-2px);';
  c.innerHTML = '<svg width="22" height="22" viewBox="0 0 22 22"><path d="M3 2 L3 17 L7 13 L10 20 L12.5 19 L9.5 12 L15 12 Z" fill="#111" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  const put = (x, y) => { c.style.left = x + 'px'; c.style.top = y + 'px'; };
  document.addEventListener('mousemove', e => put(e.clientX, e.clientY), true);
  (document.body || document.documentElement).appendChild(c);
})();"""

_pos = {}


def fitts_ms(dist, width=40.0):
    """Fitts' law: MT = a + b*log2(D/W + 1), a=120 ms, b=150 ms/bit, +-12 % jitter."""
    return (120 + 150 * math.log2(dist / width + 1)) * random.uniform(0.88, 1.12)


def bezier_path(x0, y0, x1, y1, steps, rng=random):
    """Cubic Bezier with two random off-axis control points (a curve, never a straight line) and ease-in-out timing (a bell-shaped speed)."""
    dx, dy = x1 - x0, y1 - y0
    d = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / d, dx / d
    bend = rng.uniform(-0.25, 0.25) * d
    c1 = (x0 + dx * 0.3 + nx * bend, y0 + dy * 0.3 + ny * bend)
    c2 = (x0 + dx * 0.7 + nx * bend * rng.uniform(0.3, 1.2), y0 + dy * 0.7 + ny * bend * rng.uniform(0.3, 1.2))
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        t = t * t * (3 - 2 * t)   # ease in/out
        u = 1 - t
        x = u ** 3 * x0 + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * x1
        y = u ** 3 * y0 + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * y1
        pts.append((x + rng.gauss(0, 0.6), y + rng.gauss(0, 0.6)))   # hand jitter
    return pts


async def install_cursor(page):
    """Injected cursor overlay that follows the Playwright mouse (the recorded page shows no OS cursor)."""
    await page.add_init_script(CURSOR_JS)
    await page.evaluate(CURSOR_JS)


async def move(page, x, y, overshoot=True):
    x0, y0 = _pos.get(id(page), (random.uniform(200, 600), random.uniform(150, 400)))
    dist = math.hypot(x - x0, y - y0)
    ms = fitts_ms(dist)
    tx, ty = x, y
    if overshoot and dist > 160:   # aim a few px past the target, then correct
        a = math.atan2(y - y0, x - x0)
        o = random.uniform(5, 16)
        tx, ty = x + math.cos(a) * o, y + math.sin(a) * o
    steps = max(12, int(ms / 14))
    for px, py in bezier_path(x0, y0, tx, ty, steps):
        await page.mouse.move(px, py)
        await asyncio.sleep(ms / 1000 / steps)
    if (tx, ty) != (x, y):
        await asyncio.sleep(random.uniform(0.05, 0.12))
        for px, py in bezier_path(tx, ty, x, y, 5):
            await page.mouse.move(px, py)
            await asyncio.sleep(0.016)
    _pos[id(page)] = (x, y)


async def click(page, x, y, box=None):
    """Hover beat, off-centre point (box = (w, h) of the target), then click."""
    if box:
        x += random.uniform(-0.25, 0.25) * box[0]
        y += random.uniform(-0.2, 0.2) * box[1]
    await move(page, x, y)
    await asyncio.sleep(random.uniform(0.25, 0.7))   # hover beat
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.05, 0.11))
    await page.mouse.up()


async def scroll(page, total_px, pause=(0.5, 1.6)):
    """Eased wheel scroll in small variable steps with reading pauses; total_px signed."""
    left, sign = abs(total_px), 1 if total_px >= 0 else -1
    while left > 0:
        burst = random.randint(3, 7)
        for k in range(burst):
            step = min(left, random.choice([40, 52, 64, 78, 96]) * random.uniform(0.8, 1.2) * math.sin(math.pi * (k + 1) / (burst + 1)) + 12)
            await page.mouse.wheel(0, sign * step)
            left -= step
            await asyncio.sleep(random.uniform(0.02, 0.06))
            if left <= 0:
                break
        await asyncio.sleep(random.uniform(*pause))   # reading pause


async def idle(page, seconds):
    """Idle drift: tiny movements instead of a frozen pointer."""
    x, y = _pos.get(id(page), (400, 300))
    end = asyncio.get_event_loop().time() + seconds
    while asyncio.get_event_loop().time() < end:
        x, y = x + random.gauss(0, 2.5), y + random.gauss(0, 2.5)
        await page.mouse.move(x, y)
        _pos[id(page)] = (x, y)
        await asyncio.sleep(random.uniform(0.3, 0.9))


GEMINI_RUBRIC = ("Watch the mouse cursor and scrolling in this screen recording. List timestamped moments that look robotic: straight-line or constant-speed moves, "
                 "instant teleports, perfectly centered clicks, no overshoot or micro-correction, scrolls with identical steps, idle with zero drift, clicks without a hover beat. "
                 'Return JSON only: {"human_score": 1-10, "robotic_moments": [{"t": "mm:ss", "what": "..."}]}.')
