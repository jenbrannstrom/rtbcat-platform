# פרק 15: מדריך פתרון תקלות

*קהל יעד: DevOps, מהנדסי פלטפורמה*

## לולאת התחברות

**תסמינים:** המשתמש מגיע לדף ההתחברות, מזדהה, מופנה בחזרה לדף ההתחברות, והלולאה חוזרת על עצמה ללא הגבלה.

**דפוס שורש הבעיה:** כל כשל במסד הנתונים גורם ל-`_get_or_create_oauth2_user()` להיכשל בשקט. `/auth/check` מחזיר `{authenticated: false}`. צד הלקוח מפנה ל-`/oauth2/sign_in`. לולאה.

**גורמים נפוצים:**
- קונטיינר Cloud SQL Proxy נפל או הופעל מחדש מבלי להפעיל מחדש את ה-API
- ניתוק רשת בין ה-VM למופע Cloud SQL
- תחזוקה או הפעלה מחדש של מופע Cloud SQL

**זיהוי:**
- דפדפן: מונה הפניות מופעל לאחר 2 הפניות ב-30 שניות, ומציג ממשק שגיאה/ניסיון חוזר במקום לולאה
- API: `/auth/check` מחזיר HTTP 503 (ולא 200) כאשר מסד הנתונים אינו נגיש, עם `auth_error` בתגובה
- לוגים: חפשו שגיאות connection refused או timeout בלוגי catscan-api

**תיקון:**
1. בדקו את Cloud SQL Proxy: `sudo docker ps | grep cloudsql`
2. אם לא פועל: `sudo docker compose -f docker-compose.gcp.yml restart cloudsql-proxy`
3. המתינו 10 שניות, ואז הפעילו מחדש את ה-API:
   `sudo docker compose -f docker-compose.gcp.yml restart api`
4. אמתו: `curl -sS http://localhost:8000/health`

**מניעה:** התיקון בשלוש שכבות (יושם בפברואר 2026):
1. צד השרת מעביר שגיאות מסד נתונים דרך `request.state.auth_error`
2. `/auth/check` מחזיר 503 כאשר מסד הנתונים אינו נגיש
3. צד הלקוח כולל מונה הפניות (מקסימום 2 ב-30 שניות) + ממשק שגיאה/ניסיון חוזר

## פקיעת זמן רעננות נתונים

**תסמינים:** `/uploads/data-freshness` מחזיר 500, פוקע לו הזמן, או ששער התקינות בזמן ריצה מציג BLOCKED על תקינות נתונים.

**דפוס שורש הבעיה:** שאילתת רעננות הנתונים סורקת טבלאות גדולות (`rtb_daily` עם 84M שורות, `rtb_bidstream` עם 21M שורות). אם תוכנית השאילתה מדרדרת לסריקה סדרתית במקום שימוש באינדקסים, זה יכול לקחת 160+ שניות.

**זיהוי:**
1. גשו לנקודת הקצה ישירות מה-VM:
   ```bash
   curl -sS --max-time 60 -H 'X-Email: user.com' \
     'http://localhost:8000/uploads/data-freshness?days=14&buyer_id=<ID>'
   ```
2. אם פוקע הזמן או מחזיר 500, בדקו את תוכנית השאילתה:
   ```bash
   sudo docker exec catscan-api python -c "
   import os, psycopg
   conn = psycopg.connect(os.environ['POSTGRES_DSN'])
   for r in conn.execute('EXPLAIN (ANALYZE, BUFFERS) <query>').fetchall():
       print(list(r.values())[0])
   "
   ```
3. חפשו `Parallel Seq Scan` על טבלאות גדולות. זו הבעיה.

**דפוס תיקון:**
- שכתבו שאילתות GROUP BY ל-`generate_series + EXISTS` כדי לאלץ חיפושי אינדקס. ראו [פעולות מסד נתונים](14-database.md) לדפוס המלא.
- ודאו שמשתמשים ב-`SET LOCAL statement_timeout` (ולא ב-`SET` + `RESET`).
- בדקו שאינדקסים `(buyer_account_id, metric_date DESC)` קיימים על כל הטבלאות הרלוונטיות.

## כשל ייבוא Gmail

**תסמינים:** רשת רעננות הנתונים מציגה תאים "חסרים" לתאריכים אחרונים. להיסטוריית הייבוא אין רשומות עדכניות.

**זיהוי:**
```bash
curl -sS -H 'X-Email: user.com' \
  http://localhost:8000/gmail/status
```

בדקו: `last_reason`, מספר `unread`, `latest_metric_date`.

**סיבות נפוצות:**
- טוקן OAuth של Gmail פג: בצעו הרשאה מחדש ב-`/settings/accounts` > לשונית Gmail
- Cloud SQL Proxy לא פועל: ייבוא Gmail כותב ל-Postgres, כך שמסד הנתונים חייב להיות נגיש
- מספר `unread` גבוה (30+): הייבוא עשוי להיות תקוע בעיבוד או שיש צבר בתיבת הדואר

**תיקון:**
1. אם `last_reason` מציג שגיאה: הפעילו מחדש את עבודת הייבוא מהממשק או ה-API
2. אם הטוקן פג: בצעו הרשאה מחדש לאינטגרציית Gmail
3. אם Cloud SQL לא פועל: תקנו תחילה את חיבור מסד הנתונים (ראו לולאת התחברות)

## סדר הפעלה מחדש של קונטיינרים

**תסמין:** לוגי ה-API מציגים "connection refused" לפורט 5432 בהפעלה.

**סיבה:** קונטיינר ה-API הופעל לפני ש-Cloud SQL Proxy היה מוכן.

**תיקון:** הפעילו מחדש בסדר הנכון:
```bash
sudo docker compose -f docker-compose.gcp.yml up -d cloudsql-proxy
sleep 10
sudo docker compose -f docker-compose.gcp.yml up -d api
```

או הפעילו הכל מחדש (compose מטפל בתלויות):
```bash
sudo docker compose -f docker-compose.gcp.yml up -d --force-recreate
```

## שגיאת תחביר SET statement_timeout

**תסמין:** נקודת הקצה מחזירה 500 עם שגיאה:
`syntax error at or near "$1" LINE 1: SET statement_timeout = $1`

**סיבה:** psycopg3 ממיר `%s` ל-`$1` עבור קישור פרמטרים בצד השרת, אבל פקודת `SET` של PostgreSQL אינה תומכת בממלאי מקום לפרמטרים.

**תיקון:** השתמשו ב-f-string עם מספר שלם מאומת:
```python
# Wrong:
conn.execute("SET statement_timeout = %s", (timeout_ms,))

# Right:
timeout_ms = max(int(statement_timeout_ms), 1)  # validated int
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
```

## כשל שער תקינות בזמן ריצה

**תסמין:** תהליך `v1-runtime-health-strict.yml` נכשל.

**מיון:**
1. בדקו את לוגי תהליך העבודה: `gh run view <id> --log-failed`
2. חפשו FAIL לעומת BLOCKED:
   - **FAIL** = משהו נשבר, חקרו
   - **BLOCKED** = תלות חסרה (אין נתונים, אין נקודת קצה), ייתכן שקיים מלפני כן
3. סיבות BLOCKED נפוצות קיימות מראש:
   - "rtb_quality_freshness state is unavailable": אין נתוני איכות לקונה/תקופה זו
   - "proposal has no billing_id": בעיית הגדרת נתונים
   - "QPS page API rollup missing required paths": נקודת קצה אנליטיקה טרם אוכלסה
4. השוו מול הרצות קודמות כדי לזהות רגרסיות לעומת בעיות קיימות.

## קישורים

- [ניטור תקינות](13-health-monitoring.md): כלי ניטור
- [פעולות מסד נתונים](14-database.md): פרטי שאילתות ואינדקסים
- [פריסה](12-deployment.md): פריסת תיקונים
