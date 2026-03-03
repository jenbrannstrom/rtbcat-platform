# الفصل 12: النشر

*الجمهور المستهدف: مهندسو DevOps، مهندسو المنصة*

## خط أنابيب CI/CD

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

### لماذا النشر يدوي

تم تعطيل النشر التلقائي عند الدفع بعد حادثة وقعت في يناير 2026 حيث تعارضت عمليات النشر التلقائية مع عمليات النشر اليدوية عبر SSH، مما أدى إلى تلف الحاويات وفقدان البيانات. يتطلب سير عمل النشر الآن ما يلي:

1. تشغيل يدوي عبر واجهة GitHub Actions ("Run workflow")
2. اختيار صريح للبيئة المستهدفة (بيئة الاختبار أو الإنتاج)
3. كتابة `DEPLOY` كتأكيد
4. حقل اختياري لذكر السبب لأغراض التدقيق

### وسوم الصور

يتم وسم الصور باستخدام معرّف git المختصر: `sha-XXXXXXX`. تستخدم خطوة النشر `GITHUB_SHA` لتكوين الوسم، بحيث يرتبط الإصدار المنشور دائمًا بعملية إيداع محددة.

## كيفية النشر

1. تحقق من نجاح البناء: `gh run list --workflow=build-and-push.yml --limit=1`
2. أطلق عملية النشر:
   ```bash
   gh workflow run deploy.yml \
     --ref unified-platform \
     -f target=production \
     -f confirm=DEPLOY \
     -f reason="your reason here"
   ```
3. راقب التقدم: `gh run watch <run_id> --exit-status`
4. تحقق من النتيجة: `curl -sS https://scan.rtb.cat/api/health | jq -r '.git_sha,.version'`

## التحقق من النشر

يُرجع مسار `/api/health` ما يلي:

```json
{
  "git_sha": "94e9cbb0",
  "version": "sha-94e9cbb"
}
```

قارن قيمة `git_sha` مع عملية الإيداع التي كنت تنوي نشرها.

## فحص العقود بعد النشر

بعد النشر، يقوم سير العمل بتشغيل `scripts/contracts_check.py` داخل حاوية API. يتحقق هذا من أن عقود البيانات (القواعد غير القابلة للتفاوض من الاستيراد حتى مخرجات API) لا تزال سارية. في حال فشل الفحص:

- مع `ALLOW_CONTRACT_FAILURE=false` (الافتراضي): يتم تمييز النشر على أنه فاشل.
- مع `ALLOW_CONTRACT_FAILURE=true` (تجاوز مؤقت): ينجح النشر مع تحذير. يجب إزالة هذا التجاوز بعد التحقيق.

## بيئة الاختبار مقابل الإنتاج

| البيئة | اسم الآلة الافتراضية | النطاق |
|--------|----------------------|--------|
| بيئة الاختبار | `catscan-production-sg2` | (داخلي) |
| الإنتاج | `catscan-production-sg` | `scan.rtb.cat` |

انشر على بيئة الاختبار أولاً، ثم تحقق، ثم انشر على الإنتاج.

## التراجع

للتراجع، انشر عملية إيداع سابقة معروفة بأنها تعمل بشكل صحيح:

1. حدد آخر معرّف SHA صالح من سجل git أو عمليات النشر السابقة.
2. انتقل إلى ذلك المعرّف على فرع unified-platform (أو استخدم `--ref` مع عملية الإيداع).
3. أطلق سير عمل النشر.

لا توجد آلية تراجع مخصصة. إنما هو مجرد نشر لإصدار أقدم.

## مواضيع ذات صلة

- [نظرة عامة على البنية](11-architecture.md): ما الذي يتم نشره
- [مراقبة الصحة](13-health-monitoring.md): التحقق من نجاح النشر
