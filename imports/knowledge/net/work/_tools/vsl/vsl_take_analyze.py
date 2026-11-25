#!/usr/bin/env python3
"""vsl_take_analyze.py — score how Eagle drove the screen against what Tyler said (knowledge#16542).

    vsl_take_analyze.py analyze TAKE.mp4 --script tyler-script.md --cues horus-script.md --out DIR
        [--route-log FILE.jsonl] [--refs DIR] [--vision-cmd CMD] [--words words.json] [--target-s N] [--fps 2]
    vsl_take_analyze.py --selftest

Inputs: the take, its speaker script (`## N · title (Ns) [screen: manager]` sections), its Eagle cue table
(horus-script.md; `do` cells name the tab and the next line as `(line '...' next)`).
1. Words with timestamps: `--words` JSON ([{w,start,end}]) else faster-whisper (VSL_WHISPER_PY, as vsl-captions.py).
2. Screen timeline, >= 2 fps. METHOD IS NAMED IN THE REPORT, in this order:
   route-log  (`--route-log` JSONL {t, screen[, x, y]} the app/driver emitted)
   frame-match (`--refs DIR` of <screen>.png|jpg reference stills; nearest 32x18 gray frame)
   vision     (`--vision-cmd CMD`: run per frame with the frame path appended, prints the screen label)
   With none of the three there is no honest screen identity and the run exits 2 saying so.
3. Per section: Tyler's start, expected screen, when it appeared, lag, wrong-screen intervals.
4. Eagle score: on-time %, mean lag, worst miss, dead air, cursor path. Tyler score: wpm, fillers, length.
Writes report.md + frames.jpg (strip) + analysis.json into --out; --notify fleetmails Eagle the misses and the Architect the summary.
"""
import argparse, json, os, re, subprocess, sys, tempfile
from pathlib import Path

ON_TIME_S = 1.0          # a screen up within 1 s of the first word counts as on time (the cue leads by 4 s, so late is a miss)
WRONG_MIN_S = 0.5        # a wrong-screen stretch shorter than this is a transition, not a miss
DEAD_AIR_S = 3.0         # a silence this long inside the take
FILLERS = ["um", "uh", "er", "ah", "like", "you know", "basically", "actually", "sort of", "kind of", "i mean"]


def norm(s):
    return re.sub(r"[^a-z0-9' ]", "", s.lower().replace("’", "'"))


# ------------------------------------------------------------------ parsing
def parse_sections(text):
    """`## 3 · Title (30 s) [screen: manager]` + spoken lines (no [bracket] cue lines) -> [{n,title,screen,text,target_s}]."""
    secs, cur = [], None
    for ln in text.splitlines():
        m = re.match(r"##\s+(\d+)\s*[·.:-]?\s*(.*)", ln)
        if m:
            cur = {"n": int(m.group(1)), "title": m.group(2).strip(), "screen": None, "lines": [], "target_s": None}
            sc = re.search(r"\[screen:\s*([^\]]+)\]", cur["title"], re.I)
            if sc:
                cur["screen"] = sc.group(1).strip().lower()
            ts = re.search(r"\((\d+)\s*s\)", cur["title"])
            if ts:
                cur["target_s"] = int(ts.group(1))
            cur["title"] = re.sub(r"\s*(\[screen:[^\]]*\]|\(\d+\s*s\))", "", cur["title"]).strip()
            secs.append(cur)
        elif cur is not None:
            s = ln.strip()
            if s and not s.startswith(("[", "#", ">", "-", "*", "|")):
                cur["lines"].append(s)
    for c in secs:
        c["text"] = " ".join(c["lines"])
    return [c for c in secs if c["text"]]


def parse_cues(text, tabs):
    """horus-script table -> [{id, line, screen}]: `line` the phrase of the next spoken line, `screen` the tab/beat named."""
    out = []
    for ln in text.splitlines():
        if not ln.startswith("|") or ln.startswith("|--") or "| id" in ln[:8]:
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        do = cells[3]
        nxt = re.search(r"line '([^']+)'\s*next", do)
        scr = None
        for t in tabs:
            if re.search(r"\b" + re.escape(t) + r"\b", do.lower()):
                scr = t
        out.append({"id": cells[0], "line": nxt.group(1) if nxt else None, "screen": scr, "do": do})
    return out


def find_phrase(words, phrase, start_i=0, n=4):
    """Index in `words` where the first `n` words of `phrase` occur in order (allowing one ASR slip), else None."""
    want = norm(phrase).split()[:n]
    if not want:
        return None
    toks = [norm(w["w"]).strip() for w in words]
    for i in range(start_i, len(toks) - len(want) + 1):
        hit = sum(1 for k, w in enumerate(want) if toks[i + k] == w)
        if hit >= max(1, len(want) - 1) and toks[i] == want[0]:
            return i
    return None


# ------------------------------------------------------------------ alignment + scoring
def expected_screens(sections, cues):
    """Section screen = its `[screen:]` tag, else the screen of the first cue whose next-line phrase opens inside it, else the previous one."""
    prev = None
    for s in sections:
        scr = s["screen"]
        if not scr:
            for c in cues:
                if c["line"] and c["screen"] and norm(c["line"]).split()[:3] and " ".join(norm(c["line"]).split()[:3]) in norm(s["text"]):
                    scr = c["screen"]
                    break
        s["screen"] = scr or prev
        prev = s["screen"]
    return sections


def align(sections, words, timeline, t_end):
    """-> per-section rows. timeline: [(t, label)] sorted. The section runs from its first word to the next section's first word."""
    idx, last = [], 0
    for s in sections:
        i = find_phrase(words, s["text"], last)
        idx.append(i)
        if i is not None:
            last = i
    rows = []
    for k, s in enumerate(sections):
        i = idx[k]
        if i is None:
            rows.append({"n": s["n"], "title": s["title"], "expected": s["screen"], "status": "not found in transcript"})
            continue
        t0 = words[i]["start"]
        nxt = next((idx[j] for j in range(k + 1, len(sections)) if idx[j] is not None), None)
        t1 = words[nxt]["start"] if nxt is not None else t_end
        label_at = lambda t: next((l for tt, l in reversed(timeline) if tt <= t), None)
        exp = s["screen"]
        row = {"n": s["n"], "title": s["title"], "expected": exp, "start_s": round(t0, 2), "end_s": round(t1, 2)}
        if not exp:
            row["status"] = "no expected screen (no [screen:] tag and no cue names a tab)"
            rows.append(row)
            continue
        on_at = label_at(t0)
        appear = next((t for t, l in timeline if t >= t0 - 6 and t <= t1 and l == exp and (t >= t0 or on_at == exp)), None)
        if on_at == exp:
            appear = t0   # was already up when he started: lag 0 (cue led the line)
        wrong, cur = [], None
        for t, l in timeline:
            if t < t0 or t >= t1:
                continue
            if l != exp and cur is None:
                cur = [t, l]
            elif cur and (l == exp or l != cur[1]):
                wrong.append((cur[0], t, cur[1]))
                cur = [t, l] if l != exp else None
        if cur:
            wrong.append((cur[0], t1, cur[1]))
        wrong = [w for w in wrong if w[1] - w[0] >= WRONG_MIN_S]
        row.update({
            "appear_s": None if appear is None else round(appear, 2),
            "lag_s": None if appear is None else round(max(0.0, appear - t0), 2),
            "wrong": [{"from_s": round(a, 2), "to_s": round(b, 2), "dur_s": round(b - a, 2), "showing": l} for a, b, l in wrong],
        })
        row["on_time"] = appear is not None and row["lag_s"] <= ON_TIME_S
        row["status"] = "ok" if row["on_time"] and not wrong else (
            f"never showed {exp}" if appear is None else
            (f"{exp} appeared {row['lag_s']} s late" if not row["on_time"] else "") +
            (f"{'; ' if not row['on_time'] else ''}wrong screen {sum(w[1]-w[0] for w in wrong):.1f} s (" +
             ", ".join(sorted({w[2] for w in wrong})) + ")" if wrong else ""))
        rows.append(row)
    return rows


def cursor_path(events, t0, t1):
    pts = [(e["x"], e["y"]) for e in events if t0 <= e.get("t", -1) < t1 and "x" in e and "y" in e]
    return round(sum(((a[0]-b[0])**2 + (a[1]-b[1])**2) ** .5 for a, b in zip(pts, pts[1:]))) if len(pts) > 1 else None


def score(rows, words, timeline, events, target_s, t_end):
    judged = [r for r in rows if "on_time" in r]
    lags = [r["lag_s"] for r in judged if r["lag_s"] is not None]
    miss = max(judged, key=lambda r: (r["lag_s"] if r["lag_s"] is not None else 1e9) + sum(w["dur_s"] for w in r["wrong"]), default=None)
    gaps = [(a["end"], b["start"]) for a, b in zip(words, words[1:]) if b["start"] - a["end"] >= DEAD_AIR_S]
    paths = {r["n"]: cursor_path(events, r["start_s"], r["end_s"]) for r in judged}
    nw = len(words)
    dur = (words[-1]["end"] - words[0]["start"]) if nw > 1 else 0
    txt = " " + norm(" ".join(w["w"] for w in words)) + " "
    fill = {f: len(re.findall(r"(?<= )" + re.escape(f) + r"(?= )", txt)) for f in FILLERS}
    fill = {k: v for k, v in fill.items() if v}
    return {
        "eagle": {
            "sections_judged": len(judged),
            "on_time_pct": round(100 * sum(1 for r in judged if r["on_time"] and not r["wrong"]) / len(judged), 1) if judged else None,
            "mean_lag_s": round(sum(lags) / len(lags), 2) if lags else None,
            "worst_miss": None if not miss or miss["status"] == "ok" else {"section": miss["n"], "what": miss["status"]},
            "dead_air": [{"from_s": round(a, 1), "to_s": round(b, 1)} for a, b in gaps],
            "cursor_path_px_by_section": paths if any(v is not None for v in paths.values()) else "n/a (no cursor data in the route log)",
        },
        "tyler": {
            "words": nw, "speaking_s": round(dur, 1), "wpm": round(60 * nw / dur) if dur else None,
            "fillers": fill, "filler_count": sum(fill.values()),
            "take_s": round(t_end, 1), "target_s": target_s,
            "vs_target_s": None if not target_s else round(t_end - target_s, 1),
        },
    }


# ------------------------------------------------------------------ media
def transcribe(mp4):
    # TODO (Tyler 2026-11-24): move to vsl-owned venv, nova not in the chain. /opt/voice-v3/venv is used when present (Ra); nova's venv is the fallback.
    _voice = "/opt/voice-v3/venv/bin/python"
    py = os.environ.get("VSL_WHISPER_PY") or (_voice if os.access(_voice, os.X_OK) else "/home/nova/.claude/private/comms-ingest/whisper-venv/bin/python")
    code = ("import sys,json,subprocess,array;from faster_whisper import WhisperModel as M;"
            "r=subprocess.run(['ffmpeg','-v','error','-i',sys.argv[1],'-f','f32le','-ac','1','-ar','16000','-'],capture_output=True,check=True).stdout;"
            "a=array.array('f');a.frombytes(r);import numpy as np;x=np.frombuffer(r,dtype=np.float32);"
            "m=M('large-v3-turbo',compute_type='int8');s,_=m.transcribe(x,word_timestamps=True,language='en');"
            "print(json.dumps([{'w':w.word.strip(),'start':w.start,'end':w.end} for g in s for w in (g.words or [])]))")
    cmd = [py, "-I", "-c", code, str(mp4)]
    if py.startswith("/home/nova"):
        cmd = ["sudo", "-n", "-u", "nova"] + cmd
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)


def duration(mp4):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)], capture_output=True, text=True)
    return float(r.stdout.strip())


def gray_frames(mp4, fps):
    """-> [(t, bytes 32x18 gray)] via one ffmpeg pass."""
    w, h = 32, 18
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vf", f"fps={fps},scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    n = len(raw) // (w * h)
    return [(i / fps, raw[i * w * h:(i + 1) * w * h]) for i in range(n)]


def ref_gray(path):
    w, h = 32, 18
    return subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                          capture_output=True, check=True).stdout


def classify_refs(frames, refs_dir):
    refs = {p.stem.lower(): ref_gray(p) for p in sorted(Path(refs_dir).iterdir()) if p.suffix.lower() in (".png", ".jpg", ".jpeg")}
    if not refs:
        raise SystemExit(f"no reference stills in {refs_dir}")
    mse = lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)
    return [(t, min(refs, key=lambda k: mse(f, refs[k]))) for t, f in frames]


def classify_vision(mp4, fps, cmd, out):
    d = Path(out) / "frames"
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", f"fps={fps},scale=640:-1", str(d / "f%05d.jpg")], check=True)
    tl = []
    for i, f in enumerate(sorted(d.glob("f*.jpg"))):
        r = subprocess.run(cmd.split() + [str(f)], capture_output=True, text=True)
        tl.append((i / fps, r.stdout.strip().lower()))
    return tl


def load_route_log(path):
    ev = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    tl = sorted((e["t"], str(e["screen"]).lower()) for e in ev if "screen" in e)
    return tl, [e for e in ev if "x" in e]


def strip(mp4, rows, out, fps_pick=None):
    """frames.jpg: one frame at the start of every section, in a row."""
    ts = [r["start_s"] for r in rows if "start_s" in r]
    if not ts:
        return None
    sel = "+".join(f"eq(n\\,{int(t*25)})" for t in ts[:12])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", f"select='{'+'.join(f'lt(abs(t-{t:.2f}),0.04)' for t in ts[:12])}',scale=240:-1,tile={min(len(ts),12)}x1",
                    "-frames:v", "1", str(Path(out) / "frames.jpg")], capture_output=True)
    return "frames.jpg" if (Path(out) / "frames.jpg").exists() else None


def report_md(take, method, rows, sc, strip_name):
    L = [f"# Take analysis: {Path(take).name}", "", f"Screen identity method: **{method}**.", ""]
    if strip_name:
        L += [f"![section starts]({strip_name})", ""]
    L += ["| § | section | Tyler starts | expected | screen up | lag | wrong-screen | verdict |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        w = "; ".join(f"{x['dur_s']} s on {x['showing']}" for x in r.get("wrong", [])) or ""
        L.append(f"| {r['n']} | {r['title']} | {r.get('start_s','?')} s | {r.get('expected') or '?'} | {r.get('appear_s','?')} s | {r.get('lag_s','?')} s | {w} | {r['status']} |")
    e, t = sc["eagle"], sc["tyler"]
    L += ["", "## Eagle (driving)", f"- On-time: {e['on_time_pct']}% of {e['sections_judged']} sections; mean lag {e['mean_lag_s']} s",
          f"- Worst miss: {e['worst_miss'] or 'none'}", f"- Dead air (>= {DEAD_AIR_S:.0f} s silence): {e['dead_air'] or 'none'}",
          f"- Cursor path: {e['cursor_path_px_by_section']}", "", "## Tyler (delivery, separate track)",
          f"- {t['words']} words in {t['speaking_s']} s = {t['wpm']} wpm; take {t['take_s']} s" + (f", {t['vs_target_s']:+} s vs target {t['target_s']} s" if t['target_s'] else ""),
          f"- Fillers: {t['fillers'] or 'none'} ({t['filler_count']})", ""]
    return "\n".join(L)


def cue_misses(rows):
    return [f"§{r['n']} {r['title']}: {r['status']} (Tyler started {r['start_s']} s; expected {r['expected']})" for r in rows if r.get("status") not in ("ok", None) and "start_s" in r]


def analyze(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    secs = parse_sections(Path(a.script).read_text())
    cues = parse_cues(Path(a.cues).read_text(), a.tabs.split(","))
    secs = expected_screens(secs, cues)
    words = json.loads(Path(a.words).read_text()) if a.words else transcribe(a.take)
    t_end = duration(a.take)
    events = []
    if a.route_log:
        tl, events = load_route_log(a.route_log); method = "route-log (the app/driver's own screen events)"
    elif a.refs:
        tl = classify_refs(gray_frames(a.take, a.fps), a.refs); method = f"frame-match against reference stills in {a.refs}, {a.fps} fps (no route log)"
    elif a.vision_cmd:
        tl = classify_vision(a.take, a.fps, a.vision_cmd, out); method = f"vision (`{a.vision_cmd}`) per frame at {a.fps} fps (no route log)"
    else:
        print("no route log, no --refs stills and no --vision-cmd: there is no screen identity to align against", file=sys.stderr)
        return 2
    rows = align(secs, words, tl, t_end)
    tgt = a.target_s or (sum(s["target_s"] or 0 for s in secs) or None)
    sc = score(rows, words, tl, events, tgt, t_end)
    st = strip(a.take, rows, out)
    md = report_md(a.take, method, rows, sc, st)
    (out / "report.md").write_text(md)
    (out / "analysis.json").write_text(json.dumps({"method": method, "sections": rows, "score": sc}, indent=1))
    print(md)
    if a.notify:
        miss = cue_misses(rows)
        subprocess.run(["fleetmail", "send", "eagle", "Take analysis cue misses: " + (" | ".join(miss) or "none") + f" — {out}/report.md", "--thread", "vsl-take"])
        subprocess.run(["fleetmail", "send", "architect", f"Take analysis {Path(a.take).name}: on-time {sc['eagle']['on_time_pct']}%, mean lag {sc['eagle']['mean_lag_s']} s, Tyler {sc['tyler']['wpm']} wpm, {sc['tyler']['filler_count']} fillers — {out}/report.md", "--thread", "vsl-take"])
    return 0


def selftest():
    script = "## 1 · Open (10 s)\n[horus] x\nI am going through your post right now and here is how.\n## 2 · Intake (10 s)\nThe system has seven boxes in one line today.\n## 3 · Money (10 s) [screen: manager]\nThe money you are chasing late is the part that costs you cash.\n"
    cues = "| id | on | lead | do | wait | fail |\n|---|---|---|---|---|---|\n| C1 | I am | 4 | hold ceo tab (line 'The system has seven' next) | | |\n"
    sec = expected_screens(parse_sections(script), parse_cues(cues, ["ceo", "manager"]))
    assert [s["screen"] for s in sec] == [None, "ceo", "manager"] or [s["screen"] for s in sec][1:] == ["ceo", "manager"], [s["screen"] for s in sec]
    sec[0]["screen"] = "ceo"
    ws = [{"w": w, "start": 0.4 * i, "end": 0.4 * i + 0.3} for i, w in enumerate(
        "I am going through your post right now and here is how The system has seven boxes in one line today The money you are chasing late is the part that costs you cash".split())]
    t3 = next(w["start"] for w in ws if w["w"] == "money") - 0.4
    tl = [(i / 2, "ceo") for i in range(int(t3 * 2))] + [(t3 + i / 2, "ceo" if i < 15 else "manager") for i in range(40)]
    rows = align(sec, ws, tl, 20.0)
    r3 = rows[2]
    assert r3["expected"] == "manager" and r3["lag_s"] >= 7 and r3["wrong"][0]["showing"] == "ceo", r3
    assert rows[0]["status"] == "ok" and rows[1]["status"] == "ok", rows[:2]
    s = score(rows, ws, tl, [], 30, 20.0)
    assert s["eagle"]["on_time_pct"] == 66.7 and s["eagle"]["worst_miss"]["section"] == 3, s["eagle"]
    assert "n/a" in s["eagle"]["cursor_path_px_by_section"]
    print("selftest ok: section 3 flagged,", r3["status"])
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("analyze")
    a.add_argument("take"); a.add_argument("--script", required=True); a.add_argument("--cues", required=True); a.add_argument("--out", required=True)
    a.add_argument("--route-log"); a.add_argument("--refs"); a.add_argument("--vision-cmd"); a.add_argument("--words")
    a.add_argument("--target-s", type=float); a.add_argument("--fps", type=float, default=2.0)
    a.add_argument("--tabs", default="diagram,demo,ceo,manager,cfo,controller")
    a.add_argument("--notify", action="store_true")
    args = p.parse_args()
    if args.selftest:
        return selftest()
    if args.cmd != "analyze":
        p.print_help(); return 1
    return analyze(args)


if __name__ == "__main__":
    sys.exit(main())
