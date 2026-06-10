# Spec: Language-Flags page redesign — "Money at risk" triage worklist

**Status:** Ready for implementation
**Author:** Architecture (design owner)
**Implementer:** TBD
**Page:** `https://scan.rtb.cat/{buyerId}/creatives/language-flags`
**Effort estimate:** ~1.5–2.5 days (FE-heavy, small BE change)

---

## 1. Goal & success criteria

The page must answer one question at a glance: **"Which creatives are losing the most money because of a language/geo mismatch?"**

A user lands on the page and, top to bottom, sees the highest-dollar offenders first, each with a **visible thumbnail of the actual creative**, a **one-sentence plain-language explanation** of what's wrong, and a **one-click path to the full creative preview**.

**Done when:**
- [ ] Rows are ordered by **money at risk descending** (not status-first — see §4.1).
- [ ] Each row shows a creative **thumbnail** (image/video/native/html), not just an ID.
- [ ] Each row shows a **headline sentence** ("Spanish creative serving Germany") built from existing fields.
- [ ] Clicking a row opens the existing `PreviewModal` with the real creative.
- [ ] The two status `<select>` dropdowns are replaced by **one severity segmented control** with live counts + dollar totals.
- [ ] The 4 summary stat cards are replaced by **one headline figure**: total `$ at risk / 30d`.
- [ ] No regression to the refresh / pagination behaviour.

**Explicitly out of scope:** changing the `/creatives` grid page; adding format/size/tier/period filters to this page (this page is intentionally the lean, money-first antidote to that crowded grid).

---

## 2. Chosen design

**Layout: rich rows + modal** (selected by product owner over card-grid and split-pane alternatives).

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Language mismatches            $4,812 at risk / 30d   ·  23 creatives       │
│  [ ●  Confirmed wrong  12 · $3.1K ] [ ◐ Needs review 11 · $1.7K ] [ ✓ OK ]   │
│                                                              🔍 search  ↻ all │
├────────────────────────────────────────────────────────────────────────────┤
│ ┌────┐  🔴 CONFIRMED WRONG                                      $1,240 / 30d │
│ │IMG │  Spanish creative serving Germany 🇩🇪                                  │
│ │thmb│  Creative text is ES · serving DE, AT · no German variant            │
│ └────┘  #1487…2901 · "Verano Rebajas"  · DISPLAY_IMAGE · Approved   [view →] │
├────────────────────────────────────────────────────────────────────────────┤
│ ┌────┐  🟠 NEEDS REVIEW                                           $612 / 30d │
│ │html│  Possibly English in a French market 🇫🇷                              │
│ └────┘  Low-confidence detection · AI check 3d ago      [refresh] [view →]   │
└────────────────────────────────────────────────────────────────────────────┘
```

Reference for tone/spacing: the existing `creative-card.tsx` and `PreviewModal` styling. Reuse Tailwind tokens already in the file (e.g. `bg-red-100 text-red-700`, `bg-amber-100 text-amber-700`).

---

## 3. Current state (what you're modifying)

| Concern | File | Notes |
|---|---|---|
| Page component | `dashboard/src/app/creatives/language-flags/page.tsx` | 431 lines; full rewrite of the body, keep data-fetching scaffolding |
| Buyer-scoped wrapper | `dashboard/src/app/[buyerId]/creatives/language-flags/page.tsx` | Re-export only — **do not touch** |
| API client | `dashboard/src/lib/api/creatives.ts:132` (`getCreativeLanguageFlagCoverage`), `:158` (`refresh…`) | Add `severity` param (§4.2) |
| Types | `dashboard/src/types/api.ts:161` (`CreativeLanguageFlagCoverageRow`), `:188` (`…Summary`), `:197` (`…Response`) | Extend summary (§4.3) |
| Thumbnail render logic | `dashboard/src/components/creative-card.tsx:45` (`PreviewThumbnail`) | **Extract** into shared component (§5.1) |
| Modal | `dashboard/src/components/preview-modal/PreviewModal.tsx:30` (props), `:75` (self-fetch) | Reuse as-is; wire trigger (§5.3) |
| Backend handler | `api/routers/creatives.py:688` (`get_creative_language_flag_coverage`) | Sort + summary changes (§4) |

**Key fact:** the row payload is **already rich enough** — `CreativeLanguageFlagCoverageRow` (`api.ts:161`) already returns `effective_language_code`, `detected_language`, `serving_countries[]`, `detected_currencies[]`, `language_flag_reason`, `geo_linguistic_reason`, `geo_linguistic_decision`, `currency_flag_status/reason`, `spend_30d_micros`, `impressions_30d`, `is_active`, `last_active_date`, `format`, `approval_status`, `buyer_id`. No new per-row fields needed for the headline.

---

## 4. Backend changes — `api/routers/creatives.py`

### 4.1 Re-rank: money first within severity ⚠️ behaviour change

**Current** sort (`creatives.py:784`):
```python
rows.sort(key=lambda item: (
    _status_rank(item.geo_linguistic_status),
    _status_rank(item.language_flag_status),
    -item.spend_30d_micros, ...
))
```
This puts **every red above every orange regardless of spend** — a $0 red ranks above a $5,000 orange. That contradicts "which creatives lose the most money."

**Required:** when no severity filter is applied, the visible order must be **money-dominant**. Implement a single derived severity rank (red-on-either-axis = `confirmed`, orange-on-either-and-not-red = `review`, else `ok`) and sort:
```python
# severity bucket first (confirmed before review before ok), THEN money desc
rows.sort(key=lambda item: (
    _severity_rank(item),        # 0=confirmed, 1=review, 2=ok
    -item.spend_30d_micros,
    (item.creative_name or "").lower(),
    item.creative_id,
))
```
Rationale: keep confirmed-wrong grouped at the top (they're actionable now), but **within each bucket the biggest dollar losers lead**. Add a `_severity_rank(row) -> int` helper next to the existing `_status_rank` (`creatives.py:59`).

### 4.2 Replace two status filters with one `severity` param

Keep `language_state` / `geo_state` accepted for backward-compat (other callers may exist — grep before removing), but **add**:
```python
severity: str = Query("all", pattern="^(all|confirmed|review|ok)$",
                      description="confirmed=red on either axis, review=orange (not red), ok=green")
```
Filter logic: map each row to its severity bucket via `_severity_rank`, drop rows that don't match when `severity != "all"`. Apply this filter **before** pagination, same place as the existing `language_state`/`geo_state` checks (`creatives.py:752`).

### 4.3 Add spend totals to the summary

Extend `CreativeLanguageFlagCoverageSummary` (Pydantic model in the router/schema module, mirrored in `api.ts:188`):
```python
spend_at_risk_micros: int        # sum spend over confirmed + review
spend_confirmed_micros: int      # sum spend over confirmed
spend_review_micros: int         # sum spend over review
count_confirmed: int
count_review: int
count_ok: int
```
Compute over the **full filtered-but-unpaged `rows`** list (the summary already does this for the green/orange/red counts at `creatives.py:797`). Keep the existing `language_*`/`geo_*` count fields for backward-compat.

### 4.4 ⚠️ Coverage caveat — flag, don't silently ship

`scan_limit` (default 250, FE passes 200) truncates **before** spend is known (`creatives.py:718` scans, then `_get_spend_snapshot` runs over only those IDs, then sort). So a high-spend offender outside the first N scanned creatives **never appears**. For a "biggest money loser" view this is a real correctness gap.

**For this ticket:** raise the FE `scan_limit` so a buyer's full active-creative set is realistically covered (see §5.4), and **surface the limit in the UI** — if `total === scan_limit` reached, show a small "showing top N scanned — some low-spend creatives may be omitted" note. **Do not** silently cap. If a buyer can exceed ~2–3k creatives, raise a follow-up to make the scan spend-ordered at source (separate ticket — note it in the PR description).

---

## 5. Frontend changes

### 5.1 Extract `CreativeThumb` (shared) — do this first

Lift the per-format render logic out of `creative-card.tsx:45` (`PreviewThumbnail`) into a new reusable component:

`dashboard/src/components/creative-thumb.tsx`
```tsx
export function CreativeThumb({
  creative,                  // accepts Creative OR a minimal {format, video?, native?, ...}
  size = "md",               // "sm" (this page, ~64px) | "md" (card, h-20)
}: { creative: Pick<Creative, "format" | "video" | "native" | "data_source">; size?: "sm" | "md" })
```
- Move the VIDEO / NATIVE / HTML / IMAGE branches verbatim; parametrise the height (`h-16` for `sm`, `h-20` for `md`) and the live/cached badge (hide on `sm` to reduce noise).
- Refactor `creative-card.tsx` to consume `<CreativeThumb size="md" />` — **must be a no-op visual change** on the `/creatives` grid. Verify the grid looks identical after refactor.
- Keep the `eslint-disable @next/next/no-img-element` comment — these are arbitrary external assets.

### 5.2 The headline sentence — the one piece of new logic

New helper, e.g. `dashboard/src/lib/language-flag-headline.ts`:
```ts
buildLanguageFlagHeadline(row: CreativeLanguageFlagCoverageRow, t, language): {
  title: string;       // "Spanish creative serving Germany"
  subtitle: string;    // the reason line, from existing *_reason fields
}
```
Rules:
- **Language name** from `effective_language_code` (fallback `detected_language_code` → `detected_language`) via a code→name map. Check for an existing map first — `dashboard/src/lib/language-country-map.ts` already exists (used by `isLanguageCountryMismatch` in `creative-card.tsx:11`); extend it rather than adding a parallel map.
- **Country names + flags** from `serving_countries[]` (show first 1–2, "+N more").
- Title template comes from i18n (§5.5), e.g. `"{language} creative serving {country}"`. For orange/review use a hedged template (`"Possibly {language} in a {country} market"`).
- Subtitle = prefer `geo_linguistic_reason` when geo is the red axis, else `language_flag_reason`; append currency note when `detected_currencies.length` and `currency_flag_status !== "green"`.
- Must be **pure + null-safe** — every field above can be null/empty. Never throw; degrade to ID-only.

### 5.3 Wire the modal (reuse, don't rebuild)

Mirror `creatives/page.tsx:879-889` exactly:
```tsx
const [previewCreative, setPreviewCreative] = useState<Creative | null>(null);
// row onClick → setPreviewCreative(rowToCreativeStub(row))
{previewCreative && (
  <PreviewModal creative={previewCreative} onClose={() => setPreviewCreative(null)} />
)}
```
`PreviewModal` **self-fetches** full data via `getCreativeLive(id)` on mount (`PreviewModal.tsx:75`), so the stub only needs enough to satisfy the `Creative` type for first paint. Add a small mapper:
```ts
rowToCreativeStub(row): Creative  // { id: row.creative_id, name, format, buyer_id, approval_status, ... } with safe defaults
```
Put it next to the headline helper. Cast/fill required `Creative` fields with empty defaults; the modal overwrites them within ~1 fetch. The clickable target is the whole row **and** the `[view →]` affordance (button stops propagation only if it ever needs separate behaviour — currently identical).

### 5.4 Page rewrite — `language-flags/page.tsx`

Keep: the `useParams`/`useAccount`/`effectiveBuyerId` resolution (`page.tsx:60-66`), the `useQuery`/`useMutation` scaffolding (`:92-149`), pagination state, `notice` banner, auto-refresh polling.

Replace:
1. **Header (`:194-226`)** — title + one big figure: `${(summary.spend_at_risk_micros/1e6)} at risk / 30d · {count_confirmed+count_review} creatives`. Delete the 4-card grid.
2. **Filters (`:241-312`)** — replace the two `<select>`s with a **segmented control** (3 segments: Confirmed wrong / Needs review / OK), each showing count + compact `$` from the new summary fields. Keep the search input and the Refresh-all button. Drive a new `severity` state → pass to `getCreativeLanguageFlagCoverage`.
3. **Table (`:321-401`)** — replace `<table>` with a list of **row components**. Each row:
   - `<CreativeThumb size="sm" creative={rowToCreativeStub(row)} />`
   - severity dot + `buildLanguageFlagHeadline(row).title`
   - subtitle line
   - foot line: `#id · "name" · format · approval_status`
   - right: `$X / 30d` (use the existing `spend_30d_micros/1e6` formatting), `[view →]`, and `[refresh]` **only** when geo is orange/stale (reuse the per-row refresh; if the current API only supports bulk refresh by search, scope a single-creative refresh by passing `search=row.creative_id` — confirm with architect before adding a new endpoint).
   - `onClick` → open modal.
   - empty state: keep existing "no results" copy (`:391`).
4. Raise `INITIAL_SCAN_LIMIT` (`page.tsx:17`) per §4.4; surface the coverage note when `total` hits the cap.

Update `getCreativeLanguageFlagCoverage` params object (`creatives.ts:132`) and `CreativeLanguageFlagCoverageSummary` (`api.ts:188`) to include the new `severity` param and summary fields.

### 5.5 i18n

All new strings go through `t.creatives.*` (the page already uses `useTranslation`). Add keys for: headline templates (confirmed + hedged variants), severity segment labels, "at risk / 30d", coverage note. Add to **every** locale bundle the project ships (grep an existing `t.creatives.languageFlags*` key to find all bundle files). Language/country **names** should use the i18n locale where the bundle provides them; otherwise the code→name map is acceptable for v1 — note it for follow-up.

---

## 6. Data contracts (after change)

**Request** `GET /creatives/language-flag-coverage`
```
buyer_id, search, severity=all|confirmed|review|ok,
limit, offset, scan_limit, days
(language_state, geo_state still accepted, deprecated)
```

**Response** `CreativeLanguageFlagCoverageResponse` — rows unchanged; summary gains:
```ts
spend_at_risk_micros, spend_confirmed_micros, spend_review_micros,
count_confirmed, count_review, count_ok   // existing language_*/geo_* retained
```

---

## 7. Edge cases the implementer must handle

- Row with **no spend** (`spend_30d_micros === 0`, `is_active === false`): show `–` for money, still render; these sort last within bucket. Consider dimming.
- **Null language / no serving countries**: headline degrades to "Language mismatch (details unavailable)" + ID; never throw.
- **Thumbnail load failure**: existing `onError` hides the `<img>` and falls back to the format placeholder — preserve that behaviour in `CreativeThumb`.
- **Stale orange** (`geo_linguistic_completed_at` old / null): this is the row that shows `[refresh]`. Reuse existing "no AI refresh yet" copy.
- **Modal stub → live mismatch**: modal may correct format/language after its fetch; that's expected, no action.
- **`scan_limit` reached**: show coverage note (§4.4).
- **Long creative names**: truncate with `title=` tooltip (existing pattern at `page.tsx:338`).

---

## 8. Testing / acceptance

1. **Refactor safety:** `/creatives` grid renders pixel-identical after `CreativeThumb` extraction (manual diff + existing snapshot tests if any).
2. **Ordering:** with `severity=all`, confirmed rows precede review rows; within each, descending `spend_30d_micros`. Verify with a buyer that has a $0-red and a high-$ orange.
3. **Headline:** spot-check 5+ rows across ES/JP/FR/DE creatives — titles read as natural sentences, no `null`/`undefined`/`?` leaking.
4. **Modal:** click row → `PreviewModal` opens, shows correct creative after live fetch, ESC + close work, no console errors.
5. **Severity control:** counts + `$` match the table; switching segments refetches and resets to page 0.
6. **Headline figure** equals `spend_confirmed + spend_review` from summary.
7. **i18n:** switch locale → all new strings translate, no raw keys shown.
8. **Empty / error / loading** states unchanged (reuse `LoadingPage`, `ErrorPage`).
9. No new query to `rtb_daily` in batch — spend comes from the existing `_get_spend_snapshot` precompute path (per `CLAUDE.md` performance rule). Confirm no added batch `rtb_daily` reads.

---

## 9. Build order (suggested)

1. BE: `_severity_rank` + re-sort + `severity` param + summary fields (§4). Unit-test the rank/filter.
2. Types: extend `api.ts` summary + client param (§5.5, 6).
3. FE: extract `CreativeThumb`, verify `/creatives` unchanged (§5.1).
4. FE: headline helper + `rowToCreativeStub` + i18n keys (§5.2, 5.3, 5.5).
5. FE: rewrite page header + segmented control + rows + modal wiring (§5.4).
6. QA pass (§8); raise the spend-ordered-scan follow-up ticket (§4.4) if needed.

---

## 10. Open questions for architect (resolve before/while building)

- **Per-row refresh:** does a single-creative language re-analysis endpoint exist, or do we scope the bulk refresh by `search=creative_id`? (Confirm before adding any new endpoint.)
- **`scan_limit` ceiling:** what's the realistic max active-creative count per buyer? Determines whether §4.4's source-side spend-ordered scan is a fast-follow or can wait.
- **Language/country naming:** use full i18n locale names now, or ship the code→name map for v1?
