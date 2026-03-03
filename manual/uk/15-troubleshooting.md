# Розділ 15: Посібник з усунення неполадок

*Аудиторія: DevOps, платформні інженери*

## Цикл входу в систему

**Симптоми:** Користувач потрапляє на сторінку входу, автентифікується, перенаправляється назад на сторінку входу, цикл повторюється нескінченно.

**Шаблон першопричини:** Будь-яка помилка бази даних спричиняє тихий збій `_get_or_create_oauth2_user()`. `/auth/check` повертає `{authenticated: false}`. Фронтенд перенаправляє на `/oauth2/sign_in`. Цикл.

**Типові тригери:**
- Контейнер Cloud SQL Proxy зупинився або був перезапущений без перезапуску API
- Мережевий розрив між VM та екземпляром Cloud SQL
- Обслуговування або перезапуск екземпляра Cloud SQL

**Виявлення:**
- Браузер: лічильник перенаправлень спрацьовує після 2 перенаправлень за 30 секунд, показуючи інтерфейс помилки/повтору замість циклу
- API: `/auth/check` повертає HTTP 503 (не 200), коли база даних недоступна, з `auth_error` у відповіді
- Логи: шукайте помилки connection refused або timeout у логах catscan-api

**Виправлення:**
1. Перевірте Cloud SQL Proxy: `sudo docker ps | grep cloudsql`
2. Якщо не працює: `sudo docker compose -f docker-compose.gcp.yml restart cloudsql-proxy`
3. Зачекайте 10 секунд, потім перезапустіть API:
   `sudo docker compose -f docker-compose.gcp.yml restart api`
4. Перевірка: `curl -sS http://localhost:8000/health`

**Запобігання:** Трирівневе виправлення (застосовано у лютому 2026):
1. Бекенд передає помилки БД через `request.state.auth_error`
2. `/auth/check` повертає 503, коли БД недоступна
3. Фронтенд має лічильник перенаправлень (макс. 2 за 30 с) + інтерфейс помилки/повтору

## Тайм-аут актуальності даних

**Симптоми:** `/uploads/data-freshness` повертає 500, перевищує час очікування, або шлюз перевірки стану показує BLOCKED на стані даних.

**Шаблон першопричини:** Запит актуальності даних сканує великі таблиці (`rtb_daily` на 84 млн рядків, `rtb_bidstream` на 21 млн рядків). Якщо план запиту деградує до послідовного сканування замість використання індексів, це може зайняти 160+ секунд.

**Виявлення:**
1. Виконайте запит до ендпоінту безпосередньо з VM:
   ```bash
   curl -sS --max-time 60 -H 'X-Email: cat-scan@rtb.cat' \
     'http://localhost:8000/uploads/data-freshness?days=14&buyer_id=<ID>'
   ```
2. Якщо перевищено час очікування або повернуто 500, перевірте план запиту:
   ```bash
   sudo docker exec catscan-api python -c "
   import os, psycopg
   conn = psycopg.connect(os.environ['POSTGRES_DSN'])
   for r in conn.execute('EXPLAIN (ANALYZE, BUFFERS) <query>').fetchall():
       print(list(r.values())[0])
   "
   ```
3. Шукайте `Parallel Seq Scan` на великих таблицях. Це і є проблема.

**Шаблон виправлення:**
- Перепишіть запити з GROUP BY на `generate_series + EXISTS` для примусового пошуку по індексу. Див. [Операції з базою даних](14-database.md) для деталей шаблону.
- Переконайтеся, що використовується `SET LOCAL statement_timeout` (а не `SET` + `RESET`).
- Перевірте, що індекси `(buyer_account_id, metric_date DESC)` існують на всіх цільових таблицях.

## Збій імпорту з Gmail

**Симптоми:** Сітка актуальності даних показує комірки "missing" для нещодавніх дат. В історії імпорту немає нових записів.

**Виявлення:**
```bash
curl -sS -H 'X-Email: cat-scan@rtb.cat' \
  http://localhost:8000/gmail/status
```

Перевірте: `last_reason`, кількість `unread`, `latest_metric_date`.

**Типові причини:**
- Закінчився термін дії токена Gmail OAuth: повторно авторизуйтесь у `/settings/accounts` > вкладка Gmail
- Cloud SQL Proxy не працює: імпорт з Gmail записує в Postgres, тому БД має бути доступна
- Велика кількість `unread` (30+): імпорт може зависнути під час обробки або в поштовій скриньці накопичилися необроблені листи

**Виправлення:**
1. Якщо `last_reason` показує помилку: перезапустіть завдання імпорту з інтерфейсу або API
2. Якщо закінчився термін дії токена: повторно авторизуйте інтеграцію з Gmail
3. Якщо Cloud SQL не працює: спершу виправте підключення до бази даних (див. цикл входу в систему)

## Порядок перезапуску контейнерів

**Симптом:** Логи API показують "connection refused" до порту 5432 при запуску.

**Причина:** Контейнер API запустився раніше, ніж Cloud SQL Proxy був готовий.

**Виправлення:** Перезапустіть у правильному порядку:
```bash
sudo docker compose -f docker-compose.gcp.yml up -d cloudsql-proxy
sleep 10
sudo docker compose -f docker-compose.gcp.yml up -d api
```

Або перезапустіть все (compose обробляє залежності):
```bash
sudo docker compose -f docker-compose.gcp.yml up -d --force-recreate
```

## Синтаксична помилка SET statement_timeout

**Симптом:** Ендпоінт повертає 500 з помилкою:
`syntax error at or near "$1" LINE 1: SET statement_timeout = $1`

**Причина:** psycopg3 перетворює `%s` на `$1` для серверного прив'язування параметрів, але команда PostgreSQL `SET` не підтримує заповнювачі параметрів.

**Виправлення:** Використовуйте f-string з валідованим цілим числом:
```python
# Wrong:
conn.execute("SET statement_timeout = %s", (timeout_ms,))

# Right:
timeout_ms = max(int(statement_timeout_ms), 1)  # validated int
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
```

## Збій шлюзу перевірки стану під час роботи

**Симптом:** Робочий процес `v1-runtime-health-strict.yml` завершується з помилкою.

**Сортування:**
1. Перевірте логи робочого процесу: `gh run view <id> --log-failed`
2. Зверніть увагу на FAIL або BLOCKED:
   - **FAIL** = щось зламалося, необхідне розслідування
   - **BLOCKED** = відсутня залежність (немає даних, немає ендпоінту), може бути вже наявною проблемою
3. Типові вже наявні причини BLOCKED:
   - "rtb_quality_freshness state is unavailable": немає даних якості для цього покупця/періоду
   - "proposal has no billing_id": проблема налаштування даних
   - "QPS page API rollup missing required paths": ендпоінт аналітики ще не заповнений
4. Порівняйте з попередніми запусками, щоб виявити регресії на відміну від вже наявних проблем.

## Пов'язані розділи

- [Моніторинг стану](13-health-monitoring.md): інструменти моніторингу
- [Операції з базою даних](14-database.md): деталі запитів та індексів
- [Розгортання](12-deployment.md): розгортання виправлень
