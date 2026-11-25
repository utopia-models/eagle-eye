---
id: sources.index
title: External sources index - where our material comes from
kind: sources
version: 1.0.0
tags: [sources, index, citations]
license: CC-BY-4.0
---
# External sources

This is an index of pointers, never copies of third-party text. Open-licence material may be quoted with attribution; everything else is cited by name.

| source | what we use it for | licence / access | where cited |
|---|---|---|---|
| Common Paper PSA and SOW standard terms | structure of templates/msa.md and templates/sow.md | CC BY 4.0, public | templates/ |
| Upwork User Agreement, Optional Service Contract Terms, offer guide, fee pages | circumvention rules, Upwork-safe variants | public web | research/upwork-contract-terms.md, copy-rules/ |
| shadcn/ui, Motion, Magic UI, Cult UI, Kokonut UI, HeroUI, Tremor, Recharts, React Bits, GSAP, Lenis | demo apps | each repo's own licence (mostly MIT) | research/ui-libraries.md |
| Belkins, Prospeo, DemoWalk, Smartlead, Instantly public posts | cold-email mechanics and benchmarks (vendor claims, graded UNSURE) | public web | research/cold-email-mechanics.md |
| Dotprompt, Prompty, promptfoo, Fabric, llms.txt, MCP | formats this library exports to | open source / public specs | research/library-design.md |
| Paid agency-building course (Client Ascension, AI-Assisted Agency) | offer, guarantee, video-letter and outbound lessons | PAID, never redistributed | the PRIVATE overlay only: `library/sources/fazio/`. Public files cite a lesson by name and write the idea in our own words |

## How to cite the paid course from a public file
Write the lesson's module and title (for example "Offers, Claims & Guarantees"), never a quote and never a link to a member area. The private overlay resolves the citation: `library_index.py search "<lesson words>" --overlay <overlay>/library`.
