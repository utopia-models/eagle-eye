---
id: research.demo-motion-patterns
title: Demo motion patterns - what moves in a product demo video, with durations
kind: research
version: 1.0.0
tags: [motion,demo,video,ui]
date: 2026-11-25
license: Apache-2.0
---
# Demo motion patterns

Each pattern is one idea that moves on screen, with the library that does it and a duration range. Use one at a time per beat (research/ui-libraries.md). Machine-readable copy: the table below is the data.

| pattern id | what moves | library | timing |
|---|---|---|---|
| stagger_rows | table or list rows enter one after another | motion | 40-60 ms between rows |
| kpi_countup | KPI numbers count up | @number-flow/react | 0.8-1.2 s |
| skeleton_swap | skeleton placeholder becomes content | shadcn skeleton | 0.4-0.7 s |
| ai_stream | AI text streams in | motion, cult-ui | 30-60 characters per second |
| cmdk_palette | command palette opened on camera | cmdk | n/a |
| chart_draw | charts draw in | recharts, tremor | n/a |
| toast_per_action | a toast on every action | sonner | n/a |
| live_status | pulsing status dots, hover polish | css, motion | n/a |

## Human cursor
A recorded cursor must move like a hand: curved paths with varying speed, a small overshoot and correction, a hover beat before a click, clicks off exact center, scroll steps that differ. Review with prompts/video-reviewer.md; straight-line or constant-speed moves and instant teleports are the common failures.
