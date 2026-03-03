# Rozdział 3: Zrozumienie lejka QPS

*Odbiorcy: kupcy mediowi, menedżerowie kampanii*

To jest strona główna Cat-Scan (`/`). Wszystko zaczyna się tutaj.

## Co widzisz

Strona QPS Waste Optimizer pokazuje Twój lejek RTB (drogę od zapytania
ofertowego do wydatków) i wskazuje, gdzie następują spadki wolumenu.

![Strona główna QPS Waste Optimizer](images/screenshot-qps-home.png)

### Lejek

| Etap | Co oznacza |
|------|------------|
| **QPS** | Maksymalna liczba zapytań ofertowych na sekundę, o które prosisz Google. Google ogranicza rzeczywisty wolumen w zależności od poziomu Twojego konta, więc zazwyczaj otrzymujesz mniej niż Twój limit. |
| **Bids** | Ile z tych zapytań Twój bidder zdecydował się licytować. Reszta została odrzucona (niewłaściwe zasoby reklamowe, brak pasującej kreacji, cena poniżej progu). |
| **Wins** | Aukcje, które Twój bidder wygrał. Płacisz tylko za wygrane. |
| **Impressions** | Reklamy faktycznie wyświetlone użytkownikom po wygraniu aukcji. |
| **Clicks** | Interakcje użytkowników z wyświetlonymi reklamami. |
| **Spend** | Łączna kwota wydana na wygrane wyświetlenia. |

Luka między każdym etapem to miejsce, w którym kryje się potencjał
optymalizacji. Duży spadek z QPS na Bids oznacza, że Twój bidder odrzuca
większość tego, co wysyła Google — to klasyczne marnotrawstwo, które
pretargeting może naprawić.

### Kluczowe metryki

- **Win rate**: Wins / Bids. Jak konkurencyjne są Twoje oferty.
- **CTR**: Clicks / Impressions. Jak angażujące są Twoje kreacje.
- **CPM**: Koszt za tysiąc wyświetleń. Ile płacisz za widoczność.
- **Współczynnik marnotrawstwa**: (QPS - Bids) / QPS. Udział ruchu, którego nie możesz wykorzystać.

### Karty konfiguracji pretargetingu

Pod lejkiem zobaczysz karty dla każdej z Twoich konfiguracji pretargetingu
(do 10 na jeden seat). Każda karta pokazuje:

- **State**: Active lub Suspended
- **Max QPS**: Limit zapytań ofertowych, które ta konfiguracja akceptuje
- **Formats**: VIDEO, DISPLAY_IMAGE, DISPLAY_HTML, NATIVE
- **Platforms**: DESKTOP, MOBILE_APP, MOBILE_WEB, CONNECTED_TV
- **Geos**: Uwzględnione i wykluczone cele geograficzne
- **Sizes**: Uwzględnione rozmiary reklam (lub wszystkie, jeśli bez filtrów)

### Kontrolki

- **Selektor okresu**: 7, 14 lub 30 dni danych
- **Filtr konta (seat)**: zawężenie do konkretnego konta kupującego
- **Przełącznik konfiguracji**: szczegółowy wgląd w konkretną konfigurację pretargetingu

## Jak to czytać

Zacznij od współczynnika marnotrawstwa. Jeśli przekracza 50%, masz znaczny
potencjał do poprawy. Następnie sprawdź, które konfiguracje generują
największe marnotrawstwo. Kliknij w analizy wymiarowe
([Geo](04-analyzing-waste.md), [Wydawca](04-analyzing-waste.md),
[Rozmiar](04-analyzing-waste.md)), aby znaleźć konkretne źródła.

## Powiązane

- [Analiza marnotrawstwa według wymiarów](04-analyzing-waste.md): szczegółowa
  analiza według geografii, wydawcy i rozmiaru
- [Konfiguracja pretargetingu](06-pretargeting.md): działanie na podstawie
  odkryć
