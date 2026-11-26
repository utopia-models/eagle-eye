"""rails.py: the hook every outward stage passes through. Stdlib only.

Which rails are fixed per System is still open, so none is built in. A rail is a Python file in $EE_CONFIG/rails/ with

    def before_outward(system_id, stage_id, artifact) -> str | None   # a string holds the action and says why

No sender ships in this repository, so an outward stage is always held, whatever the rails say. A rail that cannot be
loaded or raises holds the action.
"""
import importlib.util
import os
from pathlib import Path


def holds(system_id, stage_id, artifact="", config=None):
    config = config or os.environ.get("EE_CONFIG")
    reasons = []
    for path in sorted((Path(config) / "rails").glob("*.py")) if config else []:
        try:
            spec = importlib.util.spec_from_file_location(f"rail_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            reason = module.before_outward(system_id, stage_id, artifact)
        except Exception as e:  # a broken rail must not open the gate
            reason = f"rail failed: {type(e).__name__}: {e}"
        if reason:
            reasons.append(f"{path.stem}: {reason}")
    return reasons + ["no sender is connected"]
