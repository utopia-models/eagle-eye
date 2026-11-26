---
id: kit.readme
title: The kit - what Systems copy from and cite
kind: kit
version: 1.0.0
tags: [kit, operators, sources]
license: Apache-2.0
---
# The kit

Real operators' playbooks that Eagle Eye Systems copy from and cite.

| folder | what | licence |
|---|---|---|
| `writeups/` | our own write-ups, in our words, each linking back to the original | Apache-2.0 (the originals stay their authors') |
| `hormozi-mit/` | community skill packs about Alex Hormozi's frameworks, copied unchanged at a pinned commit | MIT, see each folder's `LICENSE` and `SOURCE.md` |

**Cite** a file as `kit:<path under kit/ without .md>`, for example `kit:writeups/ocp-wiki`. Cite a library entry as
`lib:<path under library/ without extension>`, for example `lib:playbooks/upwork-oneshot`.

**Quotes are checked.** A quoted line in a `systems/*/system.json`, or a write-up line shaped
`> the quoted line (kit:id)`, must appear in the cited file or the build fails (`packages/toolkit/quote_check.py`).

**One copy.** A consumer outside this repo reads the kit from a checkout pinned to a commit and points `EE_KIT` at its
`library/` folder.

**Not in this tree:** paid course material. See `writeups/fazio.md`.
