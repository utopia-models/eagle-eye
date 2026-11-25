---
id: playbook.client-close-and-delivery
title: Client close and delivery - from "yes" to a paid, delivered, retained client
kind: playbook
version: 1.0.0
tags: [close, delivery, onboarding, sow, follow-up, retention]
diataxis: how-to
inputs: [qualified_reply]
outputs: [signed_offer, delivered_milestones]
license: CC-BY-4.0
---
# Client close and delivery

## 1. The call
- Goal of the call: agree the one result, the date, the price. Open with their situation in their words; show the thing already built; state the offer; ask for the yes.
- Same day: send the offer pack (below). On Upwork everything stays on Upwork.

## 2. The offer pack (templates/, client-kit)
1. Offer: one page, result, guarantee, price, timeline, Q&A, next step. (templates/offer.md)
2. SOW: milestones with acceptance lines, minimums, client inputs, ownership. (templates/sow.md)
3. MSA only for off-platform clients (templates/msa.md, built on the Common Paper PSA structure, CC BY 4.0).
4. Upwork-safe pair: the same offer and SOW with `upwork: true`: no URL or contact word, payment and escrow left to the platform.
5. Onboarding: access list and intake questions. (templates/onboarding.md)
Fill with `prompts/offer-sow-writer.md`; lint the Upwork pair with `copy_lint.py upwork-circumvention`.

## 3. Guarantee design
Success guarantee: the first priced deliverable inside a stated window, or the first milestone stays held and work continues free. One plain stipulation. "We guarantee the work, not that you win." Month to month after the minimums.

## 4. Delivery
- Milestones are small and dated; each ends in something the client can open.
- Day 0 offer sent, day 1 one-line check, day 3 the result so far and the one thing needed from them, day 7 what shipped, day 14 delivery note mapping each acceptance line to evidence. (templates/follow-up.md)
- One message per person per day; answer the last question first; keep every promise made in the thread.

## 5. After delivery
Ask for the review on the platform the contract ran on, propose the next small milestone while the result is fresh, and log proof (with the client's permission) for the next proposal.

## Standards
- Access: client owns the server, accounts and data; we work in accounts in their name.
- Nothing moves off a platform that governs the contract.
