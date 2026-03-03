# Rozdział 0: Czym jest Cat-Scan?

*Odbiorcy: wszyscy*

Cat-Scan to platforma do optymalizacji QPS dla Google Authorized Buyers. Daje
wgląd w to, jak przydział zapytań na sekundę (QPS) Twojego biddera jest
wykorzystywany (i marnowany), oraz udostępnia narzędzia do jego poprawy.

![Lejek QPS](/docs/qps-funnel.svg)

## Główny problem

Gdy prowadzisz konto kupującego (seat) na giełdzie Google Authorized Buyers,
Google wysyła na endpoint Twojego biddera strumień zapytań ofertowych (bid
requests). Płacisz za ten strumień: zużywa on przydzielony Ci QPS, moc
obliczeniową biddera oraz przepustowość sieci.

Ale nie każde zapytanie ofertowe jest przydatne. Wiele z nich dotyczy
zasobów reklamowych, których nigdy byś nie kupił: kraje, na które nie
targetujesz, wydawcy, o których nigdy nie słyszałeś, rozmiary reklam, na które
nie masz kreacji. Twój bidder i tak musi odebrać i odrzucić każde takie
zapytanie.

W typowej konfiguracji **ponad połowa Twojego QPS to marnotrawstwo.**

## Co Cat-Scan z tym robi

Cat-Scan działa obok Twojego biddera i zapewnia trzy rzeczy:

### 1. Widoczność

Odtwarza raportowanie wydajności z eksportów CSV od Google (ponieważ nie
istnieje Reporting API) i pokazuje pełny lejek RTB: od surowego QPS przez
oferty, wygrane, wyświetlenia, kliknięcia i wydatki. Rozbija to według
geografii, wydawcy, rozmiaru reklamy, kreacji i konfiguracji pretargetingu.

Pozwala to odpowiedzieć na pytania takie jak:
- Które kraje zużywają QPS, ale nie generują żadnych wygranych?
- Którzy wydawcy mają wysoki QPS, ale zerowe wydatki?
- Które rozmiary reklam otrzymują ruch, ale nie mają pasującej kreacji?
- Które konfiguracje pretargetingu działają dobrze, a które słabo?

### 2. Kontrola

Google daje Ci 10 konfiguracji pretargetingu na jedno konto (seat). To Twoja
główna dźwignia do informowania Google, jaki ruch wysyłać, a jaki odfiltrować.
Cat-Scan oferuje:
- Edytor konfiguracji z podglądem próbnym (dry-run)
- Oś czasu historii zmian z przywracaniem jednym kliknięciem
- Listy dozwolonych/blokowanych wydawców na konfigurację
- Optymalizator, który ocenia segmenty i proponuje zmiany konfiguracji

### 3. Bezpieczeństwo

Każda zmiana pretargetingu jest rejestrowana. Możesz zobaczyć podgląd efektów
zmiany przed jej zastosowaniem. Jeśli coś pójdzie nie tak, możesz natychmiast
przywrócić poprzedni stan. Optymalizator korzysta z predefiniowanych trybów
(bezpieczny, zrównoważony, agresywny), więc żadna automatyczna zmiana nie
wchodzi w życie bez weryfikacji przez człowieka.

## Kluczowe pojęcia

Zanim przejdziesz dalej, upewnij się, że te terminy są jasne:

| Pojęcie | Co oznacza |
|---------|------------|
| **Seat** | Konto kupującego w Google Authorized Buyers, identyfikowane przez `buyer_account_id`. Jedna organizacja może mieć wiele kont (seats). |
| **QPS** | Queries Per Second (zapytania na sekundę): maksymalna częstotliwość zapytań ofertowych, o które prosisz Google, aby wysyłał do Twojego biddera. Google ogranicza rzeczywisty wolumen w zależności od poziomu Twojego konta, dlatego chcesz wykorzystać każde zapytanie efektywnie. |
| **Pretargeting** | Filtry po stronie serwera, które mówią Google, jakie zapytania ofertowe Ci wysyłać. Kontrolują: regiony geograficzne, rozmiary reklam, formaty, platformy, typy kreacji. Masz ich 10 na jeden seat. |
| **Lejek RTB** | Progresja od otrzymanego zapytania ofertowego, przez złożoną ofertę, wygraną aukcję, wyświetloną reklamę, kliknięcie, aż po konwersję. Na każdym etapie następuje odpływ; Cat-Scan pokazuje, gdzie. |
| **Marnotrawstwo** | QPS zużywany przez zapytania ofertowe, których Twój bidder nie może lub nie chce wykorzystać. Celem jest zmniejszenie marnotrawstwa bez utraty wartościowego ruchu. |
| **Config** | Skrót od konfiguracji pretargetingu. Każda ma stan (aktywna/zawieszona), maksymalny QPS oraz reguły włączania/wykluczania dla regionów, rozmiarów, formatów i platform. |

## Następne kroki

- [Logowanie](01-logging-in.md): dostęp do dashboardu
- [Nawigacja po dashboardzie](02-navigating-the-dashboard.md): jak się odnaleźć w interfejsie
