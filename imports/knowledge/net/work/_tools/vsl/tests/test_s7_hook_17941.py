"""knowledge#17941: the S7 hook is filled by code from a validated {noticed, made, outcome} triple; the writer never touches it."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("ONESHOT_AUTO_DIR", tempfile.mkdtemp())
os.environ.setdefault("ONESHOT_PKG_ROOT", tempfile.mkdtemp())
import s7_hook as H  # noqa: E402
import script_authoring as SA  # noqa: E402
import upwork_rules as U  # noqa: E402
import oneshot_auto as OA  # noqa: E402
import test_upwork_rules_17592 as T  # noqa: E402

GOOD = {"noticed": "your team loses hours each day sorting tickets by hand", "made": "a Zendesk queue that sorts them", "outcome": "answer faster"}


class Triple(unittest.TestCase):
    def test_fill_is_the_template_exactly(self):
        self.assertEqual(H.fill(GOOD), "I noticed your team loses hours each day sorting tickets by hand, so I made you a Zendesk queue that sorts them, so that you can answer faster.")

    def test_a_triple_past_the_hook_ceiling_is_refused(self):
        # 2046 regen 2026-11-24: an 81-word filled line ran the video to 87 s; the hook beat is beat_words.hook words
        long = dict(GOOD, made="a first version of your Zendesk ticket queue: it pulls in every ticket and its attachments and sorts them by team and by urgency",
                    outcome="answer faster and see right away which tickets need a person and which can wait")
        why = H.validate(long, T.POST if hasattr(T, "POST") else GOOD["noticed"])
        self.assertTrue(any("the hook is" in w for w in why), why)

    def test_noticed_not_in_post_is_refused(self):
        bad = dict(GOOD, noticed="your growth plans for a big expansion")
        self.assertTrue(H.validate(bad, T.POST))
        self.assertEqual(H.validate(GOOD, T.POST), [])

    def test_bad_triple_retries_the_triple_only(self):
        replies = [json.dumps(dict(GOOD, noticed="nothing from the post here")), json.dumps(GOOD)]
        prompts = []
        def ask(p):
            prompts.append(p)
            return replies[len(prompts) - 1]
        t, why = H.author(T.POST, ask)
        self.assertEqual(t, GOOD)
        self.assertEqual(len(prompts), 2)
        self.assertIn("REFUSED", prompts[1])

    def test_gives_up_after_max_loops(self):
        t, why = H.author(T.POST, lambda p: "not json", loops=2)
        self.assertIsNone(t)
        self.assertTrue(why)


class E8Nouns(unittest.TestCase):
    def test_write_prompt_carries_the_posts_nouns_for_e8(self):
        seen = []
        orig = SA._claude
        SA._claude = lambda prompt, *a, **k: seen.append(prompt)
        try:
            SA.write(tempfile.mkdtemp(), T.POST, [{"file": "script-source.yaml", "row": "x", "why": "E8: would fit a different job"}])
        finally:
            SA._claude = orig
        nouns = H.distinctive_nouns(T.POST)
        self.assertIn("zendesk", nouns)
        self.assertIn("MUST use one of the post's own nouns", seen[0])
        self.assertIn("zendesk", seen[0])


# RegenS7 (the regen fixtures that needed an S7 hook row) was deleted in #18869: the contract's hook.takes is [none], the AI voice jumps straight into their job.
