"""knowledge#18736: the voice profile is the one source; VERIFY fails on a wrong id / changed reference; blind_test never fakes a model."""
import json, subprocess, sys, tempfile, unittest
from pathlib import Path

V = Path(__file__).resolve().parents[1] / "voice"
sys.path.insert(0, str(V))
import voice_profile as vp  # noqa: E402
import adapters  # noqa: E402


class Profile(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()); self.ref = self.d / "ref.wav"; self.ref.write_bytes(b"RIFFfake")
        self.p = {"picked": True, "id": "tyler-x-1234", "reference": str(self.ref), "reference_sha256": vp.sha256(self.ref)}
        self.side = self.d / "r.json"

    def write(self, **kw):
        self.side.write_text(json.dumps({"voice_profile": "tyler-x-1234", "voice_reference_sha256": self.p["reference_sha256"], **kw}))

    def test_pass(self):
        self.write(); self.assertEqual(vp.check(self.side, self.p), [])

    def test_wrong_id_fails(self):
        self.write(voice_profile="chatterbox-energetic"); self.assertTrue(vp.check(self.side, self.p))

    def test_changed_reference_fails(self):
        self.write(); self.ref.write_bytes(b"other"); self.assertTrue(vp.check(self.side, self.p))

    def test_unpicked_fails(self):
        self.write(); self.assertTrue(vp.check(self.side, {"picked": False}))

    def test_shipped_profile_is_unpicked_until_tyler_picks(self):
        self.assertIn("picked", vp.load())


class NoFakes(unittest.TestCase):
    def test_missing_models_skip_and_exit_2(self):
        d = Path(tempfile.mkdtemp()); (d / "s.txt").write_text("hello\n"); (d / "r.wav").write_bytes(b"x")
        r = subprocess.run([sys.executable, str(V / "blind_test.py"), "--script", str(d / "s.txt"), "--ref", str(d / "r.wav"), "--models", "cosyvoice,indextts2", "--out", str(d / "o")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stderr); self.assertEqual(list((d / "o").glob("*.wav")), [])

    def test_registry(self):
        self.assertEqual(set(adapters.ADAPTERS), {"chatterbox", "cosyvoice", "indextts2", "orpheus"})


if __name__ == "__main__":
    unittest.main()
