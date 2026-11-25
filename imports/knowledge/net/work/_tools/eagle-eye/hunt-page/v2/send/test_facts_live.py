"""Live replay tests of the facts path against the RUNNING Eagle Eye on Ra (never the real ledger: each test writes its own
temp ledger, and the throwaway cards are soft-deleted and the test key revoked at the end).

  python3 -m unittest -v send/test_facts_live.py

1 push: ledger.append() of a synthetic proposal_sent row flips the throwaway card to sent within 5 s
2 fallback: a plain `>>` row (no push) on a file watched by a transient systemd .path unit flips its card within 5 s
3 replay: re-delivering every old row changes nothing, and an older weaker fact never moves a stage backwards
4 missing mapping: a fact with no card and nothing to build one from is written to unmatched.jsonl, never dropped
"""
import json, os, subprocess, sys, tempfile, time, unittest, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EMIT_DIR = os.environ.get("EAGLE_EMIT_DIR", "/home/upwork/dev/utopia-models/knowledge/net/work/_tools/upwork")
sys.path.insert(0, EMIT_DIR)
import ledger, eagle_emit  # noqa: E402

API = eagle_emit.API
RUN = str(int(time.time()))


def mint():
    out = subprocess.run([str(ROOT / "node_modules/.bin/tsx"), "src/keys-cli.ts", "mint", f"facts-live-test-{RUN}", "--scopes",
                          "huntItems:write,huntItems:read,events:write,touches:read", "--ttl", "900"], cwd=ROOT, capture_output=True, text=True, check=True)
    return out.stdout.strip(), out.stderr.split("minted key ")[1].split(" ")[0]


def call(tok, method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"authorization": "Bearer " + tok, "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


class Live(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tok, cls.key_id = mint()
        cls.items = []
        cls.tmp = Path(tempfile.mkdtemp(prefix="facts-live-"))
        os.environ["EAGLE_EVENTS_TOKEN"] = cls.tok

    @classmethod
    def tearDownClass(cls):
        for i in cls.items:
            call(cls.tok, "DELETE", f"/rest/huntItems/{i}")
        subprocess.run(["systemctl", "--user", "stop", f"facts-live-{RUN}.path"], capture_output=True)
        subprocess.run([str(ROOT / "node_modules/.bin/tsx"), "src/keys-cli.ts", "revoke", cls.key_id], cwd=ROOT, capture_output=True)

    def card(self, n):
        job = f"~02999{RUN}{n:06d}"
        s, b = call(self.tok, "POST", "/rest/huntItems?upsert=true", {"huntType": "upwork", "externalId": job, "target": "facts live test",
            "signal": "throwaway test card", "signalAt": "2026-11-22T00:00:00Z", "upwork": {"title": f"facts live test {RUN} {n}", "postedAt": "2026-11-22T00:00:00Z"}})
        self.assertIn(s, (200, 201), b)
        self.items.append(b["data"]["createHuntItem"]["id"])
        return job, b["data"]["createHuntItem"]["id"]

    def wait_stage(self, item, stage, within=5.0):
        t0 = time.time()
        while time.time() - t0 < within:
            s, b = call(self.tok, "GET", f"/rest/huntItems/{item}")
            if b["data"]["huntItem"]["stage"] == stage:
                return time.time() - t0
            time.sleep(0.2)
        self.fail(f"card {item} not {stage} within {within}s (is {b['data']['huntItem']['stage']})")

    def row(self, job, pid, ev="proposal_sent", ts="2026-11-22T06:00:00Z"):
        return {"ts": ts, "event": ev, "job": job, "proposal_id": pid, "title": "facts live test", "arm": "F", "via": "test_facts_live"}

    def test_1_push_flips_card_within_5s(self):
        job, item = self.card(1)
        led = self.tmp / "push.jsonl"
        os.environ["EAGLE_EMIT"] = "1"           # a temp ledger never emits unless the test asks
        try:
            ledger.append(self.row(job, f"9{RUN}0000001"), str(led))
        finally:
            os.environ.pop("EAGLE_EMIT")
        dt = self.wait_stage(item, "sent")
        print(f"push: card sent {dt:.2f}s after the ledger write")

    def test_2_fallback_path_unit_flips_card_within_5s(self):
        job, item = self.card(2)
        led = self.tmp / "fallback.jsonl"
        led.write_text("")
        env = {"EAGLE_UPWORK_LEDGER": str(led), "EAGLE_FACTS_STATE": str(self.tmp / "state"), "EAGLE_EVENTS_TOKEN": self.tok,
               "EAGLE_HUNT_SEND_LOG": str(self.tmp / "none.log")}
        subprocess.run(["systemd-run", "--user", f"--unit=facts-live-{RUN}", f"--path-property=PathModified={led}",
                        *[f"--setenv={k}={v}" for k, v in env.items()], "/usr/bin/python3", str(HERE / "ledger_watch.py"),
                        "--source", "upwork-ledger"], check=True, capture_output=True)
        time.sleep(0.5)
        with open(led, "a") as f:               # a hand row: no push, only the path unit can deliver it
            f.write(json.dumps(self.row(job, f"9{RUN}0000002")) + "\n")
        dt = self.wait_stage(item, "sent")
        print(f"fallback: card sent {dt:.2f}s after a plain append (inotify path unit)")

    def test_3_replay_changes_nothing_and_never_moves_back(self):
        job, item = self.card(3)
        led = self.tmp / "replay.jsonl"
        rows = [self.row(job, f"9{RUN}0000003"), {"ts": "2026-11-22T06:01:00Z", "event": "vsl_sent", "note": f"proposal 9{RUN}0000003 sent", "file": "x.mp4", "via": "t"}]
        led.write_text("".join(json.dumps(r) + "\n" for r in rows))
        env = dict(os.environ, EAGLE_UPWORK_LEDGER=str(led), EAGLE_FACTS_STATE=str(self.tmp / "s3"))
        first = json.loads(subprocess.run([sys.executable, str(HERE / "ledger_watch.py"), "--source", "upwork-ledger"], env=env,
                                          capture_output=True, text=True, check=True).stdout.splitlines()[0])
        self.assertEqual((first["applied"], first["unchanged"], first["unmatched"]), (1, 1, 0), first)  # the arm-F proposal already set vsl sent
        before = call(self.tok, "GET", f"/rest/huntItems/{item}")[1]["data"]["huntItem"]
        again = json.loads(subprocess.run([sys.executable, str(HERE / "ledger_watch.py"), "--source", "upwork-ledger", "--from-start"],
                                          env=env, capture_output=True, text=True, check=True).stdout.splitlines()[0])
        self.assertEqual((again["applied"], again["unchanged"]), (0, 2), again)
        with open(led, "a") as f:               # an older, weaker fact: recorded before the send
            f.write(json.dumps({"ts": "2026-11-22T05:00:00Z", "event": "vsl_recorded", "job": job, "file": "take.mp4", "via": "t"}) + "\n")
        subprocess.run([sys.executable, str(HERE / "ledger_watch.py"), "--source", "upwork-ledger"], env=env, check=True, capture_output=True)
        after = call(self.tok, "GET", f"/rest/huntItems/{item}")[1]["data"]["huntItem"]
        self.assertEqual((after["stage"], after["vslStage"]), (before["stage"], before["vslStage"]))
        self.assertEqual((after["stage"], after["vslStage"]), ("sent", "sent"))

    def test_4_missing_mapping_is_reported(self):
        led = self.tmp / "orphan.jsonl"
        led.write_text(json.dumps({"ts": "2026-11-22T06:02:00Z", "event": "vsl_sent", "client": f"no-such-client-{RUN}", "file": "x.mp4", "via": "t"}) + "\n")
        st = self.tmp / "s4"
        env = dict(os.environ, EAGLE_UPWORK_LEDGER=str(led), EAGLE_FACTS_STATE=str(st))
        r = json.loads(subprocess.run([sys.executable, str(HERE / "ledger_watch.py"), "--source", "upwork-ledger"], env=env,
                                      capture_output=True, text=True, check=True).stdout.splitlines()[0])
        self.assertEqual(r["unmatched"], 1, r)
        u = [json.loads(l) for l in (st / "unmatched.jsonl").read_text().splitlines()]
        self.assertEqual(u[0]["http"], 422); self.assertIn("no card matches", u[0]["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
