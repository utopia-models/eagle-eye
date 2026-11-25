---
id: template.offer
title: Offer - one page: result, guarantee, price, timeline
kind: template
version: 1.0.0
tags: [offer,client-kit,close]
inputs: [client,result,timeframe,price,guarantee]
license: CC-BY-4.0
---
# {{client_name}}: {{engagement}}

Prepared for {{client_contact}} by {{signer}}, {{provider_name}} on {{date}}. Reference {{id}}.

**You get {{result}}, in {{timeframe}}.**
{{guarantee}} We guarantee the work, not that you win.

## Price and milestones
| No. | What you receive | Due | Amount |
|---|---|---|---|
| 1 | {{milestone_1}} | {{due_1}} | {{amount_1}} |
| 2 | {{milestone_2}} | {{due_2}} | {{amount_2}} |
| | **Total, fixed price** | | {{price}} |

{{ownership}}

## What you do
{{stipulation}}

## Timeline
{{day_stamped_timeline}}

## After {{timeframe}}
Month to month. Either side can stop with one message; you keep everything.

## Questions
{{short_qa}}

## Next step
{{next_step}}

Rendered HTML version: `html/offer.html.j2` (Jinja2, with `base.css`).
