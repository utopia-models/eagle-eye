#!/usr/bin/env python3
"""capture_browser.py -- REAL screen recording of a REAL Chrome on Eagle's sway seat (Desk Horus output), human input.

Launches a fresh Chrome (throwaway profile /home/desk-vsl/capture/profile-<tag>, deleted first) with three tabs
  1 THEIR JOB  (scrolls slowly during the face intro)
  2 MVP app    (mouse click on the tab, then a human click on a sidebar item per row)
  3 DIAGRAM    (ctrl+3 key press, then beats typed in the address bar: ctrl+l, End, "#beat=N", Enter)
records the vsl desk output (desk-vsl, HEADLESS-1) with wf-recorder (the real seat cursor is composited into the frames), drives it through
deskd with /opt/vsl-follow/desk_human (Bezier/Fitts glide, human typing, notch scroll) and crops the Chrome window
(1920x1080, tab strip + address bar included) to an h264 yuv420p 30 fps CFR silent mp4.

  capture_browser.py --tag 3307 --out /home/desk-vsl/capture/3307-browser.mp4 \
      --job https://www.upwork.com/jobs/~022125100658484433307 \
      --app https://oneshot.utopiamodels.ai/3307/app/ --diagram https://oneshot.utopiamodels.ai/3307/diagram/ \
      --sidebar "Review the codebase,Harden payments,Testing and monitoring,Growth" \
      [--timeline /home/desk-vsl/capture/3307-timeline.json | --draft-beats 1,2,3] [--intro 11.0] [--seed 7]

Timeline json (vsl): {"intro": 11.0, "rows": [{"start": s, "end": e, "click": "Harden payments" | "sidebar": 2,
"beat": 3, "tab": 2|3|"mvp"|"diagram"}, ...]}. Every key but start/end is optional; tab is inferred (click -> 2,
beat -> 3). Times are seconds from t=0 (first frame of the intro). The driver acts ~1 s BEFORE each row start.
Without --timeline a draft is built: tab 1 for --intro seconds, then ~5 s per row (one sidebar click per sidebar item,
then one beat per --draft-beats entry).

knowledge#18869 item 7: every tab is a REAL https URL (the public upwork.com job page, https://oneshot.utopiamodels.ai/<tag>/{app,diagram}/ published by
demo-site/publish.sh), Chrome runs at 100 % zoom (--force-device-scale-factor=1, default zoom pinned in Preferences), the profile has sign-in turned off so
no "Sign in to Chrome?" chip shows, and the recording is NOT cropped or scaled when the output is already 1920x1080. The Upwork page is only ever driven by
the seat's real wheel and cursor (upwork-seat-guard rule), never CDP. Item 6: --review runs render/gemini_cursor_review.py on the finished mp4.

Coordinates: deskd takes OUTPUT-local pixels (0,0 = top-left of HEADLESS-2). Chrome is placed at 0,0 of that output,
1920x1080. Sidebar item i (0-based) is at y = 169 + 48*i, x = 90; tab centres (150|390|630, 20).
"""
import argparse, glob, json, os, random, re, subprocess, sys, time

sys.path.insert(0, "/opt/vsl-follow")
from desk_human import DeskdHuman  # noqa: E402

# knowledge#18908: the capture seat is vsl's own desk (`desk-vsl` on Ra, `desk-create vsl vsl ra`), run AS that desk user
# (`sudo -u desk-vsl .../capture_as_vsl.sh`). Defaults are the vsl desk; Eagle's old seat is CAPTURE_SEAT_UID=1005 CAPTURE_OUT=HEADLESS-2 CAPTURE_OUT_X=1280.
SEAT_UID = os.environ.get("CAPTURE_SEAT_UID", "1019")
CAP_DIR = os.environ.get("CAPTURE_DIR", "/home/desk-vsl/capture")
ENV = dict(os.environ, WAYLAND_DISPLAY="wayland-1", XDG_RUNTIME_DIR=f"/run/user/{SEAT_UID}",
           DESKD_SOCK=os.environ.get("DESKD_SOCK", "/run/deskd-desk-vsl/deskd.sock"),
           SWAYSOCK=os.environ.get("SWAYSOCK") or glob.glob(f"/run/user/{SEAT_UID}/sway-ipc.{SEAT_UID}.*.sock")[0])
os.environ["DESKD_SOCK"] = ENV["DESKD_SOCK"]
OUT_NAME, OUT_X, W, H = os.environ.get("CAPTURE_OUT", "HEADLESS-1"), int(os.environ.get("CAPTURE_OUT_X", "0")), 1920, 1080
LEAD = 0.5                       # seconds of recording before t=0 (trimmed off)
TABS = {1: (150, 20), 2: (390, 20), 3: (630, 20)}
SIDE_X, SIDE_Y0, SIDE_DY = 90, 169, 48
TAB_NAMES = {"job": 1, "their job": 1, "mvp": 2, "app": 2, "diagram": 3, "architecture": 3}


def sh(*a):
    return subprocess.run(a, env=ENV, capture_output=True, text=True)


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower()).strip()


class Driver:
    def __init__(self, seed):
        self.h = DeskdHuman(os.environ["DESKD_SOCK"], seed=seed)
        self.rng = random.Random(seed)
        self.t0 = None

    def now(self):
        return time.monotonic() - self.t0

    def wait_until(self, t):
        d = t - self.now()
        if d > 0:
            time.sleep(d)

    def move(self, x, y):
        self.h.move_to(x + self.rng.uniform(-6, 6), y + self.rng.uniform(-6, 6))

    def click(self, x, y):
        self.h.click(x + self.rng.uniform(-4, 4), y + self.rng.uniform(-3, 3))

    def key(self, combo):
        self.h.ask("key", combo=combo)

    def scroll_for(self, notches, t_from, t_to):
        """Reading scroll: bursts of 2-4 notches with pauses, spread to finish by t_to."""
        times, t, k = [], t_from, 0
        while k < notches:
            for _ in range(min(notches - k, self.rng.randint(1, 3))):
                times.append(t); t += self.rng.uniform(.14, .38); k += 1
            t += self.rng.uniform(.9, 2.2)   # pause while 'reading'
        scale = (t_to - t_from) / max(times[-1] - t_from, .01)
        for tt in times:
            self.wait_until(t_from + (tt - t_from) * min(1, scale))
            self.h.ask("scroll", n=1)

    def beat(self, n, first):
        """Human keyboard: focus the address bar, jump to the end, type the fragment, Enter."""
        self.key("ctrl+l"); time.sleep(self.rng.uniform(.15, .3)); self.key("End")
        if not first:
            self.key("BackSpace")
        self.h.type(f"#beat={n}" if first else str(n))
        time.sleep(self.rng.uniform(.1, .25)); self.key("Return")


def load_rows(a):
    intro = a.intro
    if a.timeline:
        tl = json.load(open(a.timeline))
        intro = float(tl.get("intro", intro))
        rows = tl.get("rows") or tl.get("lines") or []
        return intro, [dict(r, start=float(r["start"]), end=float(r.get("end", r["start"] + 5))) for r in rows]
    rows, t = [], intro
    for i, _ in enumerate(a.sidebar):
        rows.append({"start": t, "end": t + 5, "sidebar": i + 1}); t += 5
    for b in a.draft_beats:
        rows.append({"start": t, "end": t + 5, "beat": b}); t += 5
    return intro, rows


def row_tab(r):
    if r.get("tab") is not None:
        t = r["tab"]
        return t if isinstance(t, int) else TAB_NAMES.get(norm(t), 2)
    return 3 if "beat" in r else 2 if ("click" in r or "sidebar" in r) else None


def sidebar_y(r, sidebar):
    if "sidebar" in r:
        i = int(r["sidebar"]) - 1
    elif r.get("click") is not None:
        c = norm(str(r["click"]).replace("text=", ""))
        names = [norm(s) for s in sidebar]
        i = next((k for k, n in enumerate(names) if n == c or c in n or n in c), None)
        if i is None:
            return None
    else:
        return None
    return SIDE_Y0 + SIDE_DY * i


def launch_chrome(tag, urls):
    prof = os.environ.get("CAPTURE_PROFILE") or f"{CAP_DIR}/profile-{tag}"
    sh("pkill", "-f", f"user-data-dir={prof}")
    time.sleep(1)
    if not os.environ.get("CAPTURE_PROFILE"):
        subprocess.run(["rm", "-rf", prof])
    os.makedirs(prof + "/Default", exist_ok=True)   # item 7: signed-out-by-policy (no sign-in chip), zoom 100 %, bookmarks bar off
    pf = prof + "/Default/Preferences"
    if not os.path.exists(pf):
        json.dump({"signin": {"allowed": False}, "browser": {"has_seen_welcome_page": True}, "bookmark_bar": {"show_on_all_tabs": False},
                   "partition": {"default_zoom_level": {"x": 0.0}}}, open(pf, "w"))
    if os.environ.get("CAPTURE_SET_MODE", "0") == "1":      # vsl's own seat: the output IS the 1920x1080 frame, so nothing is cropped or scaled
        sh("swaymsg", "output", OUT_NAME, "mode", f"{W}x{H}@60Hz")
    sh("pkill", "-f", "^/opt/google/chrome/chrome .*desk-vsl/.config/vsl-chrome")   # the desk's idle resident Chrome is not part of the shot
    sh("swaymsg", "focus", "output", OUT_NAME)
    sh("swaymsg", "seat", "seat0", "xcursor_theme", "Adwaita", "48")   # big, visible arrow in the recording
    # Popen, NOT `swaymsg exec`: sway splits its command on "," so --disable-features=Translate,SigninInterceptBubble was cut in two and Chrome
    # started with NO urls (a bare New Tab was recorded; found 2026-11-24, knowledge#18908).
    subprocess.Popen(["google-chrome", "--ozone-platform=wayland", "--force-device-scale-factor=1", f"--user-data-dir={prof}", "--no-first-run",
                      "--disable-sync", f"--window-size={W},{H}", *os.environ.get("CAPTURE_CHROME_FLAGS", "").split(), "--no-default-browser-check",
                      "--disable-features=Translate,SigninInterceptBubble", "--disable-infobars", "--new-window", *urls],
                     env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(40):
        time.sleep(.5)
        if '"app_id": "google-chrome"' in sh("swaymsg", "-t", "get_tree").stdout:
            break
    else:
        sys.exit("chrome window never appeared on the sway seat")
    time.sleep(1)
    # Target OUR window by pid: [app_id="google-chrome"] also matched another session's Chrome on this seat (2026-11-24: Russell's govbids
    # windows were resized and recorded into 3307 captures). The browser process whose argv carries our user-data-dir owns the window.
    pids = sh("pgrep", "-f", f"^/opt/google/chrome/chrome .*user-data-dir={prof} ").stdout.split()
    # vsl's seat is its own (desk-vsl runs nothing else), so app_id is safe here; the pid match picked a helper process (2026-11-24, #18908).
    crit = '[app_id="google-chrome"]'
    time.sleep(4)   # let the window finish mapping and restoring its size before sway places it (placed too early it re-centres)
    for _ in range(6):
        sh("swaymsg", crit + ' floating enable, resize set width %d px height %d px, move absolute position %d 0' % (W, H, OUT_X))
        time.sleep(1)
        try:
            def walk(n):
                yield n
                for c in n.get("nodes", []) + n.get("floating_nodes", []):
                    yield from walk(c)
            ws = [n for n in walk(json.loads(sh("swaymsg", "-t", "get_tree", "-r").stdout)) if n.get("pid") and n.get("app_id") == "google-chrome"]
            if not ws or any(r["rect"]["x"] == OUT_X and r["rect"]["y"] == 0 and r["rect"]["width"] == W and r["rect"]["height"] == H for r in ws):
                break
        except ValueError:
            break
    sh("swaymsg", crit + " focus")
    time.sleep(9)   # all three tabs finish loading


def take_seat_lock():
    """One capture at a time on the seat: a second run would record the first one's windows (knowledge#18869). Blocks up to 15 min."""
    import fcntl
    f = open(f"{CAP_DIR}/.seat.lock", "a")
    for _ in range(180):
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); return f
        except OSError:
            time.sleep(5)
    sys.exit("seat lock busy for 15 min: another capture is recording")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--job", required=True)
    ap.add_argument("--app", required=True)
    ap.add_argument("--diagram", required=True)
    ap.add_argument("--sidebar", default="", help="comma list of the app's sidebar labels, top to bottom")
    ap.add_argument("--timeline")
    ap.add_argument("--draft-beats", default="1,2,3")
    ap.add_argument("--intro", type=float, default=11.0)
    ap.add_argument("--tail", type=float, default=1.0, help="seconds kept after the last row ends")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--review", action="store_true", help="item 6: Gemini cursor review of the finished mp4 (<out>.cursor-review.json); non-zero under score 8")
    ap.add_argument("--scroll-notches", type=int, default=26)
    a = ap.parse_args()
    a.sidebar = [s.strip() for s in a.sidebar.split(",") if s.strip()]
    a.draft_beats = [int(x) for x in a.draft_beats.split(",") if x.strip()]
    intro, rows = load_rows(a)
    rows.sort(key=lambda r: r["start"])
    total = max(r["end"] for r in rows) + a.tail
    print(f"intro {intro}s, {len(rows)} rows, total {total:.1f}s", flush=True)

    lock = take_seat_lock()  # noqa: F841  (held until exit)
    launch_chrome(a.tag, [a.job, a.app, a.diagram])
    d = Driver(a.seed)
    d.key("ctrl+1"); time.sleep(.4)
    d.h.move_to(1650, 420)
    raw = a.out + ".raw.mp4"
    rec = subprocess.Popen(["wf-recorder", "-o", OUT_NAME, "-g", f"{OUT_X},0 {W}x{H}", "-f", raw, "-y", "-r", "30", "-c", "libx264",
                            "-p", "preset=ultrafast", "-p", "crf=20"], env=ENV, stderr=subprocess.DEVNULL)
    time.sleep(LEAD)
    d.t0 = time.monotonic()
    cur, beat_typed = 1, False
    try:
        first = rows[0]["start"]
        d.scroll_for(a.scroll_notches, .6, min(intro, first) - 2.0)
        for r in rows:
            tab, s = row_tab(r), r["start"]
            if tab and tab != cur:
                if tab == 2 or cur == 3 and tab == 2:
                    d.wait_until(s - 2.4); d.click(*TABS[tab])         # mouse click on the tab
                else:
                    d.wait_until(s - 1.9); d.key(f"ctrl+{tab}")        # keyboard
                cur = tab
            if "beat" in r:
                d.wait_until(s - 1.5)
                d.beat(int(r["beat"]), not beat_typed); beat_typed = True
                d.wait_until(s - .2); d.move(1100 + d.rng.uniform(-80, 80), 560 + d.rng.uniform(-60, 60))
            else:
                y = sidebar_y(r, a.sidebar)
                if y is not None:
                    d.wait_until(s - 1.0)
                    d.click(SIDE_X, y)
                    d.wait_until(s + .9); d.move(900 + d.rng.uniform(-60, 60), 300 + d.rng.uniform(-30, 60))
                elif tab == 2:
                    d.wait_until(s); d.move(900, 330)
        d.wait_until(total - .3)
        d.move(1500, 650)
        d.wait_until(total)
    finally:
        rec.send_signal(2)
        try:
            rec.wait(timeout=10)
        except subprocess.TimeoutExpired:
            rec.kill(); rec.wait()
    dim = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", raw],
                         capture_output=True, text=True).stdout.strip()
    crop = "" if dim == f"{W},{H}" else f"crop={W}:{H}:0:0,"    # item 7: no ffmpeg crop/scale of the page when the output is already 1920x1080
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{LEAD:.2f}", "-i", raw, "-t", f"{total:.2f}",
                        "-vf", f"{crop}fps=30,tpad=stop_mode=clone:stop_duration=60,scale=in_range=full:out_range=tv,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", a.out])
    if r.returncode:
        sys.exit("ffmpeg failed")
    os.remove(raw)
    print(json.dumps({"out": a.out, "seconds": round(total, 2), "size": f"{W}x{H}"}))
    if a.review:
        here = os.path.dirname(os.path.abspath(__file__))
        sys.exit(subprocess.run([sys.executable, os.path.join(here, "gemini_cursor_review.py"), a.out]).returncode)


if __name__ == "__main__":
    main()
