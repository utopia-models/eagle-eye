"""Fake-dir tests for vsl_archive (knowledge#15179). Run: python3 -m pytest net/work/_tools/vsl/tests/test_vsl_archive.py"""
import os, sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vsl_archive as A


def env(tmp, free_gb=500):
    lap_d, store, dr = tmp / "lap", tmp / "ra", tmp / "drive"
    lap_d.mkdir(); store.mkdir(); dr.mkdir()
    return lap_d, store, A.DirLaptop(lap_d, free_gb), A.DirDrive(dr)


def take(d, name, data=b"x" * 2048, age=600):
    p = d / name
    p.write_bytes(data)
    t = time.time() - age
    os.utime(p, (t, t))
    return p


def run(lap, dr, store, tmp):
    logs = []
    return A.sync(lap, dr, store, tmp / "state", logs.append), logs


def test_copy_writes_verified_sidecar(tmp_path):
    d, store, lap, dr = env(tmp_path)
    take(d, "a.mkv")
    st, _ = run(lap, dr, store, tmp_path)
    raw = A.find_raw(store, "a.mkv")
    sc = A.read_side(raw)
    assert sc["sha256"] == A.sha256_file(d / "a.mkv") and sc["size"] == 2048 and sc["ra"]["verified_at"]
    assert sc["drive"]["key"] == "raw.vsl-takes" and sc["drive"]["id"]
    assert (d / "a.mkv").exists()            # verified but under 24 h and plenty of space: stays
    assert st["pending_ra"] == 0 and st["pending_drive"] == 0


def test_in_progress_file_not_copied(tmp_path):
    d, store, lap, dr = env(tmp_path)
    take(d, "live.mkv", age=5)
    run(lap, dr, store, tmp_path)
    assert A.find_raw(store, "live.mkv") is None


def test_label_is_a_label_not_a_storage_decision(tmp_path):
    d, store, lap, dr = env(tmp_path)
    take(d, "a.mkv"); run(lap, dr, store, tmp_path)
    assert A.keep(store, "a", "sent") == ("a.mkv", "sent")
    assert A.read_side(A.find_raw(store, "a.mkv"))["label"] == "sent"


def test_prune_after_24h_both_verified(tmp_path):
    d, store, lap, dr = env(tmp_path)
    take(d, "a.mkv"); run(lap, dr, store, tmp_path)
    logs = []
    assert A.prune_stage(lap, store, logs.append, t=time.time() + 23 * 3600) == []
    assert A.prune_stage(lap, store, logs.append, t=time.time() + 25 * 3600) == ["a.mkv"]
    assert not (d / "a.mkv").exists() and A.find_raw(store, "a.mkv").exists()


def test_low_space_deletes_oldest_verified_first_never_unverified(tmp_path):
    d, store, lap, dr = env(tmp_path)
    take(d, "old.mkv", age=900); take(d, "new.mkv", age=700); run(lap, dr, store, tmp_path)
    lap.free = 5 * A.GB
    # an unverified take (just written, never copied) and a copied-but-not-on-Drive take
    take(d, "unverified.mkv", age=5)
    take(d, "nodrive.mkv", age=800)
    A.copy_stage(lap, store, lambda m: None)           # copies nodrive, no drive stage
    logs = []
    gone = A.prune_stage(lap, store, logs.append)
    assert gone[0] == "old.mkv" and "unverified.mkv" not in gone and "nodrive.mkv" not in gone
    assert (d / "unverified.mkv").exists() and (d / "nodrive.mkv").exists()


def test_changed_laptop_file_is_not_deleted(tmp_path):
    d, store, lap, dr = env(tmp_path, free_gb=1)
    take(d, "a.mkv"); run(lap, dr, store, tmp_path)
    (d / "a.mkv").write_bytes(b"y" * 4096)             # a different file under the same name
    assert A.prune_stage(lap, store, lambda m: None) == []


def test_drive_mismatch_blocks_prune(tmp_path):
    d, store, lap, dr = env(tmp_path, free_gb=1)
    class BadDrive(A.DirDrive):
        def stat(self, name): return {"id": "x", "size": 1, "md5": "0"}
    take(d, "a.mkv"); run(lap, BadDrive(tmp_path / "drive"), store, tmp_path)
    assert A.read_side(A.find_raw(store, "a.mkv"))["drive"] is None
    assert (d / "a.mkv").exists()


def test_copy_corruption_is_refused(tmp_path):
    d, store, lap, dr = env(tmp_path, free_gb=1)
    class Flaky(A.DirLaptop):
        def fetch(self, name, dest): Path(dest).write_bytes(b"corrupt")
    take(d, "a.mkv"); run(Flaky(d, 1), dr, store, tmp_path)
    assert A.find_raw(store, "a.mkv") is None and (d / "a.mkv").exists()
