# Phase 1 Translation Audit (Hardcoded String Inventory)

Date: 2026-02-23

## Scope

- Phase 1 only: audit and inventory of hardcoded user-facing strings that need to be moved behind the dashboard i18n system.
- Audited frontend app code under `dashboard/src` (the only part currently wired to the translation layer).
- Backend/API/server-side strings are out of scope for this phase unless surfaced directly in frontend source files.

## Current Language Table (What Exists Today)

Source: `dashboard/src/lib/i18n/index.ts` (languages list + translation map).

| Code | Language | Native Name | RTL | Current Backing | Current Status |
| --- | --- | --- | --- | --- | --- |
| en | English | English | No | `dashboard/src/lib/i18n/translations/en.ts` | Real dictionary (source of truth) |
| pl | Polish | Polish | No | alias to `en` | Not translated (falls back to English) |
| zh | Chinese | Chinese | No | alias to `en` | Not translated (falls back to English) |
| ru | Russian | Russian | No | alias to `en` | Not translated (falls back to English) |
| uk | Ukrainian | Ukrainian | No | alias to `en` | Not translated (falls back to English) |
| es | Spanish | Spanish | No | alias to `en` | Not translated (falls back to English) |
| da | Danish | Danish | No | alias to `en` | Not translated (falls back to English) |
| fr | French | French | No | alias to `en` | Not translated (falls back to English) |
| nl | Dutch | Dutch | No | alias to `en` | Not translated (falls back to English) |
| he | Hebrew | Hebrew | Yes | alias to `en` | RTL supported by layout toggle, but text untranslated |
| ar | Arabic | Arabic | Yes | alias to `en` | RTL supported by layout toggle, but text untranslated |

## Methodology

- AST-based scan (TypeScript parser) across `.tsx` and `.ts` files in `dashboard/src`, excluding tests and the existing translation dictionary files.
- Collected high-confidence hardcoded UI text in these contexts: JSX text nodes, placeholders/titles/aria labels, rendered JSX expression strings, error/message calls, and label/tooltip metadata properties.
- Exported a full machine-readable inventory CSV with file/line/column references.
- This is intentionally conservative on coverage: a small number of enum/control literals may remain in the inventory and should be filtered during Phase 2 implementation.

## Summary

- Files scanned: **141**
- Files with hardcoded-string hits: **83**
- Hardcoded string inventory items: **1459**
- App/components TSX files: **103**
- App/components files using `useTranslation()`: **19** (18.4%)
- Inventory CSV (full list): `docs/I18N_PHASE1_HARDCODED_STRING_INVENTORY_2026-02-23.csv`

## Inventory Breakdown by Category

| Category | Count |
| --- | --- |
| `jsx_text` | 1093 |
| `jsx_expr_string` | 146 |
| `property:label` | 50 |
| `jsx_attr:title` | 47 |
| `jsx_template_text` | 28 |
| `error_literal` | 27 |
| `jsx_attr:placeholder` | 16 |
| `jsx_attr:label` | 11 |
| `property:tooltip` | 10 |
| `jsx_attr:alt` | 6 |
| `call:setError` | 5 |
| `property:description` | 5 |
| `call:setErrorMessage` | 4 |
| `jsx_attr:aria-label` | 4 |
| `call:alert` | 3 |
| `call:confirm` | 2 |
| `property:title` | 1 |
| `property:message` | 1 |

## Inventory Breakdown by Area

| Area | Count |
| --- | --- |
| `components` | 1074 |
| `app` | 346 |
| `lib` | 28 |
| `contexts` | 11 |

## Highest-Impact Hotspots (Top Files by Hardcoded String Count)

| Rank | File | Count |
| --- | --- | --- |
| 1 | `dashboard/src/components/import/ExportInstructions.tsx` | 105 |
| 2 | `dashboard/src/components/rtb/pretargeting-settings-editor.tsx` | 99 |
| 3 | `dashboard/src/components/rtb/config-breakdown-panel.tsx` | 80 |
| 4 | `dashboard/src/app/settings/accounts/components/ApiConnectionTab.tsx` | 74 |
| 5 | `dashboard/src/components/rtb/app-drilldown-modal.tsx` | 62 |
| 6 | `dashboard/src/components/preview-modal/PreviewModal.tsx` | 46 |
| 7 | `dashboard/src/app/settings/accounts/components/GmailReportsTab.tsx` | 44 |
| 8 | `dashboard/src/components/waste-analyzer/SizeAnalysisSection.tsx` | 43 |
| 9 | `dashboard/src/components/import/RequiredColumnsTable.tsx` | 38 |
| 10 | `dashboard/src/components/waste-analyzer/PublisherPerformanceSection.tsx` | 38 |
| 11 | `dashboard/src/app/settings/retention/page.tsx` | 36 |
| 12 | `dashboard/src/app/campaigns/[id]/page.tsx` | 35 |
| 13 | `dashboard/src/components/waste-analyzer/FunnelCard.tsx` | 35 |
| 14 | `dashboard/src/app/settings/accounts/components/SystemTab.tsx` | 32 |
| 15 | `dashboard/src/components/waste-analyzer/GeoAnalysisSection.tsx` | 32 |
| 16 | `dashboard/src/components/rtb/snapshot-comparison-panel.tsx` | 29 |
| 17 | `dashboard/src/components/rtb/recommended-optimizations-panel.tsx` | 28 |
| 18 | `dashboard/src/app/import/page.tsx` | 27 |
| 19 | `dashboard/src/components/rtb/endpoint-efficiency-panel.tsx` | 24 |
| 20 | `dashboard/src/components/preview-modal/CountrySection.tsx` | 23 |
| 21 | `dashboard/src/components/rtb/pretargeting-config-card.tsx` | 23 |
| 22 | `dashboard/src/app/page.tsx` | 22 |
| 23 | `dashboard/src/components/preview-modal/LanguageSection.tsx` | 22 |
| 24 | `dashboard/src/components/creative-card.tsx` | 21 |
| 25 | `dashboard/src/components/qps/geo-waste-panel.tsx` | 21 |
| 26 | `dashboard/src/components/rtb/config-performance.tsx` | 21 |
| 27 | `dashboard/src/app/login/page.tsx` | 20 |
| 28 | `dashboard/src/components/qps/qps-summary-card.tsx` | 20 |
| 29 | `dashboard/src/components/recommendations/recommendation-card.tsx` | 20 |
| 30 | `dashboard/src/lib/url-utils.ts` | 20 |
| 31 | `dashboard/src/components/import/ImportTrackingMatrixSection.tsx` | 19 |
| 32 | `dashboard/src/components/qps/pretargeting-panel.tsx` | 19 |
| 33 | `dashboard/src/components/waste-report.tsx` | 17 |
| 34 | `dashboard/src/components/rtb/account-endpoints-header.tsx` | 14 |
| 35 | `dashboard/src/app/settings/accounts/components/GeminiApiKeySection.tsx` | 13 |
| 36 | `dashboard/src/components/import/ImportResultCard.tsx` | 13 |
| 37 | `dashboard/src/components/import/TroubleshootingSection.tsx` | 13 |
| 38 | `dashboard/src/components/size-coverage-chart.tsx` | 13 |
| 39 | `dashboard/src/components/recommendations/recommendations-panel.tsx` | 12 |
| 40 | `dashboard/src/components/campaigns/draggable-creative.tsx` | 11 |

## Sample Findings (Representative)

### `dashboard/src/app/login/page.tsx` (20 hits)

| Line | Category | Text |
| --- | --- | --- |
| 54 | `call:setErrorMessage` | Server unavailable. Please try again in a moment. |
| 56 | `call:setErrorMessage` | Login service is temporarily unavailable. |
| 58 | `call:setErrorMessage` | Login failed |
| 67 | `call:setErrorMessage` | Cannot reach server. Please check your connection and try again. |
| 93 | `jsx_attr:alt` | Cat-Scan |
| 95 | `jsx_text` | Cat-Scan |
| 96 | `jsx_text` | QPS manager for Google Auth Buyers |
| 112 | `jsx_text` | Sign in to continue |
| 130 | `jsx_text` | Sign in with Authing |
| 162 | `jsx_text` | Sign in with Google |
| 184 | `jsx_text` | Sign in with Email |
| 197 | `jsx_text` | &larr; Back to options |
| 202 | `jsx_text` | Sign in with Email |
| 208 | `jsx_text` | Email |
| 219 | `jsx_attr:placeholder` | you@example.com |

### `dashboard/src/app/page.tsx` (22 hits)

| Line | Category | Text |
| --- | --- | --- |
| 21 | `property:label` | 7 days |
| 22 | `property:label` | 14 days |
| 23 | `property:label` | 30 days |
| 323 | `jsx_text` | Data as of |
| 326 | `jsx_text` | (home: |
| 326 | `jsx_text` | , bidstream: |
| 332 | `jsx_text` | Data freshness pending… |
| 348 | `jsx_expr_string` | Config CPM |
| 348 | `jsx_expr_string` | Avg CPM |
| 398 | `jsx_text` | Unable to load buyer seats. Retry to continue. |
| 403 | `jsx_text` | Retry |
| 412 | `jsx_text` | Loading seat access... |
| 417 | `jsx_text` | No active buyer seats found. Sync seats in Settings to load home analytics. |
| 422 | `jsx_text` | Select a seat to load home analytics. |
| 463 | `jsx_expr_string` | Use "Sync All" in the sidebar to fetch pretargeting configs. |

### `dashboard/src/components/import/ExportInstructions.tsx` (105 hits)

| Line | Category | Text |
| --- | --- | --- |
| 12 | `jsx_text` | Why 5 Separate Reports? |
| 14 | `jsx_text` | Google Authorized Buyers has |
| 14 | `jsx_text` | field incompatibilities |
| 14 | `jsx_text` | that prevent getting all data in one export: |
| 17 | `jsx_text` | • To get Creative-level bid metrics, you lose &quot;Bid requests&quot; |
| 18 | `jsx_text` | • To get &quot;Bid requests&quot;, you lose Creative detail |
| 19 | `jsx_text` | • Pretargeting config (Billing ID) cannot be combined with bid pipeline metrics |
| 24 | `jsx_text` | Create 5 Scheduled Reports in Authorized Buyers |
| 26 | `jsx_text` | Open |
| 26 | `jsx_text` | Authorized Buyers |
| 27 | `jsx_text` | Go to |
| 27 | `jsx_text` | Reporting |
| 27 | `jsx_text` | Scheduled Reports |
| 27 | `jsx_text` | New Report |
| 28 | `jsx_text` | Create each report below with schedule: |

### `dashboard/src/components/rtb/config-breakdown-panel.tsx` (80 hits)

| Line | Category | Text |
| --- | --- | --- |
| 35 | `property:label` | By Creative |
| 36 | `property:label` | By Size |
| 37 | `property:label` | By Geo |
| 38 | `property:label` | By Publisher |
| 634 | `jsx_text` | Loading breakdown... |
| 640 | `jsx_text` | Failed to load breakdown data |
| 651 | `jsx_text` | No publisher breakdown available for this config |
| 654 | `jsx_expr_string` | Billing-level CSV missing or the precompute job has not yet processed publisher-level data for this config. |
| 661 | `jsx_text` | Go to Import |
| 670 | `jsx_text` | data for this config |
| 675 | `jsx_expr_string` | Geographic breakdown is not available. This config may not have geographic targeting data, or the precompute job has not yet processed this config. |
| 677 | `jsx_expr_string` | Size breakdown is not available. This config may not have had bid activity in the selected period, or the precompute job has not yet processed this config. |
| 679 | `jsx_expr_string` | Creative breakdown is not available. This config may not have active creatives with bid activity, or the precompute job has not yet processed this config. |
| 680 | `jsx_template_text` | To see |
| 680 | `jsx_template_text` | breakdown, import both catscan-quality (includes pretargeting config / billing_id) and catscan-bidsinauction CSV reports. |

### `dashboard/src/components/import/ImportTrackingMatrixSection.tsx` (19 hits)

| Line | Category | Text |
| --- | --- | --- |
| 53 | `jsx_text` | Pass |
| 62 | `jsx_text` | Fail |
| 70 | `jsx_text` | Not Imported |
| 97 | `jsx_text` | Import Coverage Matrix |
| 99 | `jsx_text` | Account x CSV type status: pass, fail, or not imported |
| 106 | `jsx_attr:title` | Refresh |
| 114 | `jsx_text` | Accounts: |
| 117 | `jsx_text` | Pass: |
| 120 | `jsx_text` | Fail: |
| 123 | `jsx_text` | Not imported: |
| 132 | `jsx_text` | Loading matrix... |
| 136 | `jsx_text` | No import coverage data yet. |
| 143 | `jsx_text` | Account |
| 144 | `jsx_text` | CSV Type |
| 145 | `jsx_text` | Status |

## Full File Inventory Counts (All Files with Hits)

| File | Count |
| --- | --- |
| `dashboard/src/components/import/ExportInstructions.tsx` | 105 |
| `dashboard/src/components/rtb/pretargeting-settings-editor.tsx` | 99 |
| `dashboard/src/components/rtb/config-breakdown-panel.tsx` | 80 |
| `dashboard/src/app/settings/accounts/components/ApiConnectionTab.tsx` | 74 |
| `dashboard/src/components/rtb/app-drilldown-modal.tsx` | 62 |
| `dashboard/src/components/preview-modal/PreviewModal.tsx` | 46 |
| `dashboard/src/app/settings/accounts/components/GmailReportsTab.tsx` | 44 |
| `dashboard/src/components/waste-analyzer/SizeAnalysisSection.tsx` | 43 |
| `dashboard/src/components/import/RequiredColumnsTable.tsx` | 38 |
| `dashboard/src/components/waste-analyzer/PublisherPerformanceSection.tsx` | 38 |
| `dashboard/src/app/settings/retention/page.tsx` | 36 |
| `dashboard/src/app/campaigns/[id]/page.tsx` | 35 |
| `dashboard/src/components/waste-analyzer/FunnelCard.tsx` | 35 |
| `dashboard/src/app/settings/accounts/components/SystemTab.tsx` | 32 |
| `dashboard/src/components/waste-analyzer/GeoAnalysisSection.tsx` | 32 |
| `dashboard/src/components/rtb/snapshot-comparison-panel.tsx` | 29 |
| `dashboard/src/components/rtb/recommended-optimizations-panel.tsx` | 28 |
| `dashboard/src/app/import/page.tsx` | 27 |
| `dashboard/src/components/rtb/endpoint-efficiency-panel.tsx` | 24 |
| `dashboard/src/components/preview-modal/CountrySection.tsx` | 23 |
| `dashboard/src/components/rtb/pretargeting-config-card.tsx` | 23 |
| `dashboard/src/app/page.tsx` | 22 |
| `dashboard/src/components/preview-modal/LanguageSection.tsx` | 22 |
| `dashboard/src/components/creative-card.tsx` | 21 |
| `dashboard/src/components/qps/geo-waste-panel.tsx` | 21 |
| `dashboard/src/components/rtb/config-performance.tsx` | 21 |
| `dashboard/src/app/login/page.tsx` | 20 |
| `dashboard/src/components/qps/qps-summary-card.tsx` | 20 |
| `dashboard/src/components/recommendations/recommendation-card.tsx` | 20 |
| `dashboard/src/lib/url-utils.ts` | 20 |
| `dashboard/src/components/import/ImportTrackingMatrixSection.tsx` | 19 |
| `dashboard/src/components/qps/pretargeting-panel.tsx` | 19 |
| `dashboard/src/components/waste-report.tsx` | 17 |
| `dashboard/src/components/rtb/account-endpoints-header.tsx` | 14 |
| `dashboard/src/app/settings/accounts/components/GeminiApiKeySection.tsx` | 13 |
| `dashboard/src/components/import/ImportResultCard.tsx` | 13 |
| `dashboard/src/components/import/TroubleshootingSection.tsx` | 13 |
| `dashboard/src/components/size-coverage-chart.tsx` | 13 |
| `dashboard/src/components/recommendations/recommendations-panel.tsx` | 12 |
| `dashboard/src/components/campaigns/draggable-creative.tsx` | 11 |
| `dashboard/src/components/campaigns/list-cluster.tsx` | 10 |
| `dashboard/src/components/import/ImportHistorySection.tsx` | 10 |
| `dashboard/src/components/sidebar.tsx` | 10 |
| `dashboard/src/app/settings/accounts/page.tsx` | 9 |
| `dashboard/src/components/campaign-card.tsx` | 9 |
| `dashboard/src/components/campaigns/cluster-card.tsx` | 9 |
| `dashboard/src/components/rtb/ai-control-settings.tsx` | 9 |
| `dashboard/src/contexts/auth-context.tsx` | 8 |
| `dashboard/src/components/campaigns/api.ts` | 7 |
| `dashboard/src/components/campaigns/list-item.tsx` | 7 |
| `dashboard/src/components/preview-modal/PreviewRenderers.tsx` | 7 |
| `dashboard/src/components/validation-errors.tsx` | 7 |
| `dashboard/src/components/campaigns/SortFilterControls.tsx` | 6 |
| `dashboard/src/components/import-dropzone.tsx` | 5 |
| `dashboard/src/lib/chunked-uploader.ts` | 5 |
| `dashboard/src/app/admin/page.tsx` | 4 |
| `dashboard/src/app/qps/geo/page.tsx` | 4 |
| `dashboard/src/app/qps/publisher/page.tsx` | 4 |
| `dashboard/src/app/qps/size/page.tsx` | 4 |
| `dashboard/src/app/admin/users/page.tsx` | 3 |
| `dashboard/src/app/creatives/page.tsx` | 3 |
| `dashboard/src/app/settings/system/page.tsx` | 3 |
| `dashboard/src/components/campaigns/unassigned-pool.tsx` | 3 |
| `dashboard/src/components/import-preview.tsx` | 3 |
| `dashboard/src/app/bill_id/[billingId]/page.tsx` | 2 |
| `dashboard/src/app/layout.tsx` | 2 |
| `dashboard/src/components/error.tsx` | 2 |
| `dashboard/src/components/import-progress.tsx` | 2 |
| `dashboard/src/components/language-selector.tsx` | 2 |
| `dashboard/src/contexts/i18n-context.tsx` | 2 |
| `dashboard/src/lib/api/core.ts` | 2 |
| `dashboard/src/app/admin/configuration/page.tsx` | 1 |
| `dashboard/src/app/admin/settings/page.tsx` | 1 |
| `dashboard/src/app/connect/page.tsx` | 1 |
| `dashboard/src/app/setup/page.tsx` | 1 |
| `dashboard/src/app/uploads/page.tsx` | 1 |
| `dashboard/src/components/first-run-check.tsx` | 1 |
| `dashboard/src/components/format-chart.tsx` | 1 |
| `dashboard/src/components/import/ColumnMappingCard.tsx` | 1 |
| `dashboard/src/components/preview-modal/SharedComponents.tsx` | 1 |
| `dashboard/src/components/preview-modal/utils.ts` | 1 |
| `dashboard/src/contexts/account-context.tsx` | 1 |
| `dashboard/src/lib/api/analytics.ts` | 1 |

## Phase 1 Deliverables

- Audit report (this file): `docs/I18N_PHASE1_TRANSLATION_AUDIT_2026-02-23.md`
- Full hardcoded-string inventory CSV: `docs/I18N_PHASE1_HARDCODED_STRING_INVENTORY_2026-02-23.csv`

## Phase 2 Notes (Not Executed Yet)

- Convert hardcoded strings to `t.*` lookups in priority order: login/auth, app shell/status/error states, import workflows, RTB config panels, settings tabs.
- Keep a temporary compatibility list for strings intentionally left as raw data (e.g., vendor reason codes, IDs, URLs) to prevent churn.
- After each conversion batch, re-run this audit and diff the CSV count.
