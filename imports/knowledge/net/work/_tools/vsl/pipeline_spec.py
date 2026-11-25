#!/usr/bin/env python3
"""pipeline_spec.py: load, validate and lint vsl/pipelines/*.yaml against the code (knowledge#17826).
  lint   exit 1 when: a spec fails pipeline.schema.json; a stage's handler file/function does not exist; a stage id repeats; an owner is not in
         wi/registry/organization.yaml; or (upwork) oneshot_auto.STAGE_HANDLERS and the spec disagree (a handler with no stage, a stage with no handler).
  feed   print the JSON the OCC OneShotsSection renders: per pipeline, per stage the fields plus `handler_url` (a GitHub link to the handler file).
Usage: pipeline_spec.py lint | feed"""
import ast
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
KNOW = HERE.parents[3]
WORK = KNOW / "net/work"
SPECS = WORK / "vsl/pipelines"
SCHEMA = SPECS / "pipeline.schema.json"
REGISTRY = KNOW / "wi/registry/organization.yaml"
GH = "https://github.com/utopia-models/knowledge/blob/main/net/work/"


def load_all():
    return {p.stem: yaml.safe_load(p.read_text()) for p in sorted(SPECS.glob("*.yaml"))}


def functions(path):
    return {n.name for n in ast.walk(ast.parse(Path(path).read_text())) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def lint(specs=None, registry_ids=None, handlers=None):
    """-> [problem strings]; empty = code and spec agree. `handlers` = {stage_id: 'file:function'} of the upwork dispatch table (read from code by AST)."""
    import jsonschema
    specs = specs if specs is not None else load_all()
    schema = json.loads(SCHEMA.read_text())
    if registry_ids is None:
        registry_ids = set(yaml.safe_load(REGISTRY.read_text())["agents"])
    out = []
    for name, doc in specs.items():
        for e in jsonschema.Draft202012Validator(schema).iter_errors(doc):
            out.append(f"{name}: schema: {e.message}")
        if out and any(x.startswith(f"{name}: schema") for x in out):
            continue
        seen = set()
        if doc["owner_agent"] if "owner_agent" in doc else False:
            if doc["owner_agent"] not in registry_ids:
                out.append(f"{name}: owner_agent {doc['owner_agent']!r} is not in the registry")
        for s in doc["stages"]:
            if s["id"] in seen:
                out.append(f"{name}: stage id {s['id']} repeats")
            seen.add(s["id"])
            if s["owner"] not in registry_ids:
                out.append(f"{name}.{s['id']}: owner {s['owner']!r} is not in the registry")
            f, fn = s["handler"].split(":")
            fp = WORK / f
            if not fp.is_file():
                out.append(f"{name}.{s['id']}: handler file {f} does not exist")
            elif fn not in functions(fp):
                out.append(f"{name}.{s['id']}: handler {fn} is not defined in {f}")
    up = specs.get("upwork")
    if up is not None:
        table = handlers if handlers is not None else code_handlers()
        spec_h = {s["id"]: s["handler"].split(":")[1] for s in up["stages"]}
        for sid, fn in table.items():
            if sid not in spec_h:
                out.append(f"upwork: handler {fn} registered for {sid!r} has no stage in upwork.yaml")
            elif spec_h[sid] != fn:
                out.append(f"upwork.{sid}: spec says {spec_h[sid]} but the dispatch table runs {fn}")
        for sid in spec_h:
            if sid not in table:
                out.append(f"upwork.{sid}: stage has no handler in oneshot_auto.STAGE_HANDLERS")
    return out


def code_handlers():
    """STAGE_HANDLERS read from the source by AST (no import: importing oneshot_auto touches state dirs)."""
    tree = ast.parse((HERE / "oneshot_auto.py").read_text())
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "STAGE_HANDLERS" for t in n.targets):
            return {k.value: v.id for k, v in zip(n.value.keys, n.value.values)}
    return {}


def feed():
    return {"pipelines": [{"pipeline": n, "owner_agent": d.get("owner_agent"),
                           "stages": [dict(s, handler_url=GH + s["handler"].split(":")[0]) for s in d["stages"]]} for n, d in load_all().items()]}


if __name__ == "__main__":
    if sys.argv[1:] == ["feed"]:
        print(json.dumps(feed(), indent=1))
    elif sys.argv[1:] == ["lint"]:
        p = lint()
        print("\n".join(p) or "pipeline spec: code and spec agree")
        sys.exit(1 if p else 0)
    else:
        sys.exit(__doc__)
