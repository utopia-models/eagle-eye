"""knowledge#18734: VERIFY gates every intro send. The sent job-3307 file (low-rate copy) is the replay fixture: it MUST fail on post-not-first, no tabs, no orb,
cropped diagram and loudness. A synthetic file built to the rules passes; each single violation fails exactly its own check."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import intro_verify as V  # noqa: E402
import intro_sender  # noqa: E402

pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("tesseract")), reason="needs ffmpeg + tesseract")
FIX = Path(__file__).parent / "fixtures" / "3307-intro-v2.lowrate.mp4"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
HANDOFF = 19.0


def make(path, *, tabs=True, orb=True, face=True, wide_diagram=False, gain_db=0.0, dur=50):
    """A 1920x1080 5 fps file: post (white) 0-19 s with the face card, MVP 19-32 s, diagram 32+ s (dark) with the orb after the hand-off; three tabs."""
    f = []
    bar = []
    if tabs:
        bar.append("drawbox=0:0:1920:96:0xdee1e6:t=fill")
        for k, (name, lo, hi) in enumerate([("Their Job", 0, 19), ("MVP", 19, 32), ("Architecture", 32, dur + 1)]):
            x = 12 + k * 306
            bar.append(f"drawbox={x}:8:300:34:white:t=fill:enable='between(t,{lo},{hi})'")
            bar.append(f"drawtext=fontfile={FONT}:text='{name}':x={x + 38}:y=17:fontsize=20:fontcolor=0x202124")
    base = "color=c=white:s=1920x1080:r=5:d=%d" % dur
    chain = [f"[0:v]drawbox=0:0:1920:1080:0x0a0907:t=fill:enable='gte(t,32)'"]
    dx = 4 if wide_diagram else 300
    chain.append(f"drawbox={dx}:300:{1920 - 2 * dx}:300:0x3a3a3a:t=fill:enable='gte(t,32)'")
    chain += bar
    chain.append(f"drawtext=fontfile={FONT}:text='Orders':x=500:y=200:fontsize=40:fontcolor=black:enable='between(t,19,32)'")
    chain_s = ",".join(chain) + "[b]"
    ov = "[b]"
    parts = [chain_s]
    if face:
        parts.append("[1:v]scale=346:346[fc];[b][fc]overlay=1534:694:enable='lt(t,%s)'[b2]" % HANDOFF)
        ov = "[b2]"
    # the corner slot is dark after the hand-off, with the gold orb in it
    parts.append(f"{ov}drawbox=1534:694:346:346:0x0a0907:t=fill:enable='gte(t,{HANDOFF})'[b3]")
    ov = "[b3]"
    if orb:
        parts.append(f"{ov}drawbox=1580:850:200:190:0xd4a94e:t=fill:enable='gte(t,{HANDOFF})'[b4]")
        ov = "[b4]"
    fc = ";".join(parts) + f";{ov}format=yuv420p[v]"
    vol = f"-16.0" if gain_db == 0 else f"{-16.0 + gain_db}"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", base, "-f", "lavfi", "-i", "testsrc2=s=346x346:r=5",
           "-f", "lavfi", "-i", f"sine=f=220:d={dur}:r=48000", "-filter_complex", fc,
           "-map", "[v]", "-map", "2:a", "-af", f"loudnorm=I={vol}:TP=-1.0:LRA=11", "-ar", "48000", "-t", str(dur), "-c:v", "libx264", "-crf", "30", "-preset", "veryfast", "-c:a", "aac", "-b:a", "64k", str(path)]
    subprocess.run(cmd, check=True)
    return path


def failed_ids(res):
    return {c["id"] for c in res["checks"] if not c["pass"]}


def test_3307_replay_fails_every_named_rule(tmp_path):
    res = V.verify(FIX, HANDOFF, tmp_path / "frames")
    assert not res["pass"]
    assert {"tabs_present", "post_first", "orb", "diagram_whole", "loudness"} <= failed_ids(res)
    assert list((tmp_path / "frames").glob("t*.png")), "frame captures are saved next to the verdict"


def test_rule_built_file_passes(tmp_path):
    mp4 = make(tmp_path / "ok.mp4")
    res = V.verify(mp4, HANDOFF, tmp_path / "f")
    assert res["pass"], V.failing(res)


@pytest.mark.parametrize("kw,expect", [
    ({"tabs": False}, {"tabs_present", "post_first"}),
    ({"orb": False}, {"orb"}),
    ({"face": False}, {"face_card"}),
    ({"wide_diagram": True}, {"diagram_whole"}),
    ({"gain_db": -7.0}, {"loudness"}),
])
def test_single_violation_fails_its_check(tmp_path, kw, expect):
    res = V.verify(make(tmp_path / "bad.mp4", **kw), HANDOFF, tmp_path / "f")
    assert not res["pass"]
    assert expect <= failed_ids(res), (kw, V.failing(res))


def test_sender_holds_unverified_and_failing_and_stale(tmp_path):
    pkg = tmp_path / "j1"
    pkg.mkdir()
    (pkg / "intro.mp4").write_bytes(b"x")
    job = {"slug": "j1", "link": "l"}
    assert intro_sender.hold_reason(job, tmp_path) == "verify_missing"
    sha = V.hashlib.sha256(b"x").hexdigest()
    (pkg / "verify.json").write_text(json.dumps({"pass": False, "sha256": sha, "checks": [{"id": "orb", "pass": False, "detail": "none"}]}))
    assert intro_sender.hold_reason(job, tmp_path) == "verify_failed"
    (pkg / "verify.json").write_text(json.dumps({"pass": True, "sha256": "0" * 64}))
    assert intro_sender.hold_reason(job, tmp_path) == "verify_stale"
    (pkg / "verify.json").write_text(json.dumps({"pass": True, "sha256": sha}))
    assert intro_sender.hold_reason(job, tmp_path) is None
