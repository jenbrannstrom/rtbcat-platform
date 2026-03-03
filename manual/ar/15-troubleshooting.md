# الفصل 15: دليل استكشاف الأخطاء وإصلاحها

*الجمهور المستهدف: مهندسو DevOps، مهندسو المنصة*

## حلقة تسجيل الدخول

**الأعراض:** يصل المستخدم إلى صفحة تسجيل الدخول، يُصادق، يُعاد توجيهه إلى صفحة تسجيل الدخول مرة أخرى، وتتكرر الحلقة إلى ما لا نهاية.

**نمط السبب الجذري:** أي عطل في قاعدة البيانات يتسبب في فشل `_get_or_create_oauth2_user()` بصمت. يُرجع `/auth/check` القيمة `{authenticated: false}`. تُعيد الواجهة الأمامية التوجيه إلى `/oauth2/sign_in`. تتكرر الحلقة.

**المسببات الشائعة:**
- توقف حاوية Cloud SQL Proxy أو إعادة تشغيلها دون إعادة تشغيل API
- انقطاع الشبكة بين الآلة الافتراضية ومثيل Cloud SQL
- صيانة مثيل Cloud SQL أو إعادة تشغيله

**الاكتشاف:**
- المتصفح: يتم تفعيل عدّاد إعادة التوجيه بعد إعادتي توجيه خلال 30 ثانية، ويعرض واجهة خطأ/إعادة محاولة بدلاً من الاستمرار في الحلقة
- API: يُرجع `/auth/check` الحالة HTTP 503 (وليس 200) عندما تكون قاعدة البيانات غير قابلة للوصول، مع `auth_error` في الاستجابة
- السجلات: ابحث عن أخطاء رفض الاتصال أو انتهاء المهلة في سجلات catscan-api

**الإصلاح:**
1. تحقق من Cloud SQL Proxy: `sudo docker ps | grep cloudsql`
2. إذا كان متوقفًا: `sudo docker compose -f docker-compose.gcp.yml restart cloudsql-proxy`
3. انتظر 10 ثوانٍ، ثم أعد تشغيل API:
   `sudo docker compose -f docker-compose.gcp.yml restart api`
4. تحقق: `curl -sS http://localhost:8000/health`

**الوقاية:** الإصلاح ثلاثي الطبقات (طُبّق في فبراير 2026):
1. تنشر الواجهة الخلفية أخطاء قاعدة البيانات عبر `request.state.auth_error`
2. يُرجع `/auth/check` الحالة 503 عندما تكون قاعدة البيانات غير قابلة للوصول
3. تحتوي الواجهة الأمامية على عدّاد إعادة توجيه (بحد أقصى 2 خلال 30 ثانية) + واجهة خطأ/إعادة محاولة

## انتهاء مهلة حداثة البيانات

**الأعراض:** يُرجع `/uploads/data-freshness` الحالة 500، أو ينتهي وقت الاستجابة، أو تُظهر بوابة الصحة أثناء التشغيل حالة BLOCKED على صحة البيانات.

**نمط السبب الجذري:** يقوم استعلام حداثة البيانات بمسح جداول كبيرة (جدول `rtb_daily` بـ 84 مليون صف، وجدول `rtb_bidstream` بـ 21 مليون صف). إذا تدهورت خطة الاستعلام إلى مسح تسلسلي بدلاً من استخدام الفهارس، فقد يستغرق أكثر من 160 ثانية.

**الاكتشاف:**
1. استدعِ نقطة النهاية مباشرة من الآلة الافتراضية:
   ```bash
   curl -sS --max-time 60 -H 'X-Email: cat-scan@rtb.cat' \
     'http://localhost:8000/uploads/data-freshness?days=14&buyer_id=<ID>'
   ```
2. إذا انتهت المهلة أو أُرجعت الحالة 500، تحقق من خطة الاستعلام:
   ```bash
   sudo docker exec catscan-api python -c "
   import os, psycopg
   conn = psycopg.connect(os.environ['POSTGRES_DSN'])
   for r in conn.execute('EXPLAIN (ANALYZE, BUFFERS) <query>').fetchall():
       print(list(r.values())[0])
   "
   ```
3. ابحث عن `Parallel Seq Scan` على الجداول الكبيرة. هذه هي المشكلة.

**نمط الإصلاح:**
- أعد كتابة استعلامات GROUP BY كـ `generate_series + EXISTS` لفرض عمليات البحث في الفهرس. انظر [عمليات قاعدة البيانات](14-database.md) للاطلاع على النمط.
- تأكد من استخدام `SET LOCAL statement_timeout` (وليس `SET` + `RESET`).
- تحقق من وجود الفهارس `(buyer_account_id, metric_date DESC)` على جميع الجداول المستهدفة.

## فشل استيراد Gmail

**الأعراض:** تُظهر شبكة حداثة البيانات خلايا "مفقودة" للتواريخ الأخيرة. لا يحتوي سجل الاستيراد على إدخالات حديثة.

**الاكتشاف:**
```bash
curl -sS -H 'X-Email: cat-scan@rtb.cat' \
  http://localhost:8000/gmail/status
```

تحقق من: `last_reason`، وعدد `unread`، و`latest_metric_date`.

**الأسباب الشائعة:**
- انتهاء صلاحية رمز OAuth لـ Gmail: أعد التفويض من `/settings/accounts` > تبويب Gmail
- توقف Cloud SQL Proxy: يكتب استيراد Gmail إلى Postgres، لذا يجب أن تكون قاعدة البيانات قابلة للوصول
- عدد كبير من الرسائل غير المقروءة `unread` (أكثر من 30): قد يكون الاستيراد متوقفًا في المعالجة أو يوجد تراكم في صندوق البريد

**الإصلاح:**
1. إذا أظهر `last_reason` خطأ: أعد تشغيل مهمة الاستيراد من الواجهة أو API
2. إذا انتهت صلاحية الرمز: أعد تفويض تكامل Gmail
3. إذا كان Cloud SQL متوقفًا: أصلح اتصال قاعدة البيانات أولاً (انظر حلقة تسجيل الدخول)

## ترتيب إعادة تشغيل الحاويات

**الأعراض:** تُظهر سجلات API رسالة "connection refused" على المنفذ 5432 عند بدء التشغيل.

**السبب:** بدأت حاوية API قبل أن يكون Cloud SQL Proxy جاهزًا.

**الإصلاح:** أعد التشغيل بالترتيب الصحيح:
```bash
sudo docker compose -f docker-compose.gcp.yml up -d cloudsql-proxy
sleep 10
sudo docker compose -f docker-compose.gcp.yml up -d api
```

أو أعد تشغيل كل شيء (يتولى compose إدارة التبعيات):
```bash
sudo docker compose -f docker-compose.gcp.yml up -d --force-recreate
```

## خطأ بناء جملة SET statement_timeout

**الأعراض:** تُرجع نقطة النهاية الحالة 500 مع الخطأ:
`syntax error at or near "$1" LINE 1: SET statement_timeout = $1`

**السبب:** يحوّل psycopg3 الرمز `%s` إلى `$1` لربط المعاملات من جانب الخادم، لكن أمر `SET` في PostgreSQL لا يدعم العناصر النائبة للمعاملات.

**الإصلاح:** استخدم سلسلة نصية منسّقة مع عدد صحيح مُتحقق منه:
```python
# Wrong:
conn.execute("SET statement_timeout = %s", (timeout_ms,))

# Right:
timeout_ms = max(int(statement_timeout_ms), 1)  # validated int
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
```

## فشل بوابة الصحة أثناء التشغيل

**الأعراض:** فشل سير عمل `v1-runtime-health-strict.yml`.

**الفرز:**
1. تحقق من سجلات سير العمل: `gh run view <id> --log-failed`
2. ابحث عن FAIL مقابل BLOCKED:
   - **FAIL** = شيء تعطّل، يجب التحقيق
   - **BLOCKED** = تبعية مفقودة (لا توجد بيانات، لا توجد نقطة نهاية)، قد تكون مشكلة قائمة مسبقًا
3. أسباب BLOCKED الشائعة القائمة مسبقًا:
   - "rtb_quality_freshness state is unavailable": لا توجد بيانات جودة لهذا المشتري/الفترة
   - "proposal has no billing_id": مشكلة في إعداد البيانات
   - "QPS page API rollup missing required paths": نقطة نهاية التحليلات لم تُملأ بعد
4. قارن مع عمليات التشغيل السابقة لتحديد التراجعات مقابل المشكلات القائمة مسبقًا.

## مواضيع ذات صلة

- [مراقبة الصحة](13-health-monitoring.md): أدوات المراقبة
- [عمليات قاعدة البيانات](14-database.md): تفاصيل الاستعلامات والفهارس
- [النشر](12-deployment.md): نشر الإصلاحات
