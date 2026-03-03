# Краткий справочник по API

Это навигационный указатель 118+ эндпоинтов API Cat-Scan, сгруппированных по
доменам. Полные схемы запросов и ответов доступны в интерактивной документации
OpenAPI по адресу `https://scan.rtb.cat/api/docs`.

## Ядро / Система

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/health` | Проверка доступности (git_sha, версия) |
| GET | `/stats` | Системная статистика |
| GET | `/sizes` | Доступные размеры объявлений |
| GET | `/system/status` | Состояние сервера (Python, Node, FFmpeg, БД, диск) |
| GET | `/system/data-health` | Полнота данных по покупателю |
| GET | `/system/ui-page-load-metrics` | Метрики производительности фронтенда |
| GET | `/geo/lookup` | Разрешение Geo ID в название |
| GET | `/geo/search` | Поиск стран/городов |

## Авторизация

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/auth/check` | Проверка аутентификации текущей сессии |
| POST | `/auth/logout` | Завершение сессии |

## Места (Seats)

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/seats` | Список мест покупателей |
| GET | `/seats/{buyer_id}` | Получение конкретного места |
| PUT | `/seats/{buyer_id}` | Обновление отображаемого имени места |
| POST | `/seats/populate` | Автоматическое создание мест из данных |
| POST | `/seats/discover` | Обнаружение мест через Google API |
| POST | `/seats/{buyer_id}/sync` | Синхронизация конкретного места |
| POST | `/seats/sync-all` | Полная синхронизация (все места) |
| POST | `/seats/collect-creatives` | Сбор данных о креативах |

## Креативы

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/creatives` | Список креативов (с фильтрами) |
| GET | `/creatives/paginated` | Постраничный список креативов |
| GET | `/creatives/{id}` | Детали креатива |
| GET | `/creatives/{id}/live` | Актуальные данные креатива (с учетом кэша) |
| GET | `/creatives/{id}/destination-diagnostics` | Состояние целевого URL |
| GET | `/creatives/{id}/countries` | Разбивка эффективности по странам |
| GET | `/creatives/{id}/geo-linguistic` | Геолингвистический анализ |
| POST | `/creatives/{id}/detect-language` | Автоопределение языка |
| PUT | `/creatives/{id}/language` | Ручное переопределение языка |
| GET | `/creatives/thumbnail-status` | Пакетный статус миниатюр |
| POST | `/creatives/thumbnails/batch` | Генерация недостающих миниатюр |

## Кампании

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/campaigns` | Список кампаний |
| GET | `/campaigns/{id}` | Детали кампании |
| GET | `/campaigns/ai` | Кластеры, сгенерированные AI |
| GET | `/campaigns/ai/{id}` | Детали AI-кампании |
| PUT | `/campaigns/ai/{id}` | Обновление кампании |
| DELETE | `/campaigns/ai/{id}` | Удаление кампании |
| GET | `/campaigns/ai/{id}/creatives` | Креативы кампании |
| DELETE | `/campaigns/ai/{id}/creatives/{creative_id}` | Удаление креатива из кампании |
| POST | `/campaigns/auto-cluster` | Автоматическая AI-кластеризация |
| GET | `/campaigns/ai/{id}/performance` | Эффективность кампании |
| GET | `/campaigns/ai/{id}/daily-trend` | Данные о тренде кампании |

## Аналитика

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/analytics/waste-report` | Общие метрики потерь |
| GET | `/analytics/size-coverage` | Покрытие по размерам таргетинга |
| GET | `/analytics/rtb-funnel` | Разбивка RTB-воронки |
| GET | `/analytics/rtb-funnel/configs` | Воронка на уровне конфигов |
| GET | `/analytics/endpoint-efficiency` | Эффективность QPS по эндпоинтам |
| GET | `/analytics/spend-stats` | Статистика расходов |
| GET | `/analytics/config-performance` | Эффективность конфигов во времени |
| GET | `/analytics/config-performance/breakdown` | Разбивка по полям конфига |
| GET | `/analytics/qps-recommendations` | AI-рекомендации |
| GET | `/analytics/performance/batch` | Пакетная эффективность креативов |
| GET | `/analytics/performance/{creative_id}` | Эффективность отдельного креатива |
| GET | `/analytics/publishers` | Метрики по доменам издателей |
| GET | `/analytics/publishers/search` | Поиск издателей |
| GET | `/analytics/languages` | Эффективность по языкам |
| GET | `/analytics/languages/multi` | Анализ по нескольким языкам |
| GET | `/analytics/geo-performance` | Географическая эффективность |
| GET | `/analytics/geo-performance/multi` | Анализ по нескольким регионам |
| POST | `/analytics/import` | Импорт CSV |
| POST | `/analytics/mock-traffic` | Генерация тестовых данных |

## Настройки / Претаргетинг

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/settings/rtb-endpoints` | RTB-эндпоинты биддера |
| POST | `/settings/rtb-endpoints/sync` | Синхронизация данных эндпоинтов |
| GET | `/settings/pretargeting-configs` | Список конфигов претаргетинга |
| GET | `/settings/pretargeting-configs/{id}` | Детали конфига |
| GET | `/settings/pretargeting-history` | История изменений конфигов |
| POST | `/settings/pretargeting-configs/sync` | Синхронизация конфигов из Google |
| POST | `/settings/pretargeting-configs/{id}/apply` | Применение изменения конфига |
| POST | `/settings/pretargeting-configs/apply-all` | Применение всех ожидающих изменений |
| PUT | `/settings/pretargeting-configs/{id}` | Пакетное обновление конфига |

## Загрузки

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/uploads/tracking` | Ежедневная сводка загрузок |
| GET | `/uploads/import-matrix` | Статус импорта по типам отчетов |
| GET | `/uploads/data-freshness` | Таблица актуальности данных (дата x тип) |
| GET | `/uploads/history` | История импорта |

## Оптимизатор

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/optimizer/models` | Список BYOM-моделей |
| POST | `/optimizer/models` | Регистрация модели |
| PUT | `/optimizer/models/{id}` | Обновление модели |
| POST | `/optimizer/models/{id}/activate` | Активация модели |
| POST | `/optimizer/models/{id}/deactivate` | Деактивация модели |
| POST | `/optimizer/models/{id}/validate` | Тестирование эндпоинта модели |
| POST | `/optimizer/score-and-propose` | Генерация предложений |
| GET | `/optimizer/proposals` | Список активных предложений |
| GET | `/optimizer/proposals/history` | История предложений |
| POST | `/optimizer/proposals/{id}/approve` | Одобрение предложения |
| POST | `/optimizer/proposals/{id}/apply` | Применение предложения |
| POST | `/optimizer/proposals/{id}/sync-status` | Проверка статуса применения |
| GET | `/optimizer/segment-scores` | Оценки на уровне сегментов |
| GET | `/optimizer/economics/efficiency` | Сводка эффективности |
| GET | `/optimizer/economics/effective-cpm` | Анализ CPM |
| GET | `/optimizer/setup` | Конфигурация оптимизатора |
| PUT | `/optimizer/setup` | Обновление конфигурации оптимизатора |

## Конверсии

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/conversions/health` | Статус приема и агрегации |
| GET | `/conversions/readiness` | Проверка готовности источника |
| GET | `/conversions/ingestion-stats` | Количество событий по источнику/периоду |
| GET | `/conversions/security/status` | Статус безопасности вебхуков |
| GET | `/conversions/pixel` | Эндпоинт пиксельного отслеживания |

## Снимки

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/snapshots` | Список снимков конфигов |
| POST | `/snapshots/rollback` | Восстановление снимка (с пробным прогоном) |

## Интеграции

| Метод | Путь | Назначение |
|-------|------|------------|
| POST | `/integrations/credentials` | Загрузка JSON сервисного аккаунта GCP |
| GET | `/integrations/service-accounts` | Список сервисных аккаунтов |
| DELETE | `/integrations/service-accounts/{id}` | Удаление сервисного аккаунта |
| GET | `/integrations/language-ai/config` | Статус AI-провайдера |
| PUT | `/integrations/language-ai/config` | Настройка AI-провайдера |
| GET | `/integrations/gmail/status` | Статус импорта через Gmail |
| POST | `/integrations/gmail/import/start` | Запуск ручного импорта |
| POST | `/integrations/gmail/import/stop` | Остановка задачи импорта |
| GET | `/integrations/gmail/import/history` | История импорта |
| GET | `/integrations/gcp/project-status` | Состояние GCP-проекта |
| POST | `/integrations/gcp/validate` | Тестирование подключения к GCP |

## Администрирование

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/admin/users` | Список пользователей |
| POST | `/admin/users` | Создание пользователя |
| GET | `/admin/users/{id}` | Детали пользователя |
| PUT | `/admin/users/{id}` | Обновление пользователя |
| POST | `/admin/users/{id}/deactivate` | Деактивация пользователя |
| GET | `/admin/users/{id}/permissions` | Глобальные разрешения пользователя |
| GET | `/admin/users/{id}/seat-permissions` | Разрешения пользователя по местам |
| POST | `/admin/users/{id}/seat-permissions` | Предоставление доступа к месту |
| DELETE | `/admin/users/{id}/seat-permissions/{buyer_id}` | Отзыв доступа к месту |
| POST | `/admin/users/{id}/permissions` | Предоставление глобального разрешения |
| DELETE | `/admin/users/{id}/permissions/{sa_id}` | Отзыв глобального разрешения |
| GET | `/admin/audit-log` | Журнал аудита |
| GET | `/admin/stats` | Статистика панели администратора |
| GET | `/admin/settings` | Системная конфигурация |
| PUT | `/admin/settings/{key}` | Обновление системной настройки |
