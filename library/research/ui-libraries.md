---
id: research.ui-libraries
title: UI libraries for per-job demo apps
kind: research
version: 1.0.0
tags: [ui,mvp,shadcn,motion,demo]
date: 2026-11-25
license: CC-BY-4.0
---
# UI libraries for per-job demo apps
The original scratchpad (ui-research/libraries.md, demo-patterns.md) was absent on the dispatch box; this is the distilled decision, versions read from `npm view` on 2026-11-25.

| lib | role | delivery |
|---|---|---|
| shadcn/ui | base components, CLI + MCP, blocks | registry |
| Motion | enter/stagger/layout animation | npm |
| Magic UI | animated hero moments, marquee, beams | registry |
| Cult UI | AI chat / agent surfaces | registry |
| Kokonut UI | AI chat, polished cards | registry |
| HeroUI | alt full component set | npm |
| Tremor + Recharts | data-heavy dashboards, charts | npm |
| React Bits + GSAP + Lenis | Tyler's saved-reel toolkit: text/bg effects, scroll | registry + npm |
| sonner, cmdk, number-flow | toast, Cmd+K, count-up | npm |

Templates (MIT): satnaing/shadcn-admin, Kiranism/next-shadcn-dashboard-starter, shadcn blocks, tremorlabs/template-dashboard.
Motion patterns: `motion/patterns.json`. Video rules: `VIDEO-RULES.md`. Per-job choice: `../vsl_stack_decide.py` (rubric in `rubric.json`).

## Sources
Package versions read from `npm view` on 2026-11-25. Libraries: ui.shadcn.com, motion.dev, magicui.design, cult-ui.com, kokonutui.com, heroui.com, tremor.so, recharts.org, reactbits.dev, gsap.com, lenis.darkroom.engineering, sonner, cmdk, number-flow (all on npm or their registries).

Video capture rules: text 16 px or larger, 3-5 regions per screen, realistic seeded data from the post, hold each end state 1.5 s, one thing moving at a time, capture 60 fps at DPR 2.
