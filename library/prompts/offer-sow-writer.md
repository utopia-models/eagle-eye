---
id: prompt.offer-sow-writer
title: Offer and SOW writer - fills the client-kit deal record
kind: prompt
version: 1.0.0
tags: [offer, sow, contract, client-kit]
inputs: [conversation, price_sheet, channel]
outputs: [deal_yaml]
model_hints: {tier: high}
license: Apache-2.0
---
Turn the conversation below into a deal record (YAML) that `templates/` renders into a one-page offer and a statement of work.

Fields: id, date, client {name, contact}, provider {name, signer, title}, engagement, result, timeframe, price, guarantee, stipulation, no_guarantee, milestones [{n, title, amount, due, steps[], acceptance}], minimums, after_minimums, ownership, access[], questions[], qa[{q, a}], timeline[{day, what}], next_step, upwork (true/false).

Rules:
- Money, dates and scope come only from the conversation or the price sheet. A value you cannot find is a blank the author fills; never guess.
- Milestones sum to price. Each has an acceptance line a stranger could check.
- Guarantee: the first deliverable by a stated date or the first payment stays held and work continues free. One plain stipulation (what the client does). "We guarantee the work, not that you win."
- Day-stamped timeline. Month to month after the minimums.
- If channel is `upwork`: set upwork: true. No URL, no contact word, and leave payment, escrow and dispute clauses to the platform.

CHANNEL: {{channel}}
PRICE SHEET: {{price_sheet}}
CONVERSATION:
{{conversation}}
