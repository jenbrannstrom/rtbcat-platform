# Bringing your own optimizer to Authorized Buyers pretargeting (BYOM)

**Atomic fact:** Cat-Scan's optimizer is deliberately "Bring Your Own Model." It scores segments and proposes pretargeting changes; you decide the scoring logic and the risk tolerance.

This design acknowledges that the ultimate value signal (post-click outcomes, LTV, margin) lives in the advertiser's or bidder's systems, not inside the exchange reporting.

## The score → propose → approve → apply lifecycle

1. **Score**: An external endpoint you control receives a payload of segments (geo × publisher × size × config combinations) plus the proxy signals Cat-Scan has (bids, wins, spend, waste, etc.).
2. **Propose**: Cat-Scan calls your scorer and receives proposed changes (add geo to exclusion list, lower max QPS on this config, block this publisher, etc.).
3. **Approve**: Proposals are shown with impact preview. You can accept, reject, or modify.
4. **Apply**: Accepted proposals go through the normal safe change workflow (preview, push, snapshot).

## Workflow presets

Cat-Scan ships with three presets that control how aggressive the proposals are allowed to be:

- **Safe**: Small changes, high confidence threshold, limited to clear dead weight.
- **Balanced**: The default for most production seats.
- **Aggressive**: Willing to make larger moves when the signals are strong.

You can also register completely custom profiles.

## Economics before you have conversion data

Until MMP data is connected, the optimizer optimizes for:
- Shifting QPS toward segments where the bidder actually bids.
- Protecting configs and geos where real spend is concentrated.
- Killing configs with zero bids or zero impressions (they are pure waste of your 10 slots).

Once conversion webhooks or bidder logs are connected, the same proposal machinery can optimize directly for the outcomes you actually care about.

## Why this architecture exists

Most "optimization" tools in ad tech are either:
- Fully black-box (you have no idea why a change was made), or
- Fully manual (you do all the analysis yourself in spreadsheets).

The BYOM design sits in the middle: Cat-Scan owns the hard parts (data joining, safe application to Google, history, rollback). You own the value model.

## Implementation

- Optimizer routes and proposal storage in the API
- The external scoring contract is documented in `docs/BYOM_MODEL_INTEGRATION_GUIDE.md`
- Current proxy-signal logic: [OPTIMIZATION_LOGIC.md](https://github.com/jenbrannstrom/rtbcat-platform/blob/main/OPTIMIZATION_LOGIC.md)

**Last updated:** June 2026  
Part of the RTB.cat / Cat-Scan technical explainers.  
The BYOM approach is one of the clearest signs that the system was built by people who have run real seats and know where the real intelligence has to live.