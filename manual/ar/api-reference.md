# مرجع API السريع

هذا فهرس قابل للتصفح لأكثر من 118 نقطة اتصال API في Cat-Scan، مجمّعة حسب
المجال. للاطلاع على مخططات الطلبات والاستجابات الكاملة، راجع وثائق OpenAPI
التفاعلية على `https://scan.rtb.cat/api/docs`.

## الأساسي / النظام

| الطريقة | المسار | الغرض |
|---------|--------|-------|
| GET | `/health` | فحص الحياة (git_sha، الإصدار) |
| GET | `/stats` | إحصائيات النظام |
| GET | `/sizes` | أحجام الإعلانات المتاحة |
| GET | `/system/status` | حالة الخادم (Python، Node، FFmpeg، قاعدة البيانات، القرص) |
| GET | `/system/data-health` | اكتمال البيانات لكل مشتري |
| GET | `/system/ui-page-load-metrics` | مقاييس أداء الواجهة الأمامية |
| GET | `/geo/lookup` | تحويل معرّف المنطقة الجغرافية إلى اسم |
| GET | `/geo/search` | البحث في البلدان/المدن |

## المصادقة

| الطريقة | المسار | الغرض |
|---------|--------|-------|
| GET | `/auth/check` | التحقق مما إذا كانت الجلسة الحالية مُصادَقة |
| POST | `/auth/logout` | إنهاء الجلسة |

## المقاعد

| الطريقة | المسار | الغرض |
|---------|--------|-------|
| GET | `/seats` | عرض مقاعد المشترين |
| GET | `/seats/{buyer_id}` | الحصول على مقعد محدد |
| PUT | `/seats/{buyer_id}` | تحديث اسم العرض للمقعد |
| POST | `/seats/populate` | إنشاء المقاعد تلقائياً من البيانات |
| POST | `/seats/discover` | اكتشاف المقاعد من Google API |
| POST | `/seats/{buyer_id}/sync` | مزامنة مقعد محدد |
| POST | `/seats/sync-all` | مزامنة كاملة (جميع المقاعد) |
| POST | `/seats/collect-creatives` | جمع بيانات التصاميم الإبداعية |

## التصاميم الإبداعية

| الطريقة | المسار | الغرض |
|---------|--------|-------|
| GET | `/creatives` | عرض التصاميم الإبداعية (مع فلاتر) |
| GET | `/creatives/paginated` | قائمة التصاميم الإبداعية مُرقّمة الصفحات |
| GET | `/creatives/{id}` | تفاصيل التصميم الإبداعي |
| GET | `/creatives/{id}/live` | بيانات التصميم الإبداعي الحية (مع وعي بالتخزين المؤقت) |
| GET | `/creatives/{id}/destination-diagnostics` | صحة عنوان URL للوجهة |
| GET | `/creatives/{id}/countries` | تحليل الأداء حسب البلد |
| GET | `/creatives/{id}/geo-linguistic` | التحليل الجغرافي-اللغوي |
| POST | `/creatives/{id}/detect-language` | الكشف التلقائي عن اللغة |
| PUT | `/creatives/{id}/language` | تجاوز اللغة يدوياً |
| GET | `/creatives/thumbnail-status` | حالة الصور المصغرة بالجملة |
| POST | `/creatives/thumbnails/batch` | توليد الصور المصغرة المفقودة |

## الحملات

| الطريقة | المسار | الغرض |
|---------|--------|-------|
| GET | `/campaigns` | عرض الحملات |
| GET | `/campaigns/{id}` | تفاصيل الحملة |
| GET | `/campaigns/ai` | المجموعات المُولَّدة بالذكاء الاصطناعي |
| GET | `/campaigns/ai/{id}` | تفاصيل حملة الذكاء الاصطناعي |
| PUT | `/campaigns/ai/{id}` | تحديث الحملة |
| DELETE | `/campaigns/ai/{id}` | حذف الحملة |
| GET | `/campaigns/ai/{id}/creatives` | التصاميم الإبداعية للحملة |
| DELETE | `/campaigns/ai/{id}/creatives/{creative_id}` | إزالة تصميم إبداعي من الحملة |
| POST | `/campaigns/auto-cluster` | التجميع التلقائي بالذكاء الاصطناعي |
| GET | `/campaigns/ai/{id}/performance` | أداء الحملة |
| GET | `/campaigns/ai/{id}/daily-trend` | بيانات اتجاه الحملة |

## التحليلات

| الطريقة | المسار | الغرض |
|---------|--------|-------|
| GET | `/analytics/waste-report` | مقاييس الهدر الإجمالية |
| GET | `/analytics/size-coverage` | تغطية استهداف الحجم |
| GET | `/analytics/rtb-funnel` | تحليل قمع RTB |
| GET | `/analytics/rtb-funnel/configs` | القمع على مستوى الإعداد |
| GET | `/analytics/endpoint-efficiency` | كفاءة QPS حسب نقطة الاتصال |
| GET | `/analytics/spend-stats` | إحصائيات الإنفاق |
| GET | `/analytics/config-performance` | أداء الإعداد عبر الزمن |
| GET | `/analytics/config-performance/breakdown` | تحليل حقول الإعداد |
| GET | `/analytics/qps-recommendations` | توصيات الذكاء الاصطناعي |
| GET | `/analytics/performance/batch` | أداء التصاميم الإبداعية بالجملة |
| GET | `/analytics/performance/{creative_id}` | أداء تصميم إبداعي واحد |
| GET | `/analytics/publishers` | مقاييس نطاقات الناشرين |
| GET | `/analytics/publishers/search` | البحث في الناشرين |
| GET | `/analytics/languages` | أداء اللغات |
| GET | `/analytics/languages/multi` | تحليل لغات متعددة |
| GET | `/analytics/geo-performance` | الأداء الجغرافي |
| GET | `/analytics/geo-performance/multi` | تحليل مناطق جغرافية متعددة |
| POST | `/analytics/import` | استيراد CSV |
| POST | `/analytics/mock-traffic` | توليد بيانات اختبار |

## الإعدادات / الاستهداف المسبق

| الطريقة | المسار | الغرض |
|---------|--------|-------|
| GET | `/settings/rtb-endpoints` | نقاط اتصال RTB للمزايد |
| POST | `/settings/rtb-endpoints/sync` | مزامنة بيانات نقاط الاتصال |
| GET | `/settings/pretargeting-configs` | عرض إعدادات الاستهداف المسبق |
| GET | `/settings/pretargeting-configs/{id}` | تفاصيل الإعداد |
| GET | `/settings/pretargeting-history` | سجل تغييرات الإعداد |
| POST | `/settings/pretargeting-configs/sync` | مزامنة الإعدادات من Google |
| POST | `/settings/pretargeting-configs/{id}/apply` | تطبيق تغيير إعداد |
| POST | `/settings/pretargeting-configs/apply-all` | تطبيق جميع التغييرات المعلّقة |
| PUT | `/settings/pretargeting-configs/{id}` | تحديث الإعداد بالجملة |

## الرفع

| الطريقة | المسار | الغرض |
|---------|--------|-------|
| GET | `/uploads/tracking` | ملخص الرفع اليومي |
| GET | `/uploads/import-matrix` | حالة الاستيراد حسب نوع التقرير |
| GET | `/uploads/data-freshness` | شبكة تحديث البيانات (التاريخ × النوع) |
| GET | `/uploads/history` | سجل الاستيراد |

## المحسّن

| الطريقة | المسار | الغرض |
|---------|--------|-------|
| GET | `/optimizer/models` | عرض نماذج BYOM |
| POST | `/optimizer/models` | تسجيل نموذج |
| PUT | `/optimizer/models/{id}` | تحديث النموذج |
| POST | `/optimizer/models/{id}/activate` | تفعيل النموذج |
| POST | `/optimizer/models/{id}/deactivate` | إلغاء تفعيل النموذج |
| POST | `/optimizer/models/{id}/validate` | اختبار نقطة اتصال النموذج |
| POST | `/optimizer/score-and-propose` | توليد المقترحات |
| GET | `/optimizer/proposals` | عرض المقترحات النشطة |
| GET | `/optimizer/proposals/history` | سجل المقترحات |
| POST | `/optimizer/proposals/{id}/approve` | الموافقة على مقترح |
| POST | `/optimizer/proposals/{id}/apply` | تطبيق مقترح |
| POST | `/optimizer/proposals/{id}/sync-status` | التحقق من حالة التطبيق |
| GET | `/optimizer/segment-scores` | تقييمات على مستوى الشرائح |
| GET | `/optimizer/economics/efficiency` | ملخص الكفاءة |
| GET | `/optimizer/economics/effective-cpm` | تحليل CPM |
| GET | `/optimizer/setup` | إعداد المحسّن |
| PUT | `/optimizer/setup` | تحديث إعداد المحسّن |

## التحويلات

| الطريقة | المسار | الغرض |
|---------|--------|-------|
| GET | `/conversions/health` | حالة الاستيعاب والتجميع |
| GET | `/conversions/readiness` | فحص جاهزية المصدر |
| GET | `/conversions/ingestion-stats` | أعداد الأحداث حسب المصدر/الفترة |
| GET | `/conversions/security/status` | حالة أمان Webhook |
| GET | `/conversions/pixel` | نقطة اتصال تتبع البكسل |

## اللقطات

| الطريقة | المسار | الغرض |
|---------|--------|-------|
| GET | `/snapshots` | عرض لقطات الإعداد |
| POST | `/snapshots/rollback` | استعادة لقطة (مع تشغيل تجريبي) |

## التكاملات

| الطريقة | المسار | الغرض |
|---------|--------|-------|
| POST | `/integrations/credentials` | رفع ملف JSON لحساب خدمة GCP |
| GET | `/integrations/service-accounts` | عرض حسابات الخدمة |
| DELETE | `/integrations/service-accounts/{id}` | حذف حساب خدمة |
| GET | `/integrations/language-ai/config` | حالة مزود الذكاء الاصطناعي |
| PUT | `/integrations/language-ai/config` | إعداد مزود الذكاء الاصطناعي |
| GET | `/integrations/gmail/status` | حالة استيراد Gmail |
| POST | `/integrations/gmail/import/start` | تشغيل الاستيراد يدوياً |
| POST | `/integrations/gmail/import/stop` | إيقاف مهمة الاستيراد |
| GET | `/integrations/gmail/import/history` | سجل الاستيراد |
| GET | `/integrations/gcp/project-status` | صحة مشروع GCP |
| POST | `/integrations/gcp/validate` | اختبار اتصال GCP |

## الإدارة

| الطريقة | المسار | الغرض |
|---------|--------|-------|
| GET | `/admin/users` | عرض المستخدمين |
| POST | `/admin/users` | إنشاء مستخدم |
| GET | `/admin/users/{id}` | تفاصيل المستخدم |
| PUT | `/admin/users/{id}` | تحديث المستخدم |
| POST | `/admin/users/{id}/deactivate` | إلغاء تفعيل المستخدم |
| GET | `/admin/users/{id}/permissions` | صلاحيات المستخدم العامة |
| GET | `/admin/users/{id}/seat-permissions` | صلاحيات المستخدم لكل مقعد |
| POST | `/admin/users/{id}/seat-permissions` | منح الوصول إلى مقعد |
| DELETE | `/admin/users/{id}/seat-permissions/{buyer_id}` | سحب الوصول إلى مقعد |
| POST | `/admin/users/{id}/permissions` | منح صلاحية عامة |
| DELETE | `/admin/users/{id}/permissions/{sa_id}` | سحب صلاحية عامة |
| GET | `/admin/audit-log` | سجل التدقيق |
| GET | `/admin/stats` | إحصائيات لوحة الإدارة |
| GET | `/admin/settings` | إعدادات النظام |
| PUT | `/admin/settings/{key}` | تحديث إعداد النظام |
