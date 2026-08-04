---
name: rtb-traffic-drop-diagnosis
description: Diagnose RTB or CTV traffic drops where a customer asks whether Google, Authorized Buyers, exchange demand, QPS, bidder settings, or a platform-side issue caused lower bid requests, spotty hourly volume, or reduced spend. Use for before/after traffic investigations that must check creative approval, bid filtering, spend, and Google's waste-throttling feedback loop before blaming Google-side traffic.
---

# RTB Traffic Drop Diagnosis

## Workflow

Use a before/after comparison. Anchor the timeline in UTC unless the customer specifies another timezone.

1. Establish the drop window.
   - Identify the last healthy hour and first bad hour.
   - Compare the same hours from the prior day and the prior 7 days when available.
   - Separate bid requests, bids, filtered bids, impressions, wins, and spend.

2. Check spend and approvals before QPS settings.
   - Rank creatives by spend before the drop.
   - For the top spend contributors, inspect current and historical approval status.
   - Look for creatives that first ran and spent, then became disapproved or restricted.

3. Trace the causal chain.
   - If top-spend creatives became disapproved, bids can no longer win or spend.
   - After repeated rejected or unspendable bids, Google may send fewer requests because the bidder is wasting opportunities.
   - The visible symptom is reduced bid requests, but the root cause can be creative approval loss.

4. Rule out RTB settings only after approval and filtering checks.
   - Check pretargeting, endpoint health, bidder availability, QPS caps, and report freshness.
   - Treat unchanged settings plus new disapprovals as approval-driven until evidence says otherwise.

5. Answer the customer with the actual failure layer.
   - State whether the issue is Google-side supply, RTB configuration, bidder health, reporting lag, or creative approval.
   - When approval-driven, explain that the customer was looking at request volume after the spend path had already broken.

## Required Evidence

Collect these before giving a root cause:

- Hourly before/after bid requests and spend.
- Creative-level spend before the drop.
- Creative approval status for top spenders, including disapproval reasons.
- Bid filtering or rejection signals if available.
- Any config or endpoint changes in the same window.

## Common Pattern

If the customer says, "CTV traffic has dropped. We checked yesterday's hourly data UTC 0. Volume is very low and spotty across hours. Is this on Google's side?", first test whether the previously spending CTV creatives were disapproved. Read [traffic-drop-approval-loop.md](references/traffic-drop-approval-loop.md) for the canonical scenario and response framing.
