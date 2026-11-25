---
id: playbook.cold-apply-campaign
title: Cold apply and cold outreach campaign - volume with a gate in front of every send
kind: playbook
version: 1.0.0
tags: [cold-email, outbound, applications, campaign, deliverability]
diataxis: how-to
inputs: [target_list, offer]
outputs: [sent_touches, reply_log]
license: CC-BY-4.0
---
# Cold apply / cold outreach campaign

**Goal:** put a specific, checkable message in front of many qualified targets per day, and learn from the replies, without burning the sending domains.

## 1. Targets
- One buyer type per campaign. A target passes a written gate (role, company stage, size, funded recently, a live post that names the need) before anything is built for them. A target that fails is dropped, not "maybe".
- Each target gets a record: source, the exact post or fact quoted, the contact route.

## 2. Offer
- One offer per message: a result, a date, a price on the page (not in the email), and a guarantee that names what you do if you miss. See playbooks/founder-oneshot.md for a full example, templates/ for the sheet.
- Free first deliverable built from the target's own post: specific, zero risk, shown on a link.

## 3. Mechanics (research/cold-email-mechanics.md)
- Plain text, no tracking pixel, one new angle per day per campaign, business hours in the target's time zone, 3-4 follow-ups.
- Touch 1: about 60 words, line 1 quotes their post, one question, no link from a fresh domain. Touch 2 carries the one link (their page). Touch 3 a one-line bump. Touch 4 closes the loop.
- Warm new domains before volume; cap sends per inbox per day to the provider's safe range; stop a domain on a spike in bounces.
- Check each draft with copy-rules/outbound-email.yaml.

## 4. Volume vs personalization
Two schools disagree (thousands of sends before judging vs ten hyper-personalized beating five hundred generic). Rule: when the qualified list is small (about ten per cycle) run the personalized version and measure on the first ten; when it is large, run the plain-text template at volume and read reply counts per angle.

## 5. Replies
- Positive reply: the page URL within the hour, a booking route the same day.
- "Not now": one follow-up in 30 days. Any "no" or unsubscribe: stop that person everywhere.
- Log every reply with its touch number; the angle that earns replies becomes the default.

## 6. Job applications as a background channel
Applications keep running at volume as a safety net: tailored resume per post, the same quote-the-post first line, tracked per ATS, never two applications to one company in a window. They never own the calendar.

## Standards
- No message goes out that the gate has not passed. Failures announce themselves; silence is the failure mode.
- Never contact anyone the target list marks as off-limits.
