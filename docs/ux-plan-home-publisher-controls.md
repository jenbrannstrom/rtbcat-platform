# UX Plan: Home Page Publisher Block Controls

**Date:** 2026-02-22
**Branch:** `ui/ux-fixes`
**Scope:** Frontend only (no backend changes)

---

## 1. Audit: What Exists Today

### Home Page Structure

```
┌══════════════════════════════════════════════════════════════════════┐
║  STICKY TOP BAR   [Fresh: Feb 22] [CPM] [7d|14d|30d] [Refresh]    ║
├──────────────────────────────────────────────────────────────────────┤
│  Account Endpoints Header  |  Endpoint Efficiency Panel              │
├──────────────────────────────────────────────────────────────────────┤
│  Pretargeting Configs (N active)     sortable: Name|Reached|WR|Waste │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Config: "US Mobile Display"  ACTIVE     Reached  WR  Waste    │  │
│  │ [Expand v]                                                    │  │
│  │  ┌──────────────────────────────────────────────────────────┐ │  │
│  │  │ [By Creative] [By Size] [By Geo] [By Publisher]          │ │  │
│  │  │                                                          │ │  │
│  │  │ Mode info bar: "Blacklist. Block adds to denylist..."    │ │  │
│  │  │                                                          │ │  │
│  │  │ Table: Name | Spend | Reached | Imps | WR | Status | Act│ │  │
│  │  │ row: publisher.com  $120  450K  12K  2.7%  Blocked [Unbl]│ │  │
│  │  │ row: premium.com    $890  1.2M  98K  8.1%  Allowed [Blk]│ │  │
│  │  │                                                          │ │  │
│  │  │ Pending Changes (N)  [Discard All]  [Review & Commit]    │ │  │
│  │  └──────────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ... more config cards ...                                           │
└──────────────────────────────────────────────────────────────────────┘
```

### What's Already Working

| Feature | File | Status |
|---------|------|--------|
| Publisher breakdown table (By Publisher tab) | config-breakdown-panel.tsx | DONE |
| Block/Unblock button per publisher row | config-breakdown-panel.tsx | DONE |
| Pending changes panel with per-item undo | config-breakdown-panel.tsx | DONE |
| "Review & Commit" -> confirmation modal | config-breakdown-panel.tsx | DONE |
| "Commit to Google" API call + sync | config-breakdown-panel.tsx | DONE |
| Blacklist/Whitelist mode info bar | config-breakdown-panel.tsx | DONE |
| Status badges: Allowed/Blocked/Pending | config-breakdown-panel.tsx | DONE |
| Size block/unblock (same pattern) | config-breakdown-panel.tsx | DONE |
| Full publisher editor (separate page) | pretargeting-settings-editor.tsx | DONE |

### What's Missing

| # | Gap | Impact |
|---|-----|--------|
| 1 | **No way to block a publisher not in the breakdown** | HIGH - can only block what appears in performance data |
| 2 | **No search/filter on publisher table** | MEDIUM - hard to find specific publisher in long list |
| 3 | **No "commonly blocked" guidance** | HIGH - operator has no intelligence about known bad actors |
| 4 | **No link from Home to Full Editor** | LOW - no way to jump to history/rollback/bulk |
| 5 | **Inconsistent push wording** | LOW - "Commit" vs "Apply" across pages |

---

## 2. Design Principle

**Block where you see the data.** The operator's workflow is:

1. Expand a pretargeting config on Home
2. See the publisher breakdown (who's eating QPS, who's winning, who's waste)
3. Block the bad ones immediately
4. Push to Google

Everything the operator needs for blocking must be reachable **without leaving the Home page**.

---

## 3. Proposed Features

### 3.1 Block Publisher Input (on Home)

A single input below the publisher table to block a publisher by ID. This is the
#1 missing feature -- today you can only block publishers that already appear in
performance data.

**Before (current):**
```
│ Publisher       │ Spend │ Reached │ Imps │ WR   │ Status  │ Action │
│─────────────────┼───────┼─────────┼──────┼──────┼─────────┼────────│
│ com.fake.slots  │ $120  │ 450K    │ 12K  │ 2.7% │ Blocked │ [Unbl] │
│ premium-news    │ $890  │ 1.2M    │ 98K  │ 8.1% │ Allowed │ [Blck] │
│                 │       │         │      │      │         │        │
│ (end of table)                                                      │
```

**After (proposed):**
```
│ Publisher       │ Spend │ Reached │ Imps │ WR   │ Status  │ Action │
│─────────────────┼───────┼─────────┼──────┼──────┼─────────┼────────│
│ com.fake.slots  │ $120  │ 450K    │ 12K  │ 2.7% │ Blocked │ [Unbl] │
│ premium-news    │ $890  │ 1.2M    │ 98K  │ 8.1% │ Allowed │ [Blck] │
│ com.fraud.new   │  --   │  --     │  --  │  --  │ Pending │ [Undo] │
├─────────────────────────────────────────────────────────────────────│
│ Block: [com.scam.example____________] [Block]                       │
│                                                   ^ enter to block  │
└─────────────────────────────────────────────────────────────────────┘
```

**Behaviour:**
- Input label says "Block:" (blacklist mode) or "Deny:" (whitelist mode -- removes from allowlist)
- Enter key or [Block] button submits
- Validates publisher ID format (domain or bundle ID: `example.com`, `com.example.app`)
- Inline error below input on invalid format or duplicate
- On success: publisher appears in the table as "Pending" with [Undo], and in the Pending Changes panel
- Input clears on success

**Validation errors (inline):**
```
│ Block: [not valid!___] [Block]                                      │
│   Invalid ID. Use com.example.app or publisher.com                  │
```
```
│ Block: [com.fake.slots] [Block]                                     │
│   Already blocked                                                   │
```

### 3.2 Publisher Search / Filter

A search input in the mode info bar for instant client-side filtering.

```
┌─────────────────────────────────────────────────────────────────────┐
│ Mode: Blacklist                [Filter: ________]   [Full Editor >] │
├─────────────────────────────────────────────────────────────────────┤
│ Publisher       │ Spend │ Reached │ Imps │ WR   │ Status  │ Action │
│ (filtered rows only)                                                │
```

- Filters on publisher name AND publisher ID (target_value)
- Case-insensitive substring match
- No API call -- filters the already-loaded breakdown data
- Placeholder: "Filter publishers..."
- Clear button (X) when text is entered

### 3.3 Commonly Blocked Publishers (Intelligence Panel)

This is the new feature. Below the block input, an expandable panel shows
publishers frequently blocked by other media buyers. This gives operators
intelligence they don't currently have.

**Collapsed (default):**
```
├─────────────────────────────────────────────────────────────────────┤
│ Block: [____________________] [Block]                               │
│                                                                     │
│ [v] Commonly blocked publishers (12 suggestions)                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Expanded:**
```
├─────────────────────────────────────────────────────────────────────┤
│ Block: [____________________] [Block]                               │
│                                                                     │
│ [^] Commonly blocked publishers                                     │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ Publishers frequently blocked by media buyers in your vertical. │ │
│ │ Click [Block] to add to your pending changes.                   │ │
│ │                                                                 │ │
│ │  Publisher              │ Category      │ Blocked by │ Action   │ │
│ │  ───────────────────────┼───────────────┼────────────┼────────  │ │
│ │  com.fakegame.slots     │ Fake games    │ 78% buyers │ [Block]  │ │
│ │  clickbait-news.com     │ Clickbait     │ 72% buyers │ [Block]  │ │
│ │  com.vpn.scam           │ Scam VPN      │ 68% buyers │ [Block]  │ │
│ │  spammy-rewards.net     │ Incentivized  │ 65% buyers │ [Block]  │ │
│ │  com.casino.fake        │ Fake casino   │ 61% buyers │ [Block]  │ │
│ │  adfraud-proxy.com      │ Fraud proxy   │ 58% buyers │ [Block]  │ │
│ │  made-for-ads.info      │ MFA site      │ 54% buyers │ [Block]  │ │
│ │  com.clone.whatsapp     │ Clone app     │ 52% buyers │ [Block]  │ │
│ │                                                                 │ │
│ │  [Block all suggestions]                       Showing 8 of 12  │ │
│ │                                                [Show all]       │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│ Pending Changes (3)                                                 │
│  • Block: com.fakegame.slots                                [Undo] │
│  • Block: clickbait-news.com                                [Undo] │
│  • Block: com.vpn.scam                                      [Undo] │
│ [Discard All]                            [Review & Push to Google]  │
└─────────────────────────────────────────────────────────────────────┘
```

**After a suggestion is blocked, the row updates:**
```
│  com.fakegame.slots     │ Fake games    │ 78% buyers │ Pending  │
│  clickbait-news.com     │ Clickbait     │ 72% buyers │ [Block]  │
```

**Already-blocked suggestions are marked:**
```
│  com.casino.fake        │ Fake casino   │ 61% buyers │ Blocked  │
```

**Where does the data come from?**

Phase 1 (MVP): A static curated list embedded in the frontend. Categories of
known bad traffic sources in RTB:

| Category | Examples | Why block |
|----------|----------|-----------|
| Fake games | com.fakegame.*, com.idle.clicker.* | Low quality installs, bot traffic |
| Clickbait/MFA | clickbait-*.com, made-for-ads.* | Made-for-advertising sites, no real users |
| Scam apps | com.vpn.scam, com.cleaner.* | Deceptive apps, ad fraud |
| Clone/copycat apps | com.clone.*, com.fake.* | Impersonating legitimate apps |
| Incentivized traffic | *-rewards.*, *-earn.* | Users motivated by rewards, not intent |
| Fraud proxies | adfraud-*, proxy-traffic-* | Known ad fraud infrastructure |
| Adult miscat | Miscategorized adult publishers | Brand safety risk |

Phase 2 (future, needs backend): API endpoint that returns commonly blocked
publishers across all seats in the platform, with block frequency percentages.
This is out of scope for this frontend-only plan but the UI is designed for it.

**Implementation detail:** The static list lives in a new file:
`dashboard/src/lib/commonly-blocked-publishers.ts`

```typescript
export interface BlockSuggestion {
  publisher_id: string;
  category: string;
  reason: string;
  block_rate: number;       // 0.0-1.0, hardcoded for MVP
}

export const COMMONLY_BLOCKED: BlockSuggestion[] = [
  // Curated from industry knowledge + platform data
  { publisher_id: "com.fakegame.slots", category: "Fake games", ... },
  ...
];
```

The panel filters out publishers that are already blocked (in `effectivePublisherValues`
for EXCLUSIVE mode) and already pending.

### 3.4 Full Editor Link

A small link in the publisher info bar to jump to the full publisher management
page (history, rollback, bulk import, export CSV).

```
│ Mode: Blacklist              [Filter: ________]   [Full Editor >]  │
```

- Links to `/bill_id/${billing_id}?tab=publishers`
- Same tab navigation

### 3.5 Standardize "Push to Google" Wording

| Element | Current | Proposed |
|---------|---------|----------|
| Pending changes CTA | "Review & Commit" | "Review & Push to Google" |
| Modal title | "Confirm Changes to Google" | "Push Changes to Google?" |
| Modal confirm button | "Commit to Google" | "Push to Google" |
| Settings editor CTA | "Apply to Google" | "Push to Google" |
| Success message | generic | "N changes pushed to Google at HH:MM" |

### 3.6 Enhanced Confirmation Modal

Add config name, snapshot info, and clearer diff format:

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Push Changes to Google?                                  [X]    │
│                                                                  │
│  Config: US Mobile Display                                       │
│  Billing ID: 123456789                                           │
│                                                                  │
│  3 publisher changes:                                            │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  BLOCK   com.fakegame.slots                                │  │
│  │  BLOCK   clickbait-news.com                                │  │
│  │  UNBLOCK old-legit.com                                     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  (i) A snapshot will be saved automatically.               │  │
│  │      Rollback available in Full Editor.                    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│                         [Cancel]     [Push to Google]             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Full Proposed Layout (All Features)

### Publisher Tab -- Expanded Config on Home

```
┌══════════════════════════════════════════════════════════════════════════┐
║  Config: "US Mobile Display"  ACTIVE                            [v]    ║
╞════════════════════════════════════════════════════════════════════════╡
║                                                                        ║
║  [By Creative] [By Size] [By Geo] [*By Publisher*]                     ║
║                                                                        ║
║  ┌──────────────────────────────────────────────────────────────────┐  ║
║  │ Mode: Blacklist                [Filter:________]  [Full Editor>] │  ║
║  │ Block adds to denylist; Unblock removes from denylist.           │  ║
║  └──────────────────────────────────────────────────────────────────┘  ║
║                                                                        ║
║  ┌──────────────────────────────────────────────────────────────────┐  ║
║  │ Publisher          │ Spend │ Reached │ Imps │ WR   │ Stat │ Act │  ║
║  │ ───────────────────┼───────┼─────────┼──────┼──────┼──────┼──── │  ║
║  │ com.fake.slots     │ $120  │  450K   │  12K │ 2.7% │ Blkd │Unbl │  ║
║  │ premium-news.com   │ $890  │  1.2M   │  98K │ 8.1% │ Alwd │Blck │  ║
║  │ com.ok.game        │ $340  │  800K   │  45K │ 5.6% │ Alwd │Blck │  ║
║  │ com.vpn.scam       │  --   │  --     │  --  │  --  │ Pend │Undo │  ║
║  │ clickbait-news.com │  --   │  --     │  --  │  --  │ Pend │Undo │  ║
║  └──────────────────────────────────────────────────────────────────┘  ║
║                                                                        ║
║  Block: [________________________] [Block]                             ║
║                                                                        ║
║  [v] Commonly blocked publishers (8 suggestions)                       ║
║  ┌──────────────────────────────────────────────────────────────────┐  ║
║  │ Frequently blocked by media buyers. Click Block to stage.       │  ║
║  │                                                                  │  ║
║  │  Publisher            │ Category      │ Buyers  │ Action         │  ║
║  │  ─────────────────────┼───────────────┼─────────┼──────          │  ║
║  │  com.fakegame.slots   │ Fake games    │ 78%     │ (Pending)      │  ║
║  │  clickbait-news.com   │ Clickbait     │ 72%     │ (Pending)      │  ║
║  │  com.vpn.scam         │ Scam VPN      │ 68%     │ (Pending)      │  ║
║  │  spammy-rewards.net   │ Incentivized  │ 65%     │ [Block]        │  ║
║  │  com.casino.fake      │ Fake casino   │ 61%     │ [Block]        │  ║
║  │  adfraud-proxy.com    │ Fraud proxy   │ 58%     │ [Block]        │  ║
║  │  made-for-ads.info    │ MFA site      │ 54%     │ [Block]        │  ║
║  │  com.clone.whatsapp   │ Clone app     │ 52%     │ [Block]        │  ║
║  │                                                                  │  ║
║  │  [Block all suggestions]                          8 of 12 shown  │  ║
║  └──────────────────────────────────────────────────────────────────┘  ║
║                                                                        ║
║  ┌──────────────────────────────────────────────────────────────────┐  ║
║  │ Pending Changes (3)                                              │  ║
║  │  BLOCK   com.fakegame.slots                              [Undo]  │  ║
║  │  BLOCK   clickbait-news.com                              [Undo]  │  ║
║  │  BLOCK   com.vpn.scam                                    [Undo]  │  ║
║  │                                                                  │  ║
║  │ [Discard All]                       [Review & Push to Google]    │  ║
║  └──────────────────────────────────────────────────────────────────┘  ║
║                                                                        ║
╘════════════════════════════════════════════════════════════════════════╛
```

### Workflow Sequence Diagram

```
Operator opens Home
        │
        v
  Expands config card
        │
        v
  Clicks "By Publisher" tab
        │
        v
  Sees publisher performance table
  with Block/Unblock per row
        │
        ├──────────────────────────────────────┐
        │                                      │
        v                                      v
  Blocks a publisher               Opens "Commonly blocked"
  from the table                   suggestions panel
  (one click)                              │
        │                                  v
        │                         Clicks [Block] on
        │                         suggested publishers
        │                         (one click each)
        │                                  │
        │                         or clicks
        │                         [Block all suggestions]
        │                                  │
        ├──────────────────────────────────┘
        │
        v
  Types publisher ID in
  "Block: [____]" input
  (for IDs not in table or suggestions)
        │
        v
  All changes appear in
  "Pending Changes (N)" panel
        │
        ├──── [Undo] individual changes
        ├──── [Discard All] to clear
        │
        v
  Clicks [Review & Push to Google]
        │
        v
  Confirmation modal shows diff:
  "BLOCK com.x, BLOCK com.y, ..."
  "A snapshot will be saved"
        │
        ├──── [Cancel] goes back
        │
        v
  Clicks [Push to Google]
        │
        v
  API call: applyAllPendingChanges()
  then: syncPretargetingConfigs()
        │
        v
  Success banner:
  "3 changes pushed to Google at 14:34"
  "Rollback available in Full Editor"
```

---

## 5. Commonly Blocked: Category Reference

These categories represent known sources of low-quality or fraudulent RTB
traffic. The static list is curated from industry knowledge; a future API
endpoint can make this dynamic.

```
┌────────────────────┬───────────────────────────────────────────────┐
│ Category           │ What it is / why block                        │
├────────────────────┼───────────────────────────────────────────────┤
│ Fake games         │ Low quality gaming apps that generate bot     │
│                    │ traffic. High QPS, near-zero conversion.      │
├────────────────────┼───────────────────────────────────────────────┤
│ Clickbait / MFA    │ Made-for-advertising sites. No real audience. │
│                    │ Inflate impressions with recycled pageviews.  │
├────────────────────┼───────────────────────────────────────────────┤
│ Scam apps          │ "Cleaner", "booster", fake VPN apps.         │
│                    │ Deceptive installs, background ad fraud.      │
├────────────────────┼───────────────────────────────────────────────┤
│ Clone / copycat    │ Apps impersonating legitimate brands.         │
│                    │ Often sideloaded, high fraud risk.            │
├────────────────────┼───────────────────────────────────────────────┤
│ Incentivized       │ Users watch ads for rewards, not intent.      │
│                    │ High reach but zero downstream value.         │
├────────────────────┼───────────────────────────────────────────────┤
│ Fraud proxies      │ Known ad fraud infrastructure domains.        │
│                    │ Route fake traffic through proxy layers.      │
├────────────────────┼───────────────────────────────────────────────┤
│ Adult miscategorized│ Publishers miscategorized to avoid filters.  │
│                    │ Brand safety risk for most buyers.            │
├────────────────────┼───────────────────────────────────────────────┤
│ SDK spoofing       │ Apps that spoof bundle IDs of premium apps.   │
│                    │ Bid requests claim to be a top-100 app.       │
└────────────────────┴───────────────────────────────────────────────┘
```

---

## 6. States & Edge Cases

### Suggestion Already Blocked

When a suggested publisher is already in the config's denylist, show "Blocked"
instead of a button:

```
│  com.fakegame.slots   │ Fake games    │ 78%     │ Blocked         │
```

### Suggestion Pending

When a suggested publisher has been staged but not yet pushed:

```
│  com.vpn.scam         │ Scam VPN      │ 68%     │ Pending [Undo]  │
```

### All Suggestions Already Blocked

```
┌─────────────────────────────────────────────────────────────┐
│ [v] Commonly blocked publishers                             │
│                                                             │
│ All suggested publishers are already blocked or pending     │
│ for this config. Nice work.                                 │
└─────────────────────────────────────────────────────────────┘
```

### Block Input: Invalid ID

```
│ Block: [not a valid id!___] [Block]                         │
│   Invalid publisher ID.                                     │
│   Use bundle ID (com.example.app) or domain (example.com)   │
```

### Block Input: Already Blocked

```
│ Block: [com.fake.slots____] [Block]                         │
│   Already in block list for this config.                    │
```

### Block Input: Already Pending

```
│ Block: [com.vpn.scam______] [Block]                         │
│   Already in pending changes.                               │
```

### Push Failure

```
┌─────────────────────────────────────────────────────────────────┐
│ (X) Failed to push changes                          [Dismiss]   │
│     Google API: Rate limit exceeded.                            │
│     Changes are still pending -- try again shortly.   [Retry]   │
└─────────────────────────────────────────────────────────────────┘
```

### Push Success

```
┌─────────────────────────────────────────────────────────────────┐
│ (ok) 3 changes pushed to Google at 14:34            [Dismiss]   │
│      Snapshot saved. Rollback available in Full Editor.         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Confirmation Modal

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Push Changes to Google?                                  [X]    │
│                                                                  │
│  Config: US Mobile Display                                       │
│  Billing ID: 123456789                                           │
│                                                                  │
│  3 publisher blocks:                                             │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  BLOCK   com.fakegame.slots                                │  │
│  │  BLOCK   clickbait-news.com                                │  │
│  │  BLOCK   com.vpn.scam                                      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  If other change types (size/geo) are also pending, they         │
│  appear here too with their own labels.                          │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  (i) A snapshot will be saved automatically.               │  │
│  │      Rollback available in Full Editor.                    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│                         [Cancel]     [Push to Google]             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 8. Implementation Plan

### Phase 1: Block Input + Search Filter + Wording

**Files changed:**

| File | Changes |
|------|---------|
| `dashboard/src/components/rtb/config-breakdown-panel.tsx` | Add block input row, filter input, Full Editor link, update wording |
| `dashboard/src/lib/publisher-validation.ts` | NEW: shared `isValidPublisherId()` extracted from settings editor |
| `dashboard/src/components/rtb/pretargeting-settings-editor.tsx` | Import shared validation, update "Apply" -> "Push" wording |

**Steps:**

1. Create `publisher-validation.ts` with `isValidPublisherId(id)` and `getPublisherType(id)` ("App" / "Web")
2. In config-breakdown-panel.tsx, add state: `blockInput`, `blockInputError`, `publisherFilter`
3. Add filter input in publisher info bar (right of mode label)
4. Add block input row below publisher table (only when `activeTab === 'publisher'`)
5. Wire block input to `createChangeMutation` with `add_publisher` (blacklist) or `remove_publisher` (whitelist)
6. Add inline validation errors
7. Add "Full Editor >" link to info bar
8. Update all button labels to "Push to Google"
9. Add snapshot info note to confirmation modal
10. Update success/error banners

### Phase 2: Commonly Blocked Publishers

**Files changed:**

| File | Changes |
|------|---------|
| `dashboard/src/lib/commonly-blocked-publishers.ts` | NEW: static curated list with categories |
| `dashboard/src/components/rtb/config-breakdown-panel.tsx` | Add collapsible suggestions panel below block input |

**Steps:**

1. Create `commonly-blocked-publishers.ts` with curated `BlockSuggestion[]`
2. In config-breakdown-panel.tsx, add collapsible "Commonly blocked" section
3. Filter suggestions: exclude already-blocked (in `effectivePublisherValues`) and already-pending
4. Show category, block rate, and [Block] / "Pending" / "Blocked" state per row
5. Add [Block all suggestions] button that stages all unblocked suggestions
6. "All blocked" empty state when nothing left to suggest

### Phase 3 (future, needs backend): Dynamic Suggestions

- API endpoint: `GET /api/publishers/commonly-blocked?vertical={vertical}`
- Returns publishers with actual block rate across platform seats
- Replace static list with API response
- **Out of scope for this frontend-only plan**

---

## 9. What Stays on the Full Editor Page

The full publisher editor (`/bill_id/[billingId]?tab=publishers`) keeps features
that are important but don't belong in the Home breakdown:

- **Complete publisher list** (all publishers, not just those with performance data)
- **Mode switching** (Blacklist/Whitelist toggle with confirmation)
- **View History** and **Rollback**
- **Export CSV**
- **Bulk Import** (paste/CSV with full preview)

Home is for **see data, block bad, push**. Full Editor is for **manage, audit, rollback**.

---

## 10. Out of Scope

- Backend API changes
- Dynamic commonly-blocked API endpoint
- Whitelist "add publisher" flow (blocking is the primary use case)
- Mode toggle on Home (use Full Editor)
- Cross-config pending changes
- Keyboard shortcuts
- Responsive/mobile layout
