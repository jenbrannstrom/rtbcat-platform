# Chinese (zh) Readiness Audit - Dashboard Frontend (Phase 3)

Date: 2026-02-24
Scope: `dashboard/src` frontend UI + i18n wiring (static audit)
Goal: Identify blockers/risks for shipping a usable Chinese UI (priority locale)

## Executive Summary

Chinese is selectable in the UI today (`zh` appears in the language selector), but the app is not Chinese-ready yet.

Primary blockers:
1. `zh` still aliases to English (no real Chinese dictionary loaded).
2. Global font setup uses `Inter` with `latin` subset only, which is not a deliberate CJK typography strategy.
3. Several date/time displays still hardcode English locale (`en-US`) even after translation work.
4. Many dense operational tables/panels use Latin-centric styling (`uppercase`, `tracking-wide`, `whitespace-nowrap`, fixed widths) that will need CJK layout verification.

This is fixable without changing core app behavior. The main work is:
- add `zh` translations,
- normalize formatting helpers to use app language,
- make a small typography/layout pass on high-density screens.

## Current Locale Status (Chinese)

- Chinese is listed in the selector: `dashboard/src/lib/i18n/index.ts:67`
- Chinese currently falls back to English entirely: `dashboard/src/lib/i18n/index.ts:50`
- Only `en`, `es`, and `nl` locale files are currently exported/loaded: `dashboard/src/lib/i18n/index.ts:2`, `dashboard/src/lib/i18n/index.ts:3`, `dashboard/src/lib/i18n/index.ts:4`
- Language type uses generic `zh` (not region-specific `zh-CN` / `zh-TW`): `dashboard/src/lib/i18n/types.ts:2`

## Audit Method (Static)

Heuristic scans across `dashboard/src` for Chinese-risk patterns:
- Hardcoded locale formatting (`en-US`, `en-GB`)
- `toLocale*`/`Intl.*` usage that may ignore selected app language
- Dense UI layout constraints (`whitespace-nowrap`, `truncate`, `line-clamp-*`)
- Latin-centric typography styling (`uppercase`, `tracking-wide`, `tracking-wider`)
- Global font and document language setup

Counts (heuristic, not all are bugs):
- Hardcoded English locale strings (`en-US`/`en-GB`): `3`
- `toLocale*` / `Intl.*` formatting calls: `59`
- `truncate` / `whitespace-nowrap` / `line-clamp-*`: `70`
- `uppercase` class usage: `51`
- `tracking-wide` / `tracking-wider`: `35`

## Findings (Prioritized)

### P0 - Chinese locale is selectable but still English-only

Chinese users can select `zh`, but the dictionary resolves to English because `zh` is mapped directly to `en`.

Evidence:
- `dashboard/src/lib/i18n/index.ts:50`
- `dashboard/src/lib/i18n/index.ts:67`

Impact:
- Users expecting Chinese will see English UI.
- Makes QA misleading because language switching appears to work but only changes locale code/dir.

Fix:
- Add `dashboard/src/lib/i18n/translations/zh.ts` (or `zh-CN.ts`) and wire it via English fallback (`withEnglishFallback(...)`).

### P0 - Global font setup is not CJK-ready (Inter Latin subset only)

The app uses `Inter` with `subsets: ["latin"]` globally.

Evidence:
- `dashboard/src/app/layout.tsx:2`
- `dashboard/src/app/layout.tsx:10`
- `dashboard/src/app/layout.tsx:44`

Why this matters for Chinese:
- Chinese glyphs will fall back to OS fonts implicitly and inconsistently.
- Typography will vary by platform and may look mismatched next to Inter Latin text.
- No explicit CJK fallback stack means harder QA and less predictable line wrapping/metrics.

Fix:
- Add an explicit CJK-capable fallback stack for body text (for example `PingFang SC`, `Microsoft YaHei`, `Noto Sans SC`, `Hiragino Sans GB`, `Source Han Sans SC`, then system sans fallback).
- Optional stronger fix: locale-aware font class for `zh`.

### P1 - Some dates still hardcode English locale (`en-US`)

Even after UI strings are translated, several date labels will still render in English formatting.

Evidence:
- `dashboard/src/lib/utils.ts:13`
- `dashboard/src/components/rtb/config-breakdown-panel.tsx:1035`
- `dashboard/src/components/rtb/config-breakdown-panel.tsx:1092`

Impact:
- Chinese UI will show mixed-language formatting (e.g. English month names in otherwise Chinese screens).

Fix:
- Standardize all date formatting through locale-aware helpers fed by the selected app language.
- Remove hardcoded `en-US` in component-level formatting.

### P1 - Initial HTML `lang` is hardcoded to `en` until client hydration

The app correctly updates `document.documentElement.lang` and `dir` after hydration, but SSR markup starts as `<html lang="en">`.

Evidence:
- Hardcoded SSR lang: `dashboard/src/app/layout.tsx:43`
- Runtime correction after hydration: `dashboard/src/contexts/i18n-context.tsx:81`

Impact:
- Minor but real: screen readers, browser heuristics, and crawlers may see the wrong language initially.
- Can produce a brief mismatch during initial paint.

Fix:
- Acceptable short-term for client-only locale selection.
- Better long-term: derive initial language server-side from cookie and set `<html lang>` on first render.

### P1 - Formatting calls often use browser locale instead of selected app language

There are many `toLocaleString()` / `toLocaleDateString()` calls without an explicit locale. Those use the browser/OS locale, not necessarily the in-app selected language.

Evidence examples:
- `dashboard/src/components/import/ImportHistoryTable.tsx:144`
- `dashboard/src/components/rtb/account-endpoints-header.tsx:163`
- `dashboard/src/components/recommendations/recommendation-card.tsx:267`
- `dashboard/src/components/waste-analyzer/FunnelCard.tsx:16`

Impact:
- A user can select Chinese UI and still see English/US number formatting if their browser locale differs.

Fix:
- Introduce shared formatting helpers that always accept the current app `language` (number, currency, compact number, date/time).
- Replace direct `toLocaleString()` calls in hotspot screens first.

### P2 - Dense operational tables use `nowrap`/truncate heavily; Chinese needs layout QA pass

Many tables/pills/headers use `whitespace-nowrap`, `truncate`, and fixed widths, which can clip translated labels or reduce readability on narrow screens.

Representative evidence:
- Admin users table headers/cells: `dashboard/src/app/admin/users/page.tsx:251`, `dashboard/src/app/admin/users/page.tsx:274`, `dashboard/src/app/admin/users/page.tsx:324`
- Import history table date column (`nowrap`) + row count formatting: `dashboard/src/components/import/ImportHistoryTable.tsx:127`, `dashboard/src/components/import/ImportHistoryTable.tsx:144`
- RTB endpoints header small fixed-width metrics and URL truncation: `dashboard/src/components/rtb/account-endpoints-header.tsx:136`, `dashboard/src/components/rtb/account-endpoints-header.tsx:147`, `dashboard/src/components/rtb/account-endpoints-header.tsx:150`
- Large RTB panel has many truncation/nowrap hotspots: `dashboard/src/components/rtb/config-breakdown-panel.tsx:995`, `dashboard/src/components/rtb/config-breakdown-panel.tsx:1764`

Impact:
- Chinese is often shorter than English for some labels, but not always.
- Dense panels can still overflow or become hard to scan with CJK glyph density and smaller font sizes.

Fix:
- Do a targeted visual QA pass for Chinese on these screens first:
  1. `Admin > Users`
  2. `Import`
  3. RTB endpoints / breakdown panels
  4. Pretargeting editor
- Replace `whitespace-nowrap` on non-critical labels with wrapping where possible.
- Increase minimum font size in ultra-dense metric labels (`text-[9px]`, `text-[10px]`) where Chinese readability suffers.

### P2 - Latin-centric visual styling (`uppercase` + tracking) is widespread

The UI uses uppercase + letter-spacing patterns heavily for headers, badges, and micro-labels. These are tuned for Latin text and often look awkward or ineffective in Chinese.

Representative evidence:
- Sidebar section labels: `dashboard/src/components/sidebar.tsx:429`, `dashboard/src/components/sidebar.tsx:529`, `dashboard/src/components/sidebar.tsx:599`
- Admin tables: `dashboard/src/app/admin/users/page.tsx:251`
- Preview modal section labels: `dashboard/src/components/preview-modal/PreviewModal.tsx:267`
- RTB endpoint micro labels: `dashboard/src/components/rtb/account-endpoints-header.tsx:136`

Impact:
- `uppercase` has no useful effect on Chinese characters.
- `tracking-wide` / `tracking-wider` may degrade CJK visual quality.

Fix:
- Add locale-aware typography helpers/classes (e.g., disable `uppercase` + tracking for CJK locales on label components).
- This can be incremental and component-level.

### P2 - Generic `zh` locale code is workable, but ambiguous for product rollout

Current app language type and selector use generic `zh`.

Evidence:
- `dashboard/src/lib/i18n/types.ts:2`
- `dashboard/src/lib/i18n/index.ts:67`

Impact:
- Hard to distinguish Simplified vs Traditional Chinese later.
- If your 4 customers are all Simplified Chinese users, generic `zh` is okay short-term, but region/script clarity is better for future support.

Fix:
- Short-term: keep `zh` and ship Simplified Chinese content under it.
- Medium-term: migrate to `zh-CN` and optionally `zh-TW` with a compatibility alias from old `zh` preference.

## What Is Not a Chinese Blocker (Right Now)

- RTL support is a separate concern (Arabic/Hebrew). The app already tracks RTL languages and sets `dir` dynamically: `dashboard/src/lib/i18n/index.ts:78`, `dashboard/src/contexts/i18n-context.tsx:82`
- Chinese does not require pluralization rules in the same way Slavic languages do. Existing string interpolation is acceptable for a first Chinese release.

## Recommendation: Split/Refactor Translation Files?

Yes. The current locale files should be split.

Current size (approx):
- `en.ts`: 1971 lines
- `es.ts`: 2031 lines
- `nl.ts`: 2171 lines

Problems with current structure:
- High merge conflict risk (multiple worktrees/sessions editing one file)
- Hard to review and audit by namespace
- Easy to accidentally duplicate/misplace keys during large Phase 3 passes

Recommended refactor (incremental, low risk):
1. Keep the existing `Translations` type as the contract.
2. Split by namespace per locale, e.g.:
   - `dashboard/src/lib/i18n/translations/zh/common.ts`
   - `dashboard/src/lib/i18n/translations/zh/pretargeting.ts`
   - `dashboard/src/lib/i18n/translations/zh/import.ts`
   - etc.
3. Add a locale index composer:
   - `dashboard/src/lib/i18n/translations/zh/index.ts` that exports a merged `PartialTranslations`
4. Do the same for `en`, `nl`, `es` over time (not all at once).
5. Keep deep English fallback in `i18n/index.ts`.

This directly reduces worktree conflicts and makes Chinese rollout faster because we can translate only `zh/pretargeting.ts`, `zh/import.ts`, `zh/admin.ts`, etc.

## Chinese-First Implementation Order (Recommended)

1. `zh` dictionary scaffold + English fallback wiring
2. `zh` translations for high-use operational namespaces:
   - `common`, `language`, `sidebar`, `auth`, `dashboard`
   - `pretargeting`
   - `import`
   - `admin`
3. Locale-aware formatting cleanup (remove hardcoded `en-US`, centralize formatters)
4. Font stack/CJK typography baseline
5. Visual QA pass on dense screens (Import/Admin/RTB/Pretargeting)
6. Optional: region split (`zh-CN` / `zh-TW`)

## Quick Wins (1-2 sessions)

- Add `zh` partial dictionary (English fallback) and translate top operational screens.
- Replace the 3 hardcoded `en-US` date formatters.
- Add explicit CJK fallback fonts in global layout/styles.
- Patch a few obvious `toLocaleString()` calls in high-traffic screens to use selected app language.

