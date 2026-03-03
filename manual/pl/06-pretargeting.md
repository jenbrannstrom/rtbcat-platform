# Rozdział 6: Konfiguracja pretargetingu

*Odbiorcy: media buyerzy, managerowie kampanii*

Konfiguracje pretargetingu to główne narzędzie kontroli nad tym, co Google
wysyła do Twojego biddera. Ten rozdział opisuje, jak bezpiecznie zarządzać
nimi w Cat-Scan.

## Co kontroluje konfiguracja pretargetingu

Każda konfiguracja to zbiór reguł mówiących Google: „wysyłaj mi tylko te
zapytania o stawkę, które spełniają podane kryteria." Na każdy seat przypada
**10 konfiguracji**.

| Pole | Co filtruje |
|------|-------------|
| **Stan** | Aktywny (odbiera ruch) lub Zawieszony (wstrzymany). |
| **Maks. QPS** | Górny limit zapytań na sekundę akceptowanych przez tę konfigurację. |
| **Geolokalizacje (uwzględnione)** | Kraje, regiony lub miasta, z których ma napływać ruch. |
| **Geolokalizacje (wykluczone)** | Obszary geograficzne blokowane nawet przy dopasowaniu do uwzględnionych. |
| **Rozmiary (uwzględnione)** | Akceptowane rozmiary reklam (np. 300x250, 728x90). |
| **Formaty** | Typy kreacji: VIDEO, DISPLAY_IMAGE, DISPLAY_HTML, NATIVE. |
| **Platformy** | Typy urządzeń: DESKTOP, MOBILE_APP, MOBILE_WEB, CONNECTED_TV. |
| **Wydawcy** | Listy dozwolonych/zablokowanych domen lub aplikacji wydawców. |

## Odczytywanie karty konfiguracji

Na stronie głównej i w ustawieniach każda konfiguracja jest wyświetlana jako
karta pokazująca jej bieżący stan.

![Karty konfiguracji pretargetingu pokazujące stany aktywny i wstrzymany](images/screenshot-pretargeting-configs.png)

Na co zwrócić uwagę:

- **Aktywny + wysoki maks. QPS + szerokie geo** = ta konfiguracja przechwytuje
  dużo ruchu. Jeśli jednocześnie generuje dużo strat, jest głównym celem
  optymalizacji.
- **Zawieszony** = nie odbiera ruchu. Przydatne do przygotowywania zmian przed
  uruchomieniem.
- **Uwzględnione rozmiary: (wszystkie)** = akceptuje każdy rozmiar reklamy
  przesyłany przez Google. Przy reklamach display o stałym rozmiarze jest to
  niemal na pewno marnotrawne.

## Wprowadzanie zmian

### Tryb podglądu (dry-run)

1. Przejdź do konfiguracji, którą chcesz zmienić (strona główna lub
   `/settings/system`).
2. Wybierz pole do modyfikacji (np. wykluczone geo, uwzględnione rozmiary).
3. Wprowadź nowe wartości.
4. Kliknij **Podgląd** (dry-run). Cat-Scan pokaże dokładnie, co się zmieni,
   bez faktycznego zastosowania zmian.
5. Jeśli podgląd wygląda poprawnie, kliknij **Zastosuj**.
6. Zmiana jest rejestrowana w historii ze znacznikiem czasu i informacją o
   tożsamości użytkownika.

### Edytor dozwolonych/zablokowanych wydawców

Do blokowania na poziomie wydawców Cat-Scan udostępnia dedykowany edytor
dla każdej konfiguracji. Możesz:
- Wyszukiwać wydawców po nazwie domeny
- Blokować poszczególne domeny lub aplikacje
- Zezwalać na konkretne domeny, nadpisując szersze blokady
- Stosować zmiany hurtowo

Jest to znacznie prostsze niż zarządzanie wydawcami przez interfejs Authorized
Buyers.

## Historia zmian (`/history`)

Każda zmiana pretargetingu jest rejestrowana na osi czasu pod adresem `/history`.

![Oś czasu historii zmian z filtrami i eksportem](images/screenshot-change-history.png)

Dla każdego wpisu widoczne są:
- **Kiedy**: znacznik czasu zmiany
- **Kto**: użytkownik, który ją wprowadził
- **Co**: nazwa pola, stara wartość, nowa wartość
- **Typ**: rodzaj zmiany (dodanie, usunięcie, aktualizacja)

## Cofanie zmian

Jeśli zmiana powoduje problemy (np. wzrost strat, spadek wskaźnika wygranych),
możesz ją cofnąć:

1. Przejdź do `/history`.
2. Znajdź zmianę, którą chcesz cofnąć.
3. Kliknij **Podgląd cofnięcia**. Wyświetli się podgląd (dry-run) powrotu do
   poprzedniego stanu.
4. Opcjonalnie dodaj powód cofnięcia.
5. Kliknij **Potwierdź cofnięcie**.

Cofnięcie jest samo w sobie rejestrowane jako nowy wpis w historii, więc
dysponujesz pełną ścieżką audytu.

## Powiązane

- [Analiza strat wg wymiarów](04-analyzing-waste.md): znajdź to, co warto zmienić
- [Optymalizator](07-optimizer.md): automatyczne sugestie zmian konfiguracji
- Dla DevOps: migawki konfiguracji są przechowywane jako wersjonowane encje.
  Zobacz [Operacje bazodanowe](14-database.md).
