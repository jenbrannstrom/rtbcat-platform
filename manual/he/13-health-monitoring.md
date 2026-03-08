# פרק 13: ניטור תקינות ואבחון

*קהל יעד: DevOps, מהנדסי פלטפורמה*

## נקודות קצה לבדיקת תקינות

### `/api/health`: בדיקת חיוּת

מחזירה סטטוס בסיסי של ה-API, SHA של git וגרסה. משמשת את תהליך הפריסה וניטור חיצוני.

```bash
curl -sS https://your-deployment.example.com/api/health | jq .
```

### `/system/data-health`: שלמות נתונים

מחזירה סטטוס תקינות נתונים לכל קונה, כולל מצב רעננות לכל סוג דוח. מקבלת פרמטרים `days`, `buyer_id` ו-`availability_state`.

משמשת את רשימת הבדיקות להקמה ואת שער התקינות בזמן ריצה.

## דף סטטוס מערכת (`/settings/system`)

ממשק המשתמש מציג:

| בדיקה | מה היא מנטרת |
|--------|--------------|
| Python | גרסת סביבת הריצה וזמינות |
| Node | בניית Next.js וסטטוס SSR |
| FFmpeg | יכולת יצירת תמונות ממוזערות לווידאו |
| Database | חיבור Postgres ומספרי שורות |
| Thumbnails | סטטוס יצירה בקבוצות ותור |
| Disk space | ניצולת דיסק של ה-VM |

## סקריפטים לבדיקת תקינות בזמן ריצה

סקריפטים אלה מהווים את השדרה התפעולית לאימות שהמערכת פועלת מקצה לקצה.

### `diagnose_v1_buyer_report_coverage.sh`

מאבחן מדוע לקונה מסוים חסרה כיסוי CSV.

```bash
export CATSCAN_CANARY_EMAIL="user.com"
scripts/diagnose_v1_buyer_report_coverage.sh \
  --buyer-id <BUYER_ID> \
  --timeout 180 \
  --days 14
```

בדיקות (לפי סדר):
1. מיפוי מושבים: buyer_id -> bidder_id
2. מטריצת ייבוא: הצלחה/כישלון/לא יובא לפי סוג CSV
3. רעננות נתונים: כיסוי תאים מיובאים/חסרים
4. היסטוריית ייבוא: שורות ייבוא אחרונות
5. סטטוס Gmail: מספר הודעות שלא נקראו, סיבה אחרונה, תאריך מטריקה אחרון

תוצאה: PASS או FAIL עם אבחון ספציפי.

### `run_v1_runtime_health_strict_dispatch.sh`

מריץ את שער התקינות המלא בזמן ריצה, הבודק:

- תקינות API
- תקינות נתונים (רעננות וכיסוי ממדים)
- תקינות המרות ומוכנות
- זמן טעינת QPS
- סיכום SLO של דף QPS
- כלכלת אופטימייזר ומודלים
- אימות נקודות קצה של מודלים
- תהליך Score+propose
- מחזור חיי הצעות
- הרצת שחזור יבשה (dry-run)

כל בדיקה מחזירה PASS, FAIL או BLOCKED (עם סיבה).

### תהליך CI: `v1-runtime-health-strict.yml`

מריץ את השער הקפדני ב-CI. מופעל ידנית דרך workflow_dispatch.

```bash
gh workflow run v1-runtime-health-strict.yml \
  --ref main \
  -f api_base_url="https://your-deployment.example.com/api" \
  -f buyer_id="<BUYER_ID>" \
  -f canary_profile="balanced" \
  -f canary_timeout_seconds="180"
```

## אימות canary

סקריפטים בזמן ריצה מבצעים אימות באמצעות משתני סביבה:

| משתנה | ייעוד |
|--------|-------|
| `CATSCAN_CANARY_EMAIL` | כותרת X-Email עבור קריאות API ישירות (מקומי ב-VM) |
| `CATSCAN_BEARER_TOKEN` | טוקן Bearer (סביבת CI, מאוחסן ב-GitHub secrets) |
| `CATSCAN_SESSION_COOKIE` | עוגיית סשן OAuth2 Proxy (סביבת CI) |

מה-VM עצמו, השתמשו ב-`CATSCAN_CANARY_EMAIL` עם `http://localhost:8000`.
מ-CI (חיצוני), השתמשו ב-`CATSCAN_BEARER_TOKEN` או `CATSCAN_SESSION_COOKIE`
עם `https://your-deployment.example.com/api`.

## פרשנות תוצאות

| סטטוס | משמעות |
|--------|--------|
| **PASS** | הבדיקה עברה, המערכת תקינה |
| **FAIL** | הבדיקה נכשלה, יש לחקור מיידית |
| **BLOCKED** | לא ניתן היה להשלים את הבדיקה בגלל תלות חסרה (למשל, אין נתונים לקונה זה, נקודת קצה חסרה). לא בהכרח באג בקוד. |

## קישורים

- [פריסה](12-deployment.md): אימות פריסה
- [פתרון תקלות](15-troubleshooting.md): כאשר בדיקות תקינות נכשלות
- לקוני מדיה: [ייבוא נתונים](09-data-import.md) מסביר את רשת רעננות הנתונים במונחים ידידותיים לקונה.
