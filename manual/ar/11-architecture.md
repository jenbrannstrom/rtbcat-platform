# الفصل 11: نظرة عامة على البنية

*الجمهور المستهدف: فريق DevOps، مهندسو المنصة*

## طوبولوجيا النظام

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

## تخطيط الحاويات

يعمل الإنتاج على جهاز افتراضي واحد من GCP (`catscan-vm`، منطقة
`asia-southeast1-b`) باستخدام `docker-compose.gcp.yml`.

| الحاوية | الصورة | المنفذ | الدور |
|-----------|-------|------|------|
| `catscan-api` | `asia-southeast1-docker.pkg.dev/.../api:sha-XXXXXXX` | 8000 | واجهة FastAPI الخلفية |
| `catscan-dashboard` | `asia-southeast1-docker.pkg.dev/.../dashboard:sha-XXXXXXX` | 3000 | واجهة Next.js الأمامية |
| `oauth2-proxy` | صورة oauth2-proxy القياسية | 4180 | مصادقة Google OAuth2 |
| `cloudsql-proxy` | Google Cloud SQL Auth Proxy | 5432 | وكيل اتصال Postgres |
| `nginx` | صورة nginx القياسية مع إعدادات مخصصة | 80/443 | وكيل عكسي، TLS، توجيه |

## سلسلة ثقة المصادقة

```
Browser → nginx → OAuth2 Proxy → sets X-Email header → nginx → API
```

1. يصل المتصفح إلى nginx.
2. يوجّه nginx مسارات `/oauth2/*` إلى OAuth2 Proxy.
3. يُصادق OAuth2 Proxy عبر Google، ويُعيّن ترويسة `X-Email`.
4. تمر الطلبات اللاحقة عبر nginx مع ترويسة `X-Email` سليمة.
5. تقرأ API ترويسة `X-Email` وتثق بها (عندما يكون `OAUTH2_PROXY_ENABLED=true`).

**مهم:** تثق API بترويسة `X-Email` فقط من الحركة الداخلية. يتم رفض
الطلبات الخارجية التي تحتوي على ترويسة `X-Email` مزوّرة بواسطة nginx.

## لماذا قاعدتا بيانات

يستخدم Cat-Scan كلًا من Postgres وBigQuery لأدوار مختلفة:

| الجانب | Postgres (Cloud SQL) | BigQuery |
|---------|---------------------|----------|
| **الدور** | قاعدة بيانات تشغيلية: تخدم التطبيق | مستودع بيانات: يخزّن البيانات الخام، يُشغّل التحليلات الدفعية |
| **نموذج التكلفة** | تكلفة استضافة ثابتة، استعلامات غير محدودة | الدفع لكل استعلام بناءً على البيانات المُمسوحة |
| **زمن الاستجابة** | استجابات بالمللي ثانية | حمل إضافي يتراوح بين 1-3 ثوانٍ حتى للاستعلامات البسيطة |
| **التزامن** | يتعامل مع مئات اتصالات API | غير مُصمّم لتحديثات لوحة المعلومات المتزامنة |
| **البيانات** | ملخصات مُجمّعة مسبقًا، إعدادات، بيانات المستخدمين | صفوف خام تفصيلية (ملايين يوميًا) |

النمط: BigQuery هو مستودع الأرشيف؛ Postgres هو رف المتجر.
لا تُرسل العملاء للبحث في المستودع.

## الهيكل الرئيسي لقاعدة الشيفرة

```
/api/routers/       FastAPI route handlers (118+ endpoints)
/services/          Business logic layer
/storage/           Database access (Postgres repos, BigQuery clients)
/dashboard/src/     Next.js 14 frontend (App Router)
/scripts/           Operational and diagnostic scripts
docs.rtb.cat/       Public documentation portal
```

تتبع الواجهة الخلفية نمط **Router -> Service -> Repository**. تتعامل الموجّهات
مع HTTP؛ تحتوي الخدمات على منطق الأعمال؛ وتُنفّذ المستودعات استعلامات SQL.

## مواضيع ذات صلة

- [النشر](12-deployment.md): كيف يُنشر النظام
- [عمليات قاعدة البيانات](14-database.md): تفاصيل Postgres
- [التكاملات](17-integrations.md): اتصالات الخدمات الخارجية
