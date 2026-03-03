# Rozdział 17: Integracje

*Odbiorcy: DevOps, inżynierowie platformy*

## Konta usługowe GCP

Cat-Scan potrzebuje poświadczeń konta usługowego GCP do komunikacji z interfejsami API Google.

**Konfiguracja:**
1. Utwórz konto usługowe w projekcie GCP z dostępem do Authorized Buyers API.
2. Pobierz plik klucza JSON.
3. Prześlij go w `/settings/accounts` > zakładka API Connection.
4. Zwaliduj połączenie: Cat-Scan testuje osiągalność i uprawnienia.

**Co umożliwia:**
- Odkrywanie stanowisk (`discoverSeats`)
- Synchronizacja konfiguracji pretargetingu (`syncPretargetingConfigs`)
- Synchronizacja endpointów RTB (`syncRTBEndpoints`)
- Zbieranie kreacji (`collectCreatives`)

**Status projektu:**
Sprawdź stan projektu GCP w `/settings/accounts` lub przez
`GET /integrations/gcp/project-status`. Weryfikuje to, czy konto usługowe jest prawidłowe, projekt jest dostępny, a wymagane interfejsy API są włączone.

## Google Authorized Buyers API

Cat-Scan synchronizuje dane z Authorized Buyers API:

| Operacja | Co pobiera | Kiedy uruchamiać |
|----------|-----------|------------------|
| **Odkrywanie stanowisk** | Konta kupujących powiązane z kontem usługowym | Początkowa konfiguracja, gdy dodawane są nowe stanowiska |
| **Synchronizacja pretargetingu** | Aktualny stan konfiguracji pretargetingu z Google | Po zewnętrznych zmianach w interfejsie AB |
| **Synchronizacja endpointów RTB** | Adresy URL i status endpointów licytujących | Początkowa konfiguracja, po zmianach endpointów |
| **Synchronizacja kreacji** | Metadane kreacji (formaty, rozmiary, miejsca docelowe) | Okresowo, przez „Sync All" na pasku bocznym |

## Integracja z Gmailem

Google Authorized Buyers wysyła dzienne raporty CSV mailem. Cat-Scan może je automatycznie pobierać i przetwarzać.

**Konfiguracja:**
1. Przejdź do `/settings/accounts` > zakładka Gmail Reports.
2. Autoryzuj Cat-Scan do dostępu do konta Gmail otrzymującego raporty AB.
3. Cat-Scan będzie odpytywać skrzynkę o nowe e-maile z raportami i importować załączone pliki CSV.

**Monitoring:**
- `GET /gmail/status`: aktualny stan, liczba nieprzeczytanych, ostatni powód
- `POST /gmail/import/start`: ręczne uruchomienie cyklu importu
- `POST /gmail/import/stop`: zatrzymanie trwającego importu
- `GET /gmail/import/history`: historia importów

**Rozwiązywanie problemów:**
- Duża liczba nieprzeczytanych (30+): zaległości w imporcie, może wymagać ręcznej interwencji
- `last_reason: error`: sprawdź logi, może być potrzebna ponowna autoryzacja
- Zobacz [Rozwiązywanie problemów](15-troubleshooting.md) po szczegółowe instrukcje.

## Dostawcy sztucznej inteligencji językowej

Cat-Scan wykorzystuje AI do wykrywania języka kreacji i oznaczania niezgodności geolingwistycznych (np. reklama po hiszpańsku na rynku arabskim).

**Obsługiwani dostawcy:**

| Dostawca | Konfiguracja |
|----------|--------------|
| Gemini | Klucz API w `/settings/accounts` |
| Claude | Klucz API w `/settings/accounts` |
| Grok | Klucz API w `/settings/accounts` |

Konfiguracja przez `GET/PUT /integrations/language-ai/config`. Tylko jeden dostawca musi być aktywny.

## Webhooki konwersji

Zewnętrzne systemy wysyłają zdarzenia konwersji do Cat-Scan przez webhooki.

**Warstwy bezpieczeństwa:**

| Warstwa | Cel | Konfiguracja |
|---------|-----|--------------|
| **Weryfikacja HMAC** | Zapewnia autentyczność żądań (podpisane wspólnym sekretem) | Wspólny sekret skonfigurowany w ustawieniach webhooka |
| **Ograniczanie częstotliwości** | Zapobiega nadużyciom | Automatyczne, konfigurowalne progi |
| **Monitoring świeżości** | Alertuje, gdy zdarzenia przestają napływać | Konfigurowalne okno przeterminowania |

**Monitoring:**
- `GET /conversions/security/status`: status HMAC, status ograniczania
  częstotliwości, status świeżości
- `GET /conversions/health`: ogólny stan pozyskiwania i agregacji
- `GET /conversions/readiness`: czy dane konwersji są wystarczająco świeże,
  aby im ufać

## Powiązane

- [Przegląd architektury](11-architecture.md): gdzie integracje pasują do całości
- [Administracja użytkownikami](16-user-admin.md): zarządzanie kontami usługowymi
- Dla media buyerów: [Konwersje i atrybucja](08-conversions.md) opisuje konfigurację konwersji od strony kupującego.
