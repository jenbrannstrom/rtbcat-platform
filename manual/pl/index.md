# Podręcznik użytkownika Cat-Scan

## Problem w jednym obrazku

![Lejek QPS](../assets/qps-funnel.svg)

Google wysyła do Twojego biddera strumień zapytań o licytację. Co sekundę
dziesiątki tysięcy zapytań napływają z giełdy Authorized Buyers do Twojego
endpointu. Twój bidder analizuje każde z nich, decyduje, czy licytować,
i odpowiada — wszystko w ciągu kilku milisekund.

Jest jedna rzecz, której większość osób nie dostrzega: **zdecydowana większość
tego sygnału to szum.** Typowy seat przetwarzający 50 000 QPS może odkryć,
że 30 000 z tych zapytań dotyczy zasobów reklamowych, których media buyer
nigdy nie zamierzał kupić: nieodpowiednie lokalizacje geograficzne, nieistotne
domeny wydawców, rozmiary reklam bez pasujących kreacji. Twój bidder i tak musi
odebrać, przetworzyć i odrzucić każde z nich. To kosztuje transfer, moc
obliczeniową i pieniądze.

Powyższy diagram przedstawia to jak opady deszczu. QPS od Google to dysza
na górze; krople rozpryskują się na szeroki obszar. Twój bidder to małe
wiadro na dole. Wszystko, co mija wiadro (krople spadające na lewo i prawo),
to marnotrawstwo. Zapłaciłeś za to. Nie uzyskałeś nic w zamian.

**Cat-Scan istnieje po to, aby wiadro było szersze, a deszcz węższy.**

Osiąga to, dając Ci wgląd w to, gdzie powstaje marnotrawstwo (jakie regiony
geograficzne, jacy wydawcy, jakie rozmiary reklam, jakie kreacje) oraz
narzędzia do jego eliminacji u źródła, wykorzystując konfiguracje pretargetingu
udostępniane przez Google.

### Dlaczego jest to trudniejsze, niż się wydaje

Google Authorized Buyers daje Ci tylko **10 konfiguracji pretargetingu na
seat**, plus przybliżone zakresy geograficzne (Wschodnie USA, Zachodnie USA,
Europa, Azja). Nie istnieje Reporting API. Wszystkie dane o wynikach pochodzą
z eksportów CSV przesyłanych e-mailem. Sam interfejs pretargetingu AB jest
funkcjonalny, ale utrudnia przeglądanie pełnego obrazu między konfiguracjami
lub cofnięcie zmiany, która poszła nie tak.

Cat-Scan wypełnia te luki:

- **Odbudowuje raportowanie z eksportów CSV** (ręczny upload lub automatyczne
  pobieranie z Gmaila), deduplikując podczas importu, więc ponowne
  przetwarzanie nigdy nie powoduje podwójnego zliczania.
- Pokazuje **pełny lejek RTB** — od surowego QPS przez licytacje, wygrane,
  odsłony, kliknięcia i wydatki — z podziałem na dowolny wymiar: geografię,
  wydawcę, rozmiar reklamy, kreację, konfigurację.
- Zapewnia **bezpieczne zarządzanie pretargetingiem** z historią zmian,
  etapowymi zmianami, podglądem próbnym (dry-run) i cofaniem jednym
  kliknięciem.
- Uruchamia **optymalizator**, który ocenia segmenty i proponuje zmiany
  w konfiguracji, z zabezpieczeniami przepływu pracy (ostrożny / zrównoważony
  / agresywny), tak aby żadna zmiana nie weszła w życie bez przeglądu.

### Dla kogo jest ten podręcznik

Ten podręcznik ma dwie ścieżki, ponieważ Cat-Scan obsługuje dwie zupełnie
różne role:

**Media buyerzy i managerowie kampanii** używają Cat-Scan, aby zrozumieć,
na co idzie ich budżet, znaleźć marnotrawstwo, zarządzać kreacjami, dostrajać
pretargeting i zatwierdzać propozycje optymalizacji. Myślą w kategoriach CPM,
współczynnika wygranych i ROAS. Ich rozdziały skupiają się na tym, co pokazuje
interfejs, co oznaczają liczby i jakie działania podjąć.

**Inżynierowie DevOps i platformowi** używają Cat-Scan do wdrażania,
monitorowania i rozwiązywania problemów systemu. Myślą w kategoriach
kontenerów, endpointów stanu systemu i planów zapytań. Ich rozdziały skupiają
się na architekturze, pipeline'ach wdrożeniowych, operacjach bazodanowych
i poradnikach awaryjnych.

Obie ścieżki dzielą wspólne podstawy (pierwsze kroki, glosariusz), a rozdziały
odwołują się do siebie nawzajem tam, gdzie przepływy pracy się pokrywają. Media
buyer zgłaszający problem „aktualność danych nie działa" i inżynier DevOps
debugujący zapytanie, które za tym stoi, powinni móc wskazać ten sam wpis
w glosariuszu i zrozumieć się nawzajem.

---

## Jak czytać ten podręcznik

- **Część 0** jest dla każdego. Zacznij tutaj.
- **Część I** to ścieżka media buyera. Jeśli zajmujesz się kampaniami,
  optymalizacją lub zakupem mediów, to Twoja ścieżka.
- **Część II** to ścieżka DevOps. Jeśli wdrażasz, monitorujesz lub
  administrujesz Cat-Scan, to Twoja ścieżka.
- **Część III** to wspólna baza referencyjna: glosariusz, FAQ i indeks API.

Nie musisz czytać liniowo. Każdy rozdział jest samodzielny. Podążaj za linkami
odpowiadającymi Twojej roli.

---

## Spis treści

### Część 0: Pierwsze kroki

Czyta to każdy.

- [Rozdział 0: Czym jest Cat-Scan?](00-what-is-cat-scan.md)
  Czym zajmuje się platforma, dla kogo jest i jakie podstawowe pojęcia musisz
  znać: seaty, QPS, pretargeting, lejek RTB.

- [Rozdział 1: Logowanie](01-logging-in.md)
  Metody uwierzytelniania (Google OAuth, konta lokalne), strona logowania, co
  zrobić, gdy logowanie nie działa, i jak działa selektor seatów.

- [Rozdział 2: Nawigacja po dashboardzie](02-navigating-the-dashboard.md)
  Pasek boczny, przełączanie seatów, wybór języka, lista kontrolna konfiguracji
  dla nowych kont i organizacja stron.

### Część I: Ścieżka media buyera

Dla media buyerów, managerów kampanii i inżynierów optymalizacji.

- [Rozdział 3: Zrozumienie lejka QPS](03-qps-funnel.md)
  Strona główna. Jak czytać podział lejka: odsłony, licytacje, wygrane,
  wydatki, współczynnik wygranych, CTR, CPM. Co oznacza „marnotrawstwo"
  w konkretnych kategoriach. Karty konfiguracji i co kontrolują ich pola.

- [Rozdział 4: Analiza marnotrawstwa według wymiaru](04-analyzing-waste.md)
  Trzy widoki analizy marnotrawstwa i kiedy używać każdego z nich:
  - **Geograficzny** (`/qps/geo`): które kraje i miasta pochłaniają QPS bez
    konwersji.
  - **Wydawca** (`/qps/publisher`): które domeny i aplikacje mają słabe wyniki.
  - **Rozmiar** (`/qps/size`): które rozmiary reklam otrzymują ruch, ale nie
    mają pasujących kreacji. Google przesyła ~400 różnych rozmiarów; większość
    jest nieistotna dla reklam displayowych o stałym rozmiarze.

- [Rozdział 5: Zarządzanie kreacjami](05-managing-creatives.md)
  Galeria kreacji (`/creatives`): przeglądanie według formatu, filtrowanie
  według poziomu wydajności, wyszukiwanie po ID. Miniatury, znaczniki formatu,
  diagnostyka docelowego URL. Klastrowanie kampanii (`/campaigns`): przeciągnij
  i upuść, automatyczne klastrowanie AI, pula nieprzypisanych.

- [Rozdział 6: Konfiguracja pretargetingu](06-pretargeting.md)
  Co kontroluje konfiguracja pretargetingu (regiony, rozmiary, formaty,
  platformy, maksymalne QPS). Jak czytać kartę konfiguracji. Wdrażanie zmian
  z podglądem próbnym. Oś czasu historii zmian (`/history`). Cofanie: jak
  działa, dlaczego istnieje i kiedy go używać.

- [Rozdział 7: Optymalizator (BYOM)](07-optimizer.md)
  Bring Your Own Model: rejestracja zewnętrznego endpointu scoringowego,
  walidacja, aktywacja. Cykl życia: punktacja-propozycja-zatwierdzenie-
  wdrożenie. Presety przepływu pracy: ostrożny, zrównoważony, agresywny.
  Ekonomia: efektywne CPM, bazowy koszt hostingu, podsumowanie wydajności.
  Jak wygląda propozycja i jak ją ocenić.

- [Rozdział 8: Konwersje i atrybucja](08-conversions.md)
  Podłączanie źródła konwersji. Integracja piksela. Konfiguracja webhooka:
  podpisy HMAC, współdzielone sekrety, limitowanie żądań. Kontrole gotowości.
  Statystyki pozyskiwania danych. Co oznacza „zdrowie konwersji" i jak czytać
  stronę statusu bezpieczeństwa.

- [Rozdział 9: Import danych](09-data-import.md)
  Jak dane trafiają do Cat-Scan i dlaczego to ważne. Ręczny upload CSV
  (`/import`): przeciągnij i upuść, mapowanie kolumn, walidacja, upload
  częściowy dla dużych plików. Automatyczny import z Gmaila: jak działa, jak
  sprawdzić status, co się dzieje, gdy zawiedzie. Siatka aktualności danych:
  co oznacza „zaimportowano" vs. „brakuje" dla danej daty i typu raportu.
  Gwarancje deduplikacji.

- [Rozdział 10: Czytanie raportów](10-reading-reports.md)
  Statystyki wydatków, panele wydajności konfiguracji, metryki efektywności
  endpointu. Jak interpretować trendy. Co pokazuje dzienny podział. Porównania
  migawek: przed i po zmianie pretargetingu.

### Część II: Ścieżka DevOps

Dla inżynierów platformowych, SRE i administratorów systemów.

- [Rozdział 11: Przegląd architektury](11-architecture.md)
  Topologia systemu: backend FastAPI, frontend Next.js 14, Postgres (Cloud SQL),
  BigQuery. Dlaczego istnieją obie bazy danych (koszt, opóźnienie,
  pre-agregacja, obsługa połączeń). Układ kontenerów: api, dashboard,
  oauth2-proxy, cloudsql-proxy, nginx. Łańcuch zaufania uwierzytelniania:
  OAuth2 Proxy ustawia `X-Email`, nginx go przekazuje, API mu ufa.

- [Rozdział 12: Wdrażanie](12-deployment.md)
  Pipeline CI/CD: GitHub Actions `build-and-push.yml` buduje obrazy przy pushu;
  `deploy.yml` wymaga ręcznego wyzwolenia (z potwierdzeniem `DEPLOY`). Tagi
  obrazów Artifact Registry (`sha-XXXXXXX`). Sekwencja wdrożenia: git pull na
  VM, docker compose pull, recreate, prune. Weryfikacja po wdrożeniu: health
  check, contract check. Dlaczego auto-deploy jest wyłączony (incydent ze
  stycznia 2026). Jak zweryfikować wdrożenie:
  `curl /api/health | jq .git_sha`.

- [Rozdział 13: Monitorowanie stanu i diagnostyka](13-health-monitoring.md)
  Endpointy stanu: `/api/health` (liveness), `/system/data-health`
  (kompletność danych). Strona statusu systemu (`/settings/system`): Python,
  Node, FFmpeg, baza danych, dysk, miniatury. Skrypty diagnostyki
  uruchomieniowej: `diagnose_v1_buyer_report_coverage.sh`,
  `run_v1_runtime_health_strict_dispatch.sh`. Uwierzytelnianie canary:
  `CATSCAN_CANARY_EMAIL`, `CATSCAN_BEARER_TOKEN`. Przepływy CI:
  `v1-runtime-health-strict.yml` i co oznaczają PASS/FAIL/BLOCKED.

- [Rozdział 14: Operacje bazodanowe](14-database.md)
  Produkcja wyłącznie na Postgresie. Cloud SQL przez kontener proxy. Kluczowe
  tabele i ich skala: `rtb_daily` (~84M wierszy), `rtb_bidstream` (~21M
  wierszy), `rtb_quality`, `rtb_bid_filtering`. Krytyczne indeksy:
  `(buyer_account_id, metric_date DESC)`. Model połączeń: per-request (bez
  poola), `run_in_executor` dla async. Timeouty zapytań
  (`SET LOCAL statement_timeout`). Ustawienia retencji danych. Rola BigQuery:
  hurtownia wsadowa dla surowych danych; Postgres serwuje pre-zagregowane dane
  do aplikacji.

- [Rozdział 15: Poradnik rozwiązywania problemów](15-troubleshooting.md)
  Znane wzorce awarii i sposoby ich rozwiązywania:
  - **Pętla logowania**: Cloud SQL Proxy nie działa,
    `_get_or_create_oauth2_user` zawodzi cicho, `/auth/check` zwraca
    `{authenticated:false}`, frontend wpada w pętlę przekierowań.
    Trójwarstwowa naprawa. Jak wykryć: licznik przekierowań w przeglądarce,
    503 z `/auth/check`.
  - **Timeout aktualności danych**: Duże tabele wykonują skany sekwencyjne
    zamiast korzystać z indeksów. Objawy: `/uploads/data-freshness` przekracza
    czas lub zwraca 500. Diagnoza: `pg_stat_activity`, `EXPLAIN ANALYZE`.
    Wzorzec naprawy: generate_series + EXISTS.
  - **Awaria importu z Gmaila**: `/gmail/status` pokazuje błąd. Sprawdź
    kontener Cloud SQL Proxy. Sprawdź liczbę nieprzeczytanych wiadomości.
  - **Kolejność restartu kontenerów**: `cloudsql-proxy` musi być zdrowy, zanim
    wystartuje `api`. Oznaki nieprawidłowej kolejności: connection refused
    w logach API.

- [Rozdział 16: Administracja użytkownikami i uprawnieniami](16-user-admin.md)
  Panel administracyjny (`/admin`): tworzenie użytkowników (lokalne i pre-create
  OAuth), zarządzanie rolami, uprawnienia per-seat. Konta serwisowe:
  przesyłanie pliku JSON z poświadczeniami GCP, co to odblokuje (wykrywanie
  seatów, synchronizacja pretargetingu). Użytkownicy z ograniczeniami: co widzą
  i co jest ukryte. Dziennik audytu: jakie akcje są śledzone, jak filtrować,
  retencja.

- [Rozdział 17: Integracje](17-integrations.md)
  Konta serwisowe GCP i połączenie z projektem. Google Authorized Buyers API:
  wykrywanie seatów, synchronizacja konfiguracji pretargetingu, synchronizacja
  endpointów RTB. Integracja z Gmailem: OAuth2 do automatycznego pobierania
  raportów. Dostawcy AI językowego: Gemini, Claude, Grok (do wykrywania języka
  kreacji i alertów o niezgodnościach). Webhooki konwersji: rejestracja
  endpointu, weryfikacja HMAC, limitowanie żądań, monitorowanie aktualności.

### Część III: Materiały referencyjne

Wspólne dla obu ścieżek.

- [Glosariusz](glossary.md)
  Każdy termin w dwóch perspektywach. Kolumna media buyera: „pretargeting" to
  „reguły kontrolujące, które zapytania o licytację docierają do Twojego
  biddera." Kolumna DevOps: „pretargeting" to „mutowalny obiekt synchronizowany
  z AB API, przechowywany w `pretargeting_configs`, dostępny przez
  `/settings/pretargeting`." Obie strony potrzebują tego samego słowa; żadna nie
  posługuje się definicją drugiej.

- [Najczęściej zadawane pytania](faq.md)
  Otagowane według odbiorcy. Pytania media buyera („Dlaczego moje pokrycie
  wynosi 74%?") obok pytań inżyniera DevOps („Dlaczego bramka runtime health
  strict nie przeszła?"). Odpowiedzi odsyłają do odpowiedniego rozdziału.

- [Szybka referencja API](api-reference.md)
  Wszystkie 118+ endpointów pogrupowanych według domeny: core, seats, creatives,
  campaigns, analytics, settings, admin, optimizer, conversions, integrations,
  uploads, snapshots, auth. Metoda, ścieżka, kluczowe parametry i co zwraca.
  Nie zastępuje specyfikacji OpenAPI pod `/api/docs`, ale jest nawigowanym
  indeksem.
