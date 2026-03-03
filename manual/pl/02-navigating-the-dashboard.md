# Rozdział 2: Nawigacja po dashboardzie

*Odbiorcy: wszyscy*

## Układ paska bocznego

Pasek boczny to Twoja główna nawigacja. Można go zwinąć (tryb samych ikon)
lub rozwinąć. Twoje preferencje są zapamiętywane między sesjami.

```
Seat Selector
 ├── QPS Waste Optimizer         /              (home)
 ├── Creatives                   /creatives
 ├── Campaigns                   /campaigns
 ├── Change History              /history
 ├── Import                      /import
 │
 ├── QPS (expandable)
 │   ├── Publisher                /qps/publisher
 │   ├── Geo                     /qps/geo
 │   └── Size                    /qps/size
 │
 ├── Settings (expandable)
 │   ├── Connected Accounts      /settings/accounts
 │   ├── Data Retention          /settings/retention
 │   └── System Status           /settings/system
 │
 ├── Admin (sudo users only)
 │   ├── Users                   /admin/users
 │   ├── Configuration           /admin/configuration
 │   └── Audit Log               /admin/audit-log
 │
 └── Footer: user email, version, docs link
```

Sekcje rozwijają się automatycznie, gdy do nich nawigujesz.

## Użytkownicy z ograniczonym dostępem

Niektóre konta są oznaczone przez administratora jako „ograniczone". Użytkownicy
z ograniczonym dostępem widzą tylko podstawowe strony: stronę główną, kreacje,
kampanie, import i historię. Sekcje analizy QPS, ustawień i administracji
są ukryte.

## Lista kontrolna konfiguracji

Nowe konta widzą listę kontrolną konfiguracji pod adresem `/setup`, która
prowadzi przez początkową konfigurację:

1. Podłączenie kont kupujących (przesłanie poświadczeń GCP, wykrycie kont seat)
2. Weryfikacja kondycji danych (sprawdzenie, czy importy CSV docierają)
3. Rejestracja modelu optymalizatora (endpoint BYOM)
4. Walidacja endpointu modelu (wywołanie testowe)
5. Ustawienie bazowych kosztów hostingu (do obliczeń ekonomicznych)
6. Podłączenie źródła konwersji (piksel lub webhook)

Procent ukończenia jest śledzony. Każdy krok prowadzi do odpowiedniej strony
ustawień.

## Obsługa języków

Cat-Scan obsługuje angielski, niderlandzki i chiński (uproszczony). Selektor
języka znajduje się na pasku bocznym. Twoje preferencje są zapisywane
per użytkownik.

## Następne kroki

- Kupcy mediowi: zacznij od [Zrozumienie lejka QPS](03-qps-funnel.md)
- DevOps: zacznij od [Przegląd architektury](11-architecture.md)
