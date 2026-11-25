"""oneshot_auto.py: arrival -> job record once, the build stamps every stage, a failing gate or an empty author step blocks with its reason, the
feed carries ET stamps (Tyler 2026-11-22 6:45 AM ET). The self-test holds the cases; this runs it under the suite."""
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


class OneshotAuto(unittest.TestCase):
    def test_self_test(self):
        r = subprocess.run([sys.executable, str(HERE / "oneshot_auto.py"), "--self-test"], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("self-test PASS", r.stdout)


class Attempts(unittest.TestCase):
    """chief 16940: every failed or killed attempt leaves its FIRST real error line in the job record's attempts list."""

    def test_record_attempt_keeps_only_the_first_line_and_appends(self):
        import oneshot_auto as A
        j = {"t": {"build_started": "2026-11-23T05:00:00Z"}}
        A.record_attempt(j, "authored", "KeyError: 'say' (at gen_scripts.py:31 in say)\nTraceback (most recent call last):\n  File x")
        A.record_attempt(j, "app", "build exceeded 10 min and was killed")
        self.assertEqual([a["error"] for a in j["attempts"]], ["KeyError: 'say' (at gen_scripts.py:31 in say)", "build exceeded 10 min and was killed"])
        self.assertEqual(j["attempts"][0]["build_started"], "2026-11-23T05:00:00Z")
        A.record_attempt(j, "app", "")
        self.assertEqual(j["attempts"][2]["error"], "(no message)")


class ReadyWindowAndStamp(unittest.TestCase):
    """Architect 18196: the ready-unsent count ignores packages posted over 12 h ago, and a send stamps the job record."""

    def test_window_excludes_old_and_sent(self):
        import oneshot_auto as A
        from datetime import timedelta
        now = A.now()
        jobs = {
            "fresh": {"slug": "fresh", "state": "ready", "t": {"posted": A.iso(now - timedelta(hours=2))}},
            "old": {"slug": "old", "state": "ready", "t": {"posted": A.iso(now - timedelta(hours=7))}},
            "sent": {"slug": "sent", "state": "ready", "t": {"posted": A.iso(now - timedelta(hours=1)), "vsl_sent": "x"}},
            "queued": {"slug": "queued", "state": "queued", "t": {"posted": A.iso(now - timedelta(hours=1))}},
        }
        orig = A.all_jobs
        A.all_jobs = lambda: list(jobs.values())
        try:
            self.assertEqual(A.ready_unsent(now), ["fresh"])
        finally:
            A.all_jobs = orig

    def test_proposals_stamp_writes_the_job_record(self):
        import json, tempfile, sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "upwork"))
        import proposals as P
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "x-1.json").write_text(json.dumps({"slug": "x-1", "job": "~0221247", "t": {}}))
            self.assertEqual(P.stamp_oneshot_sent("~0221247", "2026-11-23T14:35:00Z", "vsl_sent", jobs_dir=d), "x-1")
            self.assertEqual(json.loads((Path(d) / "x-1.json").read_text())["t"]["vsl_sent"], "2026-11-23T14:35:00Z")
            self.assertIsNone(P.stamp_oneshot_sent("~nope", "t", "vsl_sent", jobs_dir=d))


class ExpireStale(unittest.TestCase):
    """nova 18612: a queued job older than the window is marked expired, not built; fresh, undated and non-queued jobs are untouched."""

    def test_only_old_queued_jobs_expire(self):
        import oneshot_auto as A
        from datetime import timedelta
        now = A.now()
        jobs = {
            "old": {"slug": "old", "state": "queued", "t": {"posted": A.iso(now - timedelta(hours=7))}},
            "fresh": {"slug": "fresh", "state": "queued", "t": {"posted": A.iso(now - timedelta(hours=2))}},
            "undated": {"slug": "undated", "state": "queued", "t": {}},
            "ready": {"slug": "ready", "state": "ready", "t": {"posted": A.iso(now - timedelta(hours=30))}},
            "oldblocked": {"slug": "oldblocked", "state": "blocked", "t": {"posted": A.iso(now - timedelta(hours=9))}},
            "freshblocked": {"slug": "freshblocked", "state": "blocked", "t": {"posted": A.iso(now - timedelta(hours=1))}},
        }
        saved = []
        o_all, o_save = A.all_jobs, A.save_job
        A.all_jobs = lambda: list(jobs.values())
        A.save_job = lambda j: saved.append(j["slug"])
        try:
            self.assertEqual(A.expire_stale(now), ["old", "oldblocked"])
        finally:
            A.all_jobs, A.save_job = o_all, o_save
        self.assertEqual(jobs["old"]["state"], "expired")
        self.assertIn("past the", jobs["old"]["expired"]["why"])
        self.assertEqual([jobs[k]["state"] for k in ("fresh", "undated", "ready")], ["queued", "queued", "ready"])
        self.assertEqual((jobs["oldblocked"]["state"], jobs["freshblocked"]["state"]), ("expired", "blocked"))
        self.assertEqual(saved, ["old", "oldblocked"])



class FeedState(unittest.TestCase):
    """knowledge#18771: a blocked job whose intro VSL was sent reads `sent` in the feed; an unsent blocked job stays blocked."""

    def test_sent_overrides_stale_blocked(self):
        sys.path.insert(0, str(HERE))
        import oneshot_auto as A
        self.assertEqual(A.feed_state({"state": "blocked", "t": {"vsl_sent": "2026-11-24T20:33:00Z"}}), "sent")
        self.assertEqual(A.feed_state({"state": "blocked", "t": {}}), "blocked")
        self.assertEqual(A.feed_state({"state": "ready", "t": {"vsl_sent": "x"}}), "ready")

if __name__ == "__main__":
    unittest.main()

class FeedJobDesc(unittest.TestCase):
    """knowledge#17917: the job-description desk's reads become the builder's post.md; blocked-only-on-missing jobs re-queue."""

    def setUp(self):
        import json, tempfile
        import oneshot_auto as A
        self.A, self.json = A, json
        self.tmp = Path(tempfile.mkdtemp())
        self.orig = A.STATE
        A.STATE = self.tmp / "state"
        self.c = {"hunts_dir": str(self.tmp / "hunts"), "job_desc_dir": str(self.tmp / "desc"), "min_post_chars": 150}
        (self.tmp / "desc").mkdir()
        self.long = "Build us a dashboard. " * 20

    def tearDown(self):
        self.A.STATE = self.orig

    def desc(self, job, desc, ok=True):
        (self.tmp / "desc" / f"{job}.json").write_text(self.json.dumps({"job": job, "title": "T " + job, "desc": desc, "ok": ok}))

    def job(self, slug, job, state, blocked_by=None):
        self.A.save_job({"slug": slug, "job": job, "title": "T " + job, "text": "excerpt", "state": state, "t": {"scripts_gates": "x"}, **({"blocked_by": blocked_by} if blocked_by else {})})

    def post(self, slug):
        return Path(self.c["hunts_dir"]) / slug / "post.md"

    def test_ok_desc_becomes_post_and_requeues(self):
        self.job("a-1", "~1", "blocked", "script_check: input: post.md missing: x")
        self.desc("~1", self.long)
        self.assertEqual(self.A.feed_job_desc(self.c), ["a-1"])
        self.assertEqual(self.post("a-1").read_text(), f"T ~1\n\n{self.long}\n")
        j = self.A.load_job("a-1")
        self.assertEqual((j["state"], j["post_source"], "blocked_by" in j, "scripts_gates" in j["t"]), ("queued", "job-desc", False, False))
        self.assertTrue(j["text"].startswith("T ~1"))

    def test_not_ok_or_short_writes_nothing(self):
        self.job("b-1", "~2", "blocked", "script_check: input: post.md missing: x")
        self.job("c-1", "~3", "queued")
        self.desc("~2", self.long, ok=False)
        self.desc("~3", "short")
        self.assertEqual(self.A.feed_job_desc(self.c), [])
        self.assertFalse(self.post("b-1").exists() or self.post("c-1").exists())
        self.assertEqual(self.A.load_job("b-1")["state"], "blocked")

    def test_existing_post_never_overwritten_and_other_blocks_left(self):
        self.job("d-1", "~4", "blocked", "gate 3 Script: too long")
        self.job("e-1", "~5", "queued")
        self.desc("~4", self.long)
        self.desc("~5", self.long)
        self.post("e-1").parent.mkdir(parents=True)
        self.post("e-1").write_text("by hand")
        self.A.feed_job_desc(self.c)
        self.assertEqual(self.post("e-1").read_text(), "by hand")
        self.assertFalse(self.post("d-1").exists())
        self.assertEqual(self.A.load_job("d-1")["state"], "blocked")


class PendingPostIsNotASkip(unittest.TestCase):
    """knowledge#18251: a feed row whose post is not read yet becomes needs_description (never a permanent skip), and an old
    'post integrity' skip is forgotten so the row is re-evaluated; the desk's description then promotes it to queued."""

    def test_empty_post_row_is_kept_and_old_skip_forgotten(self):
        import json, os, tempfile
        d = tempfile.mkdtemp()
        os.environ["ONESHOT_AUTO_DIR"] = d
        sys.path.insert(0, str(HERE))
        import importlib, oneshot_auto as A
        importlib.reload(A)
        (Path(d) / "jobs").mkdir()
        (Path(d) / "skipped.json").write_text(json.dumps({"~9": "post integrity: post is 0 chars"}))
        row = {"signal": "Go Backend Dev", "signalAt": "2026-11-24T11:32:16.000Z", "details": {"job": "~9", "link": "https://x/~9"}}
        c = dict(A.cfg(), hunts_dir=str(Path(d) / "hunts"))
        new = A.scan([row], c)
        self.assertEqual([(j["job"], j["state"]) for j in new], [("~9", "needs_description")])
        self.assertNotIn("~9", json.loads((Path(d) / "skipped.json").read_text()))


class SelfUpdate(unittest.TestCase):
    """knowledge#18538: the builder clone on ra sat 652 commits behind main and silently ran dead code. Real git, no mocks."""

    def _repos(self):
        import tempfile
        global oneshot_auto
        sys.path.insert(0, str(HERE))
        import oneshot_auto
        d = Path(tempfile.mkdtemp())
        sh = lambda *a, cwd=d: subprocess.run(a, cwd=cwd, check=True, capture_output=True, text=True)
        sh("git", "init", "-q", "-b", "main", "origin")
        o = d / "origin"
        for k, v in (("user.email", "t@t"), ("user.name", "t")):
            sh("git", "config", k, v, cwd=o)
        (o / "f.txt").write_text("1\n")
        sh("git", "add", ".", cwd=o), sh("git", "commit", "-qm", "one", cwd=o)
        sh("git", "clone", "-q", str(o), "clone")
        (o / "f.txt").write_text("2\n")
        sh("git", "commit", "-qam", "two", cwd=o)
        return d / "clone"

    def test_behind_clean_clone_fast_forwards(self):
        c = self._repos()
        self.assertEqual(oneshot_auto.self_update(c), "updated")
        self.assertEqual((c / "f.txt").read_text(), "2\n")
        self.assertEqual(oneshot_auto.self_update(c), "current")

    def test_dirty_clone_is_named_not_clobbered(self):
        c = self._repos()
        (c / "f.txt").write_text("hot patch\n")
        self.assertIn("dirty tree", oneshot_auto.self_update(c))
        self.assertEqual((c / "f.txt").read_text(), "hot patch\n")


class BacklogAlarm(unittest.TestCase):
    """knowledge#18593: a dead reader or a >20 backlog held 15 min alerts chief once."""
    def test_dead_reader_and_backlog(self):
        import tempfile, datetime
        from pathlib import Path
        import oneshot_auto as o
        d = Path(tempfile.mkdtemp()); st, jobs = o.STATE, o.all_jobs
        o.STATE = Path(tempfile.mkdtemp()); o.all_jobs = lambda: [{"state": "needs_description", "slug": str(i)} for i in range(25)]
        sent = []
        try:
            c = {"job_desc_dir": str(d)}
            self.assertEqual(len(o.backlog_alarm(c, send=sent.append)), 1)       # no heartbeat
            self.assertIsNone(o.backlog_alarm(c, send=sent.append))               # once per episode
            (o.STATE / "backlog-alarm.json").unlink(); (d / ".reader-heartbeat").touch()
            self.assertIsNone(o.backlog_alarm(c, send=sent.append))               # healthy reader, backlog just crossed 20
            later = o.iso(o.parse(o.iso()) + datetime.timedelta(minutes=16))
            (d / ".reader-heartbeat").touch()
            self.assertEqual(len(o.backlog_alarm(c, at=later, send=sent.append)), 2)
            self.assertEqual(len(sent), 2)
        finally:
            o.STATE, o.all_jobs = st, jobs


class SyncSends(unittest.TestCase):
    """2026-11-24: sends in the upwork ledger reach the job record (vsl_sent / text_proposal), idempotent."""

    def test_ledger_sends_stamp_jobs_once(self):
        import json, tempfile
        import oneshot_auto as A
        d = Path(tempfile.mkdtemp())
        old = A.STATE
        A.STATE = d
        try:
            for slug, job in (("a", "~021"), ("b", "~022"), ("c", "~023")):
                A.save_job({"slug": slug, "job": job, "state": "ready", "t": {}})
            led = d / "ledger.jsonl"
            rows = [{"ts": "T1", "event": "proposal_sent", "job": "~021"}, {"ts": "T2", "event": "vsl_sent", "job": "~021"},
                    {"ts": "T3", "event": "proposal_sent", "job": "~022"}, {"ts": "T4", "event": "job_read", "job": "~023"}]
            led.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            self.assertEqual(sorted(A.sync_sends(led)), [("a", "vsl_sent"), ("b", "text_proposal")])
            self.assertEqual(A.load_job("a")["t"], {"vsl_sent": "T2"})
            self.assertEqual(A.load_job("b")["t"], {"text_proposal": "T3"})
            self.assertEqual(A.load_job("c")["t"], {})
            self.assertEqual(A.sync_sends(led), [])
        finally:
            A.STATE = old
