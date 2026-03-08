# Глава 12: Развёртывание

*Аудитория: DevOps, платформенные инженеры*

## CI/CD-конвейер

```
Push to main
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

### Почему развёртывание запускается вручную

Автоматическое развёртывание при пуше было отключено после инцидента в январе 2026 года, когда автоматические деплои конкурировали с ручными SSH-деплоями, что привело к повреждению контейнеров и потере данных. Теперь для запуска развёртывания необходимо:

1. Ручной запуск через интерфейс GitHub Actions («Run workflow»)
2. Явный выбор целевого окружения (staging или production)
3. Ввод `DEPLOY` для подтверждения
4. Необязательное поле с причиной для журнала аудита

### Теги образов

Образы помечаются коротким SHA коммита: `sha-XXXXXXX`. На этапе развёртывания используется `GITHUB_SHA` для формирования тега, поэтому развёрнутая версия всегда соответствует конкретному коммиту.

## Как выполнить развёртывание

1. Убедитесь, что сборка прошла успешно: `gh run list --workflow=build-and-push.yml --limit=1`
2. Запустите развёртывание:
   ```bash
   gh workflow run deploy.yml \
     --ref main \
     -f target=production \
     -f confirm=DEPLOY \
     -f reason="your reason here"
   ```
3. Отслеживайте выполнение: `gh run watch <run_id> --exit-status`
4. Проверьте результат: `curl -sS https://your-deployment.example.com/api/health | jq -r '.git_sha,.version'`

## Проверка развёртывания

Эндпоинт `/api/health` возвращает:

```json
{
  "git_sha": "94e9cbb0",
  "version": "sha-94e9cbb"
}
```

Сравните `git_sha` с SHA коммита, который вы планировали развернуть.

## Проверка контрактов после развёртывания

После развёртывания рабочий процесс запускает `scripts/contracts_check.py` внутри API-контейнера. Скрипт проверяет соблюдение контрактов данных (неизменных правил от импорта до вывода через API). Если проверка не пройдена:

- При `ALLOW_CONTRACT_FAILURE=false` (по умолчанию): развёртывание помечается как неуспешное.
- При `ALLOW_CONTRACT_FAILURE=true` (временный обход): развёртывание считается успешным, но выводится предупреждение. Этот обход необходимо убрать после расследования.

## Staging и production

| Окружение | Имя ВМ | Домен |
|-----------|--------|-------|
| Staging | `catscan-vm` | (внутренний) |
| Production | `catscan-vm` | `your-deployment.example.com` |

Сначала разверните на staging, проверьте, затем разверните на production.

## Откат

Чтобы выполнить откат, разверните предыдущий заведомо рабочий коммит:

1. Определите последний рабочий SHA из git log или предыдущих запусков развёртывания.
2. Переключитесь на этот SHA в ветке main (или используйте `--ref` с нужным коммитом).
3. Запустите рабочий процесс развёртывания.

Специального механизма отката нет — это просто развёртывание более старой версии.

## Связанные разделы

- [Обзор архитектуры](11-architecture.md): что именно развёртывается
- [Мониторинг состояния](13-health-monitoring.md): проверка успешности развёртывания
