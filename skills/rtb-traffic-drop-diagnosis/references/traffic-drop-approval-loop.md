# Traffic Drop Approval Loop

## Canonical Scenario

Customer claim:

> CTV traffic has dropped. We checked yesterday's hourly data (UTC 0). CTV traffic started dropping yesterday. Volume is very low and spotty across hours. Can you please check if this is on Google's side?

Observed root cause pattern:

- Before the drop, a small set of creatives drove most spend.
- Those creatives first ran, spent, and gave Google evidence that the bidder could monetize the traffic.
- The creative filter then flagged or disapproved those creatives.
- Once disapproved, the bidder could still see some opportunities but could no longer spend on the affected creatives.
- Google gradually reduced waste by sending fewer bid requests where the bidder repeatedly could not produce valid spend.

The apparent issue is "bid requests reduced." The actual issue is "approval loss removed the spend path, then bid-request volume dwindled."

## Investigation Cues

Look for:

- Top creatives before the drop now showing `DISAPPROVED`, serving restrictions, or missing from the live Google list.
- Bid filtering reasons tied to creative policy or creative approval.
- Spend falling before or at the same time as request volume.
- No matching RTB configuration, endpoint, or QPS cap change.

Examples from the original scenario included creatives `1216`, `1226`, `1264`, and similar top spend contributors.

## Customer Response Frame

Use this structure:

1. Confirm what was checked: hourly UTC before/after data and top creative spend.
2. Explain that the highest-spend creatives were later disapproved.
3. Explain the feedback loop: no approved spend path means bids are rejected or cannot win; Google then reduces low-yield requests.
4. State that the problem is at creative approval level, not RTB settings or Google-side traffic supply.
5. Give the next action: fix or replace disapproved creatives, then monitor whether spend and request volume recover.

Avoid saying "Google traffic disappeared" unless supply evidence proves that. In this pattern, Google is reducing waste after creative disapproval, not failing to send valid traffic.
