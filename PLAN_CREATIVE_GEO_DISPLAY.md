# Plan: Display Country Targeting Data in Creative Detail Modal

## Problem Statement

Creatives can have localization issues - e.g., a creative showing "AED0" (UAE currency) with a Spanish "instalar" button. Without seeing where the creative is actually serving, these geo/language inconsistencies go unnoticed.

**Goal:** Surface country data in the creative detail modal so users can review geo/language alignment.

---

## Current State Analysis

### Data Already Available

The data we need **already exists** in the database:

| Table | Relevant Columns | Notes |
|-------|------------------|-------|
| `rtb_daily` | `creative_id`, `country`, `spend_micros`, `impressions`, `clicks` | Full daily breakdown by country |
| `performance_metrics` | `creative_id`, `geography`, `spend_micros`, `impressions` | Aggregated metrics |

### Existing Code

| Component | File | What It Does |
|-----------|------|--------------|
| `_get_primary_countries_for_creatives()` | `api/routers/creatives.py:349` | Gets TOP country per creative (by spend) |
| `get_campaign_country_breakdown()` | `storage/campaign_repository.py:360` | Gets country breakdown for campaigns |
| `CountryBreakdownEntry` | `api/campaigns_router.py:29` | Pydantic model: `{creative_ids, spend_micros, impressions}` |

### Current Modal Structure

`dashboard/src/components/preview-modal.tsx` has:
- Header (ID, Google Console link)
- Preview Area (VIDEO/HTML/NATIVE)
- Performance Section (Spend/Imps/Clicks/CTR grid)
- Data Notes Section
- Two-Column Details:
  - Left: Creative Details, Technical IDs
  - Right: Destination URLs, Tracking Parameters

---

## Implementation Plan

### Phase 1: Backend - New API Endpoint

**File:** `api/routers/creatives.py`

#### 1.1 Add Pydantic Response Model

```python
# Add near line 50 with other models

class CreativeCountryMetrics(BaseModel):
    """Country-level metrics for a creative."""
    country_code: str
    country_name: str  # Human-readable name
    spend_micros: int
    impressions: int
    clicks: int
    spend_percent: float  # % of total spend for this creative

class CreativeCountryBreakdownResponse(BaseModel):
    """Response for creative country breakdown."""
    creative_id: str
    countries: list[CreativeCountryMetrics]
    total_countries: int
    period_days: int
```

#### 1.2 Add Helper Function

```python
# Add near line 400

async def _get_country_breakdown_for_creative(
    store: SQLiteStore,
    creative_id: str,
    days: int = 7,
) -> list[dict]:
    """Get country breakdown with spend/impressions for a single creative.

    Returns list of {country_code, spend_micros, impressions, clicks}
    sorted by spend descending.
    """
    result = []
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT
                        country as country_code,
                        SUM(spend_micros) as spend_micros,
                        SUM(impressions) as impressions,
                        SUM(clicks) as clicks
                    FROM rtb_daily
                    WHERE creative_id = ?
                      AND country IS NOT NULL
                      AND country != ''
                      AND metric_date >= date('now', ? || ' days')
                    GROUP BY country
                    ORDER BY spend_micros DESC
                    """,
                    (creative_id, f"-{days}"),
                )
                return [dict(row) for row in cursor.fetchall()]

            result = await loop.run_in_executor(None, _query)
    except Exception as e:
        logger.debug(f"Could not fetch country breakdown: {e}")

    return result
```

#### 1.3 Add New Endpoint

```python
# Add near line 770

@router.get("/creatives/{creative_id}/countries", response_model=CreativeCountryBreakdownResponse)
async def get_creative_countries(
    creative_id: str,
    days: int = Query(7, ge=1, le=90, description="Days to look back"),
    store: SQLiteStore = Depends(get_store),
):
    """Get country breakdown for a specific creative.

    Returns all countries where this creative has served,
    with spend, impressions, and clicks per country.
    Useful for reviewing geo/language alignment.
    """
    # Verify creative exists
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    breakdown = await _get_country_breakdown_for_creative(store, creative_id, days)

    # Calculate total spend for percentage calculation
    total_spend = sum(c.get("spend_micros", 0) for c in breakdown)

    # Map country codes to names
    from utils.country_codes import COUNTRY_NAMES  # Need to create this

    countries = [
        CreativeCountryMetrics(
            country_code=c["country_code"],
            country_name=COUNTRY_NAMES.get(c["country_code"], c["country_code"]),
            spend_micros=c.get("spend_micros", 0),
            impressions=c.get("impressions", 0),
            clicks=c.get("clicks", 0),
            spend_percent=round((c.get("spend_micros", 0) / total_spend * 100) if total_spend > 0 else 0, 1),
        )
        for c in breakdown
    ]

    return CreativeCountryBreakdownResponse(
        creative_id=creative_id,
        countries=countries,
        total_countries=len(countries),
        period_days=days,
    )
```

#### 1.4 Create Country Name Utility

**New File:** `utils/country_codes.py`

```python
"""ISO 3166-1 alpha-2 country code to name mapping."""

COUNTRY_NAMES = {
    "US": "United States",
    "GB": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "ES": "Spain",
    "IT": "Italy",
    "BR": "Brazil",
    "MX": "Mexico",
    "JP": "Japan",
    "KR": "South Korea",
    "AU": "Australia",
    "CA": "Canada",
    "IN": "India",
    "AE": "UAE",
    "SA": "Saudi Arabia",
    # ... add ~200 more countries
    # Alternative: use pycountry package
}

def get_country_name(code: str) -> str:
    """Get country name from ISO alpha-2 code."""
    return COUNTRY_NAMES.get(code.upper(), code)
```

**Alternative:** Use `pycountry` package (add to requirements.txt):
```python
import pycountry
def get_country_name(code: str) -> str:
    try:
        return pycountry.countries.get(alpha_2=code.upper()).name
    except:
        return code
```

---

### Phase 2: Frontend - API Client

**File:** `dashboard/src/lib/api.ts`

#### 2.1 Add Types

```typescript
// Add to types/api.ts

export interface CreativeCountryMetrics {
  country_code: string;
  country_name: string;
  spend_micros: number;
  impressions: number;
  clicks: number;
  spend_percent: number;
}

export interface CreativeCountryBreakdown {
  creative_id: string;
  countries: CreativeCountryMetrics[];
  total_countries: number;
  period_days: number;
}
```

#### 2.2 Add API Function

```typescript
// Add to lib/api.ts

export async function getCreativeCountries(
  creativeId: string,
  days: number = 7
): Promise<CreativeCountryBreakdown> {
  const response = await fetch(
    `${API_BASE}/creatives/${creativeId}/countries?days=${days}`
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch creative countries: ${response.statusText}`);
  }
  return response.json();
}
```

---

### Phase 3: Frontend - Modal Component

**File:** `dashboard/src/components/preview-modal.tsx`

#### 3.1 Add Country Section Component

```tsx
// Add inside the file

interface CountrySectionProps {
  creativeId: string;
}

function CountrySection({ creativeId }: CountrySectionProps) {
  const [data, setData] = useState<CreativeCountryBreakdown | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getCreativeCountries(creativeId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [creativeId]);

  if (loading) {
    return (
      <div className="bg-gray-50 rounded-lg p-3">
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Serving Countries
        </h4>
        <div className="flex items-center gap-2 text-gray-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">Loading...</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-gray-50 rounded-lg p-3">
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Serving Countries
        </h4>
        <p className="text-sm text-gray-400 italic">No country data available</p>
      </div>
    );
  }

  // Show top 5 countries, with "show more" if >5
  const [showAll, setShowAll] = useState(false);
  const displayCountries = showAll ? data.countries : data.countries.slice(0, 5);

  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Serving Countries ({data.total_countries})
      </h4>

      {data.countries.length === 0 ? (
        <p className="text-sm text-gray-400 italic">No serving data yet</p>
      ) : (
        <>
          <div className="space-y-2">
            {displayCountries.map((country) => (
              <div key={country.country_code} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs bg-gray-200 px-1.5 py-0.5 rounded">
                    {country.country_code}
                  </span>
                  <span className="text-gray-700">{country.country_name}</span>
                </div>
                <div className="text-right">
                  <span className="text-gray-900 font-medium">
                    {formatSpend(country.spend_micros)}
                  </span>
                  <span className="text-gray-400 ml-1 text-xs">
                    ({country.spend_percent}%)
                  </span>
                </div>
              </div>
            ))}
          </div>

          {data.countries.length > 5 && (
            <button
              onClick={() => setShowAll(!showAll)}
              className="mt-2 text-xs text-primary-600 hover:text-primary-700"
            >
              {showAll ? "Show less" : `Show ${data.countries.length - 5} more`}
            </button>
          )}
        </>
      )}
    </div>
  );
}
```

#### 3.2 Update Modal Layout

In the `PreviewModal` component, add the CountrySection to the right column:

```tsx
{/* Right Column: Destination URLs + Tracking Params + Countries */}
<div className="space-y-4">
  {/* Destination URLs - existing */}
  <div className="bg-gray-50 rounded-lg p-3">
    {/* ... existing URL code ... */}
  </div>

  {/* NEW: Serving Countries */}
  <CountrySection creativeId={creative.id} />

  {/* Tracking Parameters - existing */}
  <div className="bg-gray-50 rounded-lg p-3">
    {/* ... existing tracking params code ... */}
  </div>
</div>
```

---

## Edge Cases

### 1. Creative with No Report Data

**Scenario:** New creative, not yet in any CSV reports.

**Handling:**
- API returns `countries: []`, `total_countries: 0`
- Frontend shows: "No serving data yet"

### 2. Creative Serving in 50+ Countries

**Scenario:** Global creative with many countries.

**Handling:**
- API returns all countries, sorted by spend
- Frontend shows top 5 by default with "Show X more" button
- Consider pagination for extreme cases (100+ countries)

### 3. Unknown Country Codes

**Scenario:** CSV contains country code not in our mapping.

**Handling:**
- `get_country_name()` returns the raw code if not found
- Display: "XX" → "XX" (shows code twice, acceptable)

### 4. Missing spend_micros in Some Rows

**Scenario:** Some reports may have impressions but no spend data.

**Handling:**
- Query uses `SUM()` which handles NULL as 0
- Countries with 0 spend but >0 impressions still appear

---

## File Changes Summary

| File | Action | Lines Changed |
|------|--------|---------------|
| `api/routers/creatives.py` | Add models + endpoint | ~80 new lines |
| `utils/country_codes.py` | Create new | ~50 lines |
| `dashboard/src/types/api.ts` | Add types | ~15 new lines |
| `dashboard/src/lib/api.ts` | Add function | ~10 new lines |
| `dashboard/src/components/preview-modal.tsx` | Add section | ~80 new lines |

**Total:** ~235 lines of new code

---

## Future: MCP + AI Image Recognition

Once this foundation is in place, the next phase adds:

1. **Image Recognition via MCP**
   - Extract text from creative images (OCR)
   - Identify language, currency symbols, phone formats

2. **Localization Review**
   - Compare identified language vs. serving countries
   - Show notification: "Spanish text identified but serving in Germany (DE)"
   - Show notification: "AED currency but 80% traffic from US"

3. **Dashboard Indicators**
   - Add review badges to creative cards
   - Add "Needs Localization Review" filter
   - Bulk review page for creatives needing attention

---

## Testing Checklist

- [ ] API returns correct country breakdown
- [ ] Empty state displays properly
- [ ] 50+ countries handled gracefully
- [ ] Modal loads countries without rendering delay
- [ ] Country percentages sum to ~100%
- [ ] Unknown country codes display raw code
- [ ] Performance acceptable (query <100ms)
