# Pretargeting configurations are the main control surface for most Authorized Buyers buyers

**Atomic fact:** You get exactly 10 pretargeting configurations per Google Authorized Buyers seat.

Everything else (bidder logic, creative selection, frequency capping) happens after the traffic has already been sent to you. Pretargeting is the only volume control you have on the exchange side.

## What one pretargeting config actually controls

Each config is a rule set that tells Google: "only send me bid requests matching these criteria."

| Field                | Effect                                                                 | Common mistake |
|----------------------|------------------------------------------------------------------------|---------------|
| **State**            | Active or Suspended                                                    | Leaving dead configs active |
| **Max QPS**          | Hard cap on queries per second for this rule set                       | Setting it too high "just in case" |
| **Geos (included)**  | Countries, regions, cities (coarse buckets only)                       | Relying only on broad "Europe" or "Asia" |
| **Geos (excluded)**  | Explicit blocks that override inclusions                               | Not using exclusions aggressively enough |
| **Sizes (included)** | Specific ad sizes or "all"                                             | "All" when you only have fixed-size creatives |
| **Formats**          | VIDEO, DISPLAY_IMAGE, DISPLAY_HTML, NATIVE                             | Accepting formats you have no creatives for |
| **Platforms**        | DESKTOP, MOBILE_APP, MOBILE_WEB, CONNECTED_TV                          | Sending mobile app traffic to desktop-only campaigns |
| **Publishers**       | Allow/deny lists for specific domains or app bundles                   | Managing via Google's clunky CSV upload/download cycle |

**Atomic fact:** Google still only exposes coarse geographic buckets (Eastern US, Western US, Europe, Asia, etc.). Fine-grained city or DMA targeting inside pretargeting is not available.

## Why the native UI is painful

The Authorized Buyers pretargeting interface requires downloading a CSV template, editing it offline, and uploading it again for even a one-line change. There is no history, no preview of impact, and no easy rollback.

This is the exact problem Cat-Scan was built to solve.

## The safe change workflow (what a real operator needs)

A production-grade workflow must support:

1. Edit in the UI (or via API).
2. Dry-run / preview the exact delta before anything is pushed to Google.
3. Stage the change.
4. Record who changed what and when (full audit).
5. One-click rollback to any previous snapshot.

Cat-Scan implements exactly this flow on top of the Authorized Buyers API. Changes are previewed, then explicitly pushed, then snapshotted for instant rollback.

See the full description in the manual chapter and the implementation in the collectors and settings routers.

## 10 configs is not a lot

With only ten slots you quickly learn to be ruthless:

- One or two "broad but safe" configs for proven volume.
- Several narrow, high-precision configs for specific geos + sizes + formats where you have strong creative coverage.
- Suspended configs used as staging areas before promotion.

Anything that is not actively producing bids or spend is consuming one of your ten precious slots and should be suspended or deleted.

## Related

- Full field reference and UI screenshots: [Pretargeting Configuration](../06-pretargeting.md)
- How to act on waste signals: [Analyzing QPS waste by dimension](qps-waste-analysis.md)
- The safe change implementation: Cat-Scan settings/pretargeting and snapshot logic in the platform repo

**Last updated:** June 2026  
Part of the RTB.cat / Cat-Scan technical explainers.  
The 10-config reality and the need for safe editing tooling is why Cat-Scan exists.