# Rozdział 16: Administracja użytkownikami i uprawnieniami

*Odbiorcy: DevOps, administratorzy systemów*

## Panel administracyjny (`/admin`)

Panel administracyjny jest widoczny tylko dla użytkowników z flagą `is_sudo`. Udostępnia zarządzanie użytkownikami, konfigurację systemu oraz rejestrowanie audytowe.

## Zarządzanie użytkownikami (`/admin/users`)

### Tworzenie użytkowników

Dwie metody:

| Metoda | Kiedy stosować |
|--------|----------------|
| **Konto lokalne** | Dla użytkowników logujących się adresem e-mail i hasłem. Ustawiasz hasło początkowe. |
| **Wstępne tworzenie OAuth** | Dla użytkowników logujących się przez Google OAuth. Wcześniejsze utworzenie rekordu pozwala przypisać uprawnienia przed ich pierwszym logowaniem. |

Pola: e-mail (wymagany), nazwa wyświetlana, rola, metoda uwierzytelniania, hasło (tylko dla kont lokalnych).

### Role i uprawnienia

**Uprawnienia globalne** kontrolują, co użytkownik może robić w całym systemie:
- Standardowy użytkownik: dostęp do głównych funkcji
- Użytkownik z ograniczeniami: ograniczony pasek boczny (brak ustawień, panelu admina i sekcji QPS)
- Administrator (`is_sudo`): pełny dostęp, w tym panel administracyjny

**Uprawnienia na stanowisko (seat)** kontrolują, które konta kupujących widzi użytkownik:
- Przyznawanie dostępu do konkretnych wartości `buyer_account_id`
- Poziomy dostępu mogą się różnić w zależności od stanowiska
- Użytkownik bez uprawnień do stanowisk nie widzi żadnych danych

### Zarządzanie uprawnieniami

1. Przejdź do `/admin/users`
2. Wybierz użytkownika
3. W sekcji „Seat Permissions": przyznaj lub odbierz dostęp do stanowisk kupujących
4. W sekcji „Global Permissions": przyznaj lub odbierz dostęp na poziomie systemu
5. Zmiany wchodzą w życie przy następnym załadowaniu strony przez użytkownika

### Dezaktywacja użytkowników

Dezaktywacja użytkownika zachowuje jego rekord (na potrzeby ścieżki audytu), ale uniemożliwia logowanie. Nie usuwa danych ani uprawnień; użytkownik może zostać ponownie aktywowany.

## Konta usługowe (`/settings/accounts`)

Konta usługowe reprezentują poświadczenia GCP umożliwiające Cat-Scan komunikację z interfejsami API Google.

### Przesyłanie poświadczeń

1. Przejdź do `/settings/accounts` > zakładka API Connection
2. Prześlij plik klucza JSON konta usługowego GCP
3. Cat-Scan zwaliduje poświadczenia i pokaże status połączenia

**Uwaga dotycząca bezpieczeństwa:** Dodaj plik klucza JSON konta usługowego dopiero na końcu konfiguracji, aby zminimalizować ryzyko ekspozycji.

### Co odblokowują konta usługowe

- **Odkrywanie stanowisk**: znajdowanie kont kupujących powiązanych z poświadczeniami
- **Synchronizacja pretargetingu**: pobieranie aktualnego stanu konfiguracji z Google
- **Synchronizacja endpointów RTB**: wykrywanie endpointów licytujących
- **Zbieranie kreacji**: gromadzenie metadanych kreacji

## Dziennik audytu (`/admin/audit-log`)

Każde istotne działanie jest rejestrowane:

| Akcja | Co ją wyzwala |
|-------|---------------|
| `login` | Pomyślne uwierzytelnienie |
| `login_failed` | Nieudana próba uwierzytelnienia |
| `login_blocked` | Logowanie odrzucone (dezaktywowany użytkownik itp.) |
| `create_user` | Utworzenie nowego użytkownika |
| `update_user` | Modyfikacja profilu użytkownika |
| `deactivate_user` | Dezaktywacja użytkownika |
| `reset_password` | Resetowanie hasła |
| `change_password` | Zmiana hasła |
| `grant_permission` | Przyznanie uprawnienia |
| `revoke_permission` | Odebranie uprawnienia |
| `update_setting` | Zmiana ustawienia systemowego |
| `create_initial_admin` | Utworzenie pierwszego administratora podczas konfiguracji |

Filtry: po użytkowniku, typie akcji, typie zasobu, oknie czasowym (dni), z paginacją.

## Konfiguracja systemowa (`/admin/configuration`)

Globalne ustawienia klucz-wartość kontrolujące zachowanie systemu. Edytowalne przez administratorów. Zmiany są rejestrowane w dzienniku audytu.

## Powiązane

- [Logowanie](01-logging-in.md): doświadczenie uwierzytelniania od strony użytkownika
- [Przegląd architektury](11-architecture.md): szczegóły łańcucha zaufania uwierzytelniania
