# Rozdział 5: Zarządzanie kreacjami

*Odbiorcy: kupcy mediowi, menedżerowie kampanii*

## Galeria kreacji (`/creatives`)

Galeria pokazuje wszystkie kreacje powiązane z wybranym kontem (seat).

![Galeria kreacji ze znacznikami formatów i poziomami wydajności](images/screenshot-creatives.png)

### Co widzisz

Każda kreacja pojawia się jako karta z następującymi elementami:

- **Miniaturka**: automatycznie wygenerowany podgląd reklamy (klatka wideo
  lub zrzut ekranu reklamy displayowej)
- **Znacznik formatu**: VIDEO, DISPLAY_IMAGE, DISPLAY_HTML lub NATIVE
- **Creative ID**: identyfikator kreacji w Authorized Buyers
- **Rozmiar kanoniczny**: główny rozmiar reklamy (np. 300x250, 728x90)
- **Poziom wydajności**: HIGH, MEDIUM, LOW lub NO_DATA, na podstawie
  rankingu percentylowego wydatków w ramach Twojego konta

### Filtrowanie i wyszukiwanie

- **Filtr formatu**: pokaż tylko Video, Display Image, Display HTML lub Native
- **Filtr poziomu wydajności**: wyodrębnij najlepsze lub najsłabsze kreacje
- **Wyszukiwanie**: znajdź kreację po jej identyfikatorze
- **Selektor okresu**: 7, 14 lub 30 dni danych wydajnościowych

### Miniaturki

Miniaturki są generowane partiami. Jeśli widzisz obrazy zastępcze, użyj
przycisku generowania miniaturek wsadowych, aby dodać brakujące miniaturki
do kolejki. Status jest wyświetlany w interfejsie.

### Szczegóły kreacji

Kliknij dowolną kreację, aby otworzyć modal podglądu z:

- Docelowy URL i diagnostyka (czy strona docelowa jest osiągalna?)
- Wykrywanie języka (automatyczne + opcja ręcznego nadpisania)
- Podział wydajności według kraju (w jakich regionach ta kreacja działa)
- Raport geolingwistyczny (wykrywanie niezgodności języka z geografią)

**Wykrywanie niezgodności językowych** to wyróżniająca funkcja: Cat-Scan
potrafi oznaczyć przypadki takie jak reklama w języku hiszpańskim wyświetlana
na rynkach arabskich lub ceny w AED targetujące użytkowników w Indiach.
Wykorzystuje do tego skonfigurowanego dostawcę AI (Gemini, Claude lub Grok).

## Grupowanie w kampanie (`/campaigns`)

Kampanie pozwalają organizować kreacje w logiczne grupy.

### Widoki

- **Widok siatki**: karty kampanii z liczbą kreacji, wydatkami, wyświetleniami, kliknięciami
- **Widok listy**: kompaktowy format tabelaryczny

### Akcje

- **Przeciągnij i upuść**: przenoś kreacje między kampaniami lub do puli nieprzypisanych
- **Utwórz kampanię**: nazwij nową grupę i przeciągnij do niej kreacje
- **Automatyczne grupowanie AI**: pozwól Cat-Scan zaproponować grupowanie na
  podstawie atrybutów kreacji (format, rozmiar, cel, język)
- **Usuń kampanię**: usuwa grupowanie (kreacje wracają do puli nieprzypisanych)

### Filtry

- **Sortuj według**: nazwy, wydatków, wyświetleń, kliknięć, liczby kreacji
- **Filtr kraju**: pokaż tylko kampanie z kreacjami działającymi w
  konkretnym regionie
- **Filtr problemów**: wyróżnij kampanie z problemami (niezgodności, słaba
  wydajność)

## Powiązane

- [Analiza marnotrawstwa według rozmiaru](04-analyzing-waste.md): marnotrawstwo
  na rozmiarach jest bezpośrednio związane z posiadanymi kreacjami
- [Czytanie raportów](10-reading-reports.md): wydajność na poziomie kampanii
