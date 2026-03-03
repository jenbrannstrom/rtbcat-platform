# Rozdział 1: Logowanie

*Odbiorcy: wszyscy*

## Metody uwierzytelniania

Cat-Scan obsługuje trzy metody logowania:

| Metoda | Jak działa | Kiedy używać |
|--------|-----------|--------------|
| **Google OAuth** | Kliknij „Zaloguj się przez Google", co przekierowuje przez OAuth2 Proxy | Większość użytkowników. Wykorzystuje konto Google Workspace. |
| **Authing (OIDC)** | Kliknij „Zaloguj się przez Authing", co przekierowuje do dostawcy OIDC | Organizacje korzystające z Authing jako dostawcy tożsamości. |
| **E-mail i hasło** | Wprowadź dane logowania bezpośrednio na stronie logowania | Konta lokalne utworzone przez administratora. |

## Pierwsze logowanie

1. Przejdź do `https://scan.rtb.cat` (lub adresu URL Twojego wdrożenia).
2. Zobaczysz stronę logowania z dostępnymi opcjami logowania.
3. Wybierz metodę i uwierzytelnij się.
4. Przy pierwszym logowaniu system automatycznie tworzy Twój rekord użytkownika
   (dla metod OAuth). Administrator może musieć przyznać Ci dostęp do
   konkretnych kont kupujących (seats).

## Selektor konta (seat)

Po zalogowaniu zobaczysz pasek boczny z **selektorem konta (seat)** u góry.
Jeśli Twoje konto ma dostęp do wielu kont kupujących, użyj rozwijanej listy,
aby się między nimi przełączać. Wszystkie dane na każdej stronie są zawężone
do wybranego konta.

- **Jedno konto**: selektor pokazuje bezpośrednio nazwę i identyfikator konta.
- **Wiele kont**: rozwijana lista pozwala się przełączać. Każdy wpis zawiera
  nazwę wyświetlaną kupującego, `buyer_account_id` oraz liczbę kreacji.
- **Przycisk „Sync All"**: odświeża kreacje, endpointy i konfiguracje
  pretargetingu z API Google dla wybranego konta.

## Gdy logowanie nie powiedzie się

| Objaw | Prawdopodobna przyczyna | Co zrobić |
|-------|------------------------|-----------|
| Pętla przekierowań (strona się ciągle przeładowuje) | Baza danych nieosiągalna, więc sprawdzenie autoryzacji kończy się cichym błędem | Sprawdź kontener Cloud SQL Proxy. Zobacz [Rozwiązywanie problemów](15-troubleshooting.md). |
| „Server unavailable" (502/503/504) | Kontener API lub nginx jest wyłączony | Skontaktuj się z zespołem DevOps. Zobacz [Monitorowanie zdrowia systemu](13-health-monitoring.md). |
| „Authentication required" | Sesja wygasła lub ciasteczko zostało usunięte | Zaloguj się ponownie. |
| „You don't have access to this buyer account" | Uprawnienia do tego konta nie zostały przyznane | Skontaktuj się z administratorem. Zobacz [Administracja użytkownikami](16-user-admin.md). |

## Następne kroki

- [Nawigacja po dashboardzie](02-navigating-the-dashboard.md)
