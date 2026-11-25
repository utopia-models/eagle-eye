---
id: research.library-design
title: Library design - formats, layout, index and overlay for an agent-neutral knowledge base
kind: research
version: 1.0.0
tags: [library,markdown,dotprompt,mcp,llms-txt,index]
date: 2026-11-24
license: CC-BY-4.0
---
# Eagle Eye `library/` research (2026-11-24)

Legend: [F] = fetched this session and read; [K] = background knowledge, not re-verified (check before relying).

## 1. Prompt-as-code
- Dotprompt (Google, github.com/google/dotprompt) [F]: executable prompt template, cross-language and cross-provider; Handlebars body (`{{text}}`); YAML frontmatter with `model`, `input.schema`, `output` (format json + schema, `?` marks optional), model config (temperature, max tokens). Partials/versioning are in /spec, not read. Takeaway: input/output schemas in frontmatter are what make a prompt testable.
- Prompty (Microsoft, prompty.ai) [F]: one `.prompty` = YAML frontmatter + markdown body. Frontmatter: model config, typed inputs with defaults, tools (function/MCP/OpenAPI), agent controls. Template engine Jinja2 or Mustache, rendered first, then parsed to messages. Fields name/description/version/authors/tags/outputs [K], not confirmed on page. Takeaway: ties a prompt file to a model - we do NOT want that coupling.
- Promptfoo [F]: `promptfooconfig.yaml` with `prompts` (file:// paths), `providers` (list of models, so the same prompt runs on Claude, GPT, Gemini, local), `tests` (vars + `assert:`: contains-json, javascript, similar; also llm-rubric, is-json [K]), `defaultTest`, `$ref` reuse. Run `promptfoo eval -c`. GitHub Action `promptfoo/promptfoo-action@v1` [F]: trigger `pull_request` with `paths: prompts/**`, needs `pull-requests: write`, inputs github-token, prompts (glob), config; posts before/after diff as a PR comment; cache `~/.cache/promptfoo`.
- LangChain Hub, OpenAI prompt files, Anthropic prompt library [K, not fetched]: all are hosted/registry-style, tied to a vendor UI. Not a fit for repo-as-data; skip as format. Anthropic's cookbook is notebooks, not a prompt format.
- Design call: do not adopt any one vendor format as the canonical one. Use plain Markdown + YAML frontmatter, a `{{var}}` Mustache-subset placeholder (Handlebars-compatible, Prompty-compatible, trivially regex-checked), and a script that EXPORTS to .prompt (Dotprompt) / .prompty / promptfoo config if wanted. Model hints go in an optional `model_hints` block that is advisory only.

## 2. Agent-readable conventions
- AGENTS.md [F, agents.md]: open Markdown "README for agents", no required fields; read by Codex, Jules, Aider, goose, opencode, Zed, Warp, VS Code, Devin, Cursor, Windsurf, Copilot coding agent, Gemini CLI; stewarded by Agentic AI Foundation (Linux Foundation); nested files allowed, nearest wins, user chat prompt overrides. Migration advice: rename to AGENTS.md and symlink the old name.
- Claude Code [F, code.claude.com/docs/en/memory]: reads AGENTS.md when no CLAUDE.md exists; if CLAUDE.md exists it reads only CLAUDE.md; a CLAUDE.md that imports AGENTS.md (an `@AGENTS.md` line [K on exact syntax; page has a "share one file with other coding tools" section]) loads both. `.claude/rules/` scopes rules by file type.
- Cursor [F, cursor.com/docs/context/rules]: `.cursor/rules/*.mdc` with frontmatter `description`, `globs`, `alwaysApply`; plain .md there is ignored; also reads AGENTS.md (nested, nearest wins); keep rules < 500 lines and reference files rather than copy.
- llms.txt [F, llmstxt.org]: file at site root: H1 name (only required), blockquote summary, H2 sections of `[name](url): note` links, "Optional" H2 for skippable links; clean `.md` twin of each page; discovery via `rel=alternate type=text/markdown`. Used by Anthropic/OpenAI/Google docs; MCP docs expose /llms.txt too.
- One source of truth: AGENTS.md is the only hand-written file; `CLAUDE.md` = one line `@AGENTS.md` (or symlink); `GEMINI.md`, `.github/copilot-instructions.md` = symlinks or generated copies; Cursor reads AGENTS.md natively. Rule: symlink where the tool follows it, otherwise generate with a script and CI-fail on drift (`git diff --exit-code` after regenerate). The library gets its own `library/AGENTS.md` (nested, nearest wins) saying how to find/use entries.

## 3. Docs-as-code structure
- Diataxis [F, diataxis.fr]: four needs - tutorials, how-to guides, reference, explanation; lightweight, no mandated tooling. Use it as a `kind`-adjacent axis for DOCS only; for a prompt/template library the natural axis is artifact type (playbook, prompt, template, report, rule), with Diataxis applied inside playbooks (how-to) vs rationale (explanation) vs schema (reference).
- Markdown + YAML frontmatter, validated against JSON Schema (one schema per `kind`). Site generators (MkDocs Material, Docusaurus) read the same frontmatter [K]; not required - the repo must work with no build.
- IDs: stable, human-readable, never reused: `<kind>.<slug>` (e.g. `prompt.cold-email-first-touch`); path may change, id may not; links use ids (`[[prompt.cold-email-first-touch]]` or relative path + id check). `version` = semver of the entry; `CHANGELOG.md` per library (Keep a Changelog [K]) plus `deprecated`/`replaced_by` fields; git history is the audit trail.
- Examples with a registry file: OpenAI cookbook [F] root has `registry.yaml` + `authors.yaml`, AGENTS.md, MIT; Anthropic cookbook [F] has `registry.yaml`, `authors.yaml`, CLAUDE.md, `lychee.toml` (link checker), pre-commit, tests/, MIT. Pattern: a generated/validated registry at root + author file + link checker + pre-commit.

## 4. Retrieval
- Baseline with zero infra: a generated `library/index.json` (id, kind, title, summary, tags, path, version, status, license, content hash, headings list) + `library/llms.txt` (links grouped by kind). Agents grep/read; humans browse README tables. Rebuilt by a script, CI-checked for staleness.
- Lexical-first search over it (SQLite FTS5 / ripgrep); embeddings optional and derived (never committed, or in a gitignored cache). Existing MCP servers over markdown+frontmatter [F via search]: mcp-kb (PyPI, optional Chroma), kb-mcp (Rust, frontmatter-only index), markdown-vault-mcp (FTS5 + semantic + frontmatter, incremental), frontmatter-mcp (DuckDB SQL over frontmatter), LocalVectorSearchMcp (SQLite, lexical-only mode). Do not depend on them; the contract below is small enough to own.
- MCP spec [F, 2025-06-18]: servers expose `resources` (`resources/list` paginated, `resources/read`, URI templates e.g. `library://{kind}/{id}`, annotations audience/priority/lastModified, optional subscribe/listChanged) and `prompts` (prompt templates with arguments) [K for prompts]. Map: each entry -> a resource; each `kind: prompt` entry -> an MCP prompt with its `inputs` as arguments; tools: `library_search(query, kind?, tags?)`, `library_get(id)`.
- Chunking [F-ish, LangChain/docs.rs results]: split at ATX headings (levels 1-3), never inside fenced code, keep `header_path` as chunk metadata, split higher if oversize; frontmatter parsed separately and copied to every chunk [search did not confirm; my practice]. Convention to make this work: one H1 per file, `##` = chunk boundary, each section self-contained (no "as above"), target 200-800 tokens per section.

## 5. Licensing and separation
- CC BY 4.0 [F]: must give credit (name, copyright notice, license notice, disclaimer, link to material), link license, indicate changes, keep record of earlier modifications.
- Policy: every entry carries `license` (SPDX id or `proprietary`/`all-rights-reserved`), `source` (url/citation), `origin: original|derived|third-party`. Eagle Eye code MIT/Apache; original library text under CC BY 4.0 or CC0 (pick one, say it in `library/LICENSE`). Third-party copyrighted material (books, paid courses, competitor decks, others' templates): NEVER in the public repo. Keep only your own notes, short attributed quotes (cap ~25 words, 1 quote per source per entry [my rule, not law]), and a link/citation. The full text lives in a private overlay repo (`eagle-eye-library-private`) mounted at `library/_private/` (gitignored in public; same schema; index merges both when present). Public CI fails if any file under public paths has `origin: third-party` without `license` in an allowlist, or `license: proprietary`.
- Legal quoting limits vary by jurisdiction; this is engineering policy, not legal advice [K].

## 6. Real examples
- Fabric (danielmiessler) [F]: `data/patterns/<name>/system.md` (one folder per pattern, Markdown, system prompt), custom patterns in a separate dir (`~/.config/fabric/patterns`, or one set by `fabric --setup`), custom overrides built-in with same name and survives `--updatepatterns`; strategies as JSON; `--listpatterns`; no index/MCP on the page. Direct precedent for public-core + private-overlay with name-override.
- OpenAI cookbook [F] and Anthropic cookbook [F]: registry.yaml + authors.yaml, MIT, AGENTS.md / CLAUDE.md, link checking.
- CrewAI [F]: new default scaffold has `agents/*.jsonc` (role, goal, backstory, llm, tools), `crew.jsonc` (tasks: description, expected_output, agent, context, output_file; `{topic}` placeholders filled from `inputs`), plus `knowledge/`, `skills/`, `tools/`. Classic: `config/agents.yaml`, `tasks.yaml`. Shows agents/tasks as data files with `expected_output` - copy that field name idea into playbooks.
- awesome-prompts-style repos [K, not fetched]: flat README lists; no schema, rot quickly; the lesson is the opposite of what we want.

## Recommended design for eagle-eye/library

### Folder layout
```
library/
  AGENTS.md            # how to use/extend the library (nested, nearest wins)
  README.md            # human index (generated tables by kind)
  LICENSE              # CC BY 4.0 (or CC0) for original content; note per-entry overrides
  CHANGELOG.md
  llms.txt             # generated, links grouped by kind
  index.json           # generated; ci-checked
  schema/              # JSON Schemas: base.json + playbook|prompt|template|report|rule.json
  playbooks/           # how-to; step lists, inputs, outputs, success check
  prompts/             # model-agnostic meta prompts (one .md each) + prompts/evals/
  templates/           # offer/, sow/, msa/ - body with {{placeholders}} + legal-review note
  reports/             # research reports (dated, immutable, source-cited)
  rules/               # copy rules, style, banned phrases (data, machine-checkable)
  _private/            # gitignored overlay mount, same layout
  tools/               # build_index.py, lint.py, export.py (dotprompt/prompty/promptfoo), mcp_server.py
```
Root: `AGENTS.md` (hand-written), `CLAUDE.md` -> `@AGENTS.md`, `GEMINI.md` -> symlink.

### Front-matter schema (all kinds)
```yaml
id: prompt.cold-email-first-touch   # required, immutable, <kind>.<slug>
kind: prompt                        # playbook|prompt|template|report|rule
title: ...                          # required
summary: one sentence               # required, <= 200 chars (used in index/llms.txt)
version: 1.2.0                      # semver; bump on any body change
status: draft|stable|deprecated     # replaced_by: <id> when deprecated
tags: [outreach, email]
owner: team/handle
created: 2026-11-24
updated: 2026-11-24
license: CC-BY-4.0                  # SPDX or proprietary
origin: original|derived|third-party
sources: [{title, url, accessed}]   # required when origin != original
related: [playbook.outbound-sequence]
# kind: prompt only
inputs:  {company: {type: string, required: true, description: ...}}
outputs: {format: markdown|json, schema: schemas/x.json}
model_hints: {min_context: 8000, temperature: 0.4, notes: "works on any chat model"}  # advisory
evals: evals/cold-email-first-touch.promptfoo.yaml
# kind: template only: placeholders: [...], jurisdiction, review_required: true
```
Body: one H1; sections `##`; placeholders `{{name}}` only (no logic) so any tool/human can fill them.

### Index / MCP
`tools/build_index.py` walks `library/` (+ `_private/` if present), validates, writes `index.json` and `llms.txt` and README tables. `tools/mcp_server.py` (stdio, reads index.json): resources `library://{kind}/{id}` (+annotations priority/lastModified), prompts for `kind: prompt` with `inputs` as arguments, tools `library_search` (FTS5 over heading chunks, lexical; embeddings optional plug-in) and `library_get`. Any non-MCP agent just reads AGENTS.md -> index.json.

### CI checks (GitHub Actions, paths: library/**)
1. Front-matter validates against `schema/<kind>.json`; ids unique, match `<kind>.<slug>` and filename slug.
2. `related`/`replaced_by`/links resolve (internal check + lychee for external, as Anthropic cookbook does).
3. Prompt `{{vars}}` used == `inputs` declared (no undeclared, no unused).
4. Index freshness: rerun build_index, `git diff --exit-code index.json llms.txt README.md`; same for generated CLAUDE.md/GEMINI.md copies.
5. Version bump enforced: body hash changed => `version` and CHANGELOG changed.
6. Licensing: third-party/proprietary not allowed in public paths; `sources` required for non-original; quote-length lint (> ~25 words inside blockquote with a source fails).
7. Secret/PII scan (gitleaks) and no real customer names in templates/examples.
8. Copy-rule lint: `rules/` banned-phrase list run over prompts/templates/playbooks examples.
9. Prompt evals: promptfoo on changed prompts only (`promptfoo/promptfoo-action@v1`, paths filter), PR-time against 2+ providers incl. a local one; deterministic asserts (is-json, contains, javascript) gate, llm-rubric advisory; needs provider secrets so run on same-repo PRs only; cache enabled.
10. Markdown lint (one H1, heading depth <= 3 used for chunking, no empty sections) and a size cap per section (~800 tokens).
