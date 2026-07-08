# Creative clustering and click macro auditing for Authorized Buyers

Two operational hygiene problems that become expensive at scale: mismatched creatives and missing click macros.

## Creative clustering by destination

Google Authorized Buyers reports performance at the creative ID level. When you have hundreds or thousands of creatives, you need a way to understand "which campaign is this actually for?"

Cat-Scan automatically clusters creatives by destination URL patterns. This reveals:
- Multiple creatives pointing at the same offer (intentional or accidental overlap).
- Spend concentration on a small number of real campaigns.
- Creatives that are orphaned (no matching campaign logic on the bidder side).

You can also manually create clusters and use AI-assisted auto-clustering.

**Atomic fact:** Destination URL clustering works even when the bidder uses different campaign IDs or when Google reporting does not expose the bidder's internal structure.

## Geo / language mismatch detection

A common and expensive error: a creative localized for one market is served in another.

Example: A creative with Arabic text and an "Install" button in Spanish being shown in the UAE, or a USD price shown to users in a market that uses a different currency.

Cat-Scan's optional AI creative analysis (supports Gemini, Claude, or Grok) reads the creative image + text and flags mismatches against the actual serving countries reported in the performance data.

This feature is deliberately optional and off by default in production because it requires explicit configuration of an LLM provider.

## Click macro compliance

Google requires that click URLs support the `{clickurl}` or equivalent macro so that Google can properly track and attribute clicks.

Many creatives are uploaded without the macro or with it in the wrong place.

Cat-Scan has a dedicated click macro audit view that shows exactly which creatives are missing the required macro.

Failing this audit is a fast way to lose credit for clicks or to trigger compliance issues.

## Why these checks matter

Creative problems are silent killers:
- You pay for QPS that produces impressions for the wrong audience.
- You lose attribution and therefore cannot optimize.
- You risk account-level problems if macros are systematically missing.

These are exactly the kinds of details that separate teams that have run real seats from teams that have only configured DSPs.

## Related

- [Managing Creatives](../05-managing-creatives.md) in the manual
- Creative audit and clustering routes in Cat-Scan
- The AI language / geo mismatch code lives in the collectors/creatives and api routers (configurable, not enabled by default)

**Last updated:** June 2026  
Part of the RTB.cat / Cat-Scan technical explainers.