# Rozdział 12: Wdrożenie

*Odbiorcy: DevOps, inżynierowie platformy*

## Potok CI/CD

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

### Dlaczego wdrożenie jest ręczne

Automatyczne wdrożenie przy push zostało wyłączone po incydencie ze stycznia 2026, kiedy automatyczne wdrożenia kolidowały z ręcznymi wdrożeniami przez SSH, co powodowało uszkodzenie kontenerów i utratę danych. Workflow wdrożeniowy wymaga teraz:

1. Ręcznego uruchomienia przez interfejs GitHub Actions („Run workflow")
2. Jawnego wyboru środowiska docelowego (staging lub produkcja)
3. Wpisania `DEPLOY` jako potwierdzenia
4. Opcjonalnego podania powodu dla ścieżki audytu

### Tagi obrazów

Obrazy są tagowane skróconym SHA commitu: `sha-XXXXXXX`. Krok wdrożeniowy używa `GITHUB_SHA` do skonstruowania tagu, dzięki czemu wdrożona wersja zawsze odpowiada konkretnemu commitowi.

## Jak wdrożyć

1. Sprawdź, czy budowanie przeszło pomyślnie: `gh run list --workflow=build-and-push.yml --limit=1`
2. Uruchom wdrożenie:
   ```bash
   gh workflow run deploy.yml \
     --ref main \
     -f target=production \
     -f confirm=DEPLOY \
     -f reason="your reason here"
   ```
3. Monitoruj: `gh run watch <run_id> --exit-status`
4. Zweryfikuj: `curl -sS https://your-deployment.example.com/api/health | jq -r '.git_sha,.version'`

## Weryfikacja wdrożenia

Endpoint `/api/health` zwraca:

```json
{
  "git_sha": "94e9cbb0",
  "version": "sha-94e9cbb"
}
```

Porównaj `git_sha` z commitem, który zamierzałeś wdrożyć.

## Sprawdzenie kontraktów po wdrożeniu

Po wdrożeniu workflow uruchamia `scripts/contracts_check.py` wewnątrz kontenera API. Skrypt waliduje, czy kontrakty danych (niepodlegające negocjacji reguły od importu po wyjście API) są zachowane. Jeśli sprawdzenie zakończy się niepowodzeniem:

- Przy `ALLOW_CONTRACT_FAILURE=false` (domyślnie): wdrożenie jest oznaczane jako nieudane.
- Przy `ALLOW_CONTRACT_FAILURE=true` (tymczasowe obejście): wdrożenie kończy się sukcesem z ostrzeżeniem. To obejście musi zostać usunięte po wyjaśnieniu problemu.

## Staging a produkcja

| Środowisko | Nazwa VM | Domena |
|------------|----------|--------|
| Staging | `catscan-vm` | (wewnętrzna) |
| Produkcja | `catscan-vm` | `your-deployment.example.com` |

Najpierw wdróż na staging, zweryfikuj, a potem wdróż na produkcję.

## Wycofanie zmian (rollback)

Aby wycofać zmiany, wdróż poprzedni sprawdzony commit:

1. Zidentyfikuj ostatni poprawny SHA z historii gita lub poprzednich uruchomień wdrożenia.
2. Przełącz się na ten SHA w gałęzi main (lub użyj `--ref` z commitem).
3. Uruchom workflow wdrożeniowy.

Nie ma dedykowanego mechanizmu rollbacku. To po prostu wdrożenie starszej wersji.

## Powiązane

- [Przegląd architektury](11-architecture.md): co jest wdrażane
- [Monitoring stanu systemu](13-health-monitoring.md): weryfikacja poprawności wdrożenia
