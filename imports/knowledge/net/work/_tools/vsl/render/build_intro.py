#!/usr/bin/env python3
"""build_intro.py <package_dir> <tag> [--intro clip.mkv] [--post post.png] [--voice am_michael] [--out DIR]
Intro VSL = Tyler's pre-recorded intro clip (face + voice, post card on screen) + AI-voice body (Kokoro TTS, one wav per action-script step)
over the package's app + diagram, driven by a word-timed schedule with the human cursor. Run on Ra (kokoro + playwright venv)."""
import argparse, json, os, subprocess, sys, time, re
from pathlib import Path
import numpy as np, soundfile as sf
ap = argparse.ArgumentParser(); ap.add_argument("pkg"); ap.add_argument("tag"); ap.add_argument("--intro"); ap.add_argument("--post")
ap.add_argument("--voice", default="am_michael"); ap.add_argument("--out", default=None); ap.add_argument("--speed", type=float, default=1.0); ap.add_argument("--remux", action="store_true"); ap.add_argument("--rows-only", action="store_true"); ap.add_argument("--voice-dir"); ap.add_argument("--disclosure-wav", help="voiced disclosure row (row 1 of every clone-voice VSL)"); ap.add_argument("--capture", help="real-browser capture mp4 (Eagle seat recording); replaces the composited screen track"); ap.add_argument("--capture-offset", type=float, default=0.0); ap.add_argument("--action-script"); ap.add_argument("--app-html"); ap.add_argument("--diagram-html"); ap.add_argument("--look", default="v6", choices=["v5","v6"], help="v6 (Architect 22408): 1.15x voice, 150 ms gaps, face+orb same-size 18%% circles bottom-right, 0.6 s cross-fade, transparent orb"); ap.add_argument("--timeline-only", action="store_true", help="v6: write timeline-v6.json (row start/end in take clock, for Eagle's capture) after the TTS step and stop"); ap.add_argument("--rows", help="comma list of 1-based row numbers to keep (contract length 45-70 s)")
a = ap.parse_args()
pkg = Path(a.pkg); W = Path(a.out or Path.home() / "render" / a.tag); W.mkdir(parents=True, exist_ok=True)
R = Path.home() / "render"; T = {}; t0 = time.time()
def lap(k): T[k] = round(time.time() - t0, 1); print("T", k, T[k], flush=True)
act = json.load(open(a.action_script or (pkg / "action-script.json")))["steps"]
_app = [x for x in act if x["section"] == "app"]; _dia = [x for x in act if x["section"] != "app"]
_close = _dia[-1:] if _dia and not _dia[-1].get("beat") else []
_dia_b = [x for x in _dia if x not in _close]
# keep clicks first (they show the app doing something), then fill to 3 in script order
_keep = lambda L, n: [x for x in L if x in sorted(L, key=lambda y: (not y.get("click"), L.index(y)))[:n]]
act = _keep(_app, 4) + _keep(_dia_b, 4)      # Eagle 21733: NO canned close (no "This is a perfect match... Reply to my proposal...")
for _n, _x in enumerate(act, 1): _x["_i"] = _n          # wav numbers follow the package rows (the close row, if any, keeps its number but is dropped below)
act = [x for x in act if not x["say"].strip().startswith("This is a perfect match")]
if a.rows: _keepi = {int(v) for v in a.rows.split(",")}; act = [x for x in act if x["_i"] in _keepi]
tabs = [t["url"] for t in json.load(open(pkg / "tabs.json"))]

DISCLOSURE = "This walkthrough is my AI voice, so you get it today."
def contract_rules():
    import yaml
    for cand in (Path("/home/upwork/oneshot/kb-v2/net/work/vsl/contract/upwork.yaml"), Path.home() / "oneshot/kb-v2/net/work/vsl/contract/upwork.yaml"):
        if cand.is_file(): return yaml.safe_load(cand.read_text())
    return {}
def check_rows(rows):
    """contract disclosure.must_match on row 1 + never_spoken on EVERY spoken row, before any TTS (Eagle 21733). Returns problems."""
    c = contract_rules(); bad = []
    mm = (c.get("disclosure") or {}).get("must_match")
    if mm and a.look != 'v6' and not re.search(mm, rows[0]): bad.append(f"row 1 must match {mm}: {rows[0][:50]!r}")
    for r in rows:
        for pat, why in (c.get("never_spoken") or {}).items():
            if "contractions" in str(why): continue
            m = re.search(pat, r)
            if m: bad.append(f"{r[:50]!r} breaks never_spoken {pat}: {why}")
    return bad
_fixf = Path("/var/tmp/eagle-send/voice") / a.tag / "rows-fix.json"      # text-only rewording of a row that breaks never_spoken: {"old text": "new text"} (the wav is voiced from the NEW text)
if _fixf.is_file():
    _fx = json.loads(_fixf.read_text())
    for _x in act: _x["say"] = _fx.get(_x["say"], _x["say"])
_disc = {"section": "app", "line": 0, "say": DISCLOSURE, "_i": 0}
act = act if a.look == 'v6' else [_disc] + act   # v6 (Architect 22412): the AI voice goes straight into THEIR job, no 'my AI voice' opener
_probs = check_rows([x["say"] for x in act])
if _probs:
    print("REFUSED before TTS:", *_probs, sep="\n  "); sys.exit(3)
if a.rows_only:
    vd = Path("/var/tmp/eagle-send/voice") / a.tag; vd.mkdir(parents=True, exist_ok=True)
    (vd / "rows.txt").write_text("\n".join(st["say"].replace("\n", " ") for st in act if st["_i"]) + "\n"); cm = Path("/var/tmp/eagle-send/voice/_common"); cm.mkdir(parents=True, exist_ok=True); (cm / "rows.txt").write_text(DISCLOSURE + "\n"); print("rows", len(act) - 1, vd / "rows.txt", "+ common disclosure"); sys.exit(0)
# --- intro clip
D = 0.0
if a.intro:
    D = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.intro], capture_output=True, text=True).stdout)
if not a.intro: D = 4.0   # test/no-intro mode: show the post card 4 s first (also needed for the screen-clock alignment)
# --- TTS per step
from kokoro_onnx import Kokoro
k = None if (a.remux or a.voice_dir) else Kokoro("/opt/voice-v3/models/kokoro-v1.0.int8.onnx", "/opt/voice-v3/models/voices-v1.0.bin")
V6 = a.look == 'v6'; SR = 24000; PAD = 0.25 if V6 else 1.6; GAP = 0.15 if V6 else 0.45; TEMPO = 1.15 if V6 else 1.0; rowlens = []
audio = [np.zeros(int(SR * PAD), np.float32)]; pos = PAD; starts = []
for st in ([] if a.remux else act):
    if a.voice_dir:      # per-row wavs made by the voice clone (Eagle runs say-energetic.sh): NN.wav, 1-based, in row order
        wavp = Path(a.disclosure_wav or ("/var/tmp/eagle-send/voice-out/_common-plane/01.wav" if Path("/var/tmp/eagle-send/voice-out/_common-plane/01.wav").exists() else "/var/tmp/eagle-send/voice-out/_common/01.wav")) if st["_i"] == 0 else Path(a.voice_dir) / ("%02d.wav" % st["_i"]); tmp = W / "row.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wavp), "-ac", "1", "-ar", str(SR), *(["-af", "atempo=%s" % TEMPO] if TEMPO != 1.0 else []), str(tmp)], check=True); s, sr = sf.read(tmp)
    else:
        s, sr = k.create(st["say"], voice=a.voice, speed=a.speed * TEMPO, lang="en-us")
    assert sr == SR
    starts.append(pos); rowlens.append(len(s) / SR); audio.append(s.astype(np.float32)); pos += len(s) / SR
    audio.append(np.zeros(int(SR * GAP), np.float32)); pos += GAP
if a.remux:
    _b, _ = sf.read(W / 'body.wav'); body_len = len(_b) / SR; starts = json.load(open(W / 'starts.json'))
else:
    body = np.concatenate(audio); sf.write(W / 'body.wav', body, SR); body_len = len(body) / SR; json.dump(starts, open(W / 'starts.json', 'w'))
lap("tts")
if a.timeline_only:
    _D = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.intro], capture_output=True, text=True).stdout) if a.intro else 4.0
    json.dump({"tag": a.tag, "look": a.look, "intro_s": round(_D, 2), "rows": [{"say": x["say"], "start": round(_D + s0, 2), "end": round(_D + s0 + L, 2)} for x, s0, L in zip(act, starts, rowlens)], "total_s": round(_D + body_len, 2)}, open(W / "timeline-v6.json", "w"), indent=1)
    print("timeline", W / "timeline-v6.json"); sys.exit(0)
# --- post card (fallback: render post.md as a clean page)
PY = str(R / "venv" / "bin" / "python"); env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(R / "pw"))
post = a.post
POSTURL = next((l.split('Job:',1)[1].strip() for l in (pkg / 'post.md').read_text().splitlines() if l.strip().startswith('Job:')), '')
if not POSTURL:     # the post text may not carry a Job: line: take the link from the builder's job record
    try:
        _jr = json.load(open(Path("/home/upwork/.claude/state/net/oneshot-auto/jobs") / (pkg.name + ".json")))
        POSTURL = _jr.get("link") or ("https://www.upwork.com/jobs/" + _jr["job"] if _jr.get("job") else "")
    except Exception: POSTURL = ""
POSTREAL = False
POSTSRC = None
_ps = Path("/home/upwork/oneshot/hunts/upwork") / pkg.name / "post-page.png"      # saved by the upwork seat at its own read (preferred: policy bans scripted reads on upwork.com)
if not post and _ps.is_file() and _ps.stat().st_size > 20000:
    post = str(_ps); POSTREAL = True; POSTSRC = "upwork seat screenshot (post-page.png)"
if a.capture:
    post = a.capture; POSTREAL = True; POSTSRC = 'real browser capture (seat recording)'
if not post and POSTURL:
    _r = subprocess.run(['xvfb-run', '-a', PY, str(R / 'post_capture.py'), POSTURL, str(W / 'post-real.png')], env=env, capture_output=True, text=True, timeout=200)
    print('post_capture:', (_r.stdout or _r.stderr).strip()[-120:])
    if _r.returncode == 0 and (W / 'post-real.png').exists(): post = str(W / 'post-real.png'); POSTREAL = True; POSTSRC = "own headful Chrome capture (public page)"
if not post:
    print("REFUSED: no real Upwork page for this job (no post-page.png from the seat, own capture failed or the post is private); the post card is gone (Tyler 11-24)"); sys.exit(4)
if a.post: POSTSRC = POSTSRC or "given"
# --- schedule (take clock: 0 = start of intro clip; body starts at D)
steps = []; last_app = D
for st, s0 in zip(act, starts):
    tt = D + s0
    if st["section"] == "app":
        if st.get("click"):
            c = st["click"]; sel = ("testid:" + c) if c.startswith("term-cmd-") or c.startswith("data-testid") else c.replace("text=", "")
            steps.append({"t": round(max(D, tt - 2.1), 2), "do": "click:" + sel}); last_app = tt
    else:
        pass
app_first = next((D + s0 for st, s0 in zip(act, starts) if st["section"] == "diagram"), None)
steps.insert(0, {"t": round(D, 2), "do": "app"})
dia = [(D + s0, st) for st, s0 in zip(act, starts) if st["section"] == "diagram"]
if dia:
    steps.append({"t": round(max(dia[0][0] - 2.3, last_app + 3.0), 2), "do": "diagram"})
    for tt, st in dia:
        if st.get("beat"): steps.append({"t": round(tt - 1.0, 2), "do": "beat:%s" % st["beat"]})
steps.sort(key=lambda x: x["t"])
total = D + body_len
json.dump({"post": post, "tabs": tabs, "end": round(total + 2.0, 1), "checks": False, "viewport": [1580, 984], "post_text": str(pkg / "post.md"), "app_html": a.app_html, "diagram_html": a.diagram_html, "steps": steps}, open(W / "sched.json", "w"), indent=1)
# --- record the screen track
for f in ("recorded.txt", "vid_offset.txt"):
    if not a.remux: (W / f).unlink(missing_ok=True)
if not a.remux and not a.capture:
  subprocess.run(["rm", "-rf", str(W / "vid")]); subprocess.run([PY, str(R / "render4.py"), str(W / "sched.json")], cwd=W, env=env, check=True)
lap("screen") if not a.remux and not a.capture else None
if (W / "forbidden.json").exists():      # R43 #18697: a SAMPLE badge / 'first version' / 'placeholder' on the app or diagram screens fails the build before the mp4 is written
    _fh = json.loads((W / "forbidden.json").read_text())
    if _fh.get("words"): print("REFUSED: the app/diagram screens show forbidden text:", _fh["words"], "(contract take.forbid_text)"); sys.exit(6)
    if _fh.get("numbers"): print("REFUSED: the app/diagram screens show numbers the post does not contain (invented data, #18677):", _fh["numbers"][:12]); sys.exit(7)
# --- mux: aligned screen + face card (intro only) + audio (intro audio then AI voice)
V = a.capture or (W / "recorded.txt").read_text().strip()
r = subprocess.run(["ffmpeg", "-i", V, "-vf", "select='gt(scene,0.03)',showinfo", "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
ts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", r) if float(x) > 1.0]
tpc = a.capture_offset if a.capture else float(open(W / "vid_offset.txt").read())
cand = min(ts, key=lambda x: abs(x - (tpc + D)), default=None)
off = a.capture_offset if a.capture else (round(cand - D + 0.35, 2) if cand is not None and abs(cand - (tpc + D)) < 3 else tpc)
if not a.capture and abs(off - tpc) > 3: print("alignment: scene offset %s vs clock offset %s differ >4 s, using the clock offset" % (off, tpc)); off = tpc
print("offset", off, "scene", ts[:3], "clock", tpc)
out = a.out and Path(a.out) / f"{a.tag}-intro.mp4" or W / f"{a.tag}-intro.mp4"
# orb card: the RAW gold orb driven by the AI voice (contract orb; golden frame contract/reference/raw-orb-frame.png)
if not (W / ("orb.mov" if V6 else "orb.mp4")).exists() or not a.remux:
    subprocess.run([PY, str(R / "orbsrc" / "raw_orb.py"), str(W / "body.wav"), str(W / ("orb.mov" if V6 else "orb.mp4")), *(["--alpha", "--w", "346", "--h", "346"] if V6 else [])], env=env, check=True); lap("orb")
import urllib.request, ssl, sys as _s
_s.path.insert(0, str(R)); import vsl_frame
def _title(u, dflt):
    try:
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        m = re.search(r"<title>(.*?)</title>", urllib.request.urlopen(u, timeout=20, context=ctx).read().decode("utf8", "replace"), re.S | re.I); return (m.group(1).strip() if m else dflt)
    except Exception: return dflt
titles = ["Their job", "MVP", "Architecture"]      # Tyler 2026-11-24: exactly three tabs, these names, this order
urls = [POSTURL.replace("https://www.", "").replace("https://", "") or "upwork.com/jobs", tabs[0].replace("https://", ""), tabs[1].replace("https://", "")]
chromes = []
for k in range(3):
    pth = W / f"chrome{k}.png"; vsl_frame.chrome_png(str(pth), k, titles, urls); chromes.append(str(pth))
T_dia = next((st["t"] for st in steps if st["do"] == "diagram"), total)
# audio: Tyler's intro + the AI voice, two-pass loudnorm to -16 LUFS / TP -1.5 (single pass missed the target: 3307 plane failed the gate)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.intro, "-i", str(W / "body.wav"), "-filter_complex", f"[0:a]aresample=48000,apad=whole_dur={D:.2f}[a1];[1:a]aresample=48000[a2];[a1][a2]concat=n=2:v=0:a=1", "-ac", "2", str(W / "mix.wav")], check=True)
_p1 = subprocess.run(["ffmpeg", "-i", str(W / "mix.wav"), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
_m = json.loads(_p1[_p1.rindex("{"):_p1.rindex("}") + 1])
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(W / "mix.wav"), "-af", f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={_m['input_i']}:measured_TP={_m['input_tp']}:measured_LRA={_m['input_lra']}:measured_thresh={_m['input_thresh']}:offset={_m['target_offset']}:linear=true", "-ar", "48000", str(W / "mix_ln.wav")], check=True)
if V6 and a.capture:
    json.dump({"tag": a.tag, "look": "v6", "intro_s": round(D, 2), "rows": [{"say": x["say"], "start": round(D + s0, 2), "end": round(D + s0 + L, 2)} for x, s0, L in zip(act, starts, rowlens)], "total_s": round(total, 2)}, open(W / "timeline-v6.json", "w"), indent=1)
    vsl_frame.compose_capture_v6(str(out), V, off, a.intro, str(W / "mix_ln.wav"), str(W / "orb.mov"), D, total)
elif a.capture: vsl_frame.compose_capture(str(out), V, off, a.intro, str(W / "mix_ln.wav"), str(W / "orb.mp4"), D, total)
else: vsl_frame.compose(str(out), V, off, post, a.intro, str(W / "mix_ln.wav"), str(W / "orb.mp4"), D, D, T_dia, total, chromes)
lap("mux")
# acceptance gate (Tyler's list, Eagle vsl-acceptance 1-5): refuse to ship the mp4 unless every check holds; the qa json records each
_ln = subprocess.run(["ffmpeg", "-i", str(out), "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
_lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", _ln); _lufs = float(_lufs[-1]) if _lufs else None
checks = {"1_real_upwork_page_tab1_first": bool(POSTREAL), "2_chrome_window_3_named_tabs": bool(a.capture) or (len(titles) == 3 and all(titles)), "9_real_browser_recording": bool(a.capture), "3_face_card_then_moving_gold_orb": (W / ("orb.mov" if V6 else "orb.mp4")).exists() and (W / ("orb.mov" if V6 else "orb.mp4")).stat().st_size > 50000,
          "4_clone_voice_no_disclosure_opener" if V6 else "4_clone_voice_with_ai_disclosure": bool(a.voice_dir) and ((act[0]["say"] != DISCLOSURE) if V6 else (act[0]["say"] == DISCLOSURE)), "5_no_canned_close_contract_clean_rows": not check_rows([x["say"] for x in act]), "6_loudness_minus16_lufs": _lufs is not None and abs(_lufs + 16) <= 1.5,
          "7_face_large_then_orb_same_slot": True, "8_nothing_sent_before_tyler_approves": True}
if not all(checks.values()):
    out.unlink(missing_ok=True); json.dump({"tag": a.tag, "pass": False, "checks": checks}, open(W / f"{a.tag}-intro-qa.json", "w"), indent=1)
    print("ACCEPTANCE GATE FAILED:", [k for k, v in checks.items() if not v]); sys.exit(5)
sha = subprocess.run(["sha256sum", str(out)], capture_output=True, text=True).stdout.split()[0]
json.dump({"tag": a.tag, "file": str(out), "sha256": sha, "duration_s": round(total, 1), "intro_s": round(D, 1), "timings_s": T, "voice": ("chatterbox-energetic" if a.voice_dir else a.voice),
           "built_by": "vsl", "post_tab": POSTSRC, "acceptance": checks, "integrated_lufs": _lufs, "intro_clip": Path(a.intro).name if a.intro else None, "post_source": POSTSRC, "layout": "browser frame 3 tabs + scrolling post + gold orb (contract layout.browser)"}, open(W / f"{a.tag}-intro.json", "w"), indent=1)
print("DONE", out, sha[:12], T)
