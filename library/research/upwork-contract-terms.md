---
id: research.upwork-contract-terms
title: Upwork contract terms that shape our documents - circumvention, fees, escrow
kind: research
version: 1.0.0
tags: [upwork, contract, terms, circumvention, escrow, fees]
date: 2026-11-25
license: CC-BY-4.0
---
# Upwork contract terms that shape our documents

**Question:** what may a proposal, an offer and a statement of work say when the client was found on Upwork?

**Answer in one paragraph.** Upwork's User Agreement treats moving a client off the platform, or taking payment outside it, as circumvention, and a second violation can restrict or block the account. So an Upwork-channel offer and SOW carry no URL, no email or phone, no chat-app or social handle, and no off-platform payment word; payment, escrow and disputes are left to Upwork's own terms; the only call to action is "reply here". Off-platform clients get the full MSA.

## What each document does on Upwork
| document | Upwork variant |
|---|---|
| offer | one page, result, guarantee, price, timeline, Q&A; no contact words; next step is "reply here" |
| SOW | milestones and acceptance only; no payment, escrow or termination clause (the platform governs those) |
| MSA | not used; the platform's service contract terms apply |
| onboarding | access list and questions; credentials only by a one-time-link flow |

## Rules that follow
1. Before a contract: no email, phone, outside link (our own sites and demo pages included), chat app, social handle, meeting link or calendar link. "Meeting" through the platform's tool is fine.
2. During a contract: work links only on a domain list the client agrees to; still no personal contact details.
3. Payment talk stays on the platform.
4. A linted check enforces 1-3: `copy_lint.py upwork-circumvention <file|pdf>`.

## Sources
Upwork User Agreement; Upwork Optional Service Contract Terms; Upwork offer guide; Upwork Service Fee and Conversion Fee pages; Common Paper PSA and SOW standard terms (CC BY 4.0) for the off-platform structure. Read the live pages before relying on a clause; platform terms change.

## Our own evidence
A circumvention warning arrived on 2026-11-11 after messages that carried a link and a booking call to action; the rules above are the response. The same account's pre-send gate refuses any draft that matches the `upwork-circumvention` patterns.
