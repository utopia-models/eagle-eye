#!/usr/bin/env python3
"""vsl_archive.py: every VSL recording leaves the ETH laptop (knowledge#15179, Feature #15177).

Tyler 2026-11-18 12:21 AM: the laptop will run out of disk; 12:22 AM: "I do want to save ALL the VSLs, but my laptop is
not the best place to save it." So EVERY take is archived and the laptop is only a staging buffer.

  vsl_archive.py sync     [--once]   laptop -> Ra (size+sha256 verified) -> Drive (md5 verified) -> prune the laptop
  vsl_archive.py keep  TAKE [--label kept|sent|rejected]     (`vsl keep`) a retrieval label, never a storage decision
  vsl_archive.py status              one JSON line; sync also writes it to $VSL_ARCHIVE_STATE/status.json

Stages (one run does all; a failure in one take never stops the next):
  1 copy    a finished mkv (mtime >= SETTLE_S old) is pulled to <store>/<date>/raw/<name> through a .part file, its
            size and sha256 are compared with the laptop's own, and <name>.archive.json is written. Runs every 2 min,
            so a recording is on Ra with its sidecar well inside the 5 minutes the acceptance names.
  2 drive   a Ra-verified take is uploaded to Drive (manifest key raw.vsl-takes, resolved at runtime) and read back:
            size and md5 must match; the sidecar records drive.key, drive.id and drive.verified_at.
  3 prune   a laptop file is deleted ONLY when its sidecar shows BOTH copies verified AND the laptop file still has the
            sidecar's size, and (a) both were verified >= PRUNE_AFTER_H (24) ago, or (b) laptop free space is under
            LOW_GB (20): oldest verified first, stopping once free space is back at LOW_GB. A take with no sidecar, no
            Ra copy, or no Drive copy is never deleted, whatever the free space.

The transports are two small classes (Laptop, Drive) so the tests run on fake directories. The real Laptop is ssh to
the WSL side (kxdev, where /mnt/c is C:, the same hop eth-disk-alarm.sh uses); the real Drive is rclone remote
gdrive-sa (MIT) rooted at the manifest folder.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

GB = 1024 ** 3
SETTLE_S = int(os.environ.get("VSL_ARCHIVE_SETTLE_S", "60"))
PRUNE_AFTER_H = float(os.environ.get("VSL_ARCHIVE_PRUNE_AFTER_H", "24"))
LOW_GB = float(os.environ.get("VSL_ARCHIVE_LOW_GB", "20"))
LABELS = ("kept", "sent", "rejected")
DRIVE_KEY = "raw.vsl-takes"
STORE = Path(os.environ.get("VSL_STORE", "/srv/vsl"))
STATE = Path(os.environ.get("VSL_ARCHIVE_STATE", str(Path.home() / ".local/state/vsl-archive")))
HOST = os.environ.get("VSL_ARCHIVE_HOST", "kxdev@100.103.62.104")
LAPTOP_DIR = os.environ.get("VSL_ARCHIVE_LAPTOP_DIR", "/mnt/c/Users/ethde/Videos/VSL")
EXT = (".mkv",)
CATEGORIES = Path(os.environ.get("VSL_CATEGORIES") or Path(__file__).resolve().parents[2] / "vsl" / "take-categories.json")
SENT_LEDGER = os.environ.get("EAGLE_UPWORK_LEDGER") or "/home/upwork/.claude/state/net/upwork/ledger.jsonl"   # same ledger Eagle Eye reads
SENT_GOAL, SENT_GOAL_BY = 100, "2026-12-31"   # Tyler, fleetmail 11730: 100 sent VSLs by the end of 2026


def now():
    return time.time()


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def md5_file(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------- transports
class Laptop:
    """What the sync needs from the laptop. list() -> [(name, size, mtime)]."""
    def list(self): raise NotImplementedError
    def free_bytes(self): raise NotImplementedError
    def fetch(self, name, dest): raise NotImplementedError
    def sha256(self, name): raise NotImplementedError
    def size(self, name): raise NotImplementedError
    def delete(self, name): raise NotImplementedError


class SshLaptop(Laptop):
    def __init__(self, host=HOST, d=LAPTOP_DIR):
        self.host, self.d = host, d

    def _ssh(self, cmd, **kw):
        key = Path(os.environ.get("VSL_ARCHIVE_KEY", str(Path.home() / ".ssh/id_ed25519_eth")))
        ident = ["-i", str(key), "-o", "IdentitiesOnly=yes"] if key.exists() else []
        return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", *ident, self.host, cmd],
                              capture_output=True, text=True, **kw)

    def list(self):
        r = self._ssh(f"find '{self.d}' -maxdepth 1 -type f -name '*.mkv' -printf '%f\\t%s\\t%T@\\n'")
        if r.returncode != 0:
            raise RuntimeError(f"laptop unreachable: {r.stderr.strip()[:160]}")
        out = []
        for ln in r.stdout.splitlines():
            n, s, m = ln.split("\t")
            out.append((n, int(s), float(m)))
        return out

    def free_bytes(self):
        r = self._ssh(f"df -B1 --output=avail '{self.d}' | tail -1")
        return int(r.stdout.strip())

    def fetch(self, name, dest):
        key = Path(os.environ.get("VSL_ARCHIVE_KEY", str(Path.home() / ".ssh/id_ed25519_eth")))
        ident = f" -i {key} -o IdentitiesOnly=yes" if key.exists() else ""  # same key as _ssh; bare ssh offered none (16394)
        r = subprocess.run(["rsync", "-t", "-e", "ssh -o BatchMode=yes -o ConnectTimeout=10" + ident,
                            f"{self.host}:{self.d}/{name}", str(dest)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"rsync failed: {r.stderr.strip()[:160]}")

    def sha256(self, name):
        r = self._ssh(f"sha256sum '{self.d}/{name}'")
        if r.returncode != 0:
            raise RuntimeError("remote sha256sum failed")
        return r.stdout.split()[0]

    def size(self, name):
        r = self._ssh(f"stat -c %s '{self.d}/{name}'")
        return int(r.stdout.strip())

    def delete(self, name):
        r = self._ssh(f"rm -f -- '{self.d}/{name}'")
        if r.returncode != 0:
            raise RuntimeError("remote rm failed")


class DirLaptop(Laptop):
    """A plain directory standing in for the laptop (tests). `free` is settable."""
    def __init__(self, d, free_gb=500):
        self.d, self.free = Path(d), free_gb * GB

    def list(self):
        return [(p.name, p.stat().st_size, p.stat().st_mtime) for p in sorted(self.d.glob("*.mkv"))]

    def free_bytes(self): return int(self.free)
    def fetch(self, name, dest): shutil.copyfile(self.d / name, dest)
    def sha256(self, name): return sha256_file(self.d / name)
    def size(self, name): return (self.d / name).stat().st_size

    def delete(self, name):
        (self.d / name).unlink()
        self.free += 0  # tests set free explicitly


class Drive:
    def upload(self, local, name): raise NotImplementedError
    def stat(self, name): raise NotImplementedError   # -> {"id","size","md5"} or None


class RcloneDrive(Drive):
    def __init__(self, folder_id, remote="gdrive-sa"):
        self.base = ["rclone", "--drive-root-folder-id", folder_id]
        self.remote = remote

    def upload(self, local, name):
        r = subprocess.run(self.base + ["copyto", str(local), f"{self.remote}:{name}"], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"rclone copyto failed: {r.stderr.strip()[:160]}")

    def stat(self, name):
        d, _, f = name.rpartition("/")
        r = subprocess.run(self.base + ["lsjson", "--hash", "--files-only", f"{self.remote}:{d}"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return None
        for e in json.loads(r.stdout or "[]"):
            if e["Name"] == f:
                return {"id": e["ID"], "size": e["Size"], "md5": (e.get("Hashes") or {}).get("md5") or (e.get("Hashes") or {}).get("MD5")}
        return None


class DirDrive(Drive):
    def __init__(self, d): self.d = Path(d)

    def upload(self, local, name):
        p = self.d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local, p)

    def stat(self, name):
        p = self.d / name
        return {"id": "fake:" + name, "size": p.stat().st_size, "md5": md5_file(p)} if p.exists() else None


# ---------------------------------------------------------------- sidecar
def side_path(raw):
    return Path(str(raw) + ".archive.json")


def read_side(raw):
    p = side_path(raw)
    return json.loads(p.read_text()) if p.exists() else None


def write_side(raw, d):
    p = side_path(raw)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1, sort_keys=True))
    os.replace(tmp, p)


def raw_dir(store, mtime):
    return Path(store) / time.strftime("%Y-%m-%d", time.localtime(mtime)) / "raw"


def find_raw(store, name):
    for p in Path(store).glob(f"*/raw/{name}"):
        return p
    return None


# ---------------------------------------------------------------- stages
def copy_stage(lap, store, log, t=None):
    t = t or now()
    n = 0
    for name, size, mtime in lap.list():
        if t - mtime < SETTLE_S:
            continue                                   # still being written
        dest = find_raw(store, name) or raw_dir(store, mtime) / name
        sc = read_side(dest) if dest.exists() else None
        if sc and sc.get("ra", {}).get("verified_at") and sc["size"] == size:
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_name(dest.name + ".part")
            lap.fetch(name, part)
            want = lap.sha256(name)
            got = sha256_file(part)
            if part.stat().st_size != size or got != want or lap.size(name) != size:
                part.unlink()
                raise RuntimeError(f"verify failed (size {part.stat().st_size if part.exists() else '?'} vs {size}, sha {got[:8]} vs {want[:8]})")
            os.replace(part, dest)
            prev = sc or {}
            write_side(dest, {"name": name, "size": size, "sha256": got, "label": prev.get("label", "unlabeled"),
                              "ra": {"path": str(dest), "verified_at": iso(now()), "verified_ts": now()},
                              "drive": prev.get("drive")})
            log(f"copied {name} {size}B sha256 {got[:12]}")
            n += 1
        except Exception as e:
            log(f"copy FAILED {name}: {e}")
    return n


def drive_stage(store, drive, log):
    n = 0
    for raw in sorted(Path(store).glob("*/raw/*.mkv")):
        sc = read_side(raw)
        if not sc or not sc.get("ra", {}).get("verified_at") or (sc.get("drive") or {}).get("verified_at"):
            continue
        try:
            remote = f"{raw.parent.parent.name}/{raw.name}"
            drive.upload(raw, remote)
            st = drive.stat(remote)
            if not st or st["size"] != sc["size"] or st["md5"] != md5_file(raw):
                raise RuntimeError(f"read-back mismatch {st}")
            sc["drive"] = {"key": DRIVE_KEY, "path": remote, "id": st["id"], "md5": st["md5"],
                           "verified_at": iso(now()), "verified_ts": now()}
            write_side(raw, sc)
            log(f"drive {raw.name} -> {DRIVE_KEY}/{remote} id {st['id']}")
            n += 1
        except Exception as e:
            log(f"drive FAILED {raw.name}: {e}")
    return n


# ---------------------------------------------------------------- game-tape stage (Drive VSL/<date>/<take>.mp4 + index)
TAPE_ROOT = "VSL"
MKV_DIRS = [Path.home() / "vsl-takes"]


def _duration(mp4, d):
    if d.get("duration_s"):
        return round(float(d["duration_s"]), 1)
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)],
                       capture_output=True, text=True)
    try:
        return round(float(r.stdout.strip()), 1)
    except ValueError:
        return None


def _verdict(review, label):
    if label in LABELS:
        return label
    try:
        head = Path(review).read_text()[:600]
    except (OSError, TypeError):
        return "unreviewed"
    return "refused" if "REFUSED" in head else "ok"


def take_category(take, sidecar=None, rules=None):
    """The bank category of a take: its sidecar's own `category`, else the first matching rule in take-categories.json."""
    if (sidecar or {}).get("category"):
        return sidecar["category"]
    try:
        cfg = json.loads(Path(rules or CATEGORIES).read_text())
    except (OSError, ValueError):
        return "uncategorized"
    for pat, cat in cfg.get("rules", []):
        if re.search(pat, take):
            return cat
    return cfg.get("default", "uncategorized")


def sent_files(ledger=None):
    """Distinct (client, file) `vsl_sent` rows of the Upwork ledger -> set of file stems, or None when the ledger is unreadable
    (never a zero: an unread ledger is unknown)."""
    try:
        rows = [json.loads(l) for l in Path(ledger or SENT_LEDGER).read_text().splitlines() if l.strip()]
    except (OSError, ValueError):
        return None
    seen = {}
    for r in rows:
        if r.get("event") in ("vsl_sent", "video_sent"):
            seen[(r.get("client") or r.get("job") or r.get("key"), r.get("file") or "")] = Path(r.get("file") or "").stem
    return seen


def tape_rows(store):
    """One row per trimmed take mp4 under <store>/<date>/ (the json beside it is optional)."""
    rows = []
    for mp4 in sorted(Path(store).glob("20??-??-??/*.mp4")):
        jp = mp4.with_suffix(".json")
        try:
            d = json.loads(jp.read_text()) if jp.exists() else {}
        except ValueError:
            d = {}
        take, day = mp4.stem, mp4.parent.name
        client = d.get("name") or re.sub(r"-take\d+(-take\d+)?$", "", take)
        review = mp4.with_suffix(".md")
        obs = (d.get("obs_file") or "").replace("\\", "/").rsplit("/", 1)[-1]
        rows.append({"client": client, "take": take, "date": day, "length_s": _duration(mp4, d),
                     "verdict": _verdict(review, d.get("label")),
                     "category": take_category(take, d),
                     "transcript": str(review) if review.exists() else None,
                     "mp4": f"{TAPE_ROOT}/{day}/{take}.mp4", "mp4_bytes": mp4.stat().st_size, "_src": mp4,
                     "mkv": f"{TAPE_ROOT}/{day}/{take}.mkv" if obs else None, "_obs": obs})
    return rows


def tape_stage(store, drive, log, state):
    """Upload every trimmed mp4 (and its original mkv when the file is on Ra) to Drive VSL/<date>/, size+md5 read back,
    then write VSL/index.md and VSL/index.json. A take already verified (state file) is not re-uploaded."""
    stp = Path(state) / "tape.json"
    done = json.loads(stp.read_text()) if stp.exists() else {}
    n = 0
    rows = tape_rows(store)
    for r in rows:
        items = [(r["mp4"], r["_src"])]
        if r["_obs"]:
            for dd in MKV_DIRS + list(Path(store).glob("*/raw")):
                c = Path(dd) / r["_obs"]
                if c.exists():
                    items.append((r["mkv"], c))
                    break
        for key, src in items:
            sz = src.stat().st_size
            if (done.get(key) or {}).get("size") == sz:
                continue
            try:
                drive.upload(src, key)
                st = drive.stat(key)
                if not st or st["size"] != sz or st["md5"] != md5_file(src):
                    raise RuntimeError(f"read-back mismatch {st}")
                done[key] = {"size": sz, "id": st["id"], "verified_at": iso(now())}
                log(f"tape {key} id {st['id']}")
                n += 1
            except Exception as e:
                log(f"tape FAILED {key}: {e}")
    Path(state).mkdir(parents=True, exist_ok=True)
    stp.write_text(json.dumps(done))
    pub = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    for r in pub:
        r["drive_id"] = (done.get(r["mp4"]) or {}).get("id")
        r["mkv"] = r["mkv"] if r["mkv"] in done else None
    pub.sort(key=lambda r: (r["date"], r["take"]))
    seen = sent_files()
    sent_stems = None if seen is None else set(seen.values())
    for r in pub:   # a take is sent when a ledger file stem is the take or its -upwork export
        r["sent"] = None if sent_stems is None else any(s and (r["take"] == s or r["take"] + "-upwork" == s or s.startswith(r["take"] + "-upwork")) for s in sent_stems)
    total = None if seen is None else len(seen)
    if total is None:
        line = f"Sent: unknown (ledger {SENT_LEDGER} unreadable from this box); goal {SENT_GOAL} by {SENT_GOAL_BY}."
    else:
        line = f"Sent: {total} of {SENT_GOAL} by {SENT_GOAL_BY} (distinct client+file `vsl_sent` rows in the Upwork ledger; {SENT_GOAL - total} to go)."
    md = ["# VSL game tape index", "", f"Generated {iso(now())} by vsl_archive.py. Drive: manifest key {DRIVE_KEY}, path VSL/<date>/<take>.mp4.", "", line, "",
          "client | category | date | length | verdict | sent | transcript | drive path", "--- | --- | --- | --- | --- | --- | --- | ---"]
    for r in pub:
        ln = f"{r['length_s']:.0f}s" if r["length_s"] else "?"
        sn = {True: "y", False: "n", None: "?"}[r["sent"]]
        md.append(f"{r['client']} | {r['category']} | {r['date']} | {ln} | {r['verdict']} | {sn} | {r['transcript'] or '-'} | {r['mp4']}" + (" (+mkv)" if r["mkv"] else ""))
    (Path(state) / "index.md").write_text("\n".join(md) + "\n")
    (Path(state) / "index.json").write_text(json.dumps(pub, indent=1))
    (Path(state) / "sent.json").write_text(json.dumps({"sent": total, "goal": SENT_GOAL, "by": SENT_GOAL_BY}))
    for f in ("index.md", "index.json"):
        try:
            drive.upload(Path(state) / f, f"{TAPE_ROOT}/{f}")
        except Exception as e:
            log(f"tape index {f} FAILED: {e}")
    return n


def prune_stage(lap, store, log, t=None):
    """Delete only verified takes. Returns the names deleted."""
    t = t or now()
    rows = []
    for name, size, mtime in lap.list():
        raw = find_raw(store, name)
        sc = read_side(raw) if raw else None
        if not sc or sc.get("size") != size:
            continue                                   # no sidecar, or the laptop file is not the one verified
        ra, dr = sc.get("ra") or {}, sc.get("drive") or {}
        if not (ra.get("verified_at") and dr.get("verified_at") and dr.get("id")):
            continue
        rows.append((min(ra["verified_ts"], dr["verified_ts"]), name, mtime))
    rows.sort(key=lambda r: (r[2], r[1]))              # oldest recording first
    gone = []
    free = lap.free_bytes()
    for ts, name, _ in rows:
        old_enough = (t - max(ra_ts(store, name), dr_ts(store, name))) >= PRUNE_AFTER_H * 3600
        low = free < LOW_GB * GB
        if not (old_enough or low):
            continue
        try:
            sz = lap.size(name)
            lap.delete(name)
            gone.append(name)
            log(f"pruned {name} ({'free<%gGB' % LOW_GB if low and not old_enough else '>=%gh after both copies' % PRUNE_AFTER_H})")
            free = lap.free_bytes() if low else free + sz
        except Exception as e:
            log(f"prune FAILED {name}: {e}")
    return gone


def ra_ts(store, name):
    return read_side(find_raw(store, name))["ra"]["verified_ts"]


def dr_ts(store, name):
    return read_side(find_raw(store, name))["drive"]["verified_ts"]


def status(lap, store):
    pend_ra = pend_dr = 0
    try:
        listing = lap.list()
        free = lap.free_bytes()
        reach = True
    except Exception:
        listing, free, reach = [], None, False
    for name, size, mtime in listing:
        raw = find_raw(store, name)
        sc = read_side(raw) if raw else None
        if not sc or not sc.get("ra", {}).get("verified_at"):
            pend_ra += 1
        elif not (sc.get("drive") or {}).get("verified_at"):
            pend_dr += 1
    return {"at": iso(now()), "laptop_reachable": reach,
            "laptop_free_gb": None if free is None else round(free / GB, 1),
            "on_laptop": len(listing), "pending_ra": pend_ra, "pending_drive": pend_dr,
            "line": (f"vsl-archive: laptop {'%.0f' % (free / GB) if free is not None else '?'} GB free, "
                     f"{len(listing)} on laptop, {pend_ra} not on Ra, {pend_dr} not on Drive")}


def sync(lap, drive, store, state, log):
    # An offline laptop is a normal state (it travels): say so and still finish Drive for what Ra already holds.
    # Exiting non-zero here would file a board issue every 2 minutes.
    pruned = 0
    try:
        copy_stage(lap, store, log)
    except RuntimeError as e:
        log(f"laptop offline, skipping copy and prune: {e}")
        lap_up = False
    else:
        lap_up = True
    drive_stage(store, drive, log)
    try:
        tape_stage(store, drive, log, state)
    except Exception as e:
        log(f"tape stage FAILED: {e}")
    if lap_up:
        pruned = prune_stage(lap, store, log)
    st = status(lap, store)
    st["pruned"] = pruned
    Path(state).mkdir(parents=True, exist_ok=True)
    (Path(state) / "status.json").write_text(json.dumps(st))
    log(st["line"])
    return st


def keep(store, take, label):
    """`vsl keep <take>`: set the retrieval label on a take's sidecar (stem, name or path)."""
    take = Path(take).name
    cands = [p for p in Path(store).glob("*/raw/*.mkv") if p.name == take or p.stem == take or p.stem.startswith(take)]
    if len(cands) != 1:
        raise SystemExit(f"keep: {len(cands)} takes match {take!r}")
    sc = read_side(cands[0])
    if not sc:
        raise SystemExit(f"keep: {cands[0].name} has no archive sidecar yet")
    sc["label"] = label
    write_side(cands[0], sc)
    return cands[0].name, label


def resolve_drive_folder():
    here = Path(__file__).resolve()
    for up in here.parents:
        s = up / "_infra/scripts/drive-resolve.sh"
        if s.exists():
            r = subprocess.run(["bash", str(s), DRIVE_KEY], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().splitlines()[-1]
    raise SystemExit(f"cannot resolve manifest key {DRIVE_KEY}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="vsl_archive")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync"); s.add_argument("--once", action="store_true")
    k = sub.add_parser("keep"); k.add_argument("take"); k.add_argument("--label", choices=LABELS, default="kept")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    log = lambda m: print(f"{iso(now())} {m}", flush=True)
    if a.cmd == "keep":
        n, l = keep(STORE, a.take, a.label)
        print(f"{n}: label {l}")
        return 0
    lap = SshLaptop()
    if a.cmd == "status":
        print(json.dumps(status(lap, STORE)))
        return 0
    sync(lap, RcloneDrive(resolve_drive_folder()), STORE, STATE, log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
