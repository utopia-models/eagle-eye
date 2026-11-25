"""desk_observer.py's URL state machine, offline (python3 -m unittest send/test_desk_observer.py)."""
import tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import desk_observer as D


class T(unittest.TestCase):
    def setUp(self):
        self.sent, self.code = [], 200
        self.o = D.Observer(post=lambda facts: (self.sent.extend(facts), (self.code, {"data": {"applyFacts": [{"status": "updated"}]}}))[1],
                            state=tempfile.mkdtemp())

    def test_apply_then_success_is_one_proposal_sent_with_the_job(self):
        self.o.on_target({"type": "page", "targetId": "A", "url": "https://www.upwork.com/nx/proposals/job/~022124298273556552350/apply/"})
        f = self.o.on_target({"type": "page", "targetId": "A", "url": "https://www.upwork.com/nx/proposals/2124376726426906625?success"})
        self.assertEqual(f["itemRef"], {"proposalId": "2124376726426906625", "job": "~022124298273556552350"})
        self.assertEqual(f["key"], "desk:proposal_sent:2124376726426906625")
        # the same page again (a reload, a reconnect) is not a second send
        self.assertIsNone(self.o.on_target({"type": "page", "targetId": "B", "url": "https://www.upwork.com/nx/proposals/2124376726426906625?success"}))
        self.assertEqual(len(self.sent), 1)

    def test_other_pages_and_non_pages_are_ignored(self):
        for u in ["https://www.upwork.com/nx/proposals/2122517259467608065", "https://www.upwork.com/nx/search/jobs/?q=x"]:
            self.assertIsNone(self.o.on_target({"type": "page", "targetId": "A", "url": u}))
        self.assertIsNone(self.o.on_target({"type": "worker", "targetId": "W", "url": "https://www.upwork.com/nx/proposals/2124376726426906626?success"}))
        self.assertEqual(self.sent, [])

    def test_a_fact_the_server_cannot_place_stays_pending(self):
        self.code = 422
        self.o.on_target({"type": "page", "targetId": "C", "url": "https://www.upwork.com/nx/proposals/2124376726426906627?success"})
        self.assertEqual(len(self.o.pending), 1)
        self.code = 200
        self.o.flush()
        self.assertEqual(self.o.pending, [])


if __name__ == "__main__":
    unittest.main()
