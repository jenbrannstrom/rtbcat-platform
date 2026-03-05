# Rozdział 15: Podręcznik rozwiązywania problemów

*Odbiorcy: DevOps, inżynierowie platformy*

## Pętla logowania

**Objawy:** Użytkownik trafia na stronę logowania, uwierzytelnia się, zostaje przekierowany z powrotem na stronę logowania i pętla się powtarza w nieskończoność.

**Wzorzec pierwotnej przyczyny:** Dowolna awaria bazy danych powoduje, że `_get_or_create_oauth2_user()` kończy się cichym błędem. `/auth/check` zwraca `{authenticated: false}`. Frontend przekierowuje do `/oauth2/sign_in`. Pętla.

**Typowe wyzwalacze:**
- Kontener Cloud SQL Proxy umarł lub został zrestartowany bez restartu API
- Partycja sieciowa między VM a instancją Cloud SQL
- Konserwacja lub restart instancji Cloud SQL

**Wykrywanie:**
- Przeglądarka: licznik przekierowań uruchamia się po 2 przekierowaniach w ciągu 30 sekund, wyświetlając interfejs błędu/ponowienia zamiast pętli
- API: `/auth/check` zwraca HTTP 503 (nie 200), gdy baza danych jest nieosiągalna, z `auth_error` w odpowiedzi
- Logi: szukaj błędów odmowy połączenia lub przekroczenia limitu czasu w logach catscan-api

**Naprawa:**
1. Sprawdź Cloud SQL Proxy: `sudo docker ps | grep cloudsql`
2. Jeśli nie działa: `sudo docker compose -f docker-compose.gcp.yml restart cloudsql-proxy`
3. Odczekaj 10 sekund, a następnie zrestartuj API:
   `sudo docker compose -f docker-compose.gcp.yml restart api`
4. Zweryfikuj: `curl -sS http://localhost:8000/health`

**Zapobieganie:** Trójwarstwowa poprawka (wdrożona w lutym 2026):
1. Backend propaguje błędy bazy danych przez `request.state.auth_error`
2. `/auth/check` zwraca 503, gdy baza danych jest nieosiągalna
3. Frontend posiada licznik przekierowań (max 2 w 30s) + interfejs błędu/ponowienia

## Przekroczenie limitu czasu świeżości danych

**Objawy:** `/uploads/data-freshness` zwraca 500, przekracza limit czasu lub bramka zdrowia w czasie działania pokazuje BLOCKED na stanie danych.

**Wzorzec pierwotnej przyczyny:** Zapytanie o świeżość danych skanuje duże tabele (`rtb_daily` z 84M wierszami, `rtb_bidstream` z 21M wierszami). Jeśli plan zapytania zdegraduje się do skanowania sekwencyjnego zamiast korzystania z indeksów, wykonanie może trwać 160+ sekund.

**Wykrywanie:**
1. Wywołaj endpoint bezpośrednio z VM:
   ```bash
   curl -sS --max-time 60 -H 'X-Email: user.com' \
     'http://localhost:8000/uploads/data-freshness?days=14&buyer_id=<ID>'
   ```
2. Jeśli przekracza limit czasu lub zwraca 500, sprawdź plan zapytania:
   ```bash
   sudo docker exec catscan-api python -c "
   import os, psycopg
   conn = psycopg.connect(os.environ['POSTGRES_DSN'])
   for r in conn.execute('EXPLAIN (ANALYZE, BUFFERS) <query>').fetchall():
       print(list(r.values())[0])
   "
   ```
3. Szukaj `Parallel Seq Scan` na dużych tabelach. To jest problem.

**Wzorzec naprawy:**
- Przepisz zapytania GROUP BY na `generate_series + EXISTS`, aby wymusić wyszukiwanie indeksowe. Zobacz [Operacje bazodanowe](14-database.md) po wzorzec.
- Upewnij się, że używane jest `SET LOCAL statement_timeout` (nie `SET` + `RESET`).
- Sprawdź, czy indeksy `(buyer_account_id, metric_date DESC)` istnieją na wszystkich docelowych tabelach.

## Awaria importu z Gmaila

**Objawy:** Siatka świeżości danych pokazuje komórki „brakujące" dla ostatnich dat. Historia importu nie ma ostatnich wpisów.

**Wykrywanie:**
```bash
curl -sS -H 'X-Email: user.com' \
  http://localhost:8000/gmail/status
```

Sprawdź: `last_reason`, liczbę `unread`, `latest_metric_date`.

**Typowe przyczyny:**
- Wygasł token OAuth Gmaila: ponownie autoryzuj w `/settings/accounts` > zakładka Gmail
- Cloud SQL Proxy nie działa: import Gmaila zapisuje do Postgres, więc baza danych musi być osiągalna
- Duża liczba `unread` (30+): import może utknąć w przetwarzaniu lub skrzynka ma zaległości

**Naprawa:**
1. Jeśli `last_reason` pokazuje błąd: zrestartuj zadanie importu z UI lub API
2. Jeśli token wygasł: ponownie autoryzuj integrację z Gmailem
3. Jeśli Cloud SQL nie działa: najpierw napraw połączenie z bazą danych (patrz pętla logowania)

## Kolejność restartowania kontenerów

**Objaw:** Logi API pokazują „connection refused" do portu 5432 przy starcie.

**Przyczyna:** Kontener API uruchomił się, zanim Cloud SQL Proxy był gotowy.

**Naprawa:** Zrestartuj we właściwej kolejności:
```bash
sudo docker compose -f docker-compose.gcp.yml up -d cloudsql-proxy
sleep 10
sudo docker compose -f docker-compose.gcp.yml up -d api
```

Lub zrestartuj wszystko (compose obsługuje zależności):
```bash
sudo docker compose -f docker-compose.gcp.yml up -d --force-recreate
```

## Błąd składni SET statement_timeout

**Objaw:** Endpoint zwraca 500 z błędem:
`syntax error at or near "$1" LINE 1: SET statement_timeout = $1`

**Przyczyna:** psycopg3 konwertuje `%s` na `$1` dla wiązania parametrów po stronie serwera, ale polecenie PostgreSQL `SET` nie obsługuje znaczników parametrów.

**Naprawa:** Użyj f-stringa ze zwalidowaną liczbą całkowitą:
```python
# Wrong:
conn.execute("SET statement_timeout = %s", (timeout_ms,))

# Right:
timeout_ms = max(int(statement_timeout_ms), 1)  # validated int
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
```

## Niepowodzenie bramki zdrowia w czasie działania

**Objaw:** Workflow `v1-runtime-health-strict.yml` kończy się niepowodzeniem.

**Segregacja:**
1. Sprawdź logi workflow: `gh run view <id> --log-failed`
2. Szukaj FAIL versus BLOCKED:
   - **FAIL** = coś się zepsuło, zbadaj
   - **BLOCKED** = brakuje zależności (brak danych, brak endpointu), może być problemem wcześniej istniejącym
3. Typowe wcześniej istniejące powody BLOCKED:
   - „rtb_quality_freshness state is unavailable": brak danych jakościowych dla tego kupującego/okresu
   - „proposal has no billing_id": problem z konfiguracją danych
   - „QPS page API rollup missing required paths": endpoint analityczny jeszcze nie wypełniony
4. Porównaj z poprzednimi uruchomieniami, aby odróżnić regresje od wcześniej istniejących problemów.

## Powiązane

- [Monitoring stanu systemu](13-health-monitoring.md): narzędzia monitorujące
- [Operacje bazodanowe](14-database.md): szczegóły zapytań i indeksów
- [Wdrożenie](12-deployment.md): wdrażanie poprawek
