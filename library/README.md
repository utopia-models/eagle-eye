---
id: library.readme
title: Eagle Eye library - read me first
kind: readme
version: 1.0.0
tags: [library, index, start-here]
license: CC-BY-4.0
---
# Eagle Eye library

A knowledge base any person or any LLM can read: playbooks, meta prompts, templates, research and copy rules. Plain Markdown and YAML with a small front-matter block. Nothing here is specific to one agent product.

| folder | holds | start with |
|---|---|---|
| `playbooks/` | steps, standards and examples for a motion | `upwork-oneshot.md`, `cold-apply-campaign.md`, `founder-oneshot.md`, `client-close-and-delivery.md` |
| `prompts/` | meta prompts as portable files: `{{var}}` placeholders, inputs and outputs in front-matter | `vsl-script-writer.md`, `letter-writer.md`, `video-reviewer.md` |
| `templates/` | offer, SOW, MSA, Upwork-safe variants, onboarding, follow-up (+ `html/` Jinja2 renderers) | `offer.md` |
| `research/` | dated reports with sources | `ui-libraries.md`, `upwork-contract-terms.md` |
| `copy-rules/` | checks as data (YAML) read by `copy_lint.py` | `letter-caveats.yaml` |
| `sources/` | an index of external sources; the paid-course copies live ONLY in the private overlay | `INDEX.md` |

## Use it
```
python3 library/library_index.py search "guarantee"                       # lexical search, public tree
python3 library/library_index.py search "guarantee" --overlay <private>/library   # public + private overlay
python3 library/library_index.py build                                    # writes index.json and llms.txt
python3 library/library_index.py check                                    # fails if private text is in a public path
python3 library/copy_lint.py letter-caveats letter.md                     # a copy-rules file is the whole linter
```
Full text search is plain `rg`. `index.json` lists title, kind, tags, path for every public entry; `llms.txt` is the same for an LLM.

## Entry format
```
---
id: prompt.letter-writer      # <kind>.<slug>
title: ...
kind: prompt                  # playbook | prompt | template | research | copy-rules | sources
version: 1.0.0                # semver; bump on any change to meaning
tags: [..]
inputs: [..]   outputs: [..]  # prompts and templates
model_hints: {..}             # advisory only; every prompt works on any capable model
license: CC-BY-4.0
---
```
Variables are `{{name}}`. Exporters can turn `prompts/` into Dotprompt, Prompty or promptfoo files; no vendor format is canonical.

## Private overlay
The private repo `eagle-eye-utopia` holds `library/` with the same schema. A file at the same path overrides the public one; `library/sources/fazio/` holds the full copies of a paid course, which never enter this repo. Agents search both.

## Licence
Library text: CC BY 4.0. Code (`library_index.py`, `copy_lint.py`): the repository licence. Third-party material is cited in `sources/INDEX.md`, never copied.
