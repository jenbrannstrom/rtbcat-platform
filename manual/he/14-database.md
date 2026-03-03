# פרק 14: פעולות מסד נתונים

*קהל יעד: DevOps, מהנדסי פלטפורמה*

## Postgres בסביבת ייצור

Cat-Scan משתמשת ב-Cloud SQL (Postgres 15) כמסד הנתונים התפעולי היחיד. ה-API מתחבר דרך קונטיינר Cloud SQL Auth Proxy כ-sidecar על `localhost:5432`.

### טבלאות עיקריות ונפח

| טבלה | מספר שורות משוער | מה היא מאחסנת |
|-------|------------------|---------------|
| `rtb_daily` | ~84 מיליון | ביצועי RTB יומיים לפי קונה, קריאייטיב, גיאוגרפיה ועוד |
| `rtb_bidstream` | ~21 מיליון | פילוח Bidstream לפי מפרסם, גיאוגרפיה |
| `rtb_quality` | משתנה | מטריקות איכות (viewability, בטיחות מותג) |
| `rtb_bid_filtering` | ~188 אלף | סיבות סינון הצעות ונפחים |
| `pretargeting_configs` | קטנה | תצלומי תצורת Pretargeting |
| `creatives` | קטנה | מטאדאטה של קריאייטיבים ותמונות ממוזערות |
| `import_history` | קטנה | רשומות ייבוא CSV |
| `users`, `permissions`, `audit_log` | קטנה | נתוני אימות וניהול |

### אינדקסים קריטיים

דפוס האינדקס הרגיש ביותר מבחינת ביצועים הוא:

```sql
CREATE INDEX idx_<table>_buyer_metric_date_desc
    ON <table> (buyer_account_id, metric_date DESC);
```

אינדקס זה קיים על `rtb_daily`, `rtb_bidstream`, `rtb_quality` ו-`rtb_bid_filtering`. הוא תומך בשאילתת רעננות הנתונים ובאנליטיקה ברמת הקונה.

אינדקסים חשובים נוספים:
- `(metric_date, buyer_account_id)`: לסינון לפי טווח תאריכים + קונה
- `(metric_date, billing_id)`: לשאילתות ברמת חיוב
- `(row_hash)` UNIQUE: מניעת כפילויות בייבוא

### מניעת כפילויות

כל שורה מיובאת עוברת גיבוב (עמודת `row_hash`). אילוץ הייחוד על `row_hash` מונע הכנסות כפולות, מה שהופך ייבוא חוזר לבטוח.

## מודל חיבורים

ה-API משתמש ב**חיבור לכל בקשה** (ללא מאגר חיבורים). כל שאילתה יוצרת קריאה חדשה ל-`psycopg.connect()`, עטופה ב-`run_in_executor` לתאימות אסינכרונית.

```python
async def pg_query(sql, params=()):
    loop = asyncio.get_event_loop()
    def _execute():
        with _get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    return await loop.run_in_executor(None, _execute)
```

לעומסי ייצור, שקלו להוסיף `psycopg_pool` אם תקורת החיבורים הופכת לצוואר בקבוק.

## מגבלות זמן לשאילתות

עבור שאילתות יקרות (למשל, רעננות נתונים על טבלאות גדולות), ה-API משתמש ב-`pg_query_with_timeout`:

```python
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
cursor = conn.execute(sql, params)
```

פרטים מרכזיים:
- `SET LOCAL` מגביל את מגבלת הזמן לטרנזקציה הנוכחית ומתאפס אוטומטית כשהטרנזקציה מסתיימת (commit או rollback).
- מגבלת זמן ברירת מחדל לרעננות נתונים: 30 שניות.
- ניתנת להגדרה באמצעות משתנה הסביבה `UPLOADS_DATA_FRESHNESS_QUERY_TIMEOUT_MS` (מינימום 1000ms).
- `SET LOCAL` מונע את בעיית הטרנזקציה שבוטלה המתרחשת בשימוש ב-`SET` + `RESET` בתוך בלוק `try/finally` (אם השאילתה מבוטלת על ידי מגבלת הזמן, הטרנזקציה נכנסת למצב aborted, ו-`RESET` נכשל).

## דפוס שאילתת רעננות נתונים

נקודת הקצה לרעננות נתונים צריכה לדעת אילו תאריכים מכילים נתונים עבור כל סוג דוח. הדפוס היעיל משתמש ב-`generate_series` + `EXISTS`:

```sql
SELECT d::date AS metric_date, 'bidsinauction' AS csv_type, 1 AS row_count
FROM generate_series(%s::date, CURRENT_DATE - 1, '1 day'::interval) AS d
WHERE EXISTS (
    SELECT 1 FROM rtb_daily
    WHERE metric_date = d::date AND buyer_account_id = %s
    LIMIT 1
)
```

זה מבצע N חיפושי אינדקס (אחד לכל יום בחלון) במקום סריקה של מיליוני שורות. עבור חלון של 14 יום: 14 חיפושים בקצב של ~0.1ms כל אחד לעומת סריקה סדרתית מקבילית שלוקחת 160+ שניות.

**מדוע GROUP BY לא עובד כאן:** גם עם `1 AS row_count` (ללא COUNT), המתכנן בוחר סריקה סדרתית כאשר קבוצת התוצאות של GROUP BY גדולה ביחס לטבלה. האינדקס `(buyer_account_id, metric_date DESC)` קיים אבל המתכנן מעריך שזול יותר לסרוק 84M שורות מאשר לבצע 4.4M קריאות אינדקס.

## התפקיד של BigQuery

BigQuery מאחסנת נתונים גולמיים ומפורטים ומריצה עבודות אנליטיקה בקבוצות. היא לא משמשת לשאילתות API בזמן אמת. הדפוס:

1. נתוני CSV גולמיים נטענים לטבלאות BigQuery.
2. עבודות אצווה מבצעות צבירה של הנתונים.
3. תוצאות מצוברות מראש נכתבות ל-Postgres.
4. ה-API מגיש מ-Postgres.

## שמירת נתונים

ניתנת להגדרה ב-`/settings/retention`. שולטת בכמה זמן נתונים היסטוריים נשמרים ב-Postgres לפני שהם מוסרים.

## קישורים

- [סקירת ארכיטקטורה](11-architecture.md): היכן מסד הנתונים משתלב
- [פתרון תקלות](15-troubleshooting.md): דפוסי כשל של מסד נתונים
- לקוני מדיה: [ייבוא נתונים](09-data-import.md) מכסה את רשת רעננות הנתונים מצד המשתמש.
