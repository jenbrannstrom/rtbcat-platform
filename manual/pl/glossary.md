# Glosariusz

Każdy termin z dwóch perspektyw. Lewa kolumna to sposób, w jaki myśli o nim
media buyer. Prawa kolumna to sposób, w jaki znajduje go w systemie inżynier
DevOps.

| Termin | Definicja media buyera | Definicja DevOps / systemowa |
|--------|------------------------|------------------------------|
| **Seat** | Konto buyera na Google Authorized Buyers. Analizę i targetowanie wykonujesz w kontekście danego seatu. | `buyer_account_id` w Postgresie. Przechowywany w tabeli `seats`. Synchronizowany przez `GET /seats`. |
| **QPS** | Queries Per Second: maksymalna częstotliwość zapytań o licytację, o którą prosisz Google. Google ogranicza rzeczywisty wolumen w zależności od poziomu Twojego konta. | Skonfigurowany limit na konfigurację pretargetingu. Rzeczywista częstotliwość przychodząca monitorowana przez metryki lejka RTB w `rtb_daily`. |
| **Marnotrawstwo (Waste)** | QPS pochłaniane przez zapytania o licytację odrzucane przez Twojego biddera (nieodpowiednie regiony, rozmiary, brak pasującej kreacji). Pieniądze wydane na nic. | `(total_qps - bids_placed) / total_qps`. Obliczane z agregatów `rtb_daily`. Widoczne w API lejka. |
| **Konfiguracja pretargetingu** | Reguły kontrolujące, które zapytania o licytację docierają do Twojego biddera. Masz 10 na seat. Kontroluje regiony, rozmiary, formaty, platformy, wydawców. | Mutowalny obiekt synchronizowany z Google AB API. Przechowywany w `pretargeting_configs`. Zarządzany przez `/settings/pretargeting`. Snapshoty umożliwiają cofanie. |
| **Lejek (Funnel)** | Progresja od zapytania o licytację do wydatków: QPS -> Licytacje -> Wygrane -> Odsłony -> Kliknięcia -> Wydatki. Każdy krok ma odpad. | Obliczany z metryk `rtb_daily`. Serwowany przez `GET /analytics/rtb-funnel`. Frontend cache'uje przez 30 minut. |
| **Kreacja (Creative)** | Zasób reklamowy: obraz, wideo, HTML lub natywny. Ma format, rozmiar, docelowy URL i historię wydajności. | Wiersz w tabeli `creatives`. Miniatury w blob storage. Synchronizowane z Google AB API. Wydajność z joinów `rtb_daily`. |
| **Kampania (Campaign)** | Logiczne grupowanie kreacji. Używane do organizacji analiz i raportowania. | Wiersz w tabeli `ai_campaigns`. Relacja wiele-do-wielu z kreacjami. Obsługuje automatyczne klastrowanie AI. |
| **Karta konfiguracji (Config card)** | Panel interfejsu pokazujący stan konfiguracji pretargetingu, maksymalne QPS, regiony, rozmiary, formaty i platformy. | Komponent React `PretargetingConfigCard`. Dane z `GET /settings/pretargeting-configs`. |
| **Aktualność danych (Data freshness)** | Siatka pokazująca, dla których dat dane zostały zaimportowane („zaimportowano") a dla których brakuje („brakuje") — dla każdego typu raportu. | `GET /uploads/data-freshness`. Używa zapytań `generate_series + EXISTS` na `rtb_daily`, `rtb_bidstream`, `rtb_quality`, `rtb_bid_filtering`. Timeout 30s. |
| **Import** | Wprowadzanie danych wydajności CSV do Cat-Scan — ręcznym uploadem lub automatycznym importem z Gmaila. | CSV parsowane, walidowane, deduplikowane (przez ograniczenie unique `row_hash`), wstawiane do docelowych tabel. Upload częściowy dla plików > 5MB. |
| **Cofanie (Rollback)** | Przywrócenie konfiguracji pretargetingu do poprzedniego stanu. Podgląd próbny, potem potwierdzenie. | Przywrócenie snapshotu: odczyt z `pretargeting_snapshots`, aplikacja delty do Google AB API, zapis nowego snapshotu. `POST /snapshots/rollback`. |
| **Optymalizator / BYOM** | Zautomatyzowany system oceniający segmenty i proponujący zmiany konfiguracji. Wykorzystuje Twój własny model zewnętrzny. | Endpoint scoringowy wywoływany przez HTTP POST. Propozycje przechowywane w `optimizer_proposals`. Cykl życia: punktacja -> propozycja -> zatwierdzenie -> wdrożenie. |
| **Preset przepływu pracy (Workflow preset)** | Ostrożny, zrównoważony lub agresywny. Kontroluje, jak śmiałe są propozycje optymalizatora. | Parametr `canary_profile` w API score-and-propose. Wpływa na progi pewności i limity wielkości zmian. |
| **Efektywne CPM** | Ile faktycznie płacisz za tysiąc odsłon, uwzględniając marnotrawstwo i koszt infrastruktury. | Obliczane w `OptimizerEconomicsService`. Łączy dane o wydatkach z `rtb_daily` ze skonfigurowanym kosztem hostingu. |
| **Konwersja (Conversion)** | Wartościowa akcja użytkownika (zakup, rejestracja) śledzona po odsłonie. Dane zwrotne do optymalizacji targetowania. | Zdarzenie pozyskiwane przez piksel (`GET /conversions/pixel`) lub webhook (`POST /conversions/webhook`). Przechowywane w tabelach konwersji. Weryfikacja HMAC dla webhooków. |
| **Współczynnik wygranych (Win rate)** | Wygrane / Licytacje. Jak konkurencyjne są Twoje oferty w aukcji. | `auction_wins / bids_placed` z `rtb_daily`. |
| **CTR** | Kliknięcia / Odsłony. Jak angażujące są Twoje kreacje. | `clicks / impressions` z `rtb_daily`. |
| **Bramka runtime health (Runtime health gate)** | (Nie jest terminem buyera) | Przepływ CI `v1-runtime-health-strict.yml`. Uruchamia kompleksowe sprawdzenia: stan API, stan danych, konwersje, optymalizator, SLO QPS. Zwraca PASS/FAIL/BLOCKED na każde sprawdzenie. |
| **Contract check** | (Nie jest terminem buyera) | `scripts/contracts_check.py`. Waliduje kontrakty danych (nienegocjowalne reguły od importu do wyjścia API). Uruchamiany po wdrożeniu. Blokuje wydanie w przypadku niepowodzenia. |
| **Cloud SQL Proxy** | (Nie jest terminem buyera) | Kontener sidecar zapewniający uwierzytelniony dostęp do Cloud SQL Postgres. Musi być zdrowy przed startem kontenera API. |
| **Nagłówek X-Email (X-Email header)** | (Nie jest terminem buyera) | Nagłówek HTTP ustawiany przez OAuth2 Proxy po uwierzytelnieniu Google. Traktowany jako zaufany przez API, gdy `OAUTH2_PROXY_ENABLED=true`. Usuwany przez nginx dla żądań zewnętrznych. |
