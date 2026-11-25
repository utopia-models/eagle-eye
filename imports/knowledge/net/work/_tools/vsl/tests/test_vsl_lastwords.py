"""Domain 8 item 8 replay: stage.json says "send VSL", the client's last message says no spec builds and VSL already sent;
the plan (vsl_jobs.stage) must refuse, and must NOT call the pipeline."""
import json, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE.parent / "upwork")]
import vsl_jobs, vsl_lastwords  # noqa: E402


def row(ts, text, client="Lanam"):
    return {"event": "client_reply", "ts": ts, "client": client, "text": text}


class LastWords(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        self.job = {"key": "lanam", "title": "Lanam", "source": str(self.t / "src.txt"), "slug": "lanam", "blocked": None,
                    "staged_at": None}
        (self.t / "pkg" / "lanam").mkdir(parents=True)
        (self.t / "pkg" / "lanam" / "stage.json").write_text(json.dumps({"next": "send VSL", "vsl": {"recorded": False}}))

    def _stage(self, rows):
        led = self.t / "ledger.jsonl"
        led.write_text("".join(json.dumps(r) + "\n" for r in rows))
        calls = []
        r = vsl_jobs.stage(self.job, jobs=self.t / "jobs", pkg_root=self.t / "pkg", ledger=str(led),
                           pipeline=lambda *a: calls.append(a) or {"pass": False, "gate_findings": ["stop here"]})
        return r, calls

    def test_refuses_when_last_message_says_no_build_and_already_sent(self):
        (ok, why), calls = self._stage([row("2026-11-19T20:00:00Z", "Great, thanks"),
                                        row("2026-11-19T21:00:00Z", "No spec builds please, VSL already sent.")])
        self.assertFalse(ok)
        self.assertIn("last words", why)
        self.assertEqual(calls, [], "the pipeline must not run")

    def test_passes_through_when_client_is_positive(self):
        (ok, why), calls = self._stage([row("2026-11-19T21:00:00Z", "Sounds good, send it over")])
        self.assertEqual(len(calls), 1, "no refusing words: the pipeline runs as before")

    def test_other_clients_words_do_not_refuse(self):
        (ok, why), calls = self._stage([row("2026-11-19T21:00:00Z", "no spec builds", client="Someone Else")])
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
