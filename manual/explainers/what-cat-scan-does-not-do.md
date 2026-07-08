# What Cat-Scan does not do (and why that matters)

Clear boundaries are part of operational credibility.

## Cat-Scan is not a bidder

It does not evaluate bid requests, decide prices, or return bids. Your existing bidder continues to do all of that.

Cat-Scan sits beside the bidder. It observes what the bidder does with the traffic Google sends, surfaces where that traffic is wasteful, and gives you the tools to reduce the waste at the source (pretargeting).

## Cat-Scan does not have post-click or conversion data until you connect it

Until you wire in an MMP (AppsFlyer is the current best-supported path) or provide bidder-side logs, the optimizer can only use proxy signals: bids placed, win rate, spend concentration, and waste ratio.

The optimization logic document is explicit about this limitation and the planned path once conversion data is available.

**Atomic fact:** "The moment a customer connects their MMP or provides a bid-price CSV dump, everything changes — we go from 'follow the proxy signals' to 'optimize for actual outcomes.'"

## Cat-Scan does not replace your need for good creatives and good bidder logic

It can tell you which sizes and geos are receiving traffic you have no creative for. It cannot invent the missing creative.

It can reduce the volume of garbage that reaches your bidder. It cannot make a bad bidder good.

## Cat-Scan does not give you more than 10 pretargeting configurations per seat

That limit is imposed by Google. Cat-Scan helps you use the ten you have more intelligently and safely.

## Why stating the limits clearly matters

Agencies that have never run a real Authorized Buyers seat often expect a magic "set and forget" optimization product. Being explicit about the boundaries prevents disappointment and positions the tool (and the team behind it) as practitioners rather than marketers.

The same honesty applies to the consulting side of RTB.cat: we can help you obtain the seat and operate it efficiently, but you still need a bidder that bids intelligently and creatives that convert.

## Related

- [OPTIMIZATION_LOGIC.md](https://github.com/jenbrannstrom/rtbcat-platform/blob/main/OPTIMIZATION_LOGIC.md) — the full current and planned logic
- The "Current scope" and "What is not included" sections in the Cat-Scan README
- [Bringing your own optimizer (BYOM)](byom-optimizer.md)

**Last updated:** June 2026  
Part of the RTB.cat / Cat-Scan technical explainers.