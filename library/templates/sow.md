---
id: template.sow
title: Statement of work - milestones with acceptance lines
kind: template
version: 1.0.0
tags: [sow,client-kit,contract]
inputs: [deal_record]
license: CC-BY-4.0
---
# Statement of work: {{engagement}}

Between {{provider_name}} ("Provider") and {{client_name}} ("Client"), under {{agreement_reference}}. Based on the Common Paper SOW standard terms (CC BY 4.0).

1. **Deliverables and acceptance.** Each milestone below is accepted when its acceptance line is true and the Client can open the result.
| No. | Deliverable | Acceptance line | Due | Fee |
|---|---|---|---|---|
| 1 | {{milestone_1}} | {{acceptance_1}} | {{due_1}} | {{amount_1}} |
| 2 | {{milestone_2}} | {{acceptance_2}} | {{due_2}} | {{amount_2}} |
2. **Minimums.** {{minimums}}
3. **Client inputs.** {{access_list}} Delay in inputs moves the due dates by the same number of days.
4. **Ownership.** {{ownership}}
5. **After the minimums.** Month to month; either side ends it with one written message.
6. **Fees and payment.** {{payment_terms}} (Upwork variant: delete this clause; the platform's terms govern payment and escrow.)

Rendered HTML version: `html/sow.html.j2`.
