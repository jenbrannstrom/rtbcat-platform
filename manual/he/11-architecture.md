# פרק 11: סקירת ארכיטקטורה

*קהל יעד: DevOps, מהנדסי פלטפורמה*

## טופולוגיית המערכת

```
                                    Internet
                                       │
                                 ┌─────┴─────┐
                                 │   nginx    │  :443 (TLS termination)
                                 └──┬──────┬──┘
                                    │      │
                          ┌─────────┘      └─────────┐
                          │                          │
                  ┌───────┴────────┐       ┌─────────┴─────────┐
                  │  OAuth2 Proxy  │       │  Next.js Dashboard │  :3000
                  │  (Google SSO)  │       │  (static + SSR)    │
                  └───────┬────────┘       └───────────────────┘
                          │
                  ┌───────┴────────┐
                  │   FastAPI API  │  :8000
                  │  (118+ routes) │
                  └───────┬────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
    ┌─────────┴──────────┐   ┌────────┴────────┐
    │ Cloud SQL Proxy    │   │   BigQuery       │
    │ (Postgres sidecar) │   │ (batch analytics)│
    └─────────┬──────────┘   └─────────────────┘
              │
    ┌─────────┴──────────┐
    │  Cloud SQL         │
    │  (Postgres 15)     │
    └────────────────────┘
```

## פריסת קונטיינרים

סביבת הייצור רצה על מכונה וירטואלית יחידה ב-GCP (`catscan-vm`, אזור
`asia-southeast1-b`) באמצעות `docker-compose.gcp.yml`.

| קונטיינר | Image | פורט | תפקיד |
|-----------|-------|------|------|
| `catscan-api` | `asia-southeast1-docker.pkg.dev/.../api:sha-XXXXXXX` | 8000 | Backend של FastAPI |
| `catscan-dashboard` | `asia-southeast1-docker.pkg.dev/.../dashboard:sha-XXXXXXX` | 3000 | Frontend של Next.js |
| `oauth2-proxy` | image סטנדרטי של oauth2-proxy | 4180 | אימות Google OAuth2 |
| `cloudsql-proxy` | Google Cloud SQL Auth Proxy | 5432 | פרוקסי חיבור Postgres |
| `nginx` | image סטנדרטי של nginx עם הגדרות | 80/443 | פרוקסי הפוך, TLS, ניתוב |

## שרשרת אמון לאימות

```
Browser → nginx → OAuth2 Proxy → sets X-Email header → nginx → API
```

1. הדפדפן פונה ל-nginx.
2. nginx מנתב את `/oauth2/*` ל-OAuth2 Proxy.
3. OAuth2 Proxy מאמת דרך Google, מגדיר כותרת `X-Email`.
4. בקשות עוקבות עוברות דרך nginx עם `X-Email` ללא שינוי.
5. ה-API קורא את `X-Email` וסומך עליו (כאשר `OAUTH2_PROXY_ENABLED=true`).

**חשוב:** ה-API סומך על `X-Email` רק מתעבורה פנימית. בקשות
חיצוניות עם כותרת `X-Email` מזויפת נדחות על ידי nginx.

## למה שני מסדי נתונים

Cat-Scan משתמש גם ב-Postgres וגם ב-BigQuery לתפקידים שונים:

| היבט | Postgres (Cloud SQL) | BigQuery |
|---------|---------------------|----------|
| **תפקיד** | מסד נתונים תפעולי: משרת את האפליקציה | מחסן נתונים: מאחסן נתונים גולמיים, מריץ ניתוח אצוות |
| **מודל עלות** | עלות אירוח קבועה, שאילתות ללא הגבלה | תשלום לפי שאילתה בהתאם לנתונים שנסרקו |
| **זמן תגובה** | תגובות באלפיות שנייה | תקורה של 1--3 שניות גם לשאילתות פשוטות |
| **ריבוי משתמשים** | מטפל במאות חיבורי API | לא בנוי לרענון מקביל של לוח מחוונים |
| **נתונים** | סיכומים מצרפיים מראש, הגדרות, נתוני משתמשים | שורות גולמיות מפורטות (מיליונים ליום) |

הדפוס: BigQuery הוא מחסן הארכיון; Postgres הוא מדף החנות.
אתם לא שולחים לקוחות לחפור במחסן.

## מבנה קוד מרכזי

```
/api/routers/       FastAPI route handlers (118+ endpoints)
/services/          Business logic layer
/storage/           Database access (Postgres repos, BigQuery clients)
/dashboard/src/     Next.js 14 frontend (App Router)
/scripts/           Operational and diagnostic scripts
docs.rtb.cat/       Public documentation portal
```

ה-backend עוקב אחר דפוס **Router -> Service -> Repository**. נתבים
מטפלים ב-HTTP; שירותים מכילים לוגיקה עסקית; מאגרים מריצים SQL.

## קישורים נוספים

- [פריסה](12-deployment.md): כיצד המערכת נפרסת
- [פעולות מסד נתונים](14-database.md): פרטי Postgres
- [אינטגרציות](17-integrations.md): חיבורים לשירותים חיצוניים
