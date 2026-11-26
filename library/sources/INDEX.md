---
id: sources.index
title: External sources index - where our material comes from
kind: sources
version: 1.0.0
tags: [sources, index, citations]
license: Apache-2.0
---
# External sources

This is an index of pointers. The only third-party copies in this repository are open-licence packs under `kit/`. Open-licence material may be quoted with attribution; everything else is cited by name.

| source | what we use it for | licence / access | where cited |
|---|---|---|---|
| Community skill packs on Hormozi's frameworks (founder-playbook, hormozi-skills, claude-skill-hormozi-offer-audit) | offer, lead and money-model frameworks | MIT, copied unchanged at a pinned commit | `library/kit/hormozi-mit/` |
| acquisition.com free courses, ocp.wiki, Imperium Academy | operator write-ups in our own words | public web, linked | `library/kit/writeups/` |
| Common Paper PSA and SOW standard terms | structure of templates/msa.md and templates/sow.md | CC BY 4.0, public | templates/ |
| Upwork User Agreement, Optional Service Contract Terms, offer guide, fee pages | circumvention rules, Upwork-safe variants | public web | research/upwork-contract-terms.md, copy-rules/ |
| shadcn/ui, Motion, Magic UI, Cult UI, Kokonut UI, HeroUI, Tremor, Recharts, React Bits, GSAP, Lenis | demo apps | each repo's own licence (mostly MIT) | research/ui-libraries.md |
| Belkins, Prospeo, DemoWalk, Smartlead, Instantly public posts | cold-email mechanics and benchmarks (vendor claims, graded UNSURE) | public web | research/cold-email-mechanics.md |
| Dotprompt, Prompty, promptfoo, Fabric, llms.txt, MCP | formats this library exports to | open source / public specs | research/library-design.md |
| Paid agency-building course (Client Ascension, AI-Assisted Agency) | offer, guarantee, video-letter and outbound lessons | PAID, never redistributed | the PRIVATE overlay only: `library/sources/fazio/`. Public files cite a lesson by name and write the idea in our own words |

## How to cite the paid course from a public file
Write the lesson's module and title (for example "Offers, Claims & Guarantees"), never a quote and never a link to a member area. The private overlay resolves the citation: `library_index.py search "<lesson words>" --overlay <overlay>/library`.
