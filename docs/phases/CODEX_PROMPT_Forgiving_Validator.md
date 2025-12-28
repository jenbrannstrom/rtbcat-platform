# ChatGPT Codex CLI Prompt: Forgiving CSV Validator

**Project:** RTB.cat Creative Intelligence Platform  
**Context:** CSV import fails on "clicks > impressions" - but this is real fraud data we WANT to capture  
**Goal:** Make validator forgiving, import all data, flag anomalies for analysis

---

## 🎯 The Problem

Current validator rejects this row:
```
Row 531: Clicks cannot exceed impressions (got: "1 clicks > 0 impressions")
```

**But this is VALUABLE data!** It indicates:
- 🚨 **Ad fraud** - App sold fake clicks without showing the ad
- 🚨 **Click injection** - Malware clicking without impressions
- 🚨 **Tracking discrepancy** - Different systems, timing issues

**We WANT to import this data to find the scammy apps!**

---

## 🎯 Your Mission

1. **Remove blocking validations** - Import all data, never reject rows
2. **Add anomaly flags** - Mark suspicious patterns for later analysis
3. **Capture fraud signals** - Clicks > impressions is a FEATURE, not a bug
4. **Show warnings, not errors** - User should know about anomalies but not be blocked

---

## 📋 Part 1: Current Validation (Too Strict)

```typescript
// dashboard/src/lib/csv-validator.ts (CURRENT - BROKEN)

export function validateRow(row: ParsedRow, index: number): ValidationResult {
  const errors: string[] = [];
  
  // This BLOCKS the import - BAD!
  if (row.clicks > row.impressions) {
    errors.push(`Row ${index}: Clicks cannot exceed impressions`);
  }
  
  // ... other validations that might block
  
  return {
    valid: errors.length === 0,  // If any errors, reject entire file!
    errors,
  };
}
```

---

## 📋 Part 2: New Philosophy - Never Block, Always Flag

```typescript
// dashboard/src/lib/csv-validator.ts (NEW - FORGIVING)

export interface ValidationResult {
  valid: true;  // ALWAYS true - we never block imports
  warnings: Warning[];
  anomalies: Anomaly[];
  stats: ImportStats;
}

export interface Warning {
  row: number;
  field: string;
  message: string;
  severity: 'info' | 'warning';
}

export interface Anomaly {
  row: number;
  type: AnomalyType;
  details: Record<string, any>;
}

export type AnomalyType = 
  | 'clicks_exceed_impressions'    // Fraud signal!
  | 'zero_impressions_with_spend'  // Paid for nothing?
  | 'extremely_high_ctr'           // CTR > 10% is suspicious
  | 'negative_values'              // Data corruption
  | 'future_date'                  // Date in the future
  | 'very_old_date';               // Date > 1 year ago

export function validateRow(row: ParsedRow, index: number): RowValidation {
  const warnings: Warning[] = [];
  const anomalies: Anomaly[] = [];
  
  // ============================================
  // FRAUD SIGNALS - Flag but NEVER block
  // ============================================
  
  if (row.clicks > row.impressions) {
    anomalies.push({
      row: index,
      type: 'clicks_exceed_impressions',
      details: {
        clicks: row.clicks,
        impressions: row.impressions,
        app_name: row.app_name,
        app_id: row.app_id,
        creative_id: row.creative_id,
      }
    });
    
    // This is a fraud signal - we WANT this data
    warnings.push({
      row: index,
      field: 'clicks',
      message: `Clicks (${row.clicks}) > Impressions (${row.impressions}) - possible click fraud`,
      severity: 'warning',
    });
  }
  
  // Extremely high CTR is suspicious
  if (row.impressions > 0 && row.clicks / row.impressions > 0.10) {
    anomalies.push({
      row: index,
      type: 'extremely_high_ctr',
      details: {
        ctr: row.clicks / row.impressions,
        clicks: row.clicks,
        impressions: row.impressions,
        app_name: row.app_name,
      }
    });
  }
  
  // Spent money but got zero impressions?
  if (row.spend > 0 && row.impressions === 0) {
    anomalies.push({
      row: index,
      type: 'zero_impressions_with_spend',
      details: {
        spend: row.spend,
        app_name: row.app_name,
      }
    });
  }
  
  // ============================================
  // DATA QUALITY - Fix automatically
  // ============================================
  
  // Negative values - set to 0
  if (row.impressions < 0) {
    warnings.push({
      row: index,
      field: 'impressions',
      message: `Negative impressions (${row.impressions}) set to 0`,
      severity: 'info',
    });
    row.impressions = 0;
  }
  
  if (row.clicks < 0) {
    row.clicks = 0;
  }
  
  if (row.spend < 0) {
    row.spend = 0;
  }
  
  // ============================================
  // ALWAYS VALID - Never block import
  // ============================================
  
  return {
    valid: true,  // ALWAYS true
    row: row,     // Possibly cleaned/fixed
    warnings,
    anomalies,
  };
}
```

---

## 📋 Part 3: Store Anomalies for Analysis

Add anomalies to the database for later fraud detection:

```sql
-- Add to schema
CREATE TABLE IF NOT EXISTS import_anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id TEXT,                         -- Which import batch
    row_number INTEGER,
    anomaly_type TEXT NOT NULL,             -- 'clicks_exceed_impressions', etc.
    creative_id TEXT,
    app_id TEXT,
    app_name TEXT,
    details TEXT,                           -- JSON blob
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_anomalies_type ON import_anomalies(anomaly_type);
CREATE INDEX idx_anomalies_app ON import_anomalies(app_id);
```

```python
# api/storage/anomaly_repository.py

class AnomalyRepository:
    def store_anomalies(self, import_id: str, anomalies: list[dict]):
        """Store anomalies from import for later analysis."""
        for a in anomalies:
            self.db.execute("""
                INSERT INTO import_anomalies 
                (import_id, row_number, anomaly_type, creative_id, app_id, app_name, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                import_id,
                a['row'],
                a['type'],
                a['details'].get('creative_id'),
                a['details'].get('app_id'),
                a['details'].get('app_name'),
                json.dumps(a['details']),
            ))
        self.db.commit()
    
    def get_fraud_apps(self) -> list[dict]:
        """Get apps with most fraud signals."""
        return self.db.execute("""
            SELECT 
                app_id,
                app_name,
                COUNT(*) as anomaly_count,
                COUNT(DISTINCT anomaly_type) as anomaly_types
            FROM import_anomalies
            WHERE anomaly_type IN ('clicks_exceed_impressions', 'extremely_high_ctr')
            GROUP BY app_id
            ORDER BY anomaly_count DESC
            LIMIT 50
        """).fetchall()
```

---

## 📋 Part 4: Updated Import UI

Show warnings but allow continue:

```tsx
// dashboard/src/app/import/page.tsx

function ImportPreview({ validation }: { validation: ValidationResult }) {
  const hasWarnings = validation.warnings.length > 0;
  const hasAnomalies = validation.anomalies.length > 0;
  
  return (
    <div>
      {/* Stats */}
      <div className="bg-green-50 border border-green-200 rounded p-4 mb-4">
        <p className="text-green-800">
          ✅ Ready to import {validation.stats.totalRows.toLocaleString()} rows
        </p>
      </div>
      
      {/* Anomalies - Interesting, not blocking */}
      {hasAnomalies && (
        <div className="bg-yellow-50 border border-yellow-200 rounded p-4 mb-4">
          <h3 className="font-semibold text-yellow-800 mb-2">
            🔍 {validation.anomalies.length} Anomalies Detected
          </h3>
          <p className="text-sm text-yellow-700 mb-2">
            These patterns may indicate fraud or tracking issues. 
            Data will be imported and flagged for analysis.
          </p>
          
          {/* Group by type */}
          <div className="text-sm">
            {Object.entries(groupBy(validation.anomalies, 'type')).map(([type, items]) => (
              <div key={type} className="flex justify-between py-1">
                <span>{formatAnomalyType(type)}</span>
                <span className="font-medium">{items.length} rows</span>
              </div>
            ))}
          </div>
          
          {/* Expand to see details */}
          <details className="mt-2">
            <summary className="text-sm text-yellow-600 cursor-pointer">
              View affected apps
            </summary>
            <ul className="mt-2 text-xs">
              {getTopAnomalyApps(validation.anomalies).map(app => (
                <li key={app.app_id}>
                  {app.app_name} - {app.count} anomalies
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}
      
      {/* Warnings - Informational */}
      {hasWarnings && (
        <details className="mb-4">
          <summary className="text-sm text-gray-500 cursor-pointer">
            {validation.warnings.length} warnings (click to expand)
          </summary>
          <ul className="mt-2 text-xs text-gray-600 max-h-40 overflow-y-auto">
            {validation.warnings.slice(0, 50).map((w, i) => (
              <li key={i}>Row {w.row}: {w.message}</li>
            ))}
            {validation.warnings.length > 50 && (
              <li>... and {validation.warnings.length - 50} more</li>
            )}
          </ul>
        </details>
      )}
      
      {/* Always show import button - never blocked! */}
      <button
        onClick={handleImport}
        className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700"
      >
        Import {validation.stats.totalRows.toLocaleString()} rows
        {hasAnomalies && ` (${validation.anomalies.length} flagged)`}
      </button>
    </div>
  );
}

function formatAnomalyType(type: string): string {
  const labels: Record<string, string> = {
    'clicks_exceed_impressions': '🚨 Clicks > Impressions (click fraud)',
    'extremely_high_ctr': '⚠️ CTR > 10% (suspicious)',
    'zero_impressions_with_spend': '💸 Spend with no impressions',
  };
  return labels[type] || type;
}
```

---

## 📋 Part 5: Fraud Dashboard (Future Feature)

Once anomalies are collected, show a fraud detection page:

```tsx
// dashboard/src/app/fraud/page.tsx (Future)

export default function FraudDashboardPage() {
  const [fraudApps, setFraudApps] = useState([]);
  
  useEffect(() => {
    fetch('/api/fraud/suspicious-apps').then(r => r.json()).then(setFraudApps);
  }, []);
  
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">🚨 Fraud Detection</h1>
      
      <div className="bg-white rounded-lg border">
        <table className="w-full">
          <thead className="bg-red-50">
            <tr>
              <th className="px-4 py-3 text-left">App</th>
              <th className="px-4 py-3 text-left">Anomaly Count</th>
              <th className="px-4 py-3 text-left">Types</th>
              <th className="px-4 py-3 text-left">Action</th>
            </tr>
          </thead>
          <tbody>
            {fraudApps.map(app => (
              <tr key={app.app_id} className="border-t">
                <td className="px-4 py-3">
                  <div className="font-medium">{app.app_name}</div>
                  <div className="text-xs text-gray-500">{app.app_id}</div>
                </td>
                <td className="px-4 py-3 font-medium text-red-600">
                  {app.anomaly_count}
                </td>
                <td className="px-4 py-3">
                  {app.anomaly_types} types
                </td>
                <td className="px-4 py-3">
                  <button className="text-red-600 text-sm">
                    Block App
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

---

## 📋 Part 6: Files to Modify

```
dashboard/src/lib/csv-validator.ts       # Remove blocking, add anomaly detection
dashboard/src/app/import/page.tsx        # Show anomalies as warnings, not errors
api/storage/sqlite_store.py              # Add import_anomalies table
api/storage/anomaly_repository.py        # Store and query anomalies
api/performance.py                       # Store anomalies during import
```

---

## 📋 Part 7: Validation Rules Summary

| Condition | Old Behavior | New Behavior |
|-----------|--------------|--------------|
| Clicks > Impressions | ❌ BLOCK | ✅ Import + Flag as fraud |
| CTR > 10% | (no check) | ✅ Import + Flag as suspicious |
| Spend with 0 impressions | (no check) | ✅ Import + Flag |
| Negative values | ❌ BLOCK | ✅ Fix to 0 + Warning |
| Missing required field | ❌ BLOCK | ✅ Use default + Warning |
| Invalid date | ❌ BLOCK | ✅ Skip row + Warning |

**Philosophy:** The only thing that should block import is a completely unparseable file.

---

## 📋 Part 8: Testing

After fixes:

```bash
# 1. Import the CSV that was failing
# (Use UI at /import)

# 2. Should succeed with warnings

# 3. Check anomalies were stored
sqlite3 ~/.rtbcat/rtbcat.db "SELECT anomaly_type, COUNT(*) FROM import_anomalies GROUP BY anomaly_type;"

# 4. Check performance data was imported
sqlite3 ~/.rtbcat/rtbcat.db "SELECT COUNT(*) FROM performance_metrics;"
```

---

## 🚀 Summary

**Before:** "Clicks > Impressions? REJECTED! 🚫"

**After:** "Clicks > Impressions? Imported + flagged as fraud signal 🔍"

The scammy apps that sell fake clicks are now **tracked** instead of hidden. This turns a bug into a feature - you can now build a fraud detection dashboard!

---

**Location:**
```
Project: /home/jen/Documents/rtbcat-platform/
Database: ~/.rtbcat/rtbcat.db
```

**After code changes:**
```bash
sudo systemctl restart rtbcat-api
```
