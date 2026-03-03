# Rozdział 13: Monitoring stanu systemu i diagnostyka

*Odbiorcy: DevOps, inżynierowie platformy*

## Endpointy stanu

### `/api/health`: żywotność

Zwraca podstawowy status API, SHA gita i wersję. Używany przez workflow wdrożeniowy i zewnętrzny monitoring.

```bash
curl -sS https://scan.rtb.cat/api/health | jq .
```

### `/system/data-health`: kompletność danych

Zwraca status zdrowia danych na kupującego, w tym stan świeżości dla każdego typu raportu. Akceptuje parametry `days`, `buyer_id` i `availability_state`.

Używany przez listę kontrolną konfiguracji oraz bramkę zdrowia w czasie działania.

## Strona statusu systemu (`/settings/system`)

Interfejs wyświetla:

| Kontrola | Co monitoruje |
|----------|---------------|
| Python | Wersja środowiska uruchomieniowego i dostępność |
| Node | Budowanie Next.js i status SSR |
| FFmpeg | Zdolność generowania miniatur wideo |
| Baza danych | Połączenie z Postgres i liczba wierszy |
| Miniatury | Status generowania wsadowego i kolejka |
| Przestrzeń dyskowa | Wykorzystanie dysku VM |

## Skrypty sprawdzające stan w czasie działania

Poniższe skrypty stanowią operacyjną podstawę do weryfikacji, czy system działa od początku do końca.

### `diagnose_v1_buyer_report_coverage.sh`

Diagnozuje, dlaczego konkretny kupujący ma brakujące pokrycie CSV.

```bash
export CATSCAN_CANARY_EMAIL="cat-scan@rtb.cat"
scripts/diagnose_v1_buyer_report_coverage.sh \
  --buyer-id 1487810529 \
  --timeout 180 \
  --days 14
```

Kontrole (w kolejności):
1. Mapowanie stanowisk: buyer_id -> bidder_id
2. Macierz importu: zaliczone/niezaliczone/niezaimportowane wg typu CSV
3. Świeżość danych: pokrycie zaimportowanych/brakujących komórek
4. Historia importu: ostatnie wiersze importu
5. Status Gmaila: liczba nieprzeczytanych, ostatni powód, najnowsza data metryki

Wynik: PASS lub FAIL ze szczegółową diagnozą.

### `run_v1_runtime_health_strict_dispatch.sh`

Uruchamia pełną bramkę sprawdzania stanu w czasie działania, która kontroluje:

- Stan API
- Stan danych (świeżość i pokrycie wymiarów)
- Stan i gotowość konwersji
- Opóźnienie startu QPS
- Podsumowanie SLO strony QPS
- Ekonomikę i modele optymalizatora
- Walidację endpointu modelu
- Workflow score+propose
- Cykl życia propozycji
- Próbę rollbacku (dry-run)

Każda kontrola zwraca PASS, FAIL lub BLOCKED (z podaniem przyczyny).

### Workflow CI: `v1-runtime-health-strict.yml`

Uruchamia ścisłą bramkę w CI. Wyzwalana ręcznie przez workflow_dispatch.

```bash
gh workflow run v1-runtime-health-strict.yml \
  --ref unified-platform \
  -f api_base_url="https://scan.rtb.cat/api" \
  -f buyer_id="1487810529" \
  -f canary_profile="balanced" \
  -f canary_timeout_seconds="180"
```

## Uwierzytelnianie canary

Skrypty uruchomieniowe uwierzytelniają się za pomocą zmiennych środowiskowych:

| Zmienna | Przeznaczenie |
|---------|---------------|
| `CATSCAN_CANARY_EMAIL` | Nagłówek X-Email dla bezpośrednich wywołań API (lokalnie na VM) |
| `CATSCAN_BEARER_TOKEN` | Token Bearer (środowisko CI, przechowywany w sekretach GitHub) |
| `CATSCAN_SESSION_COOKIE` | Ciasteczko sesji OAuth2 Proxy (środowisko CI) |

Z hosta VM używaj `CATSCAN_CANARY_EMAIL` z `http://localhost:8000`.
Z CI (zewnętrznie) używaj `CATSCAN_BEARER_TOKEN` lub `CATSCAN_SESSION_COOKIE`
z `https://scan.rtb.cat/api`.

## Interpretacja wyników

| Status | Znaczenie |
|--------|-----------|
| **PASS** | Kontrola zakończona sukcesem, system zdrowy |
| **FAIL** | Kontrola zakończona niepowodzeniem, zbadaj natychmiast |
| **BLOCKED** | Kontrola nie mogła zostać ukończona z powodu zależności (np. brak danych dla tego kupującego, brakujący endpoint). Niekoniecznie błąd w kodzie. |

## Powiązane

- [Wdrożenie](12-deployment.md): weryfikacja wdrożenia
- [Rozwiązywanie problemów](15-troubleshooting.md): gdy kontrole stanu kończą się niepowodzeniem
- Dla media buyerów: [Import danych](09-data-import.md) opisuje siatkę świeżości danych w sposób przystępny dla kupujących.
