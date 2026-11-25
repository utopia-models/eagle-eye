"""Imports horus/vsl_cue_lint.py (a sibling tool dir, not a package) for the pipeline; one lint, never a copy (knowledge#16486)."""
import importlib.util
from pathlib import Path

_p = Path(__file__).resolve().parents[1] / "horus" / "vsl_cue_lint.py"
_s = importlib.util.spec_from_file_location("vsl_cue_lint", _p)
_m = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_m)
lint = _m.lint
