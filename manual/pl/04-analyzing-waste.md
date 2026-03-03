# Rozdział 4: Analiza marnotrawstwa według wymiarów

*Odbiorcy: kupcy mediowi, menedżerowie kampanii*

Gdy już wiesz, *ile* marnotrawstwa masz (z [lejka](03-qps-funnel.md)), te
trzy widoki powiedzą Ci, *skąd* ono pochodzi.

## Marnotrawstwo geograficzne (`/qps/geo`)

Pokazuje zużycie QPS i wydajność według kraju i miasta.

![Geograficzny podział QPS według kraju](images/screenshot-geo-qps.png)

**Na co zwrócić uwagę:**
- Kraje z wysokim QPS, ale zerowymi lub bliskimi zeru wygranymi. Google
  wysyła Ci ruch z regionów, na które Twoi kupujący nie targetują.
- Miasta z nieproporcjonalnie dużym udziałem QPS, ale niskimi wydatkami —
  czyli „długi ogon" regionów geograficznych, które dodają wolumen, ale nie
  wartość.

**Co z tym zrobić:**
- Dodaj słabo działające regiony do listy wykluczeń pretargetingu. Zobacz
  [Konfiguracja pretargetingu](06-pretargeting.md).

**Kontrolki:** Selektor okresu (7/14/30 dni), filtr konta (seat).

## Marnotrawstwo na wydawcach (`/qps/publisher`)

Pokazuje wydajność w podziale na domenę wydawcy lub aplikację.

![QPS wydawców z analizą współczynnika wygranych](images/screenshot-pub-qps.png)

**Na co zwrócić uwagę:**
- Domeny z wysokim wolumenem ofert, ale zerowymi wyświetleniami. Twój bidder
  zużywa moc obliczeniową na zasoby reklamowe, które nigdy się nie renderują.
- Aplikacje lub strony z nienormalnie niskim współczynnikiem wygranych. Licytujesz,
  ale konsekwentnie przegrywasz, co oznacza marnowanie czasu na ocenę ofert.
- Znane domeny niskiej jakości.

**Co z tym zrobić:**
- Zablokuj konkretnych wydawców na liście blokowania w konfiguracji
  pretargetingu. Edytor wydawców Cat-Scan ułatwia to w porównaniu z
  interfejsem Authorized Buyers.

**Kontrolki:** Selektor okresu, filtr geograficzny, wyszukiwanie po domenie.

## Marnotrawstwo na rozmiarach (`/qps/size`)

Pokazuje, które rozmiary reklam otrzymują ruch i czy masz dla nich kreacje.

![Podział QPS według rozmiaru](images/screenshot-size-qps.png)

**Na co zwrócić uwagę:**
- Rozmiary z wysokim QPS, ale **bez pasującej kreacji**. Google wysyła ok. 400
  różnych rozmiarów reklam. Jeśli prowadzisz reklamy displayowe o stałym
  rozmiarze (nie HTML), większość tych rozmiarów jest nieistotna. Każde
  zapytanie o niedopasowany rozmiar to czyste marnotrawstwo.
- Rozmiary z kreacjami, które słabo działają. Rozważ, czy zasoby kreacji
  są odpowiednie dla danego formatu.

**Co z tym zrobić:**
- Dodaj nieistotne rozmiary do listy wykluczonych rozmiarów w pretargetingu.
  To pojedyncza optymalizacja o największej dźwigni dla kupujących display.

**Kontrolki:** Selektor okresu, filtr konta (seat), wykres pokrycia.

## Łączenie wymiarów

Te trzy widoki są komplementarne. Typowy cykl optymalizacji:

1. Sprawdź **geografię**: wyklucz kraje, których nie potrzebujesz.
2. Sprawdź **wydawców**: zablokuj domeny, które marnują oferty.
3. Sprawdź **rozmiary**: wyklucz rozmiary bez pasującej kreacji.
4. Zastosuj zmiany przez [Konfigurację pretargetingu](06-pretargeting.md)
   z podglądem próbnym (dry-run).
5. Poczekaj jeden cykl danych (zazwyczaj jeden dzień) i ponownie sprawdź lejek.

## Powiązane

- [Zrozumienie lejka QPS](03-qps-funnel.md): punkt wyjścia
- [Konfiguracja pretargetingu](06-pretargeting.md): działanie na podstawie
  znalezionych problemów
- [Czytanie raportów](10-reading-reports.md): śledzenie wpływu zmian
