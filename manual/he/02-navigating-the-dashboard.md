# פרק 2: ניווט בלוח הבקרה

*קהל יעד: כולם*

## מבנה סרגל הצד

סרגל הצד הוא כלי הניווט העיקרי שלכם. ניתן לכווצו (מצב אייקונים בלבד) או
להרחיבו. ההעדפה שלכם נשמרת בין פגישות.

```
Seat Selector
 ├── QPS Waste Optimizer         /              (home)
 ├── Creatives                   /creatives
 ├── Campaigns                   /campaigns
 ├── Change History              /history
 ├── Import                      /import
 │
 ├── QPS (expandable)
 │   ├── Publisher                /qps/publisher
 │   ├── Geo                     /qps/geo
 │   └── Size                    /qps/size
 │
 ├── Settings (expandable)
 │   ├── Connected Accounts      /settings/accounts
 │   ├── Data Retention          /settings/retention
 │   └── System Status           /settings/system
 │
 ├── Admin (sudo users only)
 │   ├── Users                   /admin/users
 │   ├── Configuration           /admin/configuration
 │   └── Audit Log               /admin/audit-log
 │
 └── Footer: user email, version, docs link
```

מקטעים נפתחים אוטומטית כאשר מנווטים אליהם.

## משתמשים מוגבלים

חלק מהחשבונות מסומנים כ"מוגבלים" על ידי מנהל מערכת. משתמשים מוגבלים רואים רק
את הדפים המרכזיים: דף הבית, קריאייטיבים, קמפיינים, ייבוא והיסטוריה. מקטעי
ניתוח QPS, הגדרות וניהול מוסתרים.

## רשימת ההגדרה הראשונית

חשבונות חדשים רואים רשימת הגדרה ב-`/setup` שמלווה אותם בתצורה הראשונית:

1. חיבור חשבונות קונה (העלאת אישורי GCP, גילוי חשבונות)
2. אימות תקינות נתונים (בדיקה שייבוא CSV מגיע)
3. רישום מודל אופטימייזר (נקודת קצה BYOM)
4. אימות נקודת הקצה של המודל (קריאת בדיקה)
5. הגדרת קו בסיס לעלויות אירוח (לחישובים כלכליים)
6. חיבור מקור המרות (פיקסל או webhook)

אחוז ההשלמה נעקב. כל שלב מקושר לדף ההגדרות הרלוונטי.

## תמיכה בשפות

Cat-Scan תומכת באנגלית, הולנדית וסינית (פשוטה). בורר השפות נמצא בסרגל הצד.
ההעדפה נשמרת לכל משתמש.

## צעדים הבאים

- קונים מדיה: התחילו עם [הבנת משפך ה-QPS שלכם](03-qps-funnel.md)
- DevOps: התחילו עם [סקירת ארכיטקטורה](11-architecture.md)
