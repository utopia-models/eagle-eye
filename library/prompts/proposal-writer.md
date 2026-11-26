---
id: prompt.proposal-writer
title: Proposal writer - a one-page outcome proposal for a named buyer
kind: prompt
version: 1.0.0
tags: [proposal, offer, outbound, founder]
inputs: [buyer, their_post_or_situation, outcome, proof, price_sheet]
outputs: [proposal_markdown]
model_hints: {tier: high}
license: Apache-2.0
---
Write a one-page proposal to {{buyer}}.

Order: (1) a headline that states the outcome and the date, in their words; (2) one line quoting what they posted or said, proving you read it; (3) the thing you already built for them, with where to see it; (4) how it works in three short steps; (5) proof, each item labelled for exactly what it is; (6) the offer line: result, timeframe, price, the guarantee and its single stipulation; (7) the one next step.

Rules:
- Sell the outcome, never the labor. One offer per message.
- Every number and claim traces to INPUTS or the price sheet. If a number is missing, leave the row out; never invent it.
- A guarantee names a result and a date and what you do if you miss it. State that you guarantee the work, not that they win.
- Plain text, no jargon the buyer did not use.

INPUTS:
{{their_post_or_situation}}

OUTCOME: {{outcome}}
PROOF: {{proof}}
PRICE SHEET: {{price_sheet}}
