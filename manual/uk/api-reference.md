# Короткий довідник API

Це навігаційний індекс 118+ ендпоінтів API Cat-Scan, згрупованих за доменом.
Для повних схем запитів/відповідей дивіться інтерактивну документацію OpenAPI
за адресою `https://scan.rtb.cat/api/docs`.

## Основні / Системні

| Метод | Шлях | Призначення |
|-------|------|-------------|
| GET | `/health` | Перевірка живучості (git_sha, version) |
| GET | `/stats` | Системна статистика |
| GET | `/sizes` | Доступні розміри оголошень |
| GET | `/system/status` | Стан сервера (Python, Node, FFmpeg, БД, диск) |
| GET | `/system/data-health` | Повнота даних по баєрах |
| GET | `/system/ui-page-load-metrics` | Метрики продуктивності фронтенду |
| GET | `/geo/lookup` | Перетворення ідентифікатора географії на назву |
| GET | `/geo/search` | Пошук країн/міст |

## Автентифікація

| Метод | Шлях | Призначення |
|-------|------|-------------|
| GET | `/auth/check` | Перевірка автентифікації поточної сесії |
| POST | `/auth/logout` | Завершення сесії |

## Сіти

| Метод | Шлях | Призначення |
|-------|------|-------------|
| GET | `/seats` | Перелік сітів баєрів |
| GET | `/seats/{buyer_id}` | Отримання конкретного сіта |
| PUT | `/seats/{buyer_id}` | Оновлення відображуваного імені сіта |
| POST | `/seats/populate` | Автоматичне створення сітів із даних |
| POST | `/seats/discover` | Виявлення сітів через Google API |
| POST | `/seats/{buyer_id}/sync` | Синхронізація конкретного сіта |
| POST | `/seats/sync-all` | Повна синхронізація (усі сіти) |
| POST | `/seats/collect-creatives` | Збір даних про креативи |

## Креативи

| Метод | Шлях | Призначення |
|-------|------|-------------|
| GET | `/creatives` | Перелік креативів (із фільтрами) |
| GET | `/creatives/paginated` | Посторінковий перелік креативів |
| GET | `/creatives/{id}` | Деталі креативу |
| GET | `/creatives/{id}/live` | Актуальні дані креативу (з урахуванням кешу) |
| GET | `/creatives/{id}/destination-diagnostics` | Стан URL призначення |
| GET | `/creatives/{id}/countries` | Розбивка ефективності за країнами |
| GET | `/creatives/{id}/geo-linguistic` | Геолінгвістичний аналіз |
| POST | `/creatives/{id}/detect-language` | Автоматичне визначення мови |
| PUT | `/creatives/{id}/language` | Ручне перевизначення мови |
| GET | `/creatives/thumbnail-status` | Пакетний статус мініатюр |
| POST | `/creatives/thumbnails/batch` | Генерація відсутніх мініатюр |

## Кампанії

| Метод | Шлях | Призначення |
|-------|------|-------------|
| GET | `/campaigns` | Перелік кампаній |
| GET | `/campaigns/{id}` | Деталі кампанії |
| GET | `/campaigns/ai` | Кластери, згенеровані AI |
| GET | `/campaigns/ai/{id}` | Деталі AI-кампанії |
| PUT | `/campaigns/ai/{id}` | Оновлення кампанії |
| DELETE | `/campaigns/ai/{id}` | Видалення кампанії |
| GET | `/campaigns/ai/{id}/creatives` | Креативи кампанії |
| DELETE | `/campaigns/ai/{id}/creatives/{creative_id}` | Видалення креативу з кампанії |
| POST | `/campaigns/auto-cluster` | Автокластеризація AI |
| GET | `/campaigns/ai/{id}/performance` | Ефективність кампанії |
| GET | `/campaigns/ai/{id}/daily-trend` | Дані трендів кампанії |

## Аналітика

| Метод | Шлях | Призначення |
|-------|------|-------------|
| GET | `/analytics/waste-report` | Загальні метрики втрат |
| GET | `/analytics/size-coverage` | Покриття таргетингу за розміром |
| GET | `/analytics/rtb-funnel` | Розбивка воронки RTB |
| GET | `/analytics/rtb-funnel/configs` | Воронка на рівні конфігурацій |
| GET | `/analytics/endpoint-efficiency` | Ефективність QPS по ендпоінтах |
| GET | `/analytics/spend-stats` | Статистика витрат |
| GET | `/analytics/config-performance` | Ефективність конфігурацій у часі |
| GET | `/analytics/config-performance/breakdown` | Розбивка полів конфігурації |
| GET | `/analytics/qps-recommendations` | Рекомендації AI |
| GET | `/analytics/performance/batch` | Пакетна ефективність креативів |
| GET | `/analytics/performance/{creative_id}` | Ефективність окремого креативу |
| GET | `/analytics/publishers` | Метрики доменів паблішерів |
| GET | `/analytics/publishers/search` | Пошук паблішерів |
| GET | `/analytics/languages` | Ефективність за мовами |
| GET | `/analytics/languages/multi` | Аналіз кількох мов |
| GET | `/analytics/geo-performance` | Географічна ефективність |
| GET | `/analytics/geo-performance/multi` | Аналіз кількох географій |
| POST | `/analytics/import` | Імпорт CSV |
| POST | `/analytics/mock-traffic` | Генерація тестових даних |

## Налаштування / Претаргетинг

| Метод | Шлях | Призначення |
|-------|------|-------------|
| GET | `/settings/rtb-endpoints` | Ендпоінти RTB біддера |
| POST | `/settings/rtb-endpoints/sync` | Синхронізація даних ендпоінтів |
| GET | `/settings/pretargeting-configs` | Перелік конфігурацій претаргетингу |
| GET | `/settings/pretargeting-configs/{id}` | Деталі конфігурації |
| GET | `/settings/pretargeting-history` | Історія змін конфігурацій |
| POST | `/settings/pretargeting-configs/sync` | Синхронізація конфігурацій з Google |
| POST | `/settings/pretargeting-configs/{id}/apply` | Застосування зміни конфігурації |
| POST | `/settings/pretargeting-configs/apply-all` | Застосування всіх очікуваних змін |
| PUT | `/settings/pretargeting-configs/{id}` | Пакетне оновлення конфігурації |

## Завантаження

| Метод | Шлях | Призначення |
|-------|------|-------------|
| GET | `/uploads/tracking` | Щоденне зведення завантажень |
| GET | `/uploads/import-matrix` | Статус імпорту за типом звіту |
| GET | `/uploads/data-freshness` | Сітка свіжості даних (дата x тип) |
| GET | `/uploads/history` | Історія імпорту |

## Оптимізатор

| Метод | Шлях | Призначення |
|-------|------|-------------|
| GET | `/optimizer/models` | Перелік моделей BYOM |
| POST | `/optimizer/models` | Реєстрація моделі |
| PUT | `/optimizer/models/{id}` | Оновлення моделі |
| POST | `/optimizer/models/{id}/activate` | Активація моделі |
| POST | `/optimizer/models/{id}/deactivate` | Деактивація моделі |
| POST | `/optimizer/models/{id}/validate` | Тестування ендпоінта моделі |
| POST | `/optimizer/score-and-propose` | Генерація пропозицій |
| GET | `/optimizer/proposals` | Перелік активних пропозицій |
| GET | `/optimizer/proposals/history` | Історія пропозицій |
| POST | `/optimizer/proposals/{id}/approve` | Затвердження пропозиції |
| POST | `/optimizer/proposals/{id}/apply` | Застосування пропозиції |
| POST | `/optimizer/proposals/{id}/sync-status` | Перевірка статусу застосування |
| GET | `/optimizer/segment-scores` | Оцінки на рівні сегментів |
| GET | `/optimizer/economics/efficiency` | Зведення ефективності |
| GET | `/optimizer/economics/effective-cpm` | Аналіз CPM |
| GET | `/optimizer/setup` | Конфігурація оптимізатора |
| PUT | `/optimizer/setup` | Оновлення конфігурації оптимізатора |

## Конверсії

| Метод | Шлях | Призначення |
|-------|------|-------------|
| GET | `/conversions/health` | Стан отримання та агрегації |
| GET | `/conversions/readiness` | Перевірка готовності джерела |
| GET | `/conversions/ingestion-stats` | Кількість подій за джерелом/періодом |
| GET | `/conversions/security/status` | Статус безпеки вебхуків |
| GET | `/conversions/pixel` | Ендпоінт піксельного відстеження |

## Знімки

| Метод | Шлях | Призначення |
|-------|------|-------------|
| GET | `/snapshots` | Перелік знімків конфігурацій |
| POST | `/snapshots/rollback` | Відновлення знімка (з режимом dry-run) |

## Інтеграції

| Метод | Шлях | Призначення |
|-------|------|-------------|
| POST | `/integrations/credentials` | Завантаження JSON сервісного облікового запису GCP |
| GET | `/integrations/service-accounts` | Перелік сервісних облікових записів |
| DELETE | `/integrations/service-accounts/{id}` | Видалення сервісного облікового запису |
| GET | `/integrations/language-ai/config` | Статус провайдера AI |
| PUT | `/integrations/language-ai/config` | Налаштування провайдера AI |
| GET | `/integrations/gmail/status` | Статус імпорту Gmail |
| POST | `/integrations/gmail/import/start` | Запуск ручного імпорту |
| POST | `/integrations/gmail/import/stop` | Зупинка завдання імпорту |
| GET | `/integrations/gmail/import/history` | Історія імпорту |
| GET | `/integrations/gcp/project-status` | Стан проєкту GCP |
| POST | `/integrations/gcp/validate` | Тестування підключення GCP |

## Адміністрування

| Метод | Шлях | Призначення |
|-------|------|-------------|
| GET | `/admin/users` | Перелік користувачів |
| POST | `/admin/users` | Створення користувача |
| GET | `/admin/users/{id}` | Деталі користувача |
| PUT | `/admin/users/{id}` | Оновлення користувача |
| POST | `/admin/users/{id}/deactivate` | Деактивація користувача |
| GET | `/admin/users/{id}/permissions` | Глобальні дозволи користувача |
| GET | `/admin/users/{id}/seat-permissions` | Дозволи користувача по сітах |
| POST | `/admin/users/{id}/seat-permissions` | Надання доступу до сіта |
| DELETE | `/admin/users/{id}/seat-permissions/{buyer_id}` | Відкликання доступу до сіта |
| POST | `/admin/users/{id}/permissions` | Надання глобального дозволу |
| DELETE | `/admin/users/{id}/permissions/{sa_id}` | Відкликання глобального дозволу |
| GET | `/admin/audit-log` | Журнал аудиту |
| GET | `/admin/stats` | Статистика панелі адміністратора |
| GET | `/admin/settings` | Конфігурація системи |
| PUT | `/admin/settings/{key}` | Оновлення системного налаштування |
