# עיון מהיר ב-API

זהו אינדקס ניתן לניווט של 118+ נקודות הקצה של Cat-Scan, מקובצות לפי תחום.
למפרטי בקשה/תגובה מלאים, ראו את תיעוד OpenAPI האינטראקטיבי בכתובת
`https://scan.rtb.cat/api/docs`.

## ליבה / מערכת

| שיטה | נתיב | מטרה |
|-------|------|------|
| GET | `/health` | בדיקת חיים (git_sha, גרסה) |
| GET | `/stats` | סטטיסטיקות מערכת |
| GET | `/sizes` | גדלי מודעות זמינים |
| GET | `/system/status` | סטטוס שרת (Python, Node, FFmpeg, מסד נתונים, דיסק) |
| GET | `/system/data-health` | שלמות נתונים לפי קונה |
| GET | `/system/ui-page-load-metrics` | מדדי ביצועים של צד הלקוח |
| GET | `/geo/lookup` | המרת מזהה גאוגרפי לשם |
| GET | `/geo/search` | חיפוש מדינות/ערים |

## אימות

| שיטה | נתיב | מטרה |
|-------|------|------|
| GET | `/auth/check` | בדיקה אם ההפעלה הנוכחית מאומתת |
| POST | `/auth/logout` | סיום הפעלה |

## מושבים

| שיטה | נתיב | מטרה |
|-------|------|------|
| GET | `/seats` | רשימת מושבי קונים |
| GET | `/seats/{buyer_id}` | קבלת מושב ספציפי |
| PUT | `/seats/{buyer_id}` | עדכון שם תצוגה של מושב |
| POST | `/seats/populate` | יצירת מושבים אוטומטית מנתונים |
| POST | `/seats/discover` | גילוי מושבים מ-Google API |
| POST | `/seats/{buyer_id}/sync` | סנכרון מושב ספציפי |
| POST | `/seats/sync-all` | סנכרון מלא (כל המושבים) |
| POST | `/seats/collect-creatives` | איסוף נתוני קריאייטיבים |

## קריאייטיבים

| שיטה | נתיב | מטרה |
|-------|------|------|
| GET | `/creatives` | רשימת קריאייטיבים (עם מסננים) |
| GET | `/creatives/paginated` | רשימת קריאייטיבים מדופדפת |
| GET | `/creatives/{id}` | פרטי קריאייטיב |
| GET | `/creatives/{id}/live` | נתוני קריאייטיב חיים (מודע למטמון) |
| GET | `/creatives/{id}/destination-diagnostics` | תקינות כתובת URL של יעד |
| GET | `/creatives/{id}/countries` | פירוט ביצועים לפי מדינה |
| GET | `/creatives/{id}/geo-linguistic` | ניתוח גאו-לשוני |
| POST | `/creatives/{id}/detect-language` | זיהוי שפה אוטומטי |
| PUT | `/creatives/{id}/language` | דריסת שפה ידנית |
| GET | `/creatives/thumbnail-status` | סטטוס תמונות ממוזערות באצווה |
| POST | `/creatives/thumbnails/batch` | יצירת תמונות ממוזערות חסרות |

## קמפיינים

| שיטה | נתיב | מטרה |
|-------|------|------|
| GET | `/campaigns` | רשימת קמפיינים |
| GET | `/campaigns/{id}` | פרטי קמפיין |
| GET | `/campaigns/ai` | קבוצות שנוצרו בבינה מלאכותית |
| GET | `/campaigns/ai/{id}` | פרטי קמפיין בינה מלאכותית |
| PUT | `/campaigns/ai/{id}` | עדכון קמפיין |
| DELETE | `/campaigns/ai/{id}` | מחיקת קמפיין |
| GET | `/campaigns/ai/{id}/creatives` | קריאייטיבים של הקמפיין |
| DELETE | `/campaigns/ai/{id}/creatives/{creative_id}` | הסרת קריאייטיב מקמפיין |
| POST | `/campaigns/auto-cluster` | קיבוץ אוטומטי בבינה מלאכותית |
| GET | `/campaigns/ai/{id}/performance` | ביצועי קמפיין |
| GET | `/campaigns/ai/{id}/daily-trend` | נתוני מגמה של קמפיין |

## אנליטיקה

| שיטה | נתיב | מטרה |
|-------|------|------|
| GET | `/analytics/waste-report` | מדדי בזבוז כוללים |
| GET | `/analytics/size-coverage` | כיסוי טרגוט לפי גודל |
| GET | `/analytics/rtb-funnel` | פירוט משפך RTB |
| GET | `/analytics/rtb-funnel/configs` | משפך ברמת תצורה |
| GET | `/analytics/endpoint-efficiency` | יעילות QPS לפי נקודת קצה |
| GET | `/analytics/spend-stats` | סטטיסטיקות הוצאה |
| GET | `/analytics/config-performance` | ביצועי תצורה לאורך זמן |
| GET | `/analytics/config-performance/breakdown` | פירוט שדות תצורה |
| GET | `/analytics/qps-recommendations` | המלצות בינה מלאכותית |
| GET | `/analytics/performance/batch` | ביצועי קריאייטיבים באצווה |
| GET | `/analytics/performance/{creative_id}` | ביצועי קריאייטיב בודד |
| GET | `/analytics/publishers` | מדדי דומיינים של מפרסמים |
| GET | `/analytics/publishers/search` | חיפוש מפרסמים |
| GET | `/analytics/languages` | ביצועים לפי שפה |
| GET | `/analytics/languages/multi` | ניתוח מרובה שפות |
| GET | `/analytics/geo-performance` | ביצועים גאוגרפיים |
| GET | `/analytics/geo-performance/multi` | ניתוח גאוגרפי מרובה |
| POST | `/analytics/import` | ייבוא CSV |
| POST | `/analytics/mock-traffic` | יצירת נתוני בדיקה |

## הגדרות / פרה-טרגוט

| שיטה | נתיב | מטרה |
|-------|------|------|
| GET | `/settings/rtb-endpoints` | נקודות קצה RTB של המכרז |
| POST | `/settings/rtb-endpoints/sync` | סנכרון נתוני נקודות קצה |
| GET | `/settings/pretargeting-configs` | רשימת תצורות פרה-טרגוט |
| GET | `/settings/pretargeting-configs/{id}` | פרטי תצורה |
| GET | `/settings/pretargeting-history` | היסטוריית שינויי תצורה |
| POST | `/settings/pretargeting-configs/sync` | סנכרון תצורות מ-Google |
| POST | `/settings/pretargeting-configs/{id}/apply` | החלת שינוי תצורה |
| POST | `/settings/pretargeting-configs/apply-all` | החלת כל השינויים הממתינים |
| PUT | `/settings/pretargeting-configs/{id}` | עדכון תצורה באצווה |

## העלאות

| שיטה | נתיב | מטרה |
|-------|------|------|
| GET | `/uploads/tracking` | סיכום העלאות יומי |
| GET | `/uploads/import-matrix` | סטטוס ייבוא לפי סוג דוח |
| GET | `/uploads/data-freshness` | רשת רעננות נתונים (תאריך x סוג) |
| GET | `/uploads/history` | היסטוריית ייבוא |

## אופטימייזר

| שיטה | נתיב | מטרה |
|-------|------|------|
| GET | `/optimizer/models` | רשימת מודלים של BYOM |
| POST | `/optimizer/models` | רישום מודל |
| PUT | `/optimizer/models/{id}` | עדכון מודל |
| POST | `/optimizer/models/{id}/activate` | הפעלת מודל |
| POST | `/optimizer/models/{id}/deactivate` | השבתת מודל |
| POST | `/optimizer/models/{id}/validate` | בדיקת נקודת קצה של מודל |
| POST | `/optimizer/score-and-propose` | יצירת הצעות |
| GET | `/optimizer/proposals` | רשימת הצעות פעילות |
| GET | `/optimizer/proposals/history` | היסטוריית הצעות |
| POST | `/optimizer/proposals/{id}/approve` | אישור הצעה |
| POST | `/optimizer/proposals/{id}/apply` | החלת הצעה |
| POST | `/optimizer/proposals/{id}/sync-status` | בדיקת סטטוס החלה |
| GET | `/optimizer/segment-scores` | ציונים ברמת פלח |
| GET | `/optimizer/economics/efficiency` | סיכום יעילות |
| GET | `/optimizer/economics/effective-cpm` | ניתוח CPM |
| GET | `/optimizer/setup` | תצורת אופטימייזר |
| PUT | `/optimizer/setup` | עדכון תצורת אופטימייזר |

## המרות

| שיטה | נתיב | מטרה |
|-------|------|------|
| GET | `/conversions/health` | סטטוס קליטה וצבירה |
| GET | `/conversions/readiness` | בדיקת מוכנות מקור |
| GET | `/conversions/ingestion-stats` | ספירת אירועים לפי מקור/תקופה |
| GET | `/conversions/security/status` | סטטוס אבטחת webhook |
| GET | `/conversions/pixel` | נקודת קצה למעקב פיקסל |

## תמונות מצב

| שיטה | נתיב | מטרה |
|-------|------|------|
| GET | `/snapshots` | רשימת תמונות מצב של תצורה |
| POST | `/snapshots/rollback` | שחזור תמונת מצב (עם הרצת ניסיון) |

## אינטגרציות

| שיטה | נתיב | מטרה |
|-------|------|------|
| POST | `/integrations/credentials` | העלאת JSON של חשבון שירות GCP |
| GET | `/integrations/service-accounts` | רשימת חשבונות שירות |
| DELETE | `/integrations/service-accounts/{id}` | מחיקת חשבון שירות |
| GET | `/integrations/language-ai/config` | סטטוס ספק בינה מלאכותית |
| PUT | `/integrations/language-ai/config` | הגדרת ספק בינה מלאכותית |
| GET | `/integrations/gmail/status` | סטטוס ייבוא Gmail |
| POST | `/integrations/gmail/import/start` | הפעלת ייבוא ידני |
| POST | `/integrations/gmail/import/stop` | עצירת משימת ייבוא |
| GET | `/integrations/gmail/import/history` | היסטוריית ייבוא |
| GET | `/integrations/gcp/project-status` | תקינות פרויקט GCP |
| POST | `/integrations/gcp/validate` | בדיקת חיבור GCP |

## ניהול

| שיטה | נתיב | מטרה |
|-------|------|------|
| GET | `/admin/users` | רשימת משתמשים |
| POST | `/admin/users` | יצירת משתמש |
| GET | `/admin/users/{id}` | פרטי משתמש |
| PUT | `/admin/users/{id}` | עדכון משתמש |
| POST | `/admin/users/{id}/deactivate` | השבתת משתמש |
| GET | `/admin/users/{id}/permissions` | הרשאות גלובליות של משתמש |
| GET | `/admin/users/{id}/seat-permissions` | הרשאות לפי מושב של משתמש |
| POST | `/admin/users/{id}/seat-permissions` | הענקת גישה למושב |
| DELETE | `/admin/users/{id}/seat-permissions/{buyer_id}` | ביטול גישה למושב |
| POST | `/admin/users/{id}/permissions` | הענקת הרשאה גלובלית |
| DELETE | `/admin/users/{id}/permissions/{sa_id}` | ביטול הרשאה גלובלית |
| GET | `/admin/audit-log` | יומן ביקורת |
| GET | `/admin/stats` | סטטיסטיקות לוח ניהול |
| GET | `/admin/settings` | תצורת מערכת |
| PUT | `/admin/settings/{key}` | עדכון הגדרת מערכת |
