#!/usr/bin/env python3
"""desk_observer.py: the send fact no agent has to remember. Watches the desk-upwork Chrome READ-ONLY over CDP target
discovery (Target.setDiscoverTargets: URL changes of each tab; it never attaches to a page, never sends input, never
navigates) and, when a tab lands on Upwork's post-submit page /nx/proposals/<id>?success, pushes a proposal_sent fact to
Eagle Eye with that proposal id and the job key from the tab's /nx/proposals/job/~<key>/apply/ page just before it.

This is the agent-independent source (11-22: the B2 proposal went out in the desk; the card stayed at "record"). The ledger
row proposals.py writes later is a second fact about the same send (it adds the arm, bid and video), idempotent at the server.
A fact the server cannot place (no card, no job) stays in pending.jsonl and is retried on the next event and every reconnect;
the nightly drift audit's desk check reads Chrome's own history as the net under this.

  desk_observer.py            run (systemd: eagle-desk-observer.service, Restart=always)
  desk_observer.py --once     connect, print the tabs' URLs, exit (smoke test)
"""
from __future__ import annotations

import json, os, re, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger_watch as LW  # noqa: E402  (eagle_emit + the shared state dir)

E = LW.eagle_emit
CDP = os.environ.get("EAGLE_DESK_CDP", "http://127.0.0.1:9402")
STATE = LW.STATE / "desk-observer"
APPLY = re.compile(r"upwork\.com/(?:nx|ab)/proposals/job/~?(0[12]\d{10,})/apply")
SUCCESS = re.compile(r"upwork\.com/(?:nx|ab)/proposals/(\d{15,})\?success")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Observer:
    def __init__(self, post=None, state=STATE):
        self.post = post or E.post
        self.state = Path(state)
        self.state.mkdir(parents=True, exist_ok=True)
        self.apply_job: dict[str, str] = {}          # targetId -> job key of the apply page that tab was on
        self.seen = set(self._read("seen.json", []))
        self.pending = self._read("pending.json", [])

    def _read(self, name, default):
        try:
            return json.loads((self.state / name).read_text())
        except (OSError, ValueError):
            return default

    def _write(self, name, v):
        p = self.state / name
        p.with_suffix(".tmp").write_text(json.dumps(v))
        p.with_suffix(".tmp").replace(p)

    def on_target(self, info: dict) -> dict | None:
        """One Target.targetCreated / targetInfoChanged -> the fact it implies, or None."""
        if info.get("type") != "page":
            return None
        tid, url = info.get("targetId"), info.get("url") or ""
        m = APPLY.search(url)
        if m:
            self.apply_job[tid] = "~" + m.group(1)
            return None
        m = SUCCESS.search(url)
        if not m or m.group(1) in self.seen:
            return None
        pid = m.group(1)
        job = self.apply_job.get(tid)
        fact = {"kind": "proposal_sent", "key": f"desk:proposal_sent:{pid}", "at": now(),
                "itemRef": {k: v for k, v in {"proposalId": pid, "job": job}.items() if v},
                "proof": {"proposal_id": pid, "url": url, "apply_job": job, "seen_by": "desk-upwork Chrome (CDP target discovery)"},
                "source": "desk-observer"}
        self.seen.add(pid)
        self._write("seen.json", sorted(self.seen))
        self.pending.append(fact)
        self.flush()
        return fact

    def flush(self):
        keep = []
        for f in self.pending:
            try:
                code, body = self.post([f])
            except Exception as e:
                code, body = 0, {"error": str(e)}
            if code >= 300:
                keep.append(f)
                print(f"{now()} pending {f['key']}: http {code} {str(body)[:160]}", flush=True)
            else:
                r = (body.get("data") or {}).get("applyFacts", [{}])[0]
                print(f"{now()} pushed {f['key']} -> {r.get('status')} item {r.get('itemId')} via {r.get('via')}", flush=True)
        self.pending = keep
        self._write("pending.json", keep)


def browser_ws():
    with urllib.request.urlopen(CDP + "/json/version", timeout=5) as r:
        return json.loads(r.read())["webSocketDebuggerUrl"]


def run(once=False):
    import websocket   # websocket-client
    obs, back = Observer(), 5
    while True:
        try:
            ws = websocket.create_connection(browser_ws(), timeout=3 if once else None, origin="http://127.0.0.1")
            ws.send(json.dumps({"id": 1, "method": "Target.setDiscoverTargets", "params": {"discover": True}}))
            print(f"{now()} watching desk-upwork Chrome ({CDP}); pending {len(obs.pending)}", flush=True)
            obs.flush()
            back = 5
            while True:
                msg = json.loads(ws.recv())
                if msg.get("method") in ("Target.targetCreated", "Target.targetInfoChanged"):
                    info = msg["params"]["targetInfo"]
                    if once:
                        print(info.get("type"), info.get("url"))
                    obs.on_target(info)
        except websocket.WebSocketTimeoutException:
            ws.close()
            return 0
        except Exception as e:
            if once:
                print(f"error: {type(e).__name__}: {e}")
                return 1
            print(f"{now()} desk Chrome not reachable ({type(e).__name__}); reconnect in {back}s", flush=True)
            time.sleep(back)
            back = min(back * 2, 60)


if __name__ == "__main__":
    sys.exit(run(once="--once" in sys.argv))
