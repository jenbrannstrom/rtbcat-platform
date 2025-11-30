# ChatGPT Codex CLI Prompt: Phase 8.5 - Seat Hierarchy Cleanup

**Project:** RTB.cat Creative Intelligence Platform  
**Context:** Phase 8.4 complete. Seat/account modeling needs clarification.  
**Goal:** Fix seat dropdown, display names, understand multi-seat hierarchy

---

## 🎯 The Problem

### Bug 1: Dropdown Shows Wrong Count
```
Current UI:
┌─────────────────────────┐
│ All Seats ▼  0 creatives │  ← WRONG! Should show 600+
└─────────────────────────┘
```

### Bug 2: Seat ID Instead of Name
```
Current creative card:
┌─────────────────────────┐
│ Creative 131197         │
│ Seat: 299038253         │  ← Unfriendly! Should be "Tuky Data Research Ltd."
└─────────────────────────┘
```

### Bug 3: Hierarchy Unclear
```
We don't know the real structure:

Option A: Flat
Account = Seat (1:1)

Option B: Nested  
Account
├── Seat A
├── Seat B
└── Seat C

Option C: Complex
Buyer Account
├── Billing Account 1
│   └── Seat A
└── Billing Account 2
    └── Seats B, C
```

---

## 🎯 Your Mission

1. **Investigate** the actual hierarchy using a multi-seat account
2. **Fix** the dropdown to show correct creative counts
3. **Display** seat names instead of IDs
4. **Model** the correct Account → Seat → Creative relationship

---

## 📋 Part 1: Investigation

### Step 1: Examine Current Data

```bash
# Check what's in the seats table
sqlite3 ~/.rtbcat/rtbcat.db "SELECT * FROM seats;"

# Check what's in creatives
sqlite3 ~/.rtbcat/rtbcat.db "SELECT seat_id, COUNT(*) FROM creatives GROUP BY seat_id;"

# Check if creatives have seat_id set
sqlite3 ~/.rtbcat/rtbcat.db "SELECT COUNT(*) FROM creatives WHERE seat_id IS NULL;"
```

### Step 2: Examine CSV Headers

From the sample CSV, these columns identify the account/seat:

```
Column               | Example Value              | What It Means
---------------------|----------------------------|------------------
Billing ID           | 157331516553               | Payment entity ID
Buyer account name   | Tuky Data Research Ltd.    | Display name
Buyer account ID     | 299038253                  | Account ID
```

**Question:** In a multi-seat account, which of these differs per seat?

### Step 3: Test with Multi-Seat Account

When Jen connects a 3-seat account, compare CSVs:

```python
# Pseudo-code for investigation
def compare_seat_csvs(csv1, csv2, csv3):
    """
    Compare three CSVs from different seats.
    Find which columns differ.
    """
    for csv in [csv1, csv2, csv3]:
        row = csv[0]  # First data row
        print(f"Billing ID: {row['Billing ID']}")
        print(f"Buyer account name: {row['Buyer account name']}")
        print(f"Buyer account ID: {row['Buyer account ID']}")
        print("---")
    
    # Expected output might be:
    # Billing ID: 157331516553  ← Same across all (or different?)
    # Buyer account name: Tuky Data Research Ltd. ← Same
    # Buyer account ID: 299038253 ← Same
    # 
    # OR:
    # Billing ID: 157331516553 / 157331516554 / 157331516555 ← Different per seat!
```

---

## 📋 Part 2: Likely Data Model

Based on Google Authorized Buyers documentation, the probable hierarchy is:

```
Buyer Account (top level - the company)
│
├── Buyer Account ID: 299038253
├── Buyer Account Name: "Tuky Data Research Ltd."
│
└── Seats (bidding entities within the account)
    ├── Seat 1: Billing ID 157331516553, Name "Seat Alpha"
    ├── Seat 2: Billing ID 157331516554, Name "Seat Beta"
    └── Seat 3: Billing ID 157331516555, Name "Seat Gamma"
        │
        └── Creatives (belong to a seat)
            ├── Creative 131197
            ├── Creative 131198
            └── ...
```

**Key insight:** `Billing ID` is likely the seat identifier, not `Buyer Account ID`.

---

## 📋 Part 3: Schema Update

### Current Schema (Incomplete)

```sql
CREATE TABLE seats (
    id INTEGER PRIMARY KEY,
    billing_id TEXT UNIQUE,      -- This might be the seat ID
    account_name TEXT,           -- Buyer account name
    account_id TEXT,             -- Buyer account ID
    created_at TIMESTAMP
);
```

### Proposed Schema (Clarified)

```sql
-- Buyer Accounts (the company/organization)
CREATE TABLE IF NOT EXISTS buyer_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT UNIQUE NOT NULL,    -- e.g., "299038253"
    account_name TEXT,                   -- e.g., "Tuky Data Research Ltd."
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seats (bidding entities within an account)
CREATE TABLE IF NOT EXISTS seats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_account_id INTEGER REFERENCES buyer_accounts(id),
    
    billing_id TEXT UNIQUE NOT NULL,    -- e.g., "157331516553" - THE seat identifier
    seat_name TEXT,                      -- Display name (may need to fetch from API)
    
    -- Metadata
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_seats_account ON seats(buyer_account_id);

-- Creatives belong to a SEAT (not directly to account)
-- Already exists, just ensure seat_id is properly linked
ALTER TABLE creatives ADD COLUMN seat_id INTEGER REFERENCES seats(id);
```

### Migration Script

```python
# api/storage/migrations/011_seat_hierarchy.py

def upgrade(db):
    """
    Restructure seats to support multi-seat accounts.
    """
    
    # Step 1: Create buyer_accounts table
    db.execute("""
        CREATE TABLE IF NOT EXISTS buyer_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT UNIQUE NOT NULL,
            account_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Step 2: Migrate existing seats data
    # Extract unique buyer accounts from current seats
    db.execute("""
        INSERT OR IGNORE INTO buyer_accounts (account_id, account_name)
        SELECT DISTINCT account_id, account_name 
        FROM seats 
        WHERE account_id IS NOT NULL
    """)
    
    # Step 3: Add buyer_account_id to seats
    db.execute("""
        ALTER TABLE seats ADD COLUMN buyer_account_id INTEGER REFERENCES buyer_accounts(id)
    """)
    
    # Step 4: Link seats to buyer_accounts
    db.execute("""
        UPDATE seats 
        SET buyer_account_id = (
            SELECT id FROM buyer_accounts 
            WHERE buyer_accounts.account_id = seats.account_id
        )
    """)
    
    # Step 5: Add seat_name column (for display)
    db.execute("""
        ALTER TABLE seats ADD COLUMN seat_name TEXT
    """)
    
    # Step 6: Default seat_name to billing_id until we get real names
    db.execute("""
        UPDATE seats SET seat_name = 'Seat ' || billing_id WHERE seat_name IS NULL
    """)
    
    db.commit()
    print("Migration 011: Seat hierarchy restructured")
```

---

## 📋 Part 4: Fix the Dropdown Query

### Current (Broken) Query

```typescript
// Probably something like this that's returning 0:
const seats = await db.query(`
  SELECT s.*, COUNT(c.id) as creative_count
  FROM seats s
  LEFT JOIN creatives c ON c.seat_id = s.id  -- This join might be failing
  GROUP BY s.id
`);
```

### The Problem

Creatives might not have `seat_id` populated, OR the join logic is wrong.

### Fix Option 1: Creatives Have seat_id

```typescript
// dashboard/src/lib/api/seats.ts

export async function getSeatsWithCounts(): Promise<Seat[]> {
  const response = await fetch('/api/seats?include_counts=true');
  return response.json();
}
```

```python
# api/seats.py

@router.get("/api/seats")
async def list_seats(include_counts: bool = False):
    """
    List all seats, optionally with creative counts.
    """
    if include_counts:
        seats = db.execute("""
            SELECT 
                s.id,
                s.billing_id,
                s.seat_name,
                s.buyer_account_id,
                ba.account_name as buyer_account_name,
                COUNT(c.id) as creative_count
            FROM seats s
            LEFT JOIN buyer_accounts ba ON ba.id = s.buyer_account_id
            LEFT JOIN creatives c ON c.seat_id = s.id
            GROUP BY s.id
            ORDER BY creative_count DESC
        """).fetchall()
    else:
        seats = db.execute("SELECT * FROM seats").fetchall()
    
    return {"seats": [dict(s) for s in seats]}
```

### Fix Option 2: Creatives Don't Have seat_id Yet

If `seat_id` was never populated on creatives, we need to backfill:

```python
# api/storage/seat_repository.py

def backfill_creative_seats(db):
    """
    Assign seat_id to creatives that don't have one.
    Uses the most recent import's seat info.
    """
    # If there's only one seat, assign all creatives to it
    seat_count = db.execute("SELECT COUNT(*) FROM seats").fetchone()[0]
    
    if seat_count == 1:
        seat_id = db.execute("SELECT id FROM seats LIMIT 1").fetchone()[0]
        db.execute("""
            UPDATE creatives SET seat_id = ? WHERE seat_id IS NULL
        """, (seat_id,))
        db.commit()
        return
    
    # If multiple seats, need to match by some other field
    # This depends on how creatives were originally imported
    # Might need manual assignment or re-import
    raise ValueError("Multiple seats exist but creatives have no seat_id. Manual assignment needed.")
```

---

## 📋 Part 5: Display Seat Names

### Where to Get Seat Names

**Option A: From CSV import**
```
The CSV has "Buyer account name" but NOT individual seat names.
If all seats have the same buyer account name, we need another source.
```

**Option B: From Google API**
```python
# If RTB.cat has API access to Google Authorized Buyers:
# https://developers.google.com/authorized-buyers/apis/reference/rest/v1/bidders.seats

def fetch_seat_names_from_google(buyer_account_id: str):
    """
    Fetch seat details from Google Authorized Buyers API.
    """
    # This requires OAuth credentials for the buyer account
    service = build('authorizedbuyersmarketplace', 'v1', credentials=credentials)
    
    response = service.bidders().seats().list(
        parent=f'bidders/{buyer_account_id}'
    ).execute()
    
    return response.get('seats', [])
```

**Option C: User-defined names**
```
Let users name their seats in the UI:
"Seat 157331516553" → "Brand Campaigns"
```

### UI for Seat Management

```tsx
// dashboard/src/app/settings/seats/page.tsx

export default function SeatsSettingsPage() {
  const [seats, setSeats] = useState([]);
  
  const handleRename = async (seatId: number, newName: string) => {
    await fetch(`/api/seats/${seatId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seat_name: newName }),
    });
    fetchSeats();
  };
  
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Seat Management</h1>
      
      <div className="bg-white rounded-lg border">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left">Billing ID</th>
              <th className="px-4 py-3 text-left">Display Name</th>
              <th className="px-4 py-3 text-left">Creatives</th>
              <th className="px-4 py-3 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {seats.map((seat) => (
              <tr key={seat.id} className="border-t">
                <td className="px-4 py-3 font-mono text-sm">
                  {seat.billing_id}
                </td>
                <td className="px-4 py-3">
                  <EditableText
                    value={seat.seat_name}
                    onSave={(name) => handleRename(seat.id, name)}
                  />
                </td>
                <td className="px-4 py-3">
                  {seat.creative_count}
                </td>
                <td className="px-4 py-3">
                  <Link href={`/creatives?seat=${seat.id}`}>
                    View Creatives →
                  </Link>
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

## 📋 Part 6: Fix Creative Cards

### Current Card (Shows ID)

```tsx
<div className="text-sm text-gray-500">
  Seat: {creative.seat_id}  {/* Shows: 299038253 */}
</div>
```

### Fixed Card (Shows Name)

```tsx
// dashboard/src/components/CreativeCard.tsx

interface CreativeCardProps {
  creative: {
    id: number;
    // ... other fields
    seat: {
      id: number;
      billing_id: string;
      seat_name: string;
    };
  };
}

export function CreativeCard({ creative }: CreativeCardProps) {
  return (
    <div className="...">
      {/* ... other content ... */}
      
      <div className="text-sm text-gray-500">
        {creative.seat?.seat_name || `Seat ${creative.seat?.billing_id}`}
      </div>
    </div>
  );
}
```

### API: Include Seat Details with Creatives

```python
# api/creatives.py

@router.get("/api/creatives")
async def list_creatives(
    seat_id: int = None,
    include_seat_details: bool = True
):
    """
    List creatives with optional seat details.
    """
    query = """
        SELECT 
            c.*,
            s.billing_id as seat_billing_id,
            s.seat_name as seat_name
        FROM creatives c
        LEFT JOIN seats s ON s.id = c.seat_id
    """
    
    if seat_id:
        query += " WHERE c.seat_id = ?"
        creatives = db.execute(query, (seat_id,)).fetchall()
    else:
        creatives = db.execute(query).fetchall()
    
    # Reshape for frontend
    result = []
    for c in creatives:
        creative = dict(c)
        creative['seat'] = {
            'id': c['seat_id'],
            'billing_id': c['seat_billing_id'],
            'seat_name': c['seat_name'],
        }
        result.append(creative)
    
    return {"creatives": result}
```

---

## 📋 Part 7: Fix "All Seats" Dropdown

### Current Component (Broken)

```tsx
// Probably not fetching counts correctly
<select>
  <option>All Seats - 0 creatives</option>
</select>
```

### Fixed Component

```tsx
// dashboard/src/components/SeatSelector.tsx

'use client';

import { useState, useEffect } from 'react';

interface Seat {
  id: number;
  billing_id: string;
  seat_name: string;
  creative_count: number;
}

interface SeatSelectorProps {
  value: number | null;  // null = "All Seats"
  onChange: (seatId: number | null) => void;
}

export function SeatSelector({ value, onChange }: SeatSelectorProps) {
  const [seats, setSeats] = useState<Seat[]>([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchSeats();
  }, []);
  
  const fetchSeats = async () => {
    try {
      const res = await fetch('/api/seats?include_counts=true');
      const data = await res.json();
      setSeats(data.seats);
    } catch (error) {
      console.error('Failed to fetch seats:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const totalCreatives = seats.reduce((sum, s) => sum + s.creative_count, 0);
  
  if (loading) {
    return (
      <select disabled className="border rounded px-3 py-2 bg-gray-100">
        <option>Loading seats...</option>
      </select>
    );
  }
  
  return (
    <select
      value={value ?? 'all'}
      onChange={(e) => {
        const val = e.target.value;
        onChange(val === 'all' ? null : parseInt(val));
      }}
      className="border rounded px-3 py-2"
    >
      <option value="all">
        All Seats - {totalCreatives.toLocaleString()} creatives
      </option>
      
      {seats.map((seat) => (
        <option key={seat.id} value={seat.id}>
          {seat.seat_name} - {seat.creative_count.toLocaleString()} creatives
        </option>
      ))}
    </select>
  );
}
```

---

## 📋 Part 8: Files to Create/Modify

**New files:**
```
api/storage/migrations/011_seat_hierarchy.py    # Schema update
dashboard/src/app/settings/seats/page.tsx       # Seat management UI
dashboard/src/components/SeatSelector.tsx       # Fixed dropdown
dashboard/src/components/EditableText.tsx       # Inline rename component
```

**Modified files:**
```
api/seats.py                                    # Add counts, rename endpoint
api/creatives.py                                # Include seat details
dashboard/src/components/CreativeCard.tsx       # Show seat name
dashboard/src/app/creatives/page.tsx            # Use fixed SeatSelector
```

---

## 📋 Part 9: Testing Checklist

### With Single-Seat Account
- [ ] Dropdown shows "All Seats - 652 creatives" (not 0)
- [ ] Seat name displays instead of ID
- [ ] Seat settings page shows the seat
- [ ] Seat can be renamed

### With Multi-Seat Account (When Connected)
- [ ] Each seat appears in dropdown with correct count
- [ ] Filtering by seat works
- [ ] Creatives show correct seat assignment
- [ ] Import assigns new creatives to correct seat
- [ ] Hierarchy: Account → Seats → Creatives is clear

---

## 📋 Part 10: Investigation Questions for Multi-Seat Test

When Jen connects the 3-seat account, answer these:

1. **In the CSV, which field differs between seats?**
   - Billing ID?
   - Buyer Account ID?
   - Something else?

2. **Do seats have names in Google's system?**
   - Or just IDs?

3. **Can one creative belong to multiple seats?**
   - Or strictly 1:1?

4. **Is "Buyer Account" the parent of all seats?**
   - Or is there another layer?

Document findings in: `docs/SEAT_HIERARCHY_NOTES.md`

---

## 🚀 Expected Outcome

**Before:**
```
┌─────────────────────────┐
│ All Seats ▼  0 creatives │  ← Broken
└─────────────────────────┘

Creative Card:
  Seat: 299038253  ← Unfriendly
```

**After:**
```
┌──────────────────────────────────────┐
│ All Seats ▼  652 creatives           │  ← Correct!
│ ─────────────────────────────────────│
│ Brand Campaigns - 400 creatives      │
│ Performance - 200 creatives          │
│ Testing - 52 creatives               │
└──────────────────────────────────────┘

Creative Card:
  Seat: Brand Campaigns  ← Friendly!
```

---

## 📍 Location Reference

```
Project root: /home/jen/Documents/rtbcat-platform/
Database: ~/.rtbcat/rtbcat.db
```

**After code changes:**
```bash
sudo systemctl restart rtbcat-api
```

**Test the fix:**
```bash
# Check seat counts
curl "http://localhost:8000/api/seats?include_counts=true"

# Should return:
# {"seats": [{"id": 1, "seat_name": "...", "creative_count": 652}]}
```
