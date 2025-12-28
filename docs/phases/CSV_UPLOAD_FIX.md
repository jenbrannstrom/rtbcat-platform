# URGENT FIX: Phase 8.3 CSV Upload Issues

**Problem:** Google CSV doesn't match expected format  
**Status:** Frontend validation is too strict, needs flexibility

---

## 🚨 Issues Found in Google CSV

### 1. Column Name Issues
```csv
# Google's columns:
#Creative ID,Day,Buyer account ID,Country,Hour,...

# Expected by RTB.cat:
creative_id,date,impressions,clicks,spend,geography
```

**Problems:**
- ❌ `#Creative ID` has `#` prefix and space
- ❌ `Day` should be `date`
- ❌ `Country` should be `geography`
- ❌ `Spend (buyer currency)` has spaces and parens

### 2. Date Format
```
Google:   11/29/25 (MM/DD/YY)
Expected: 2025-11-29 (YYYY-MM-DD)
```

### 3. Spend Format
```
Google:   $0.10
Expected: 0.10
```

### 4. Hourly Data
Google report includes "Hour" dimension, creating 24 rows per creative per day.
Need to aggregate by day.

---

## ✅ Quick Fixes

### Fix 1: Update CSV Validator (RECOMMENDED)

Make the validator more flexible to accept Google's format.

**File:** `dashboard/lib/csv-validator.ts`

```typescript
export function normalizeCSVData(data: any[]): PerformanceRow[] {
  return data.map(row => {
    // Normalize column names (remove spaces, special chars, lowercase)
    const normalized: any = {};
    
    Object.keys(row).forEach(key => {
      const normalizedKey = key
        .replace(/^#/, '') // Remove # prefix
        .replace(/\s+/g, '_') // Spaces to underscores
        .replace(/[()]/g, '') // Remove parentheses
        .toLowerCase();
      
      normalized[normalizedKey] = row[key];
    });
    
    // Map Google columns to our format
    const creative_id = parseInt(
      normalized.creative_id || normalized.creativeid || ''
    );
    
    // Parse date (handle MM/DD/YY format)
    let date = normalized.date || normalized.day || '';
    if (date.includes('/')) {
      // Convert MM/DD/YY to YYYY-MM-DD
      const [month, day, year] = date.split('/');
      const fullYear = year.length === 2 ? `20${year}` : year;
      date = `${fullYear}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
    }
    
    // Parse spend (remove $ sign and commas)
    const spend = parseFloat(
      (normalized.spend || normalized.spend_buyer_currency || '0')
        .toString()
        .replace(/[$,]/g, '')
    );
    
    // Parse impressions and clicks
    const impressions = parseInt(normalized.impressions || '0');
    const clicks = parseInt(normalized.clicks || '0');
    
    // Geography (country)
    const geography = normalized.geography || normalized.country || undefined;
    
    return {
      creative_id,
      date,
      impressions,
      clicks,
      spend,
      geography
    };
  });
}
```

### Fix 2: Aggregate Hourly Data

If Google report has hourly breakdowns, aggregate to daily.

```typescript
export function aggregateByDay(data: PerformanceRow[]): PerformanceRow[] {
  const aggregated = new Map<string, PerformanceRow>();
  
  data.forEach(row => {
    // Create key: creative_id + date + geography
    const key = `${row.creative_id}|${row.date}|${row.geography || 'NONE'}`;
    
    if (aggregated.has(key)) {
      // Add to existing
      const existing = aggregated.get(key)!;
      existing.impressions += row.impressions;
      existing.clicks += row.clicks;
      existing.spend += row.spend;
    } else {
      // Create new
      aggregated.set(key, { ...row });
    }
  });
  
  return Array.from(aggregated.values());
}
```

### Fix 3: Better Error Messages

Update validation errors to be more helpful:

```typescript
// ❌ BAD ERROR
"Missing required column: date"

// ✅ GOOD ERROR
"Missing date column. Found columns: Day, Creative ID, Country
Tip: Your CSV has 'Day' - we'll use that as the date column."
```

---

## 🎯 Updated Import Flow

**New flow:**

1. **Upload CSV** (any format)
2. **Detect columns:**
   - Look for variations: "creative id", "creativeid", "#creative id"
   - Look for date: "day", "date", "Date"
   - Look for geography: "country", "Country", "geography"
3. **Normalize data:**
   - Remove `#`, spaces, special chars
   - Parse dates from various formats
   - Remove currency symbols
   - Aggregate hourly to daily
4. **Validate normalized data**
5. **Preview** (show what will be imported)
6. **Import**

---

## 📋 Tell Claude CLI to Fix

```
URGENT: Update Phase 8.3 CSV import to handle Google's format

The CSV validator is too strict. Update to:

1. Accept flexible column names:
   - "#Creative ID" or "Creative ID" or "creative_id" → creative_id
   - "Day" or "Date" or "date" → date  
   - "Country" or "geography" → geography
   - "Spend (buyer currency)" or "Spend" → spend

2. Parse dates from MM/DD/YY format:
   - Convert "11/29/25" to "2025-11-29"

3. Clean spend values:
   - Remove $ signs and commas
   - "$0.10" → 0.10

4. Aggregate hourly data to daily:
   - If CSV has "Hour" column, sum by creative_id + date + geography

5. Show better error messages:
   - Tell user what columns were found
   - Suggest which column to use for missing fields

6. Update example CSV on /import page to match Google's format

See /mnt/user-data/outputs/CSV_UPLOAD_FIX.md for implementation details.
```

---

## 📖 Updated Example CSV

**Change the example on `/import` page to match Google's actual format:**

```csv
#Creative ID,Day,Buyer account ID,Country,Hour,Buyer account name,Impressions,Clicks,Spend (buyer currency),Bids,Bids in auction,Auctions won,Reached queries
100518,11/29/25,299038253,India,0,Tuky Data Research Ltd.,192,1,$0.10,766,766,743,743
100518,11/29/25,299038253,India,1,Tuky Data Research Ltd.,77,1,$0.04,333,333,331,331
```

**Or provide both formats:**

**Option 1: Simple format (manual export)**
```csv
creative_id,date,impressions,clicks,spend,geography
79783,2025-11-29,1000,50,25.50,US
```

**Option 2: Google Authorized Buyers export (automatic)**
```csv
#Creative ID,Day,Country,Impressions,Clicks,Spend (buyer currency)
100518,11/29/25,India,192,1,$0.10
```

---

## 🔧 Validation Rules - Relaxed

**New approach:**

1. **Column detection:** Smart matching (fuzzy)
2. **Date parsing:** Multiple formats supported
3. **Number parsing:** Handle currency symbols
4. **Aggregation:** Auto-detect hourly and aggregate
5. **Missing optional fields:** OK (geography can be missing)

**Only fail on:**
- Can't find any column matching creative_id
- Can't find any column matching impressions/clicks/spend
- Can't parse date format
- Invalid data types (text in number fields)

---

## ✅ User-Friendly Flow

**Current (BAD):**
```
Upload → ❌ Validation Error: Missing required column: date
(User is stuck, doesn't know what to do)
```

**New (GOOD):**
```
Upload → ⚠️ Auto-detected columns:
- "Day" → will use as date
- "#Creative ID" → will use as creative_id
- "Country" → will use as geography
- "Spend (buyer currency)" → will use as spend

✅ Preview (first 10 rows after transformation):
creative_id | date       | impressions | clicks | spend  | geography
100518      | 2025-11-29 | 269        | 2      | 0.14   | India

[Cancel] [Import 24 rows] ✓
```

---

## 🎯 Priority Actions

1. **Immediate:** Update CSV validator to handle Google's format
2. **Quick win:** Better error messages
3. **Nice to have:** Auto-detect and suggest column mappings

---

**Bottom line:** The validator should be smart enough to handle Google's CSV without requiring manual transformation! 🎯
