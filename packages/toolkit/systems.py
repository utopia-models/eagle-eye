"""systems.py: load systems/<id>/system.json and check its shape. Stdlib only."""
import json

import kit

REQUIRED = ("id", "version", "title", "does", "copies", "basis", "defaults", "stages", "rails", "quotes")


def paths(root=None):
    return sorted((root or kit.REPO / "systems").glob("*/system.json"))


def load_all(root=None):
    return {p.parent.name: json.loads(p.read_text(encoding="utf-8")) for p in paths(root)}


def cited(system):
    """Every id the system may quote or read: its copies plus each basis' cites."""
    ids = list(system["copies"])
    for option in system["basis"]["options"].values():
        ids += option["cites"]
    return list(dict.fromkeys(ids))


def problems(name, system, library=None):
    """What is wrong with one manifest; an empty list means it is usable."""
    missing = [k for k in REQUIRED if k not in system]
    if missing:
        return [f"missing {', '.join(missing)}"]
    bad = []
    if system["id"] != name:
        bad.append(f"id {system['id']!r} does not match folder {name!r}")
    if system["basis"]["default"] != "ours" or "ours" not in system["basis"]["options"]:
        bad.append("basis.default must be 'ours' and listed in basis.options")
    if not system["copies"]:
        bad.append("copies is empty")
    for ref in cited(system):
        try:
            kit.resolve(ref, library)
        except KeyError as e:
            bad.append(str(e.args[0]))
    for stage in system["stages"]:
        if not stage.get("id") or not (stage.get("outward") or stage.get("task")):
            bad.append(f"stage {stage.get('id')!r} needs an id and either a task or outward: true")
    return bad
