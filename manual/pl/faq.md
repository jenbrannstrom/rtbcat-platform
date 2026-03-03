# Najczęściej zadawane pytania

Pytania są otagowane według odbiorcy: **[Buyer]** dla media buyerów
i managerów kampanii, **[DevOps]** dla inżynierów platformowych, **[Oba]**
dla pytań wspólnych.

---

### [Buyer] Dlaczego mój procent pokrycia jest poniżej 100%?

Pokrycie mierzy, ile komórek data x typ raportu zawiera dane w porównaniu
z oczekiwaną liczbą. Typowe przyczyny braków:

- **Google nie wysłał raportu** za daną datę (dzień wolny, opóźnienie
  eksportu).
- **Import z Gmaila pominął wiadomość** (sprawdź status Gmaila).
- **Dany typ raportu nie jest dostępny** dla Twojego seatu (np. dane
  o jakości mogą nie istnieć dla wszystkich buyerów).

Sprawdź siatkę aktualności danych na `/import`, aby zobaczyć dokładnie, które
komórki brakują. Patrz [Import danych](09-data-import.md).

### [Buyer] Jaka jest różnica między „marnotrawstwem" a „niskim współczynnikiem wygranych"?

**Marnotrawstwo** = zapytania o licytację, które Twój bidder *odrzucił* bez
licytowania. To QPS, za które zapłaciłeś, ale nie mogłeś w ogóle wykorzystać.
Napraw to pretargetingiem.

**Niski współczynnik wygranych** = zapytania o licytację, na które Twój bidder
*licytował*, ale przegrał aukcję. Oznacza to, że Twoje oferty nie są
wystarczająco konkurencyjne. Napraw to strategią licytacji, nie pretargetingiem.

Oba pojawiają się w lejku, ale wymagają różnych działań. Patrz
[Zrozumienie lejka QPS](03-qps-funnel.md).

### [Buyer] Czy mogę cofnąć zmianę pretargetingu?

Tak. Przejdź do `/history`, znajdź zmianę, kliknij „Podgląd cofnięcia",
aby zobaczyć, co zostanie przywrócone, a następnie potwierdź. Samo cofnięcie
jest również rejestrowane. Patrz
[Konfiguracja pretargetingu](06-pretargeting.md).

### [Buyer] Jak często powinienem ponownie importować dane?

Codziennie. Automatyczny import z Gmaila obsługuje to automatycznie. Jeśli
importujesz ręcznie, rób to raz dziennie po dotarciu raportów. Nieaktualne dane
oznaczają nieaktualne decyzje.

### [Buyer] Co dokładnie zmienia optymalizator?

Optymalizator proponuje zmiany w Twoich konfiguracjach pretargetingu: dodanie
lub usunięcie regionów geograficznych, rozmiarów, wydawców itp. Nigdy nie
wdraża zmian automatycznie. Każdą propozycję przeglądasz i zatwierdzasz
samodzielnie. Patrz [Optymalizator](07-optimizer.md).

---

### [DevOps] Dlaczego bramka runtime health strict nie przeszła?

Sprawdź logi przepływu pracy: `gh run view <id> --log-failed`. Szukaj FAIL vs.
BLOCKED:

- **FAIL** = coś się zepsuło. Timeout aktualności danych i problemy z SET
  statement_timeout to częste przyczyny. Patrz
  [Rozwiązywanie problemów](15-troubleshooting.md).
- **BLOCKED** = brakuje zależności, niekoniecznie błąd w kodzie. Przykłady:
  brak danych o jakości dla tego buyera, propozycja nie ma billing_id. Porównaj
  z poprzednimi uruchomieniami, aby odróżnić regresje od wcześniejszych braków.

### [DevOps] Dlaczego endpoint aktualności danych jest wolny?

Zapytanie skanuje `rtb_daily` (~84M wierszy) i `rtb_bidstream` (~21M wierszy).
Jeśli plan zapytania degeneruje się do skanu sekwencyjnego zamiast używania
indeksów `(buyer_account_id, metric_date DESC)`, zajmie to minuty.

Naprawa: upewnij się, że zapytania używają wzorca `generate_series + EXISTS`
(14 wyszukiwań indeksowych zamiast pełnego skanu tabeli). Patrz
[Operacje bazodanowe](14-database.md).

### [DevOps] Jak sprawdzić, jaka wersja jest wdrożona?

```bash
curl -sS https://scan.rtb.cat/api/health | jq -r '.git_sha,.version'
```

Zwraca SHA commita i tag obrazu. Porównaj z logiem commitów.

### [DevOps] Jak wdrożyć poprawkę?

1. Wypchnij na `unified-platform`
2. Poczekaj na sukces `build-and-push.yml`
3. Uruchom `deploy.yml` przez `gh workflow run` z `confirm=DEPLOY`
4. Zweryfikuj za pomocą `/api/health`

Patrz [Wdrażanie](12-deployment.md) — pełna procedura.

### [DevOps] Użytkownicy utknęli w pętli logowania. Co robić?

Sprawdź Cloud SQL Proxy: `sudo docker ps | grep cloudsql`. Jeśli nie działa,
zrestartuj go, poczekaj 10 sekund, a następnie zrestartuj kontener API. Patrz
[Rozwiązywanie problemów](15-troubleshooting.md) — pełna procedura.

---

### [Oba] Skąd pochodzą dane Cat-Scan?

Z eksportów CSV Google Authorized Buyers. Nie istnieje Reporting API. Dane
docierają albo przez ręczny upload CSV, albo automatyczny import z Gmaila.
Patrz [Import danych](09-data-import.md).

### [Oba] Czy ponowny import tego samego CSV jest bezpieczny?

Tak. Każdy wiersz jest haszowany i deduplikowany. Ponowny import nigdy nie
powoduje podwójnego zliczania.

### [Oba] Jakie języki obsługuje interfejs?

Angielski, niderlandzki i chiński (uproszczony). Selektor języka znajduje się
w pasku bocznym.
