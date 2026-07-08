# Safe pretargeting changes on Google Authorized Buyers: staging, preview, history, and rollback

**Atomic fact:** The native Google Authorized Buyers pretargeting UI has no change history and no rollback.

Every production operator eventually makes a change that tanks win rate or spikes waste. Without tooling, the only recovery is manual reconstruction of the previous state from memory or old CSVs.

## The minimum viable safe workflow

Any system that lets you edit pretargeting in production must provide:

- **Preview / dry-run** — Show the exact diff that will be sent to Google before it is sent.
- **Staging** — The change is not live until you explicitly confirm "push to Google".
- **Audit** — Who changed what, when, and what the before/after values were.
- **Snapshot + rollback** — The previous state is stored and can be restored with one action.

Cat-Scan was built around exactly this contract.

## How the workflow works in Cat-Scan

1. Operator opens a pretargeting config (on the home page or in settings).
2. Edits one or more fields (excluded geos, sizes, max QPS, publisher blocks, etc.).
3. Clicks **Preview**. Cat-Scan shows the precise changes that will be made.
4. If satisfied, clicks **Apply** (or "Yes, push to Google").
5. The change is sent to the Authorized Buyers API.
6. A snapshot of the config state is stored.
7. The action appears in the global history timeline (`/history`).

If win rate drops or waste spikes, the operator goes to history, selects the change, previews the rollback, and confirms. The previous state is restored.

**Atomic fact:** Every pretargeting mutation in Cat-Scan is recorded with timestamp, user identity, old value, new value, and a full snapshot for rollback.

## Publisher allow/deny lists

Managing publisher blocks is especially painful in the native UI (full CSV round-trip for every change).

Cat-Scan gives a per-config search + block/allow editor that supports bulk operations and immediate preview. This is one of the highest-ROI features for real seats.

## Why this matters beyond convenience

Without safe tooling, operators become conservative. They leave bad traffic flowing because "changing the config is risky and hard to undo." That conservatism directly costs money in wasted QPS and opportunity cost.

The existence of preview + snapshot + rollback changes the risk calculus. Operators make more changes, faster, with measurable results.

## Implementation references

- Manual chapter with screenshots: [Pretargeting Configuration](../06-pretargeting.md)
- Change history and rollback UI flows
- Backend snapshot and apply logic in the Cat-Scan collectors/pretargeting and API routers
- Full audit trail is queryable and exportable

This workflow is one of the clearest demonstrations that the team behind Cat-Scan has actually operated Authorized Buyers seats at scale, not just read the API docs.

**Last updated:** June 2026  
Part of the RTB.cat / Cat-Scan technical explainers.