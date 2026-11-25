---
id: template.upwork-safe
title: Upwork-safe offer and SOW variants - no contact words, platform governs payment
kind: template
version: 1.0.0
tags: [upwork,offer,sow,client-kit,circumvention]
inputs: [deal_record]
license: CC-BY-4.0
---
# Upwork-safe variants

Render `offer` and `sow` with `upwork: true`. The variant differs from the normal pair in four ways:
1. No URL, domain, email, phone, chat-app or social handle anywhere in the text or PDF.
2. No payment, escrow, dispute or termination clause; Upwork's terms govern them.
3. The next step reads "Reply here on Upwork". Calls are booked through Upwork's meeting tool.
4. Onboarding access is requested inside the contract by a one-time-link flow, never in a pre-contract message.

Check every output: `python3 copy_lint.py upwork-circumvention offer.pdf sow.pdf` must PASS (exit 0, zero findings).
Why: research/upwork-contract-terms.md. The Upwork pair is the primary document for Upwork clients; email is at most a one-line pointer after the offer is live.
