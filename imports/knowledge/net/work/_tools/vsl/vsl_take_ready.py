#!/usr/bin/env python3
"""vsl_take_ready.py: the take-ready check, read off the SCREEN before he records (knowledge#16072, B2 of #14969).

  vsl_take_ready.py READING.json            decide on a screen reading (exit 0 READY, 1 REFUSED, 2 bad input)
  vsl_take_ready.py --obs HOST:PORT [--reading R.json]   take the OBS half live (GetRecordStatus), merge into R

A READING is what was observed on the capture, never what the pipeline believes:
  diagram: {bbox:{x,y,w,h}, viewport:{w,h}, frame_hashes:[...>=2 captures ~1 s apart]}   the architecture diagram as drawn
  demo:    {screen_text:"...", checks:{boots,health,seed_data,client_stack: bool}}        the demo on the CLIENT's stack
  obs:     {window:"fullscreen"|"windowed"|"minimised", output_active: bool}              OBS window + GetRecordStatus.outputActive
Refuses unless: the diagram is fully inside the viewport and its frames differ (moving); the demo shows no sign-in/login
screen and passes all four checks; OBS is full screen; outputActive is true. Every refusal names its gate; a MISSING field is a
refusal (an unread screen is not a pass). stdlib only; the OBS read uses obs-websocket v5 over a raw socket only for --obs.
"""
import json, sys

SIGN_IN = ("sign in", "log in", "login", "sign up", "enter your password", "forgot password", "session expired")
DEMO_CHECKS = ("boots", "health", "seed_data", "client_stack")


def decide(r):
    """-> list of refusals (empty = READY)."""
    rs = []
    d = r.get("diagram")
    if not isinstance(d, dict) or not d.get("bbox") or not d.get("viewport"):
        rs.append("diagram: not read from the screen (no bbox/viewport)")
    else:
        b, v = d["bbox"], d["viewport"]
        if b["x"] < 0 or b["y"] < 0 or b["x"] + b["w"] > v["w"] or b["y"] + b["h"] > v["h"]:
            rs.append(f"diagram: clipped, bbox {b['x']},{b['y']} {b['w']}x{b['h']} exceeds viewport {v['w']}x{v['h']}")
        fh = d.get("frame_hashes") or []
        if len(fh) < 2:
            rs.append("diagram: motion not read (need >=2 frames)")
        elif len(set(fh)) < 2:
            rs.append("diagram: not moving (all captured frames identical)")
    m = r.get("demo")
    if not isinstance(m, dict):
        rs.append("demo: not read from the screen")
    else:
        t = (m.get("screen_text") or "").lower()
        hit = [s for s in SIGN_IN if s in t]
        if hit:
            rs.append(f"demo: a sign-in screen is showing ({hit[0]!r})")
        c = m.get("checks") or {}
        for k in DEMO_CHECKS:
            if c.get(k) is not True:
                rs.append(f"demo: check {k} did not pass on the client's stack")
    o = r.get("obs")
    if not isinstance(o, dict):
        rs.append("obs: not read")
    else:
        if o.get("window") != "fullscreen":
            rs.append(f"obs: window is {o.get('window')!r}, not full screen")
        if o.get("output_active") is not True:
            rs.append("obs: GetRecordStatus.outputActive is not true (not recording)")
    if r.get("dryrun_fresh") is not True:
        rs.append("dry run: the nightly dry run is missing, stale or FAIL (vsl_dryrun.py --fresh)")
    return rs


def obs_status(hostport):
    """GetRecordStatus over obs-websocket v5 (no auth only; a password-protected OBS raises and the caller refuses)."""
    import base64, os, socket, struct
    host, port = hostport.rsplit(":", 1)
    s = socket.create_connection((host, int(port)), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET / HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: obswebsocket.json\r\n\r\n").encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += s.recv(4096)
    buf = buf.split(b"\r\n\r\n", 1)[1]

    def send(o):
        p = json.dumps(o).encode(); mask = os.urandom(4)
        h = bytes([0x81]) + (bytes([0x80 | len(p)]) if len(p) < 126 else bytes([0x80 | 126]) + struct.pack(">H", len(p)))
        s.sendall(h + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(p)))

    def recv():
        nonlocal buf
        def need(n):
            nonlocal buf
            while len(buf) < n:
                buf += s.recv(4096)
        need(2); ln = buf[1] & 0x7F; off = 2
        if ln == 126: need(4); ln = struct.unpack(">H", buf[2:4])[0]; off = 4
        need(off + ln); p = buf[off:off + ln]; buf = buf[off + ln:]
        return json.loads(p)

    hello = recv()
    if hello["d"].get("authentication"):
        raise RuntimeError("OBS websocket needs a password")
    send({"op": 1, "d": {"rpcVersion": 1}}); recv()
    send({"op": 6, "d": {"requestType": "GetRecordStatus", "requestId": "r1"}})
    while True:
        m = recv()
        if m["op"] == 7:
            return bool(m["d"]["responseData"]["outputActive"])


def main(argv):
    a = list(argv); reading = {}; obs = None; path = None
    while a:
        k = a.pop(0)
        if k == "--obs" and a: obs = a.pop(0)
        elif k == "--reading" and a: path = a.pop(0)
        elif not k.startswith("--") and path is None: path = k
        else: print(__doc__); return 2
    try:
        if path: reading = json.load(open(path))
        if obs:
            reading.setdefault("obs", {})["output_active"] = obs_status(obs)
    except Exception as e:
        print(f"REFUSED: could not read the screen/OBS: {e}"); return 2
    if "dryrun_fresh" not in reading:
        try:
            sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "horus"))
            import vsl_dryrun
            reading["dryrun_fresh"] = vsl_dryrun.fresh()
        except Exception:
            reading["dryrun_fresh"] = False
    rs = decide(reading)
    if rs:
        print("REFUSED: not take-ready")
        for r in rs: print("  -", r)
        return 1
    print("TAKE-READY"); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
