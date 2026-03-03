# Rozdział 7: Optymalizator (BYOM)

*Odbiorcy: media buyerzy, inżynierowie optymalizacji*

Optymalizator to automatyczny silnik optymalizacji Cat-Scan. „BYOM" oznacza
Bring Your Own Model: rejestrujesz zewnętrzny endpoint scoringowy, a Cat-Scan
wykorzystuje go do generowania propozycji zmian konfiguracji.

## Jak to działa

```
  Score          Propose          Review          Apply
────────────> ────────────> ────────────> ────────────>
Your model     Cat-Scan       You (human)    Google AB
evaluates      generates      approve or     config is
segments       config         reject         updated
               changes
```

1. **Scoring**: Cat-Scan przesyła dane segmentów do endpointu Twojego modelu.
   Model zwraca wynik (score) dla każdego segmentu (geo, rozmiar, wydawca).
2. **Propozycja**: Na podstawie wyników Cat-Scan generuje konkretne zmiany
   pretargetingu (np. „wyklucz te 5 geo", „dodaj te 3 rozmiary").
3. **Przegląd**: Widzisz propozycję wraz z prognozowanym wpływem. Akceptujesz
   lub odrzucasz.
4. **Zastosowanie**: Zaakceptowane propozycje są wysyłane do konfiguracji
   pretargetingu po stronie Google. Zmiana jest rejestrowana w historii.

## Zarządzanie modelami

### Rejestracja modelu

Przejdź do `/settings/system` i znajdź sekcję Optymalizator.

1. Kliknij **Zarejestruj model**.
2. Wypełnij: nazwa, typ modelu, URL endpointu (Twoja usługa scoringowa).
3. Endpoint musi akceptować żądania POST z danymi segmentów i zwracać
   wyniki scoringu.
4. Zapisz.

### Walidacja endpointu

Przed aktywacją przetestuj swój model:

1. Kliknij **Waliduj endpoint** na karcie modelu.
2. Cat-Scan wyśle testowy payload do Twojego endpointu.
3. Wyniki pokazują: czas odpowiedzi, poprawność formatu odpowiedzi,
   rozkład wyników scoringu.
4. Napraw ewentualne problemy przed aktywacją.

### Aktywacja i dezaktywacja

- **Aktywacja**: model staje się aktywnym scorerem dla danego seatu.
- **Dezaktywacja**: model przestaje być używany, ale jego konfiguracja
  zostaje zachowana. W danym momencie na seat może przypadać tylko jeden
  aktywny model.

## Presety workflow

Podczas uruchamiania procesu scoring-i-propozycja wybierasz preset:

| Preset | Zachowanie | Kiedy stosować |
|--------|------------|----------------|
| **Bezpieczny** | Proponuje tylko zmiany z wysoką pewnością i niskim ryzykiem. Mniejsze usprawnienia, niższe prawdopodobieństwo błędów. | Pierwsze użycie optymalizatora lub konserwatywne konta. |
| **Zrównoważony** | Umiarkowany próg pewności. Dobry kompromis między wpływem a bezpieczeństwem. | Domyślny tryb do większości zastosowań. |
| **Agresywny** | Proponuje większe zmiany z wyższym potencjalnym wpływem. Większe ryzyko nadmiernej optymalizacji. | Doświadczeni użytkownicy, którzy monitorują dane codziennie i mogą szybko cofnąć zmiany. |

## Ekonomia

Optymalizator śledzi również ekonomię optymalizacji:

- **Efektywny CPM**: ile faktycznie płacisz za tysiąc wyświetleń, z
  uwzględnieniem strat.
- **Bazowy koszt hostingu**: koszt infrastruktury Twojego biddera,
  konfigurowany w ustawieniach optymalizatora. Służy do obliczania, czy
  oszczędności z redukcji QPS przewyższają koszty hostingu.
- **Podsumowanie wydajności**: ogólny stosunek użytecznego QPS do
  całkowitego QPS.

Skonfiguruj koszt hostingu w `/settings/system` > Ustawienia optymalizatora.

## Przeglądanie propozycji

Każda propozycja zawiera:
- **Wyniki segmentów**, które napędzały rekomendację
- **Konkretne zmiany** pól pretargetingu (dodania, usunięcia, aktualizacje)
- **Prognozowany wpływ** na QPS, współczynnik strat i wydatki

Możesz:
- **Zaakceptować**: oznacza propozycję jako przyjętą
- **Zastosować**: wysyła zaakceptowane zmiany do Google
- **Odrzucić**: odrzuca propozycję
- **Sprawdzić status zastosowania**: weryfikuje, czy zmiany zostały
  wprowadzone po stronie Google

## Powiązane

- [Konfiguracja pretargetingu](06-pretargeting.md): konfiguracje, które
  optymalizator modyfikuje
- [Konwersje i atrybucja](08-conversions.md): dane konwersji wpływają na
  jakość scoringu
- [Odczytywanie raportów](10-reading-reports.md): śledzenie wpływu
  optymalizatora
