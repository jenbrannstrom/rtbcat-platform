# Розділ 11: Огляд архітектури

*Аудиторія: DevOps, платформні інженери*

## Топологія системи

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

## Компонування контейнерів

Продакшн працює на одній GCP VM (`catscan-production-sg`, зона
`asia-southeast1-b`) з використанням `docker-compose.gcp.yml`.

| Контейнер | Образ | Порт | Роль |
|-----------|-------|------|------|
| `catscan-api` | `asia-southeast1-docker.pkg.dev/.../api:sha-XXXXXXX` | 8000 | FastAPI бекенд |
| `catscan-dashboard` | `asia-southeast1-docker.pkg.dev/.../dashboard:sha-XXXXXXX` | 3000 | Next.js фронтенд |
| `oauth2-proxy` | стандартний образ oauth2-proxy | 4180 | Автентифікація Google OAuth2 |
| `cloudsql-proxy` | Google Cloud SQL Auth Proxy | 5432 | Проксі з'єднання з Postgres |
| `nginx` | стандартний nginx із конфігурацією | 80/443 | Зворотний проксі, TLS, маршрутизація |

## Ланцюг довіри автентифікації

```
Browser → nginx → OAuth2 Proxy → sets X-Email header → nginx → API
```

1. Браузер звертається до nginx.
2. nginx маршрутизує `/oauth2/*` до OAuth2 Proxy.
3. OAuth2 Proxy автентифікує через Google та встановлює заголовок `X-Email`.
4. Наступні запити проходять через nginx із заголовком `X-Email`.
5. API читає `X-Email` і довіряє йому (коли `OAUTH2_PROXY_ENABLED=true`).

**Важливо:** API довіряє заголовку `X-Email` лише від внутрішнього трафіку.
Зовнішні запити з підробленим заголовком `X-Email` відхиляються nginx.

## Чому дві бази даних

Cat-Scan використовує як Postgres, так і BigQuery для різних ролей:

| Аспект | Postgres (Cloud SQL) | BigQuery |
|--------|---------------------|----------|
| **Роль** | Операційна база даних: обслуговує додаток | Сховище даних: зберігає необроблені дані, виконує пакетну аналітику |
| **Модель витрат** | Фіксована вартість хостингу, необмежені запити | Оплата за запит на основі обсягу сканованих даних |
| **Затримка** | Відповіді за мілісекунди | Накладні витрати 1--3 секунди навіть для простих запитів |
| **Паралельність** | Обробляє сотні API-з'єднань | Не розрахований на одночасне оновлення панелей |
| **Дані** | Попередньо агреговані зведення, конфігурації, дані користувачів | Необроблені гранулярні рядки (мільйони на день) |

Принцип: BigQuery — це архівний склад; Postgres — це полиця магазину.
Ви не відправляєте клієнтів перебирати склад.

## Ключова структура кодової бази

```
/api/routers/       FastAPI route handlers (118+ endpoints)
/services/          Business logic layer
/storage/           Database access (Postgres repos, BigQuery clients)
/dashboard/src/     Next.js 14 frontend (App Router)
/scripts/           Operational and diagnostic scripts
/docs/              Architecture docs and AI agent logs
```

Бекенд дотримується патерну **Router -> Service -> Repository**. Маршрутизатори
обробляють HTTP; сервіси містять бізнес-логіку; репозиторії виконують SQL.

## Пов'язане

- [Розгортання](12-deployment.md): як система розгортається
- [Операції з базою даних](14-database.md): деталі Postgres
- [Інтеграції](17-integrations.md): підключення до зовнішніх сервісів
