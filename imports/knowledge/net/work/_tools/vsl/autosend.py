#!/usr/bin/env python3
"""autosend.py: the intro auto-send engine (knowledge#17826, Tyler's card 20:26 MST, fm:18739). PURE decision logic over the job record; it never sends.
The current Upwork one-shot decisions (intro vs full, timers, claims, copy) are one page: net/work/vsl/UPWORK-ONESHOT-DECISIONS.md
(newest wins). This engine follows it; a change there that this code does not match is a bug here.
A READY job gets a countdown of delay_min[fit] minutes (45 / 30 / 0 for high / mid / low fit, vsl/oneshot-auto.yaml `autosend:`).
  FULL VSL button or a voice claim ("full VSL on this one", "I'm on")  -> claim(): the timer STOPS, Eagle loads the job on the prompter;
        a voice claim also opens FULL MODE for full_mode_h hours: while it holds, NO job's timer runs (Tyler is on them himself).
  claimed but no recording_started within claimed_record_min -> the intro sends anyway.
  a recording that started stops the fallback (the take is the full VSL).
`status(job, now)` -> {state, send_at, remaining_s, label}; label is what Eagle Eye shows: "Intro sends in mm:ss".
States: waiting (countdown), claimed, recording, due (send the intro now), sent, held (full mode), not_ready.
`due_jobs(jobs, mode, now)` -> slugs the sender should send this tick. The send itself belongs to the upwork desk; this module only decides.
CLI: autosend.py selftest"""
import datetime as dt
import sys
from pathlib import Path

DEFAULTS = {"delay_min": {"high": 45, "mid": 30, "low": 0}, "default_fit": "mid", "fit_high_min": 80, "fit_low_max": 50,
            "claimed_record_min": 30, "full_mode_h": 4}


def _cfg(c=None):
    return dict(DEFAULTS, **((c or {}).get("autosend") or {}))


def parse(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) if s else None


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def fit_tier(job, c=None):
    """high | mid | low from job['fit'] (a tier name or a 0-100 score); no signal -> default_fit."""
    a = _cfg(c)
    f = job.get("fit")
    if f in ("high", "mid", "low"):
        return f
    if isinstance(f, (int, float)) and not isinstance(f, bool):
        return "high" if f >= a["fit_high_min"] else ("low" if f < a["fit_low_max"] else "mid")
    return a["default_fit"]


def full_mode(mode, now):
    """mode = {'until': ISO} or None."""
    u = parse((mode or {}).get("until"))
    return bool(u and now < u)


def open_full_mode(now, c=None):
    return {"until": iso(now + dt.timedelta(hours=_cfg(c)["full_mode_h"]))}


def claim(job, now, voice=False, mode=None, c=None):
    """Record a claim on the job. -> the (possibly new) full-mode dict: a voice claim opens it, the button claim leaves it as it was."""
    job["claimed_at"] = iso(now)
    job["claim_by"] = "voice" if voice else "button"
    return open_full_mode(now, c) if voice else mode


def status(job, now, mode=None, c=None):
    a = _cfg(c)
    t, ev = job.get("t", {}), job.get("events", [])
    if job.get("state") != "ready" or not t.get("ready"):
        return {"state": "not_ready", "send_at": None, "remaining_s": None, "label": ""}
    if t.get("vsl_sent") or job.get("intro_sent_at"):
        return {"state": "sent", "send_at": None, "remaining_s": None, "label": "Sent"}
    started = any(e["kind"] == "recording_started" for e in ev)
    if started:
        return {"state": "recording", "send_at": None, "remaining_s": None, "label": "Recording"}
    if job.get("claimed_at"):
        deadline = parse(job["claimed_at"]) + dt.timedelta(minutes=a["claimed_record_min"])
        rem = int((deadline - now).total_seconds())
        if rem <= 0:
            return {"state": "due", "send_at": iso(deadline), "remaining_s": 0, "label": "Not recorded in time: intro sends now"}
        return {"state": "claimed", "send_at": iso(deadline), "remaining_s": rem, "label": f"Claimed: record within {rem // 60:02d}:{rem % 60:02d}"}
    if job.get("take_type") == "full":   # picked FULL in the Eagle Eye triage (knowledge#18050): Tyler records it, the intro never auto-sends
        return {"state": "held", "send_at": None, "remaining_s": None, "label": "Full VSL picked: waiting for Tyler"}
    if full_mode(mode, now):
        return {"state": "held", "send_at": None, "remaining_s": None, "label": "Full mode: waiting for Tyler"}
    send_at = parse(t["ready"]) + dt.timedelta(minutes=a["delay_min"][fit_tier(job, c)])
    rem = max(0, int((send_at - now).total_seconds()))
    return {"state": "due" if rem == 0 else "waiting", "send_at": iso(send_at), "remaining_s": rem,
            "label": "Intro sends now" if rem == 0 else f"Intro sends in {rem // 60:02d}:{rem % 60:02d}"}


def due_jobs(jobs, mode, now, c=None):
    return [j["slug"] for j in jobs if status(j, now, mode, c)["state"] == "due"]


def selftest():
    T = parse("2026-11-24T12:00:00Z")
    m = lambda n: T + dt.timedelta(minutes=n)
    mk = lambda **k: dict({"slug": "x", "state": "ready", "t": {"ready": iso(T)}}, **k)
    ok = []
    ok += [status(mk(fit=90), m(10))["label"] == "Intro sends in 35:00"]                  # high: 45 min
    ok += [status(mk(fit="mid"), m(29))["remaining_s"] == 60, status(mk(fit=10), m(0))["state"] == "due"]   # mid 30; low 0
    ok += [status(mk(), m(30))["state"] == "due"]                                          # no fit = default mid
    ok += [status({"state": "building", "t": {}}, m(99))["state"] == "not_ready"]
    j = mk(fit=90)
    mode = claim(j, m(5), voice=True)
    ok += [status(j, m(6), mode)["state"] == "claimed", status(j, m(34), mode)["state"] == "claimed", status(j, m(35), mode)["state"] == "due"]   # 30 min to record
    j2 = mk(fit=90, claimed_at=iso(m(5)), events=[{"at": iso(m(8)), "kind": "recording_started"}])
    ok += [status(j2, m(99))["state"] == "recording"]                                       # recording stops the fallback
    other = mk(fit=10)
    ok += [status(other, m(1), mode)["state"] == "held", status(other, m(4 * 60 + 6), mode)["state"] == "due"]   # full mode holds 4 h, then expires
    ok += [claim(mk(), m(1), voice=False, mode=None) is None, due_jobs([mk(fit=10), mk(fit=90)], None, m(1)) == ["x"]]
    ok += [status(mk(fit=10, take_type="full"), m(99))["state"] == "held", status(mk(fit=10, take_type="intro"), m(1))["state"] == "due"]
    ok += [status(mk(intro_sent_at=iso(m(3))), m(99))["state"] == "sent"]
    print("self-test " + ("PASS" if all(ok) else f"FAIL {ok}"))
    return all(ok)


if __name__ == "__main__":
    sys.exit(0 if sys.argv[1:] == ["selftest"] and selftest() else 1)
