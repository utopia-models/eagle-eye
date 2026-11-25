"""gen_scripts.action_script: exactly one step per AI row, in order, full words (takeflow/preflight.py sync, chief #15729)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gen_scripts as G  # noqa: E402

LONG = "Findings lists the issues, ranked by priority, and each one is a task you can track to done."
SRC = {"slug": "x", "sections": [
    {"id": "intro", "lines": ["Hi, I am Tyler Youk.", "I read your post."]},
    {"id": "app", "lines": ["You want X.", {"say": LONG, "do": {"tab": 1, "click": "text=Findings"}}, "Each note explains a result."]},
    {"id": "diagram", "lines": [{"say": "Data comes in.", "do": {"tab": 2, "beat": 1}}, "Findings go to your team."]},
]}


class ActionScript(unittest.TestCase):
    def setUp(self):
        self.steps = G.action_script(SRC)["steps"]

    def test_one_step_per_ai_row_and_none_for_tyler(self):
        self.assertEqual(len(self.steps), 5)
        self.assertTrue(all(s["section"] in ("app", "diagram") for s in self.steps))

    def test_the_words_are_the_full_row_never_cut(self):
        self.assertEqual(self.steps[1]["say"], LONG)
        self.assertGreater(len(LONG), 60)

    def test_a_row_without_do_is_a_hold_on_its_tab(self):
        hold = self.steps[0]
        self.assertEqual((hold["tab"], hold.get("click"), hold.get("beat")), (1, None, None))
        self.assertEqual(self.steps[4]["tab"], 2)

    def test_real_actions_are_kept_and_order_is_the_script_order(self):
        self.assertEqual(self.steps[1]["click"], "text=Findings")
        self.assertEqual(self.steps[3]["beat"], 1)
        self.assertEqual([s["line"] for s in self.steps], [0, 1, 2, 0, 1])


class Normalize(unittest.TestCase):
    def test_unquoted_colon_line_is_repaired(self):
        src = {"slug": "x", "sections": [{"id": "app", "lines": [{"It is a working app": "click the Build Queue, and each page opens."}, "Plain row."]}]}
        out = G.normalize_source(src)
        self.assertEqual(out["sections"][0]["lines"][0], {"say": "It is a working app: click the Build Queue, and each page opens."})
        self.assertEqual(len(G.action_script(out)["steps"]), 2)

    def test_a_dict_row_with_no_say_is_refused_by_name(self):
        with self.assertRaises(ValueError) as cm:
            G.normalize_source({"sections": [{"id": "app", "lines": [{"do": {"tab": 1}, "x": 1}]}]})
        self.assertIn("section app line 0", str(cm.exception))


class Repair(unittest.TestCase):
    BAD = ('slug: x\nsections:\n- id: app\n  lines:\n  - Plain row.\n'
           "  - Here is the simple workflow your post asks for: it branches on the lead's tags: then it routes it.\n"
           '  - {say: "Keeps its own colon: yes", do: {tab: 1}}\n'
           "  - say: This is the example workflow: it branches on the lead's tags: and sets the stage.\n    do: {tab: 1, click: nav}\n"
           "  - Row after a nested do block: with a second colon: here.\n")

    def test_invalid_yaml_from_an_unquoted_colon_is_repaired_and_written_back(self):
        import tempfile
        import yaml
        p = Path(tempfile.mkdtemp()) / "script-source.yaml"
        p.write_text(self.BAD)
        with self.assertRaises(yaml.YAMLError):
            yaml.safe_load(self.BAD)
        src = G.load_source(p)
        rows = src["sections"][0]["lines"]
        self.assertEqual(rows[1]["say"] if isinstance(rows[1], dict) else rows[1], "Here is the simple workflow your post asks for: it branches on the lead's tags: then it routes it.")
        self.assertEqual(rows[2]["say"], "Keeps its own colon: yes")
        self.assertEqual(rows[3]["say"], "This is the example workflow: it branches on the lead's tags: and sets the stage.")
        self.assertEqual(rows[3]["do"], {"tab": 1, "click": "nav"})
        self.assertEqual(rows[4], "Row after a nested do block: with a second colon: here.")
        self.assertEqual(yaml.safe_load(p.read_text())["sections"][0]["lines"][1], rows[1], "the repaired file is valid for every other reader")

    def test_valid_files_are_untouched(self):
        import tempfile
        p = Path(tempfile.mkdtemp()) / "script-source.yaml"
        good = 'slug: x\nsections:\n- id: app\n  lines:\n  - Plain row.\n'
        p.write_text(good)
        G.load_source(p)
        self.assertEqual(p.read_text(), good)


if __name__ == "__main__":
    unittest.main()
