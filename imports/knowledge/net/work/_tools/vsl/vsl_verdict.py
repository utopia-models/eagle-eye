#!/usr/bin/env python3
"""vsl_verdict.py: the automatic post-take verdict (Tyler 2026-11-19: "AUTOMATICALLY RUN ANALYSIS POST VIDEO AND
EITHER RE RECORD OR GO TO THE NEXT"; Feature part of #14969).

  vsl_verdict.py watch                 the watcher (systemd user unit vsl-verdict.service, user eagle on Ra)
  vsl_verdict.py analyze TAKE [--script S.md] [--run-dir D] [--no-notify]   one take -> verdict (exit 0 NEXT, 1 RE-RECORD, 2 error)
  vsl_verdict.py --selftest

Watcher: polls the laptop's OBS output folder over ssh (host alias eth-wsl = kxdev@100.103.62.104, /mnt/c is C:, the folder
`C:\\Users\\ethde\\Videos\\VSL` named in net/work/vsl/obs/basic.ini and SETUP.md), READ-ONLY (ls/stat/scp, never touches OBS or
the laptop). A new .mkv whose size and mtime are unchanged for STABLE_S (5 s) is a finished recording: it is copied to a local
cache and analysed at once. Files already there when the watcher starts are marked seen, except one finished < 15 min ago.

Analysis (stock local ASR, no metered API: faster-whisper base.en int8 from the HF cache):
 1 words with timestamps
 2 script: the best-matching script among the Vizier prompter's current file and the run packages' speaker-script.md
   (`**Part N · Title**` or `## N · Title`); word accuracy in order (difflib over normalised words, ASR near-misses mapped
   onto the script vocabulary), per part kept %, skipped sentences, ad-libbed words
 3 delivery: length, per-part length, dead air (gap between spoken words), fillers, words/min, clipping + loudness
   (ffmpeg volumedetect + loudnorm), black frames, frozen frames; a frame at each part start is saved. The screen-tab-vs-cue
   check needs a vision read; there is no free local vision model on Ra, so it is SKIPPED and the verdict says so.
 4 VERDICT `NEXT` or `RE-RECORD <part> because <reason>` -> take-<n>.verdict.json (run dir + /srv/vsl/verdicts mirror), one
   fleetmail line to eagle on thread vsl (Eagle puts it on the laptop bar; this tool never touches the laptop).

Liveness: the watcher rewrites $STATE/liveness.json every poll, fleetmails architect once on start, and fleetmails architect
when it has been unable to reach the laptop for 10 min (once per outage).
"""
import argparse, difflib, glob, json, os, re, shlex, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]                      # .../knowledge
THRESH = {"kept_pct": 92.0, "max_s": 150.0, "part_max_s": 45.0, "dead_air_s": 3.0, "clip_db": -0.3,
          "quiet_lufs": -28.0, "clip_samples": 10, "black_s": 2.0, "freeze_s": 10.0, "wpm_lo": 100, "wpm_hi": 200}
STABLE_S = 5
POLL_S = 3
HOST = os.environ.get("VSL_VERDICT_HOST", "eth-wsl")
LAPTOP_DIR = os.environ.get("VSL_VERDICT_LAPTOP_DIR", "/mnt/c/Users/ethde/Videos/VSL")
LOCAL_SRC = os.environ.get("VSL_VERDICT_LOCAL_SRC")          # tests: a local folder instead of the laptop
STATE = Path(os.environ.get("VSL_VERDICT_STATE", str(Path.home() / ".local/state/vsl-verdict")))
MIRROR = Path(os.environ.get("VSL_VERDICT_MIRROR", "/srv/vsl/verdicts"))
PY_ASR = os.environ.get("VSL_VERDICT_ASR_PY", "/opt/voice-v3/venv/bin/python")
MODEL = os.environ.get("VSL_VERDICT_MODEL", "base.en")
PROMPTER = Path(os.environ.get("VSL_VERDICT_PROMPTER", str(Path.home() / ".local/state/vsl/prompter.md")))
ROOT = Path(os.environ.get("VSL_VERDICT_ROOT", str(REPO)))
SCRIPT_GLOBS = os.environ.get("VSL_VERDICT_SCRIPTS", ":".join([
    "net/work/upwork/one-shot/runs/*/speaker-script.md", "net/work/vsl/resul/*script*.md", "net/work/vsl/scripts/*.md",
    "net/work/vsl/*/*script*.md"])).split(":")
FILLERS = ["um", "uh", "er", "ah", "erm", "you know", "basically", "sort of", "kind of", "i mean"]


def norm(s):
    return re.sub(r"[^a-z0-9' ]", " ", s.lower().replace("\u2019", "'")).split()


def mmss(s):
    return f"{int(s // 60)}:{int(s % 60):02d}"


# ------------------------------------------------------------------ script
def parse_parts(text):
    """-> [{n,title,text}]. `**Part N · Title (Tab)**` / `## N · Title (30 s)` headings; spoken lines only (no [cue] lines)."""
    parts, cur = [], None
    for ln in text.splitlines():
        m = re.match(r"\s*(?:\*\*)?(?:#{1,3}\s*)?(?:Part\s+)?(\d+)\s*[\u00b7.:\-]\s*(.+?)(?:\*\*)?\s*$", ln)
        if m and (ln.lstrip().startswith(("**", "#"))):
            cur = {"n": int(m.group(1)), "title": re.sub(r"\s*[\(\[].*$", "", m.group(2)).strip(" *"), "lines": []}
            parts.append(cur)
        elif cur is not None:
            s = ln.strip()
            if s and not s.startswith(("[", "#", ">", "|", "---", "Read aloud", "Structure:")) and not re.match(r"\*\*\[", s):
                cur["lines"].append(s.lstrip("-* ").strip())
    for p in parts:
        p["text"] = " ".join(p["lines"])
    return [p for p in parts if norm(p["text"])]


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if len(norm(s)) >= 3]


def candidates():
    out = []
    if PROMPTER.exists():
        out.append(Path(os.path.realpath(PROMPTER)))
    for g in SCRIPT_GLOBS:
        out += [Path(p) for p in sorted(glob.glob(str(ROOT / g)))]
    seen, res = set(), []
    for p in out:
        if p not in seen and p.exists():
            seen.add(p); res.append(p)
    return res


def ngram_cover(script_words, spoken_set):
    return sum(1 for w in script_words if w in spoken_set) / max(1, len(script_words))


def pick_script(words, explicit=None):
    spoken = {w for w in norm(" ".join(x["w"] for x in words))}
    if explicit:
        p = Path(explicit)
        return p, parse_parts(p.read_text()), 1.0
    best = (None, [], 0.0)
    for i, p in enumerate(candidates()):
        try:
            parts = parse_parts(p.read_text())
        except Exception:
            continue
        sw = norm(" ".join(x["text"] for x in parts))
        if len(sw) < 20:
            continue
        # trigram overlap is a sharper identity than single words
        tri = lambda ws: {tuple(ws[k:k + 3]) for k in range(len(ws) - 2)}
        tt = tri(norm(" ".join(x["w"] for x in words)))
        st = tri(sw)
        sc = len(st & tt) / max(1, len(st))
        if i == 0 and PROMPTER.exists():
            sc += 0.05                      # the script on the bar is what he read
        if sc > best[2]:
            best = (p, parts, sc)
    return best


# ------------------------------------------------------------------ compare
def compare(parts, words):
    """Script words vs spoken words in order. -> per-part rows + totals."""
    sw, owner = [], []
    for pi, p in enumerate(parts):
        for w in norm(p["text"]):
            sw.append(w); owner.append(pi)
    vocab = sorted(set(sw))
    tw, tt = [], []
    for x in words:
        for w in norm(x["w"]):
            if w not in vocab:
                m = difflib.get_close_matches(w, vocab, n=1, cutoff=0.8)
                w = m[0] if m else w
            tw.append(w); tt.append((x["start"], x["end"]))
    sm = difflib.SequenceMatcher(None, sw, tw, autojunk=False)
    matched_s, matched_t = {}, {}
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            matched_s[a + k] = b + k; matched_t[b + k] = a + k
    rows, off = [], 0
    for pi, p in enumerate(parts):
        n = len(norm(p["text"]))
        idx = range(off, off + n)
        kept = sum(1 for i in idx if i in matched_s)
        ts = [tt[matched_s[i]][0] for i in idx if i in matched_s]
        te = [tt[matched_s[i]][1] for i in idx if i in matched_s]
        skipped = []
        pos = 0
        for s in sentences(p["text"]):
            ws = norm(s)
            k = sum(1 for j in range(off + pos, off + pos + len(ws)) if j in matched_s)
            if k / len(ws) < 0.6:
                skipped.append(s.strip()[:90])
            pos += len(ws)
        rows.append({"part": p["n"], "title": p["title"], "words": n, "kept": kept, "kept_pct": round(100 * kept / max(1, n), 1),
                     "start_s": round(min(ts), 2) if ts else None, "end_s": round(max(te), 2) if te else None,
                     "skipped_lines": skipped})
        off += n
    # order: part start times must be non-decreasing
    starts = [r["start_s"] for r in rows if r["start_s"] is not None]
    out_of_order = [rows[i]["part"] for i in range(1, len(rows))
                    if rows[i]["start_s"] is not None and rows[i - 1]["start_s"] is not None and rows[i]["start_s"] < rows[i - 1]["start_s"]]
    total_kept = sum(r["kept"] for r in rows)
    ad_lib = sum(1 for i in range(len(tw)) if i not in matched_t)
    return rows, {"kept": total_kept, "script_words": len(sw), "kept_pct": round(100 * total_kept / max(1, len(sw)), 1),
                  "adlib_words": ad_lib, "spoken_words": len(tw), "adlib_pct": round(100 * ad_lib / max(1, len(tw)), 1),
                  "out_of_order_parts": out_of_order}


# ------------------------------------------------------------------ media
def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def duration(p):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip() or 0)


def transcribe(p):
    code = ("import os,sys,json,subprocess;import numpy as np;from faster_whisper import WhisperModel as M;"
            "r=subprocess.run(['ffmpeg','-v','error','-i',sys.argv[1],'-vn','-f','f32le','-ac','1','-ar','16000','-'],capture_output=True,check=True).stdout;"
            "x=np.frombuffer(r,dtype=np.float32);m=M(sys.argv[2],compute_type='int8',cpu_threads=int(os.environ.get('VSL_VERDICT_THREADS','6')));"
            "s,_=m.transcribe(x,word_timestamps=True,language='en',vad_filter=False,beam_size=1,condition_on_previous_text=False);"
            "print(json.dumps([{'w':w.word.strip(),'start':w.start,'end':w.end} for g in s for w in (g.words or [])]))")
    r = subprocess.run([PY_ASR, "-I", "-c", code, str(p), MODEL], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("ASR failed: " + r.stderr.strip()[-300:])
    return json.loads(r.stdout)


def media_checks(p):
    """ONE ffmpeg pass (the box is shared and a second 1080p decode costs ~30 s): volumedetect + ebur128 on the audio,
    blackdetect + freezedetect on the picture scaled down to 5 fps x 320 px."""
    has_v = bool(sh(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(p)]).stdout.strip())
    has_a = bool(sh(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(p)]).stdout.strip())
    chains, maps = [], []
    if has_a:
        chains.append("[0:a]volumedetect,astats=metadata=0:reset=0,ebur128=framelog=quiet[a]"); maps += ["-map", "[a]"]
    if has_v:
        chains.append(f"[0:v]fps=5,scale=320:-2,blackdetect=d={THRESH['black_s']}:pix_th=0.10,freezedetect=n=-60dB:d={THRESH['freeze_s']}[v]"); maps += ["-map", "[v]"]
    e = sh(["ffmpeg", "-hide_banner", "-nostats", "-threads", "4", "-i", str(p), "-filter_complex", ";".join(chains)] + maps + ["-f", "null", "-"]).stderr
    mx = re.search(r"max_volume:\s*(-?[\d.]+) dB", e)
    mean = re.search(r"mean_volume:\s*(-?[\d.]+) dB", e)
    pk = re.findall(r"Peak count:\s*(\d+)", e)
    li = re.search(r"Integrated loudness:\s*\n\s*I:\s*(-?[\d.]+) LUFS", e)
    lv = {"max_db": float(mx.group(1)) if mx else None, "mean_db": float(mean.group(1)) if mean else None,
          "lufs": float(li.group(1)) if li else None,
          "peak_samples": max([int(x) for x in pk], default=None)}
    black = [{"from_s": float(a), "dur_s": float(d)} for a, d in re.findall(r"black_start:([\d.]+).*?black_duration:([\d.]+)", e)]
    fs = [float(x) for x in re.findall(r"freeze_start:\s*([\d.]+)", e)]
    fd = [float(x) for x in re.findall(r"freeze_duration:\s*([\d.]+)", e)]
    frozen = [{"from_s": a, "dur_s": d} for a, d in zip(fs, fd)]
    if len(fs) > len(fd):
        frozen.append({"from_s": fs[-1], "dur_s": None})
    return lv, {"has_video": has_v, "black": black, "frozen": frozen}


def part_frames(p, rows, out):
    got = []
    out.mkdir(parents=True, exist_ok=True)
    for r in rows:
        if r["start_s"] is None:
            continue
        f = out / f"part{r['part']}.jpg"
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{r['start_s'] + 1:.2f}", "-i", str(p), "-frames:v", "1", "-vf", "scale=480:-1", str(f)])
        if f.exists():
            got.append(str(f))
    return got


# ------------------------------------------------------------------ verdict
def analyze_take(take, script=None, run_dir=None, out_dir=None, words=None):
    t0 = time.time()
    take = Path(take)
    from concurrent.futures import ThreadPoolExecutor      # ASR and the ffmpeg checks run side by side (box is shared, load is high)
    ex = ThreadPoolExecutor(3)
    f_asr = ex.submit(transcribe, take) if words is None else None
    f_mc = ex.submit(media_checks, take)
    total = duration(take)
    words = words if words is not None else f_asr.result()
    sp, parts, match = pick_script(words, script)
    res = {"take": take.name, "thresholds": THRESH, "duration_s": round(total, 1), "asr": f"faster-whisper {MODEL} int8 (local)",
           "script": str(sp) if sp else None, "script_match": round(match, 2)}
    fails = []        # (part or "all", reason)
    if not parts or (not script and match < 0.15):
        res.update({"verdict": "UNMATCHED", "reason": f"no script matches the transcript (best {match:.0%}); nothing to compare, check length and audio only"})
        parts = []
    rows, tot = compare(parts, words) if parts else ([], {"kept_pct": None, "spoken_words": len(words), "adlib_words": None, "out_of_order_parts": []})
    res["parts"], res["words"] = rows, tot
    lv, vf = f_mc.result()
    spoken_t = [(w["start"], w["end"]) for w in words]
    gaps = [{"from_s": round(a[1], 1), "to_s": round(b[0], 1), "dur_s": round(b[0] - a[1], 1)}
            for a, b in zip(spoken_t, spoken_t[1:]) if b[0] - a[1] > THRESH["dead_air_s"]]
    speak_s = (spoken_t[-1][1] - spoken_t[0][0]) if len(spoken_t) > 1 else 0
    wpm = round(60 * len(words) / speak_s) if speak_s else None
    txt = " " + " ".join(norm(" ".join(w["w"] for w in words))) + " "
    fill = {f: len(re.findall(r"(?<= )" + re.escape(f) + r"(?= )", txt)) for f in FILLERS}
    fill = {k: v for k, v in fill.items() if v}
    res["delivery"] = {"length": mmss(total), "dead_air": gaps, "wpm": wpm, "fillers": fill, "filler_count": sum(fill.values()),
                       "audio": lv, "video": vf,
                       "screen_vs_cue": "SKIPPED: needs a vision read; no free local vision model on Ra (frames at each part start are in frames/)"}
    # ---- decide
    for r in rows:
        if r["start_s"] is None:
            fails.append((f"part {r['part']}", f"skipped (not found in the take: '{r['title']}')"))
        elif r["kept_pct"] < THRESH["kept_pct"]:
            why = f"only {r['kept_pct']}% of its words kept (need {THRESH['kept_pct']:.0f}%)"
            if r["skipped_lines"]:
                why += f"; skipped line '{r['skipped_lines'][0]}'"
            fails.append((f"part {r['part']}", why))
    for k, r in enumerate(rows):
        if r["start_s"] is not None:
            nxt = next((x["start_s"] for x in rows[k + 1:] if x["start_s"] is not None), total)
            r["length_s"] = round(nxt - r["start_s"], 1)
            if len(rows) > 1 and r["length_s"] > THRESH["part_max_s"]:
                fails.append((f"part {r['part']}", f"runs {r['length_s']} s (about 30 s each, limit {THRESH['part_max_s']:.0f})"))
    for pn in tot["out_of_order_parts"]:
        fails.append((f"part {pn}", "spoken out of order"))
    if tot["kept_pct"] is not None and tot["kept_pct"] < THRESH["kept_pct"] and not any(f[0].startswith("part") for f in fails):
        fails.append(("all", f"{tot['kept_pct']}% of script words kept in order (need {THRESH['kept_pct']:.0f}%)"))
    if total > THRESH["max_s"]:
        fails.append(("all", f"length {mmss(total)} is over the 2:30 cap"))
    for g in gaps:
        part = next((f"part {r['part']}" for r in rows if r["start_s"] is not None and r["start_s"] <= g["from_s"] <= (r["end_s"] or 0) + 5), "all")
        fails.append((part, f"dead air {g['dur_s']} s at {mmss(g['from_s'])} (limit {THRESH['dead_air_s']:.0f} s)"))
    if lv["max_db"] is not None and lv["max_db"] >= THRESH["clip_db"] and (lv["peak_samples"] or 0) >= THRESH["clip_samples"]:
        fails.append(("all", f"audio clips ({lv['peak_samples']} samples at {lv['max_db']} dB; limit: peak under {THRESH['clip_db']} dB or fewer than {THRESH['clip_samples']} samples at it)"))
    if lv["lufs"] is not None and lv["lufs"] < THRESH["quiet_lufs"]:
        fails.append(("all", f"audio too quiet ({lv['lufs']} LUFS, limit {THRESH['quiet_lufs']})"))
    for b in vf["black"]:
        fails.append(("all", f"black frames {b['dur_s']} s at {mmss(b['from_s'])}"))
    for f in vf["frozen"]:
        fails.append(("all", f"frozen picture from {mmss(f['from_s'])}" + (f" for {f['dur_s']:.0f} s" if f["dur_s"] else " to the end")))
    if not words:
        fails.append(("all", "no speech detected"))
    warn = []
    if wpm and not THRESH["wpm_lo"] <= wpm <= THRESH["wpm_hi"]:
        warn.append(f"speech rate {wpm} wpm (target {THRESH['wpm_lo']}-{THRESH['wpm_hi']})")
    if sum(fill.values()) > 6:
        warn.append(f"{sum(fill.values())} fillers")
    res["warnings"] = warn
    res["failures"] = [{"part": a, "reason": b} for a, b in fails]
    if res.get("verdict") == "UNMATCHED" and not fails:
        pass
    elif fails:
        # earliest named part first; whole-take faults when no part is named
        named = [f for f in fails if f[0] != "all"]
        a, b = (named or fails)[0]
        extra = len(fails) - 1
        res["verdict"] = "RE-RECORD"
        res["line"] = f"RE-RECORD {a} because {b}" + (f" (+{extra} more)" if extra else "")
    else:
        res["verdict"] = res.get("verdict") or "NEXT"
        res["line"] = "NEXT" if res["verdict"] == "NEXT" else "UNMATCHED: " + res["reason"]
    if res["verdict"] == "UNMATCHED":
        res["line"] = "UNMATCHED: " + res["reason"]
    # one number line next to its threshold
    kp = tot["kept_pct"]
    res["numbers"] = (f"kept {kp}% (>=92) | length {mmss(total)} (<=2:30) | peak {lv['max_db']} dB, {lv['peak_samples']} at peak (clip if >={THRESH['clip_samples']}) | "
                      f"dead air {len(gaps)} gap(s) >3 s | wpm {wpm} | fillers {sum(fill.values())} | adlib {tot.get('adlib_pct')}%")
    # write
    run = Path(run_dir) if run_dir else (sp.parent if sp and sp.parent.name != "scripts" and "runs" in sp.parts else None)
    dests = [d for d in (run, MIRROR) if d]
    n = 1
    for d in dests:
        if d.exists():
            n = max(n, 1 + max([int(m.group(1)) for f in d.glob("take-*.verdict.json") if (m := re.match(r"take-(\d+)\.verdict", f.name))] or [0]))
    res["n"], res["analysis_s"] = n, round(time.time() - t0, 1)
    out = Path(out_dir) if out_dir else None
    fr = part_frames(take, rows, (out or STATE / "frames" / take.stem) / "frames") if rows else []
    res["frames"] = fr
    for d in dests:
        try:
            d.mkdir(parents=True, exist_ok=True)
            (d / f"take-{n}.verdict.json").write_text(json.dumps(res, indent=1))
            res.setdefault("written", []).append(str(d / f"take-{n}.verdict.json"))
        except OSError as e:
            res.setdefault("write_errors", []).append(str(e))
    return res


def notify(res, who="eagle"):
    line = f"VERDICT {res['take']}: {res['line']} [{res['numbers']}]"
    state = STATE
    state.mkdir(parents=True, exist_ok=True)
    (state / "latest-verdict.txt").write_text(line + "\n")      # the line Eagle puts on the laptop bar
    r = sh(["fleetmail", "send", who, line[:900], "--thread", "vsl"])
    return r.returncode == 0, (r.stdout or r.stderr).strip()[:120]


# ------------------------------------------------------------------ watcher
def ls_source():
    """-> {name: (size, mtime)} of the .mkv files in the source."""
    if LOCAL_SRC:
        return {p.name: (p.stat().st_size, int(p.stat().st_mtime)) for p in Path(LOCAL_SRC).glob("*.mkv")}
    r = sh(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6", HOST,
            f"cd {shlex.quote(LAPTOP_DIR)} && stat -c '%s %Y %n' *.mkv"], timeout=20)
    if r.returncode and "No such file" not in r.stderr:
        raise RuntimeError(r.stderr.strip()[-200:])
    out = {}
    for ln in r.stdout.splitlines():
        s, m, n = ln.split(" ", 2)
        out[n] = (int(s), int(m))
    return out


def fetch(name, dest):
    dest.mkdir(parents=True, exist_ok=True)
    f = dest / name
    if LOCAL_SRC:
        sh(["cp", str(Path(LOCAL_SRC) / name), str(f)])
    else:
        r = sh(["scp", "-q", "-o", "BatchMode=yes", f"{HOST}:{LAPTOP_DIR}/{name}", str(f)], timeout=300)
        if r.returncode:
            raise RuntimeError("scp: " + r.stderr.strip()[-200:])
    return f


def load_seen():
    try:
        return set(json.loads((STATE / "seen.json").read_text()))
    except Exception:
        return None


def save_seen(s):
    (STATE / "seen.json").write_text(json.dumps(sorted(s)))


def heartbeat(**kw):
    STATE.mkdir(parents=True, exist_ok=True)
    kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    kw["epoch"] = int(time.time())
    (STATE / "liveness.json").write_text(json.dumps(kw))


def sync_root():
    """Best effort, off the critical path: keep the script tree at origin/main so a new package's speaker-script is known."""
    if (ROOT / ".git").exists():
        sh(["git", "-C", str(ROOT), "fetch", "-q", "origin", "main"], timeout=120)
        sh(["git", "-C", str(ROOT), "checkout", "-q", "--detach", "origin/main"], timeout=60)


def watch(once=False):
    STATE.mkdir(parents=True, exist_ok=True)
    seen = load_seen()
    hist, down_since, alerted = {}, None, False
    first = seen is None
    seen = seen or set()
    sh(["fleetmail", "send", "architect", "vsl-verdict watcher up: polling the laptop OBS folder every "
        f"{POLL_S} s, verdict within 60 s of a finished recording", "--thread", "vsl"])
    last_sync = 0
    while True:
        try:
            if time.time() - last_sync > 300 and not LOCAL_SRC:
                last_sync = time.time()
                try:
                    sync_root()
                except Exception:
                    pass
            cur = ls_source()
            if down_since:
                down_since, alerted = None, False
            if first:
                now = time.time()
                for n, (sz, mt) in cur.items():
                    if now - mt > 900:
                        seen.add(n)
                save_seen(seen); first = False
            for n, (sz, mt) in cur.items():
                if n in seen:
                    continue
                h = hist.get(n)
                if h and h[0] == (sz, mt):
                    if time.time() - h[1] >= STABLE_S and sz > 0:
                        seen.add(n); save_seen(seen)
                        process(n)
                else:
                    hist[n] = ((sz, mt), time.time())
            heartbeat(ok=True, files=len(cur), seen=len(seen), watching=f"{HOST}:{LAPTOP_DIR}" if not LOCAL_SRC else LOCAL_SRC)
        except Exception as e:
            down_since = down_since or time.time()
            heartbeat(ok=False, error=str(e)[:200])
            if time.time() - down_since > 600 and not alerted:
                alerted = True
                sh(["fleetmail", "send", "architect", f"vsl-verdict watcher cannot reach the laptop OBS folder for 10 min: {str(e)[:120]}", "--thread", "vsl"])
        if once:
            return 0
        time.sleep(POLL_S)


def process(name):
    t0 = time.time()
    try:
        f = fetch(name, STATE / "in")
        res = analyze_take(f)
        res["finished_to_verdict_s"] = round(time.time() - t0 + STABLE_S, 1)
        ok, msg = notify(res)
        sys.stderr.write(f"verdict {name}: {res['line']} ({res['finished_to_verdict_s']} s, mail {ok})\n")
    except Exception as e:
        sh(["fleetmail", "send", "eagle", f"VERDICT {name}: analysis FAILED ({str(e)[:140]}); judge this take by ear", "--thread", "vsl"])
        sys.stderr.write(f"verdict {name} failed: {e}\n")


# ------------------------------------------------------------------ selftest
def selftest():
    txt = ("**Part 1 \u00b7 Promise (Overview tab)**\nYou asked for someone to set up workflows. I built the working version first. It is running right now.\n\n"
           "**Part 2 \u00b7 Intake (Intake tab)**\nA lead lands in the system. The workflow checks for a conflict and creates the matter.\n")
    parts = parse_parts(txt)
    assert [p["n"] for p in parts] == [1, 2], parts
    ws = lambda s, t=0.0: [{"w": w, "start": t + 0.4 * i, "end": t + 0.4 * i + 0.3} for i, w in enumerate(s.split())]
    full = ws("You asked for someone to set up workflows I built the working version first It is running right now A lead lands in the system The workflow checks for a conflict and creates the matter")
    rows, tot = compare(parts, full)
    assert tot["kept_pct"] == 100.0, tot
    cut = ws("You asked for someone to set up workflows A lead lands in the system The workflow checks for a conflict and creates the matter")
    rows, tot = compare(parts, cut)
    assert rows[0]["kept_pct"] < 92 and rows[0]["skipped_lines"], rows[0]
    assert rows[1]["kept_pct"] == 100.0
    print("selftest ok:", tot["kept_pct"], "% kept; skipped:", rows[0]["skipped_lines"])
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("watch")
    a = sub.add_parser("analyze")
    a.add_argument("take"); a.add_argument("--script"); a.add_argument("--run-dir"); a.add_argument("--out"); a.add_argument("--no-notify", action="store_true")
    a.add_argument("--words")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.cmd == "watch":
        return watch()
    if args.cmd == "analyze":
        words = json.loads(Path(args.words).read_text()) if args.words else None
        res = analyze_take(args.take, args.script, args.run_dir, args.out, words)
        if not args.no_notify:
            res["mail"] = notify(res)
        print(json.dumps({k: res.get(k) for k in ("take", "verdict", "line", "numbers", "script", "script_match", "duration_s", "analysis_s", "warnings", "failures", "written")}, indent=1))
        return 0 if res["verdict"] == "NEXT" else 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
