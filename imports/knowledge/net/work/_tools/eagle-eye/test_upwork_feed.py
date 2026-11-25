#!/usr/bin/env python3
"""Tests for upwork_feed.py next_action(): the 6 h proposal edit window (knowledge#14748). Offline, stdlib only.

    python3 net/work/_tools/eagle-eye/test_upwork_feed.py      # or: python3 -m pytest test_upwork_feed.py
"""
import datetime as dt
import importlib.util
import os
import unittest
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("upwork_feed", os.path.join(HERE, "upwork_feed.py"))
U = importlib.util.module_from_spec(spec)
spec.loader.exec_module(U)
U.tyler_tz = lambda: ZoneInfo("America/Denver")   # the box's cache is not the test's input

SENT = "2026-11-17T00:08:20Z"   # the AI Data Engineer send: its window closed 06:08:20Z = 11:08 PM MST on the 16th
T0 = dt.datetime(2026, 11, 17, 0, 8, 20, tzinfo=dt.timezone.utc).timestamp()


def row(recorded=True, verdict=None, generic=False, stages=None):
    return {"status": "sent", "sentAt": SENT, "stages": stages or {}, "_generic": generic,
            "vsl": {"attached": False, "recorded": recorded, "verdict": verdict},
            "demo": {"slug": None, "live": False}}


class EditWindow(unittest.TestCase):
    def test_inside_the_window_says_edit_and_when_it_closes_in_local_time(self):
        n = U.next_action(row(), T0 + 6 * 3600 - 1)
        self.assertEqual(n, "edit the proposal: attach the recorded VSL · edit window closes 1:08 AM ET")
        self.assertNotIn("Z", n)

    def test_at_and_after_the_window_the_vsl_waits_for_the_reply(self):
        for t in (T0 + 6 * 3600, T0 + 7 * 3600):
            self.assertEqual(U.next_action(row(), t), "VSL ready; posts in the room when the client replies")

    def test_a_viewed_proposal_is_past_the_window_early(self):
        n = U.next_action(row(stages={"viewed": "2026-11-17T01:00:00Z"}), T0 + 3600)
        self.assertEqual(n, "VSL ready; posts in the room when the client replies")

    def test_unrecorded_after_the_window_records_for_the_reply(self):
        self.assertEqual(U.next_action(row(recorded=False, verdict="RECORD_CUSTOM"), T0 + 7 * 3600),
                         "record the custom VSL; it posts in the room when the client replies")
        self.assertEqual(U.next_action(row(recorded=False), T0 + 7 * 3600),
                         "record the generic VSL; it posts in the room when the client replies")
        self.assertEqual(U.next_action(row(recorded=False, generic=True), T0 + 7 * 3600),
                         "VSL ready; posts in the room when the client replies")

    def test_unrecorded_inside_the_window_still_edits(self):
        self.assertEqual(U.next_action(row(recorded=False, generic=True), T0 + 60),
                         "edit the proposal: attach the generic VSL · edit window closes 1:08 AM ET")

    def test_clock_defaults_to_eastern(self):   # ask 2179
        self.assertEqual(U.clock(T0 + 6 * 3600), "1:08 AM ET")

    def test_clock_is_local_12_hour(self):
        self.assertEqual(U.clock(T0 + 6 * 3600, ZoneInfo("America/Denver")), "11:08 PM")


class JobStages(unittest.TestCase):
    def rows(self, evs):
        return [{"event": e, "job": j, "_t": t, **x} for e, j, t, x in evs]

    def test_job_walks_demo_vsl_sent_and_status_none_until_a_reply(self):
        rs = self.rows([("demo_ready", "~0123456789012345678", 100, {"url": "https://d.example"}),
                        ("vsl_recorded", "~0123456789012345678", 200, {"file": "t.mp4"}),
                        ("proposal_sent", "~0123456789012345678", 300, {})])
        s = U.stage_rows(U.job_stages(rs)["~0123456789012345678"])
        self.assertEqual([x["stage"] for x in s], ["DEMO READY", "VSL", "SENT", "STATUS"])
        self.assertEqual([x["done"] for x in s], [True, True, True, False])
        self.assertEqual(s[0]["url"], "https://d.example")
        self.assertEqual(s[1]["file"], "t.mp4")
        self.assertEqual(s[3]["value"], "none")

    def test_client_reply_sets_in_conversation_and_vsl_sent_counts_as_sent(self):
        rs = self.rows([("vsl_sent", "~0123456789012345678", 100, {}), ("client_reply", "~0123456789012345678", 200, {})])
        s = U.stage_rows(U.job_stages(rs)["~0123456789012345678"])
        self.assertEqual([x["done"] for x in s], [False, False, True, True])
        self.assertEqual(s[3]["value"], "in conversation")

    def test_jobs_carry_stages_and_a_demo_only_job_still_lists(self):
        now = 1_800_000_000
        rs = [{"event": "job_read", "job": "~0111111111111111111", "_t": now - 100, "title": "A"},
              {"event": "demo_ready", "job": "~0222222222222222222", "_t": now - 50, "url": "https://d"}]
        by = {j["key"]: j for j in U.jobs(rs, now)}
        self.assertEqual(by["~0111111111111111111"]["stages"][0]["done"], False)
        self.assertEqual(by["~0222222222222222222"]["stages"][0]["done"], True)


class PipelineStages(unittest.TestCase):
    def test_sent_without_a_vsl_is_flagged_and_owner_named(self):
        pl = U.pipeline([], row(recorded=False))
        self.assertTrue(pl["noVsl"])
        self.assertEqual([x["stage"] for x in pl["stages"]], ["DEMO READY", "VSL", "SENT", "STATUS"])
        self.assertTrue(pl["stages"][2]["done"])
        self.assertEqual(pl["stages"][3]["value"], "none")
        self.assertEqual(pl["demoOwner"], "upwork")

    def test_sent_with_a_vsl_and_a_reply_is_clean(self):
        pl = U.pipeline([], row(recorded=True, stages={"replied": SENT}))
        self.assertFalse(pl["noVsl"])
        self.assertEqual(pl["stages"][3]["value"], "in conversation")


class Matches(unittest.TestCase):
    def test_unsent_picks_list_with_owner_or_unassigned(self):
        rows = [{"event": "vsl_pick", "job": "~0111111111111111111", "slug": "rag-assistant", "_t": 2},
                {"event": "demo_ready", "job": "~0222222222222222222", "slug": "ai-automation", "who": "horus", "_t": 3},
                {"event": "vsl_pick", "job": "~0333333333333333333", "slug": "x", "_t": 1}]
        m = {x["key"]: x for x in U.matches(rows, [{"key": "~0333333333333333333", "sentAt": "2026-11-17T00:00:00Z"}])}
        self.assertEqual(set(m), {"~0111111111111111111", "~0222222222222222222"})
        self.assertEqual(m["~0111111111111111111"]["owner"], "UNASSIGNED")
        self.assertEqual(m["~0222222222222222222"]["status"], "demo ready, VSL pending")


class StatusWords(unittest.TestCase):
    def test_pipeline_words(self):
        w = U.status_word
        self.assertEqual([w(False, False), w(True, False), w(True, True), w(True, True, True), w(True, True, True, {"replied": 1}),
                          w(True, True, True, {"hired": 1}), w(True, True, True, {"declined": 1})],
                         ["Awaiting Demo", "Awaiting VSL", "Proposal Drafting", "Awaiting Reply", "In Conversation", "Won", "Lost"])


class PrivateJobs(unittest.TestCase):
    K = "~022122851667888069278"

    def test_job_private_leaves_the_jobs_and_matches_lists(self):
        rows = [{"event": "job_read", "job": self.K, "title": "AI Engineer", "mail_at": "2026-11-17T20:00:00Z", "_t": 1000.0,
                 "source": "job_alert_mail"},
                {"event": "demo_ready", "job": self.K, "url": "https://d", "_t": 1001.0}]
        self.assertEqual(len(U.matches(rows, [])), 1)
        rows.append({"event": "job_private", "job": self.K, "_t": 1002.0})
        self.assertEqual(U.matches(rows, []), [])
        self.assertNotIn(self.K, [j["key"] for j in U.jobs(rows, 2000.0)])


if __name__ == "__main__":
    unittest.main()
