"""fm:21662: a fresh build's first draft is rewritten (rewrite_loop) before generate() refuses it."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("ONESHOT_AUTO_DIR", tempfile.mkdtemp())
os.environ.setdefault("ONESHOT_PKG_ROOT", tempfile.mkdtemp())
import oneshot_auto as OA  # noqa: E402
import upwork_rules as U  # noqa: E402


def test_scripts_and_gates_runs_the_rewrite_loop_first(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(U, "rewrite_loop", lambda pkg, rw: calls.append(("rewrite", rw)) or ([], 0))
    import gen_scripts, gates
    monkeypatch.setattr(gen_scripts, "generate", lambda pkg, upwork=False: calls.append(("generate", upwork)))
    monkeypatch.setattr(gates, "run_package", lambda pkg: {"ready": True, "gates": [], "blocking": []})
    rw = object()
    OA.scripts_and_gates({"text": "x"}, tmp_path, rewriter=rw)
    assert calls[0] == ("rewrite", rw) and calls[1] == ("generate", True)


def test_a_crashed_rewriter_still_lets_generate_refuse(monkeypatch, tmp_path):
    def boom(pkg, rw):
        raise RuntimeError("model down")
    monkeypatch.setattr(U, "rewrite_loop", boom)
    import gen_scripts, gates
    seen = []
    monkeypatch.setattr(gen_scripts, "generate", lambda pkg, upwork=False: seen.append(1))
    monkeypatch.setattr(gates, "run_package", lambda pkg: {"ready": False, "gates": [], "blocking": []})
    OA.scripts_and_gates({"text": "x"}, tmp_path, rewriter=lambda p, f: None)
    assert seen == [1]
