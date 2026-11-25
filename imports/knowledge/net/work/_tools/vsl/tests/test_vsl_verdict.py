"""Tests for vsl_verdict.py: script compare, the verdict decision on synthetic media, the watcher's stable-size rule.
Replays on real takes (/srv/vsl, needs ASR) are run by hand: see the PR."""
import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("VSL_VERDICT_STATE", tempfile.mkdtemp())
os.environ["VSL_VERDICT_MIRROR"] = tempfile.mkdtemp()
os.environ["VSL_VERDICT_PROMPTER"] = "/nonexistent"
import vsl_verdict as v

SCRIPT = ("**Part 1 · Promise (Overview tab)**\nYou asked for someone to set up the workflows, so I built the working version first. "
          "It is running right now on a sample firm.\n\n**Part 2 · Intake (Intake tab)**\nA lead lands in the system. "
          "The workflow checks for a conflict and then creates the matter with the whole task list.\n")


def words(text, gap_after=None, t0=0.0):
    out, t = [], t0
    for i, w in enumerate(text.split()):
        out.append({"w": w, "start": t, "end": t + 0.3}); t += 0.4
        if gap_after == i:
            t += 5
    return out


def media(path, secs=10, audio="sine=f=300:d={d}", vol="0.7", color="c=blue"):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color={color}:s=320x180:d={secs}:r=10",
                    "-f", "lavfi", "-i", audio.format(d=secs), "-af", f"volume={vol}", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path)], check=True)


class T(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.script = self.d / "speaker-script.md"
        self.script.write_text(SCRIPT)

    def run_take(self, ws, **mk):
        m = self.d / "t.mp4"; media(m, **mk)
        return v.analyze_take(m, script=self.script, run_dir=self.d, words=ws)

    def test_parse(self):
        self.assertEqual([p["n"] for p in v.parse_parts(SCRIPT)], [1, 2])

    def test_clean_take_is_next(self):
        r = self.run_take(words(" ".join(p["text"] for p in v.parse_parts(SCRIPT))), secs=10)
        self.assertEqual(r["verdict"], "NEXT", r["failures"]); self.assertEqual(r["line"], "NEXT")
        self.assertTrue((self.d / "take-1.verdict.json").exists())

    def test_skipped_part_names_the_part(self):
        ws = words("You asked for someone to set up the workflows, so I built the working version first. It is running right now on a sample firm.")
        r = self.run_take(ws)
        self.assertEqual(r["verdict"], "RE-RECORD")
        self.assertTrue(r["line"].startswith("RE-RECORD part 2 because skipped"), r["line"])

    def test_dropped_line_and_threshold(self):
        t = " ".join(p["text"] for p in v.parse_parts(SCRIPT)).replace("so I built the working version first. ", "")
        r = self.run_take(words(t))
        self.assertIn("part 1", r["line"]); self.assertIn("92%", r["line"])

    def test_dead_air_and_length(self):
        t = " ".join(p["text"] for p in v.parse_parts(SCRIPT))
        r = self.run_take(words(t, gap_after=10))
        self.assertTrue(any("dead air" in f["reason"] for f in r["failures"]), r["failures"])
        r = self.run_take(words(t), secs=160)
        self.assertTrue(any("2:30 cap" in f["reason"] for f in r["failures"]))

    def test_clipping_and_black(self):
        t = " ".join(p["text"] for p in v.parse_parts(SCRIPT))
        r = self.run_take(words(t), vol="40", color="c=black")
        reasons = " | ".join(f["reason"] for f in r["failures"])
        self.assertIn("audio clips", reasons); self.assertIn("black frames", reasons)

    def test_asr_near_miss_is_not_a_skip(self):
        t = " ".join(p["text"] for p in v.parse_parts(SCRIPT)).replace("workflows", "workflow").replace("firm", "firms")
        rows, tot = v.compare(v.parse_parts(SCRIPT), words(t))
        self.assertGreaterEqual(tot["kept_pct"], 92.0)

    def test_stable_rule(self):
        src = Path(tempfile.mkdtemp()); (src / "a.mkv").write_bytes(b"x" * 10)
        v.LOCAL_SRC = str(src)
        self.assertEqual(set(v.ls_source()), {"a.mkv"})


if __name__ == "__main__":
    unittest.main()
