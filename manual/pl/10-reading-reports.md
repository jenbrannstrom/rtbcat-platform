# Rozdział 10: Odczytywanie raportów

*Odbiorcy: media buyerzy, managerowie kampanii*

Ten rozdział wyjaśnia panele analityczne w Cat-Scan i sposób interpretacji
prezentowanych liczb.

## Statystyki wydatków

Dostępne na stronie głównej i w szczegółach poszczególnych konfiguracji.

| Metryka | Co przekazuje |
|---------|---------------|
| **Łączne wydatki** | Wydatki brutto w wybranym okresie i dla wybranego seatu. |
| **Trend wydatków** | Ostatni okres w porównaniu z poprzednim. Rosnące wydatki przy stałych wygranach = inflacja kosztów. |
| **Wydatki wg konfiguracji** | Która konfiguracja pretargetingu odpowiada za jaką część wydatków. Pomaga określić, które konfiguracje optymalizować w pierwszej kolejności. |

## Wydajność konfiguracji

Pokazuje, jak poszczególne konfiguracje pretargetingu radziły sobie w czasie.

- **Rozbicie dzienne**: wyświetlenia, kliknięcia, wydatki, wskaźnik wygranych,
  CTR i CPM dla każdej konfiguracji w wybranym okresie.
- **Linie trendu**: pozwalają dostrzec konfiguracje o pogarszającej się
  wydajności.
- **Rozbicie wg pól**: które konkretne pola (geo, rozmiary, formaty) w ramach
  konfiguracji generują dane wyniki.

## Wydajność endpointów

Pokazuje wykorzystanie QPS na endpoint biddera.

- **Współczynnik wydajności**: użyteczny QPS / całkowity QPS. Im bliżej
  1,0, tym lepiej.
- **Rozbicie wg endpointów**: jeśli Twój bidder ma wiele endpointów,
  sprawdź, które są najbardziej, a które najmniej wydajne.
- Wykorzystaj to do oceny, czy konsolidacja endpointów przyniosłaby korzyści.

## Porównania migawek

Po cofnięciu zmiany pretargetingu (lub zastosowaniu nowej) panel porównania
migawek pokazuje:

- **Przed**: stan konfiguracji przed zmianą
- **Po**: stan konfiguracji po zmianie
- **Różnica**: co dokładnie się zmieniło (pola dodane/usunięte/zmodyfikowane)

Jest to przydatne do analizy po wprowadzeniu zmian: „Wczoraj wykluczyłem
5 geo -- co stało się z moim lejkiem?"

## Rekomendowane optymalizacje

Cat-Scan może wyświetlać rekomendacje generowane przez AI na podstawie Twoich
danych. Sugerują one konkretne zmiany konfiguracji wraz z szacowanym wpływem.
Są to sugestie, a nie automatyczne działania. To Ty zawsze decydujesz, czy
je zastosować.

## Wskazówki dotyczące odczytywania raportów

1. **Zawsze sprawdzaj selektor okresu.** Widok 7-dniowy i 30-dniowy mogą
   opowiadać zupełnie inne historie.
2. **Porównuj konfiguracje, nie patrz tylko na sumy.** Jedna źle działająca
   konfiguracja może zaniżać wyniki zagregowane, podczas gdy inne konfiguracje
   radzą sobie dobrze.
3. **Patrz na trendy, nie na migawki.** Dane z jednego dnia są zaszumione.
   Trendy z 7-14 dni są bardziej wiarygodne.
4. **Krzyżuj wymiary.** Wysokie straty w widoku geo + wysokie straty w widoku
   rozmiarów dla tej samej konfiguracji = dwie osobne możliwości optymalizacji.

## Powiązane

- [Zrozumienie lejka QPS](03-qps-funnel.md): widok podsumowujący
- [Analiza strat wg wymiarów](04-analyzing-waste.md): szczegółowa analiza
  źródeł strat
- [Konfiguracja pretargetingu](06-pretargeting.md): działanie na podstawie
  wniosków z raportów
