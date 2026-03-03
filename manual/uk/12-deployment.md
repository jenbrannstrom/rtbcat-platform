# Розділ 12: Розгортання

*Аудиторія: DevOps, платформні інженери*

## CI/CD конвеєр

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

### Чому розгортання виконується вручну

Автоматичне розгортання при push було вимкнено після інциденту в січні 2026 року, коли автоматичні розгортання конфліктували з ручними SSH-розгортаннями, пошкоджуючи контейнери та спричиняючи втрату даних. Робочий процес розгортання тепер вимагає:

1. Ручного запуску через інтерфейс GitHub Actions ("Run workflow")
2. Явного вибору цільового середовища (staging або production)
3. Введення `DEPLOY` як підтвердження
4. Необов'язкового поля причини для журналу аудиту

### Теги образів

Образи позначаються скороченим git SHA: `sha-XXXXXXX`. Крок розгортання використовує `GITHUB_SHA` для формування тегу, тому розгорнута версія завжди відповідає конкретному коміту.

## Як виконати розгортання

1. Переконайтеся, що збірка пройшла успішно: `gh run list --workflow=build-and-push.yml --limit=1`
2. Запустіть розгортання:
   ```bash
   gh workflow run deploy.yml \
     --ref unified-platform \
     -f target=production \
     -f confirm=DEPLOY \
     -f reason="your reason here"
   ```
3. Моніторинг: `gh run watch <run_id> --exit-status`
4. Перевірка: `curl -sS https://scan.rtb.cat/api/health | jq -r '.git_sha,.version'`

## Перевірка розгортання

Ендпоінт `/api/health` повертає:

```json
{
  "git_sha": "94e9cbb0",
  "version": "sha-94e9cbb"
}
```

Порівняйте `git_sha` з комітом, який ви планували розгорнути.

## Перевірка контрактів після розгортання

Після розгортання робочий процес запускає `scripts/contracts_check.py` всередині контейнера API. Це перевіряє, що контракти даних (непорушні правила від імпорту до виведення через API) дотримуються. Якщо перевірка не пройшла:

- З `ALLOW_CONTRACT_FAILURE=false` (за замовчуванням): розгортання позначається як невдале.
- З `ALLOW_CONTRACT_FAILURE=true` (тимчасовий обхід): розгортання завершується успішно з попередженням. Цей обхід необхідно видалити після розслідування.

## Staging та production

| Середовище | Назва VM | Домен |
|------------|----------|-------|
| Staging | `catscan-production-sg2` | (внутрішній) |
| Production | `catscan-production-sg` | `scan.rtb.cat` |

Спершу розгортайте на staging, перевірте, а потім розгортайте на production.

## Відкат

Для відкату розгорніть попередній стабільний коміт:

1. Визначте останній стабільний SHA з git log або попередніх запусків розгортання.
2. Переключіться на цей SHA у гілці unified-platform (або використайте `--ref` із зазначенням коміту).
3. Запустіть робочий процес розгортання.

Окремого механізму відкату не існує. Це просто розгортання старішої версії.

## Пов'язані розділи

- [Огляд архітектури](11-architecture.md): що саме розгортається
- [Моніторинг стану](13-health-monitoring.md): перевірка успішності розгортання
