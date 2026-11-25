# MVP kit research (knowledge#18941)
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
