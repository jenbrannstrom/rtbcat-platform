# QPS Info Messages - Plain English Draft (Review Only)

Date: 2026-02-27  
Scope: Draft copy only. No app changes applied.

## 1) Top "RTB Endpoints" Section (new `i` tooltips)

| UI Item | Why this matters | Proposed plain-English `i` text |
|---|---|---|
| Allocated QPS | Shows the traffic level you requested from Google. | `The QPS you are telling Google to send.` |
| Observed QPS | Shows the traffic you actually received. | `The actual queries you received per second from Google. This can be increased by reducing waste and increasing efficiency.` |

## 2) Efficiency Colored Boxes (`i` tooltips)

| UI Item | Why this matters | Proposed plain-English `i` text |
|---|---|---|
| Observed QPS | Real traffic seen at your endpoints. | (estimated from daily CSV's)`How many queries per second your endpoints actually received in this period. This is real traffic, not your configured limit.` |
| Utilization | Tells you how much of your reserved capacity you actually used. | (estimated from daily CSV's) `The percentage of your allocated QPS cap that you actually used. 100% means fully used. A low % means most requests were unsused and Google will reduce what they send.` |
| Overshoot | Shows over-allocation vs real use. | (estimated from daily CSV's) `How much capacity you reserved compared with what you actually used. 1.0x is balanced. 5.0x means you reserved about five times what you used.` |
| Delivery Win | Measures conversion from reached traffic to impressions. | (estimated from daily CSV's) `Of the queries that reached your bidder, what percent became impressions.` |
| Auction Win | Measures bidding competitiveness. | (estimated from daily CSV's)`Of all bids you sent, what percent won the auction.` |
| Filtered | Shows how much traffic is dropped before auction. | (estimated from daily CSV's)`Of all bids you sent, what percent was filtered before entering the auction.` |
| PTGT Loss | Shows loss from pretargeting restrictions. | (estimated from daily CSV's)`Of all available traffic opportunities, what percent was blocked by pretargeting before reaching your bidder. Lower is better.` |

## 3) Remaining English Alert/Status Lines (plain-English rewrites)

| Current message | Problem | Proposed plain-English rewrite |
|---|---|---|
| `Observed query-rate utilization is below 0.2% of allocated cap for this period.` | Technical wording; hard to scan quickly. | `You used less than 0.2% of your allocated QPS in this period. Most allocated capacity was unused.` |
| `Pretargeting loss is high at {x}% for selected period.` | Uses internal term without context. | `Pretargeting blocked {x}% of available traffic in this period. This means only {y}% got through.` |
| `{n} endpoint(s) configured in CatScan have no matching observed delivery row in selected period.` | Too technical ("row"). | `{n} configured endpoints showed no delivery data in this period. Check endpoint mapping and endpoint activity.` |
| `No endpoint delivery feed data available. observed_query_rate_qps is unavailable until rtb_endpoints_current is populated.` | Too technical and DB-internal. | `No endpoint delivery data is available yet, so Observed QPS cannot be calculated right now. Refresh/sync endpoint data and try again.` |
| `Feed missing` | Ambiguous. | `No delivery feed data` |

## 4) Optional label cleanups (not required, but clearer)

| Current label | Suggested plain label |
|---|---|
| `PTGT Loss` | `Pretargeting Loss` |
| `Avail` | `Available` |
| `Matched` | `Reached Bidder` |
| `Filtered` (funnel row) | `Blocked Before Bidder` |

