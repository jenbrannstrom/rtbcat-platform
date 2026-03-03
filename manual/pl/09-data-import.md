# Rozdział 9: Import danych

*Odbiorcy: media buyerzy, managerowie kampanii*

Analiza Cat-Scan opiera się w całości na danych wydajnościowych z Google
Authorized Buyers. Ponieważ Google nie udostępnia API raportowania, wszystkie
dane pochodzą z eksportów CSV. Ten rozdział wyjaśnia, jak wprowadzić dane do
Cat-Scan i jak zweryfikować, że napływają prawidłowo.

## Dlaczego to ważne

Bez zaimportowanych danych Cat-Scan nie ma czego analizować. Lejek, widoki
strat, wydajność kreacji i optymalizator -- wszystko to zależy od świeżych
danych CSV. Jeśli Twoje dane są nieaktualne, podejmujesz decyzje na
podstawie starych informacji.

## Dwa sposoby dostarczania danych

### 1. Ręczne przesyłanie CSV (`/import`)

Przeciągnij i upuść plik CSV wyeksportowany z Google Authorized Buyers.

![Strona importu danych ze strefą przesyłania i siatką świeżości](images/screenshot-import.png)

**Workflow:**

1. Wyeksportuj raport z konta Google Authorized Buyers.
2. Przejdź do `/import` w Cat-Scan.
3. Przeciągnij plik do strefy upuszczania (lub kliknij, aby przeglądać).
4. Cat-Scan **automatycznie rozpoznaje typ raportu** i wyświetla podgląd:
   - Wymagane kolumny a znalezione kolumny
   - Liczba wierszy i zakres dat
   - Ewentualne błędy walidacji
5. Przejrzyj podgląd. Jeśli kolumny wymagają ponownego mapowania, użyj
   edytora mapowania kolumn.
6. Kliknij **Importuj**.
7. Pasek postępu pokazuje status przesyłania. Pliki powyżej 5 MB są
   automatycznie przesyłane w częściach.
8. Wyniki pokazują: zaimportowane wiersze, pominięte duplikaty, ewentualne
   błędy.

**Typy raportów** rozpoznawane automatycznie:

| Typ | Wzorzec nazwy CSV | Zawartość |
|-----|-------------------|-----------|
| bidsinauction | `catscan-report-*` | Dzienna wydajność RTB: wyświetlenia, stawki, wygrane, wydatki |
| quality | `catscan-report-*` (metryki jakości) | Sygnały jakości: widoczność, oszustwa, bezpieczeństwo marki |
| pipeline-geo | `*-pipeline-geo-*` | Rozkład geograficzny strumienia stawek |
| pipeline-publisher | `*-pipeline-publisher-*` | Rozkład wg domen wydawców |
| bid-filtering | `*-bid-filtering-*` | Przyczyny i wolumeny filtrowania stawek |

### 2. Automatyczny import z Gmaila

Cat-Scan może automatycznie pobierać raporty z połączonego konta Gmail.

- Google Authorized Buyers wysyła codzienne raporty e-mailem.
- Integracja Cat-Scan z Gmailem odczytuje te wiadomości i automatycznie
  importuje załączniki CSV.
- Sprawdź status w `/settings/accounts` > zakładka Raporty Gmail lub przez
  `/gmail/status` w API.

**Aby zweryfikować, czy import z Gmaila działa:**
- Sprawdź panel Statusu Gmaila: `last_reason` powinno mieć wartość `running`.
- Sprawdź licznik `unread`: duża liczba nieprzeczytanych wiadomości może
  wskazywać, że import utknął.
- Sprawdź historię importu pod kątem ostatnich wpisów.

## Siatka świeżości danych

Siatka świeżości danych (widoczna pod `/import` i wykorzystywana przez bramkę
stanu systemu) pokazuje **macierz data x typ raportu**:

```
              bidsinauction   quality   pipeline-geo   pipeline-publisher   bid-filtering
2026-03-02    imported        missing   imported       imported             imported
2026-03-01    imported        missing   imported       imported             imported
2026-02-28    imported        imported  imported       imported             imported
...
```

- **imported**: Cat-Scan posiada dane dla tej daty i typu raportu.
- **missing**: brak danych. Raport nie został wyeksportowany, nie dotarł
  przez Gmail lub import się nie powiódł.

**Procent pokrycia** podsumowuje kompletność danych w oknie retrospekcji.
Bramka stanu systemu wykorzystuje tę wartość do określenia, czy system jest
sprawny.

## Deduplikacja

Ponowne zaimportowanie tego samego pliku CSV (lub ponowne przetworzenie tej
samej wiadomości przez Gmail) **nie powoduje** podwójnego zliczania danych.
Każdy wiersz jest haszowany, a duplikaty są pomijane przy wstawianiu. Oznacza
to, że ponowny import jest zawsze bezpieczny.

## Historia importu

Tabela historii importu pod `/import` pokazuje ostatnie 20 importów:

- Znacznik czasu
- Nazwa pliku
- Liczba wierszy
- Sposób uruchomienia importu (ręczne przesyłanie vs. gmail-auto)
- Status (ukończony, nieudany, duplikat)

## Rozwiązywanie problemów

| Problem | Co sprawdzić |
|---------|--------------|
| Komórki „missing" w siatce świeżości | Czy raport został wyeksportowany z Google w danym dniu? Sprawdź e-mail w Gmailu. |
| Import kończy się błędem walidacji | Niezgodność kolumn. Porównaj tabelę wymaganych kolumn z Twoim plikiem CSV. |
| Import Gmaila pokazuje „stopped" | Sprawdź `/settings/accounts` > zakładka Gmail. Może być konieczny restart lub ponowna autoryzacja. |
| Procent pokrycia spada | Raporty napływają, ale za mniejszą liczbę dat niż oczekiwano. Sprawdź harmonogram eksportu w Google AB. |

## Powiązane

- [Zrozumienie lejka QPS](03-qps-funnel.md): zależy od zaimportowanych danych
- [Odczytywanie raportów](10-reading-reports.md): co możesz zrobić z danymi
  po ich zaimportowaniu
- Dla DevOps: szczegóły zapytań o świeżość danych i rozwiązywanie problemów,
  zobacz [Operacje bazodanowe](14-database.md) i [Rozwiązywanie problemów](15-troubleshooting.md).
