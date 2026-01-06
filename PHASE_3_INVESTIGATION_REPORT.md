# Phase 3 Investigation Report

**Date:** January 6, 2026
**Status:** Investigation Complete - Plan Ready

---

## Part A: Navigation Corrections (Option C Implementation Fixes)

### Current State Analysis

The bottom-left navigation footer in `sidebar.tsx` currently shows:
1. Docs link (pointing to "https://rtb.cat")
2. Language selector (full component with text)
3. Logout button (with text)
4. Collapse toggle (with "Collapse" text when expanded)
5. User info + version (v0.9.0)

### Required Changes

| Item | Current | Required |
|------|---------|----------|
| **Docs** | Separate row with icon + "Docs" text | Next to v0.9.0 in small type, URL: `docs.rtb.cat` |
| **Language Selector** | Bottom footer area | Small flag icon, top-right of header (above refresh button) |
| **Logout** | In footer group | Bottom entry of main left nav (after Settings/Admin sections) |
| **Collapse** | `< Collapse` text | Just `<` icon, no text |

### Files to Modify

1. **`sidebar.tsx`** - Restructure footer, move logout to nav, move collapse button
2. **`language-selector.tsx`** - Create compact flag-only variant for header
3. **`authenticated-layout.tsx`** or create new **`header-bar.tsx`** - Add language selector to top-right

---

## Part B: Phase 3 Live App Issues

### Issue 1: Campaigns Tab Shows Nothing

**Root Cause Analysis:**

1. **Data Flow**: The campaigns page fetches:
   - `fetchCampaigns()` → `/api/campaigns` - Returns all campaigns
   - `fetchUnclustered(buyerId)` → `/api/campaigns/unclustered` - Filtered by buyer
   - `fetchAllCreatives(buyerId)` → `/api/creatives` - Filtered by buyer

2. **Problem Identified**:
   - Campaigns are NOT buyer-filtered at the API level
   - But creatives ARE buyer-filtered
   - When a specific buyer is selected in sidebar, `sortedCampaigns` filters campaigns by `_hasBuyerCreatives` (line 713)
   - If campaign creative_ids don't match ANY creatives from selected buyer, campaign is hidden

3. **Evidence** (from code):
   ```typescript
   // Line 711-717 in campaigns/page.tsx
   let filtered = campaignsWithTotals.filter(c => {
     if (selectedBuyerId && !c._hasBuyerCreatives) return false;
     if (countryFilter && !c._hasFilteredCreatives) return false;
     return true;
   });
   ```

4. **Likely Issue**:
   - Creative IDs in campaigns table might be stored as integers but fetched as strings (or vice versa)
   - Or campaigns were created before creatives were synced for a specific buyer

**Fix Required**:
- Add debug logging to verify creative ID types match
- Check if campaigns API should also filter by buyer_id
- Verify campaigns have valid creative_ids that exist in creatives table

---

### Issue 2: Three Accounts Connected, Only Two Show

**Root Cause Analysis:**

1. **Sidebar Seat Display** (`sidebar.tsx` line 146):
   ```typescript
   const { data: seats } = useQuery({
     queryKey: ["seats"],
     queryFn: () => getSeats({ active_only: true }),
   });
   ```

2. **Problem**: Sidebar uses `active_only: true`, so any seat with `is_active = false` won't appear.

3. **Possible Causes**:
   - Third account's seat has `is_active: false` in database
   - Seat discovery failed for one account but succeeded silently
   - Display name issues causing one to not render

**Fix Required**:
- Check database: `SELECT * FROM buyer_seats` for all 3 accounts
- Verify `is_active` status for each
- Check `/settings/accounts` page which uses `active_only: false`

---

### Issue 3: Some Creatives Show Placeholder in Main Page but Display in Modal

**Root Cause Analysis:**

1. **Creative Card Thumbnails** (`creative-card.tsx` lines 39-136):
   - VIDEO: Requires `creative.video?.thumbnail_url` to show actual thumbnail
   - NATIVE: Requires `creative.native?.logo?.url` or `creative.native?.image?.url`
   - HTML: Always shows placeholder (FileCode icon)
   - IMAGE: Always shows placeholder (Image icon)

2. **Problem Sources**:
   - **VIDEO**: Thumbnail generation might have failed (requires ffmpeg)
   - **NATIVE**: Logo/image URLs might not be synced from Google API
   - **HTML/IMAGE**: These formats intentionally show placeholders - the full content is only rendered in modal iframe

3. **Modal Behavior** (`preview-modal.tsx`):
   - VIDEO: Plays actual video from VAST XML or video_url
   - HTML: Loads full snippet into sandboxed iframe
   - NATIVE: Renders full card with all images

**Why Modal Works But Card Doesn't**:
- Cards show **thumbnail previews** (pre-generated images)
- Modals show **live content** (actual media/HTML)
- If thumbnails weren't generated, card shows placeholder but modal still works

**Fix Required**:
- Check thumbnail generation status: `/api/thumbnails/status`
- Verify ffmpeg is installed: `ffmpeg -version`
- Run batch thumbnail generation: `/api/thumbnails/generate-batch`
- For NATIVE: Check if logo/image URLs are being synced from Google API

---

### Issue 4: Tracking URLs Curtailed in Modal (Need Full on Hover, Clickable)

**Root Cause Analysis:**

1. **Current Implementation** (`preview-modal.tsx`):

   **Destination URLs** (lines 700-720):
   ```typescript
   <a
     href={url.url}
     className="text-primary-600 hover:text-primary-700 truncate flex-1 text-xs"
   >
     {getUrlDisplayText(url)}
   </a>
   ```
   - Uses `truncate` which cuts off text with ellipsis
   - No `title` attribute for hover tooltip

   **Tracking Parameters** (lines 730-734):
   ```typescript
   <span className="text-gray-700 truncate max-w-[150px]">{value}</span>
   ```
   - Hard limit of 150px width
   - No hover reveal
   - Values are not clickable

2. **Required Behavior**:
   - Show full URL on hover (title tooltip)
   - Make URLs clickable (already are for destinations, not for tracking params)
   - Consider expandable section for very long URLs

**Fix Required**:
- Add `title={url.url}` attribute to show full URL on hover
- For tracking params, add `title={value}` and optionally make them copyable
- Consider adding a "Show full URL" toggle or expand button

---

### Issue 5: CSV Import Not Running for All Accounts (Mismatch)

**Root Cause Analysis:**

1. **CSV Import Flow**:
   - User uploads CSV → `parseCSV()` detects columns
   - `extractSeatFromPreview()` extracts `buyer_id` from CSV headers
   - Data imported to `rtb_daily` or `performance_metrics` table
   - Links to creatives via `creative_id` column

2. **Potential Issues**:

   a) **Buyer ID Detection**:
      - CSV might not include "Buyer account ID" or "Billing ID" column
      - Seat extractor might not find buyer info

   b) **Creative ID Mismatch**:
      - CSV creative_ids don't match synced creative IDs
      - Creatives might have been synced with different ID format

   c) **Import History**:
      - Some imports might have failed silently
      - Check `/api/uploads/history` for import status

3. **Column Detection** (`csv-parser.ts` lines 14-50):
   - Looks for: `creative_id`, `date`, `impressions`, `clicks`, `spend`, `geography`
   - Also detects: `billing_id`, `buyer_account_id`

**Fix Required**:
- Check import history for all 3 accounts
- Verify CSV files include buyer/billing ID columns
- Cross-reference: `SELECT DISTINCT buyer_id FROM performance_metrics`
- Verify creative_id format matches between CSV and creatives table

---

## Proposed Fix Plan

### Phase 3A: Navigation Fixes (Estimated: 1-2 hours)

1. [ ] Restructure sidebar footer
   - Move Logout to main nav (after Admin section)
   - Move Language selector to header/top-right area
   - Simplify collapse button to just `<` icon
   - Place "Docs" link next to version number

2. [ ] Update language selector component
   - Create compact flag-only variant
   - Position in header above content area

3. [ ] Update docs URL to `docs.rtb.cat`

### Phase 3B: Data Issues Investigation (Estimated: 2-3 hours)

1. [ ] **Diagnose Campaigns Issue**
   - Add API endpoint debugging
   - Check creative_id type consistency
   - Verify campaign-creative joins work

2. [ ] **Fix Missing Account**
   - Query `buyer_seats` table directly
   - Check `is_active` status
   - Verify seat discovery for all service accounts

3. [ ] **Fix Thumbnail Previews**
   - Check ffmpeg availability
   - Run thumbnail batch generation
   - Verify native logo/image URLs sync

4. [ ] **Fix Tracking URL Display**
   - Add `title` attributes for hover reveal
   - Make full URLs accessible
   - Consider copy-to-clipboard for tracking params

5. [ ] **Diagnose CSV Import Issues**
   - Check import history by account
   - Verify buyer_id in imported data
   - Cross-check creative ID formats

### Phase 3C: Code Fixes (Estimated: 3-4 hours)

1. [ ] Implement sidebar restructure
2. [ ] Add URL hover tooltips in preview-modal
3. [ ] Fix campaigns query to handle buyer filtering correctly
4. [ ] Add diagnostic endpoints for data investigation

---

## Files to Modify

| File | Changes |
|------|---------|
| `sidebar.tsx` | Restructure footer, move logout |
| `language-selector.tsx` | Add compact flag-only mode |
| `authenticated-layout.tsx` | Add header language selector |
| `preview-modal.tsx` | Add title attributes, make URLs hoverable |
| `campaigns/page.tsx` | Debug/fix creative ID matching |

---

## Next Steps

1. **Immediate**: Run database queries to diagnose accounts/campaigns/import issues
2. **Day 1**: Implement navigation fixes (Part A)
3. **Day 2**: Implement data fixes (Part B issues 1-5)
4. **Day 3**: Testing and verification

---

*Report generated by Claude Code based on comprehensive codebase analysis.*
