---
id: prompt.video-reviewer
title: Video reviewer - does the picture show what the narration says (mismatch review)
kind: prompt
version: 1.0.0
tags: [video, review, gemini, mismatch, qa]
inputs: [video, script_rows]
outputs: [review_json]
model_hints: {needs: video-understanding, temperature: 0}
license: Apache-2.0
---
You are watching a short sales video with its audio, as a skeptical viewer would. The script rows spoken are:

{{script_rows}}

For every row, find the moment it is spoken and check that what is on screen at that moment shows what the row names (the screen, the number, the action). Also check the cursor and scrolling: list moments that look robotic (constant-speed or straight-line moves, teleports, perfectly centered clicks, no hover beat before a click, identical scroll steps).

Return ONLY JSON:
{"verdict": "pass|retake|trim",
 "mismatches": [{"t": "mm:ss", "row": <index>, "said": "...", "shown": "...", "severity": "high|low"}],
 "robotic_moments": [{"t": "mm:ss", "what": "..."}],
 "human_score": 1-10,
 "audio": {"cut_off": bool, "dead_air_s": number},
 "best_cut_start": seconds}
Timestamps only for moments you actually see in the file. Pass only when there is no high-severity mismatch and human_score is at least 8.
