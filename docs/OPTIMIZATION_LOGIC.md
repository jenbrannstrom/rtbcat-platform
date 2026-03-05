# Cat-Scan Optimization Logic

## How Cat-Scan Thinks About QPS

The advertiser's profit = what they earn from ads - what they spend on ads - what it costs to run the operation.

We can't see their earnings. So the question becomes: from what we CAN see, which signals tell us "this traffic is making them money" vs "this traffic is costing them money"?

## Available Signals (Ranked by Usefulness)

| Signal | What It Tells Us | Usefulness |
|--------|-----------------|------------|
| **Bids / Bid Rate** | The bidder chose to bid on this traffic. Their own system — which knows their campaigns, budgets, and targeting — decided this was worth spending money on. If the bidder bids on 80% of traffic from publisher X but only 2% from publisher Y, publisher X is valuable. Send more like X, less like Y. | High |
| **Win Rate** | They bid AND won. They valued this traffic enough to outbid competitors. High win rate = they're pricing aggressively = they really want this inventory. Low win rate = either being outbid or the auction is too competitive. | High |
| **Spend Concentration** | Where the money actually goes. If 90% of spend lands on 3 out of 10 configs, those 3 are where the bidder sees value. Money doesn't lie. Follow the spend. | High |
| **Bid-to-Win Ratio** | They bid but lost. A segment where they bid 10,000 times but only win 100 means they want this traffic but can't afford it at market price. They value it but are being outcompeted. Might be worth increasing QPS to give them more shots. | Medium-High |
| **Reached but Not Bid** | Traffic reached the bidder, bidder said "no thanks." Tells us they don't want it, but not WHY. Could be budget exhaustion (temporary), frequency cap (user-specific), or no matching campaign (structural). | Medium |
| **CTR** | Users clicked. Means the creative resonated in that placement. But clicks can be junk. Useful in combination with other signals, not alone. | Medium |
| **Viewability** | The ad was actually seen by a human. A non-viewable impression has zero chance of generating profit. Cutting non-viewable inventory is free improvement. | Medium |
| **IVT / Fraud Rate** | Traffic is bots, not humans. No bot will ever buy a product. Usually low enough that this is a hygiene issue, not a primary optimization lever. | Medium |
| **Spend Trend Over Time** | Increasing or decreasing? An advertiser ramping up spend is finding profit. One pulling back is not. Useful for confidence scoring, not for segment-level optimization. | Medium |
| **Impressions Without Clicks** | Ad shown, nobody cared. Could be brand awareness (intentional) or bad placement. Ambiguous without knowing campaign intent. | Low-Medium |

## What We're Missing

These are the signals that would change everything if we had them:

| Missing Signal | Why It Matters | Source |
|----------------|---------------|--------|
| **No-bid reason** | If we knew WHY the bidder passes on 99% of traffic, we could stop sending it. "Floor too high" = target cheaper publishers. "Budget exhausted" = reduce QPS in late-day hours. "No matching campaign for this geo" = exclude that geo from pretargeting. This single data point would be more valuable than everything else combined. | Bidder logs (CSV export) |
| **Bid price per segment** | The bidder's own assessment of what traffic is worth, in dollars. If they bid $3 CPM on Philippines Android gaming apps but $0.05 on Brazil desktop news sites, we know exactly where they see profit. | Bidder logs (CSV export) |
| **Post-click outcome** | Did the click become money? An install, a deposit, a purchase? This is the ultimate signal. Everything else is a proxy. | MMP postback (built, needs customer to connect) |

## What We Can Do Today

With what we have (no bidder data, no MMP connection), the best optimization is:

1. **Follow the bids.** Shift QPS toward segments where the bidder actually bids. If they ignore 99% of traffic from a config, that config's QPS is wasted.
2. **Follow the spend.** Configs and geos where the advertiser spends the most are where they see value. Protect those. Starve the ones with zero spend.
3. **Kill dead weight.** Configs with zero traffic, zero bids, zero impressions are consuming QPS that could go to performing configs.
4. **Cut fraud and non-viewable inventory.** Not the biggest lever, but it's free improvement.

The moment a customer connects their MMP or provides a bid-price CSV dump, everything changes — we go from "follow the proxy signals" to "optimize for actual outcomes."

## Bidder Data Ingestion (Planned)

The bidder knows things Google never tells us:
- "I bid $1.20 on this request" (we never see bid prices)
- "I declined this request because the floor was too high" (we never see no-bid reasons)
- "I've used 80% of today's budget" (we never see budget status)

This data would transform Cat-Scan's optimizer. If we knew why the bidder said no to 95% of requests, we could tune pretargeting to stop sending those requests in the first place.

We're building an ingestion path for bidders who want to share their metrics. Once connected, Cat-Scan's recommendations become significantly more accurate.
