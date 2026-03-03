# Szybka referencja API

To nawigowany indeks ponad 118 endpointów API Cat-Scan, pogrupowanych według
domeny. Pełne schematy żądań i odpowiedzi znajdziesz w interaktywnej
dokumentacji OpenAPI pod adresem `https://scan.rtb.cat/api/docs`.

## Core / System

| Metoda | Ścieżka | Przeznaczenie |
|--------|---------|---------------|
| GET | `/health` | Sprawdzenie żywotności (git_sha, wersja) |
| GET | `/stats` | Statystyki systemowe |
| GET | `/sizes` | Dostępne rozmiary reklam |
| GET | `/system/status` | Status serwera (Python, Node, FFmpeg, baza danych, dysk) |
| GET | `/system/data-health` | Kompletność danych na buyera |
| GET | `/system/ui-page-load-metrics` | Metryki wydajności frontendu |
| GET | `/geo/lookup` | Rozwiązywanie ID geograficznego na nazwę |
| GET | `/geo/search` | Wyszukiwanie krajów/miast |

## Auth

| Metoda | Ścieżka | Przeznaczenie |
|--------|---------|---------------|
| GET | `/auth/check` | Sprawdzenie, czy bieżąca sesja jest uwierzytelniona |
| POST | `/auth/logout` | Zakończenie sesji |

## Seats

| Metoda | Ścieżka | Przeznaczenie |
|--------|---------|---------------|
| GET | `/seats` | Lista seatów buyera |
| GET | `/seats/{buyer_id}` | Pobranie konkretnego seatu |
| PUT | `/seats/{buyer_id}` | Aktualizacja nazwy wyświetlanej seatu |
| POST | `/seats/populate` | Automatyczne tworzenie seatów z danych |
| POST | `/seats/discover` | Wykrywanie seatów z Google API |
| POST | `/seats/{buyer_id}/sync` | Synchronizacja konkretnego seatu |
| POST | `/seats/sync-all` | Pełna synchronizacja (wszystkie seaty) |
| POST | `/seats/collect-creatives` | Zbieranie danych kreacji |

## Creatives

| Metoda | Ścieżka | Przeznaczenie |
|--------|---------|---------------|
| GET | `/creatives` | Lista kreacji (z filtrami) |
| GET | `/creatives/paginated` | Stronicowana lista kreacji |
| GET | `/creatives/{id}` | Szczegóły kreacji |
| GET | `/creatives/{id}/live` | Dane kreacji na żywo (z uwzględnieniem cache) |
| GET | `/creatives/{id}/destination-diagnostics` | Stan docelowego URL |
| GET | `/creatives/{id}/countries` | Podział wydajności wg krajów |
| GET | `/creatives/{id}/geo-linguistic` | Analiza geolingwistyczna |
| POST | `/creatives/{id}/detect-language` | Automatyczne wykrywanie języka |
| PUT | `/creatives/{id}/language` | Ręczne nadpisanie języka |
| GET | `/creatives/thumbnail-status` | Zbiorczy status miniatur |
| POST | `/creatives/thumbnails/batch` | Generowanie brakujących miniatur |

## Campaigns

| Metoda | Ścieżka | Przeznaczenie |
|--------|---------|---------------|
| GET | `/campaigns` | Lista kampanii |
| GET | `/campaigns/{id}` | Szczegóły kampanii |
| GET | `/campaigns/ai` | Klastry wygenerowane przez AI |
| GET | `/campaigns/ai/{id}` | Szczegóły kampanii AI |
| PUT | `/campaigns/ai/{id}` | Aktualizacja kampanii |
| DELETE | `/campaigns/ai/{id}` | Usunięcie kampanii |
| GET | `/campaigns/ai/{id}/creatives` | Kreacje kampanii |
| DELETE | `/campaigns/ai/{id}/creatives/{creative_id}` | Usunięcie kreacji z kampanii |
| POST | `/campaigns/auto-cluster` | Automatyczne klastrowanie AI |
| GET | `/campaigns/ai/{id}/performance` | Wydajność kampanii |
| GET | `/campaigns/ai/{id}/daily-trend` | Dane trendów kampanii |

## Analytics

| Metoda | Ścieżka | Przeznaczenie |
|--------|---------|---------------|
| GET | `/analytics/waste-report` | Ogólne metryki marnotrawstwa |
| GET | `/analytics/size-coverage` | Pokrycie targetowania rozmiarem |
| GET | `/analytics/rtb-funnel` | Podział lejka RTB |
| GET | `/analytics/rtb-funnel/configs` | Lejek na poziomie konfiguracji |
| GET | `/analytics/endpoint-efficiency` | Efektywność QPS na endpoint |
| GET | `/analytics/spend-stats` | Statystyki wydatków |
| GET | `/analytics/config-performance` | Wydajność konfiguracji w czasie |
| GET | `/analytics/config-performance/breakdown` | Podział pól konfiguracji |
| GET | `/analytics/qps-recommendations` | Rekomendacje AI |
| GET | `/analytics/performance/batch` | Zbiorcza wydajność kreacji |
| GET | `/analytics/performance/{creative_id}` | Wydajność pojedynczej kreacji |
| GET | `/analytics/publishers` | Metryki domen wydawców |
| GET | `/analytics/publishers/search` | Wyszukiwanie wydawców |
| GET | `/analytics/languages` | Wydajność wg języków |
| GET | `/analytics/languages/multi` | Analiza wielu języków |
| GET | `/analytics/geo-performance` | Wydajność geograficzna |
| GET | `/analytics/geo-performance/multi` | Analiza wielu regionów |
| POST | `/analytics/import` | Import CSV |
| POST | `/analytics/mock-traffic` | Generowanie danych testowych |

## Settings / Pretargeting

| Metoda | Ścieżka | Przeznaczenie |
|--------|---------|---------------|
| GET | `/settings/rtb-endpoints` | Endpointy RTB biddera |
| POST | `/settings/rtb-endpoints/sync` | Synchronizacja danych endpointów |
| GET | `/settings/pretargeting-configs` | Lista konfiguracji pretargetingu |
| GET | `/settings/pretargeting-configs/{id}` | Szczegóły konfiguracji |
| GET | `/settings/pretargeting-history` | Historia zmian konfiguracji |
| POST | `/settings/pretargeting-configs/sync` | Synchronizacja konfiguracji z Google |
| POST | `/settings/pretargeting-configs/{id}/apply` | Wdrożenie zmiany konfiguracji |
| POST | `/settings/pretargeting-configs/apply-all` | Wdrożenie wszystkich oczekujących zmian |
| PUT | `/settings/pretargeting-configs/{id}` | Zbiorcza aktualizacja konfiguracji |

## Uploads

| Metoda | Ścieżka | Przeznaczenie |
|--------|---------|---------------|
| GET | `/uploads/tracking` | Dzienny podsumowanie uploadów |
| GET | `/uploads/import-matrix` | Status importu wg typu raportu |
| GET | `/uploads/data-freshness` | Siatka aktualności danych (data x typ) |
| GET | `/uploads/history` | Historia importów |

## Optimizer

| Metoda | Ścieżka | Przeznaczenie |
|--------|---------|---------------|
| GET | `/optimizer/models` | Lista modeli BYOM |
| POST | `/optimizer/models` | Rejestracja modelu |
| PUT | `/optimizer/models/{id}` | Aktualizacja modelu |
| POST | `/optimizer/models/{id}/activate` | Aktywacja modelu |
| POST | `/optimizer/models/{id}/deactivate` | Dezaktywacja modelu |
| POST | `/optimizer/models/{id}/validate` | Test endpointu modelu |
| POST | `/optimizer/score-and-propose` | Generowanie propozycji |
| GET | `/optimizer/proposals` | Lista aktywnych propozycji |
| GET | `/optimizer/proposals/history` | Historia propozycji |
| POST | `/optimizer/proposals/{id}/approve` | Zatwierdzenie propozycji |
| POST | `/optimizer/proposals/{id}/apply` | Wdrożenie propozycji |
| POST | `/optimizer/proposals/{id}/sync-status` | Sprawdzenie statusu wdrożenia |
| GET | `/optimizer/segment-scores` | Punktacje na poziomie segmentów |
| GET | `/optimizer/economics/efficiency` | Podsumowanie efektywności |
| GET | `/optimizer/economics/effective-cpm` | Analiza CPM |
| GET | `/optimizer/setup` | Konfiguracja optymalizatora |
| PUT | `/optimizer/setup` | Aktualizacja konfiguracji optymalizatora |

## Conversions

| Metoda | Ścieżka | Przeznaczenie |
|--------|---------|---------------|
| GET | `/conversions/health` | Status pozyskiwania i agregacji |
| GET | `/conversions/readiness` | Sprawdzenie gotowości źródła |
| GET | `/conversions/ingestion-stats` | Liczba zdarzeń wg źródła/okresu |
| GET | `/conversions/security/status` | Status bezpieczeństwa webhooków |
| GET | `/conversions/pixel` | Endpoint śledzenia pikselem |

## Snapshots

| Metoda | Ścieżka | Przeznaczenie |
|--------|---------|---------------|
| GET | `/snapshots` | Lista snapshotów konfiguracji |
| POST | `/snapshots/rollback` | Przywrócenie snapshotu (z opcją dry-run) |

## Integrations

| Metoda | Ścieżka | Przeznaczenie |
|--------|---------|---------------|
| POST | `/integrations/credentials` | Przesłanie pliku JSON konta serwisowego GCP |
| GET | `/integrations/service-accounts` | Lista kont serwisowych |
| DELETE | `/integrations/service-accounts/{id}` | Usunięcie konta serwisowego |
| GET | `/integrations/language-ai/config` | Status dostawcy AI |
| PUT | `/integrations/language-ai/config` | Konfiguracja dostawcy AI |
| GET | `/integrations/gmail/status` | Status importu z Gmaila |
| POST | `/integrations/gmail/import/start` | Ręczne uruchomienie importu |
| POST | `/integrations/gmail/import/stop` | Zatrzymanie zadania importu |
| GET | `/integrations/gmail/import/history` | Historia importów |
| GET | `/integrations/gcp/project-status` | Stan projektu GCP |
| POST | `/integrations/gcp/validate` | Test połączenia GCP |

## Admin

| Metoda | Ścieżka | Przeznaczenie |
|--------|---------|---------------|
| GET | `/admin/users` | Lista użytkowników |
| POST | `/admin/users` | Utworzenie użytkownika |
| GET | `/admin/users/{id}` | Szczegóły użytkownika |
| PUT | `/admin/users/{id}` | Aktualizacja użytkownika |
| POST | `/admin/users/{id}/deactivate` | Dezaktywacja użytkownika |
| GET | `/admin/users/{id}/permissions` | Globalne uprawnienia użytkownika |
| GET | `/admin/users/{id}/seat-permissions` | Uprawnienia użytkownika na seat |
| POST | `/admin/users/{id}/seat-permissions` | Nadanie dostępu do seatu |
| DELETE | `/admin/users/{id}/seat-permissions/{buyer_id}` | Odebranie dostępu do seatu |
| POST | `/admin/users/{id}/permissions` | Nadanie globalnego uprawnienia |
| DELETE | `/admin/users/{id}/permissions/{sa_id}` | Odebranie globalnego uprawnienia |
| GET | `/admin/audit-log` | Ścieżka audytu |
| GET | `/admin/stats` | Statystyki panelu administracyjnego |
| GET | `/admin/settings` | Konfiguracja systemowa |
| PUT | `/admin/settings/{key}` | Aktualizacja ustawienia systemowego |
