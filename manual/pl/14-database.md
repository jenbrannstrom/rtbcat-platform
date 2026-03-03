# Rozdział 14: Operacje bazodanowe

*Odbiorcy: DevOps, inżynierowie platformy*

## Postgres w produkcji

Cat-Scan używa Cloud SQL (Postgres 15) jako jedynej operacyjnej bazy danych. API łączy się przez kontener sidecar Cloud SQL Auth Proxy na `localhost:5432`.

### Kluczowe tabele i skala

| Tabela | Przybliżona liczba wierszy | Co przechowuje |
|--------|----------------------------|----------------|
| `rtb_daily` | ~84 miliony | Dzienne wyniki RTB na kupującego, kreację, lokalizację itp. |
| `rtb_bidstream` | ~21 milionów | Podział bidstreamu wg wydawcy, lokalizacji |
| `rtb_quality` | zmienna | Metryki jakości (widoczność, bezpieczeństwo marki) |
| `rtb_bid_filtering` | ~188 tysięcy | Powody filtrowania bidów i wolumeny |
| `pretargeting_configs` | niewielka | Snapshoty konfiguracji pretargetingu |
| `creatives` | niewielka | Metadane kreacji i miniatury |
| `import_history` | niewielka | Rekordy importu CSV |
| `users`, `permissions`, `audit_log` | niewielka | Dane uwierzytelniania i administracji |

### Krytyczne indeksy

Najważniejszy wzorzec indeksów pod kątem wydajności to:

```sql
CREATE INDEX idx_<table>_buyer_metric_date_desc
    ON <table> (buyer_account_id, metric_date DESC);
```

Istnieje on na tabelach `rtb_daily`, `rtb_bidstream`, `rtb_quality` i `rtb_bid_filtering`. Wspiera zapytanie o świeżość danych oraz analitykę ograniczoną do kupującego.

Inne ważne indeksy:
- `(metric_date, buyer_account_id)`: dla filtrów zakresu dat + kupujący
- `(metric_date, billing_id)`: dla zapytań ograniczonych do rozliczeń
- `(row_hash)` UNIQUE: deduplikacja przy imporcie

### Deduplikacja

Każdy importowany wiersz jest haszowany (kolumna `row_hash`). Ograniczenie unikalności na `row_hash` zapobiega duplikatom, dzięki czemu ponowny import jest bezpieczny.

## Model połączeń

API korzysta z **połączeń na żądanie** (bez puli połączeń). Każde zapytanie tworzy nowe wywołanie `psycopg.connect()`, opakowane w `run_in_executor` dla kompatybilności z asynchronicznością.

```python
async def pg_query(sql, params=()):
    loop = asyncio.get_event_loop()
    def _execute():
        with _get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    return await loop.run_in_executor(None, _execute)
```

W przypadku obciążeń produkcyjnych warto rozważyć dodanie `psycopg_pool`, jeśli narzut na tworzenie połączeń stanie się wąskim gardłem.

## Limity czasu zapytań

Dla kosztownych zapytań (np. świeżość danych na dużych tabelach) API używa `pg_query_with_timeout`:

```python
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
cursor = conn.execute(sql, params)
```

Kluczowe szczegóły:
- `SET LOCAL` ogranicza limit czasu do bieżącej transakcji i automatycznie resetuje się po jej zakończeniu (commit lub rollback).
- Domyślny limit czasu dla świeżości danych: 30 sekund.
- Konfigurowalny przez zmienną środowiskową `UPLOADS_DATA_FRESHNESS_QUERY_TIMEOUT_MS` (minimum 1000ms).
- `SET LOCAL` pozwala uniknąć problemu przerwanej transakcji, który występuje przy użyciu `SET` + `RESET` w bloku `try/finally` (jeśli zapytanie zostanie przerwane przez limit czasu, transakcja przechodzi w stan przerwany i `RESET` kończy się niepowodzeniem).

## Wzorzec zapytania o świeżość danych

Endpoint świeżości danych musi wiedzieć, dla jakich dat są dane dla każdego typu raportu. Wydajny wzorzec wykorzystuje `generate_series` + `EXISTS`:

```sql
SELECT d::date AS metric_date, 'bidsinauction' AS csv_type, 1 AS row_count
FROM generate_series(%s::date, CURRENT_DATE - 1, '1 day'::interval) AS d
WHERE EXISTS (
    SELECT 1 FROM rtb_daily
    WHERE metric_date = d::date AND buyer_account_id = %s
    LIMIT 1
)
```

Wykonuje to N wyszukiwań indeksowych (po jednym na dzień w oknie) zamiast skanowania milionów wierszy. Dla 14-dniowego okna: 14 wyszukiwań po ~0,1ms każde wobec pełnego równoległego skanowania sekwencyjnego, które trwa 160+ sekund.

**Dlaczego GROUP BY tu nie działa:** Nawet z `1 AS row_count` (bez COUNT) planista wybiera skanowanie sekwencyjne, gdy zbiór wynikowy GROUP BY jest duży w stosunku do tabeli. Indeks `(buyer_account_id, metric_date DESC)` istnieje, ale planista szacuje, że tańsze jest przeskanowanie 84M wierszy niż wykonanie 4,4M odczytów indeksowych.

## Rola BigQuery

BigQuery przechowuje surowe, szczegółowe dane i wykonuje wsadowe zadania analityczne. Nie jest używany do zapytań API w czasie rzeczywistym. Wzorzec:

1. Surowe dane CSV są ładowane do tabel BigQuery.
2. Zadania wsadowe agregują dane.
3. Wstępnie zagregowane wyniki są zapisywane do Postgres.
4. API serwuje dane z Postgres.

## Retencja danych

Konfigurowalna w `/settings/retention`. Kontroluje, jak długo dane historyczne są przechowywane w Postgres przed ich usunięciem.

## Powiązane

- [Przegląd architektury](11-architecture.md): gdzie baza danych pasuje do całości
- [Rozwiązywanie problemów](15-troubleshooting.md): wzorce awarii bazy danych
- Dla media buyerów: [Import danych](09-data-import.md) opisuje siatkę świeżości danych od strony użytkownika.
