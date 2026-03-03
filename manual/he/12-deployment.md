# פרק 12: פריסה

*קהל יעד: DevOps, מהנדסי פלטפורמה*

## צינור CI/CD

```
Push to unified-platform
         │
         ▼
build-and-push.yml (automatic)
  ├── Run contract & recovery tests
  ├── Build API image
  ├── Build Dashboard image
  └── Push to Artifact Registry
         │
         ▼ (manual trigger)
deploy.yml (workflow_dispatch)
  ├── SSH into VM via IAP tunnel
  ├── git pull on VM
  ├── docker compose pull (prebuilt images)
  ├── docker compose up -d --force-recreate
  ├── Health check (60s wait + curl localhost:8000/health)
  └── Post-deploy contract check
```

### מדוע הפריסה ידנית

פריסה אוטומטית בעת push בוטלה לאחר תקרית בינואר 2026, שבה פריסות אוטומטיות התנגשו עם פריסות ידניות דרך SSH, מה שגרם לפגיעה בקונטיינרים ולאובדן נתונים. תהליך הפריסה דורש כעת:

1. הפעלה ידנית דרך ממשק GitHub Actions ("Run workflow")
2. בחירה מפורשת של סביבת יעד (staging או production)
3. הקלדת `DEPLOY` כאישור
4. שדה אופציונלי לסיבה לצורך מעקב ביקורת

### תגיות תמונה

התמונות מתויגות עם SHA מקוצר של git: `sha-XXXXXXX`. שלב הפריסה משתמש ב-`GITHUB_SHA` לבניית התגית, כך שהגרסה שנפרסת תמיד ממופה לקומיט ספציפי.

## כיצד לפרוס

1. ודאו שהבנייה עברה: `gh run list --workflow=build-and-push.yml --limit=1`
2. הפעילו את הפריסה:
   ```bash
   gh workflow run deploy.yml \
     --ref unified-platform \
     -f target=production \
     -f confirm=DEPLOY \
     -f reason="your reason here"
   ```
3. עקבו: `gh run watch <run_id> --exit-status`
4. אמתו: `curl -sS https://scan.rtb.cat/api/health | jq -r '.git_sha,.version'`

## אימות פריסה

נקודת הקצה `/api/health` מחזירה:

```json
{
  "git_sha": "94e9cbb0",
  "version": "sha-94e9cbb"
}
```

השוו את `git_sha` מול הקומיט שהתכוונתם לפרוס.

## בדיקת חוזים לאחר פריסה

לאחר הפריסה, תהליך העבודה מריץ את `scripts/contracts_check.py` בתוך קונטיינר ה-API. הסקריפט מאמת שחוזי נתונים (כללים בלתי ניתנים למשא ומתן מייבוא ועד פלט ה-API) מתקיימים. אם הבדיקה נכשלת:

- כאשר `ALLOW_CONTRACT_FAILURE=false` (ברירת מחדל): הפריסה מסומנת ככישלון.
- כאשר `ALLOW_CONTRACT_FAILURE=true` (עקיפה זמנית): הפריסה מצליחה עם אזהרה. עקיפה זו חייבת להיות מוסרת לאחר בירור.

## Staging מול production

| סביבה | שם VM | דומיין |
|--------|-------|--------|
| Staging | `catscan-production-sg2` | (פנימי) |
| Production | `catscan-production-sg` | `scan.rtb.cat` |

פרסו תחילה ל-staging, אמתו, ואז פרסו ל-production.

## שחזור לגרסה קודמת

לשחזור לגרסה קודמת, פרסו קומיט תקין קודם:

1. זהו את ה-SHA האחרון התקין מלוג ה-git או מהרצות פריסה קודמות.
2. עשו checkout ל-SHA הזה על unified-platform (או השתמשו ב-`--ref` עם הקומיט).
3. הפעילו את תהליך הפריסה.

אין מנגנון שחזור ייעודי. מדובר פשוט בפריסה של גרסה ישנה יותר.

## קישורים

- [סקירת ארכיטקטורה](11-architecture.md): מה נפרס
- [ניטור תקינות](13-health-monitoring.md): אימות שהפריסה הצליחה
