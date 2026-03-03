# Rozdział 8: Konwersje i atrybucja

*Odbiorcy: media buyerzy, managerowie kampanii*

Śledzenie konwersji pozwala Cat-Scan mierzyć, co dzieje się po wyświetleniu
reklamy: czy użytkownik podjął wartościową akcję? Te dane zasilają scoring
optymalizatora i pomagają ocenić rzeczywistą skuteczność kampanii.

## Źródła konwersji

Cat-Scan obsługuje dwie metody integracji:

### Pixel

Piksel śledzący uruchamia się na stronie konwersji (np. potwierdzenie
zamówienia).

- Endpoint: `/api/conversions/pixel`
- Parametry: `buyer_id`, `source_type=pixel`, `event_name`, `event_value`,
  `currency`, `event_ts`
- Nie wymaga konfiguracji po stronie serwera poza umieszczeniem piksela na
  stronie.

### Webhook

Twój serwer wysyła zdarzenia konwersji do endpointu webhook Cat-Scan.

- Bardziej niezawodny niż piksele (brak adblockerów, brak zależności po
  stronie klienta).
- Wymaga integracji po stronie serwera.
- Obsługuje weryfikację podpisu HMAC w celu zapewnienia bezpieczeństwa.

## Bezpieczeństwo webhooków

Cat-Scan zapewnia wielowarstwowe zabezpieczenia webhooków:

| Funkcja | Opis |
|---------|------|
| **Weryfikacja HMAC** | Każde żądanie webhook jest podpisywane wspólnym sekretem. Cat-Scan odrzuca niepodpisane lub błędnie podpisane żądania. |
| **Limitowanie częstotliwości** | Zapobiega nadużyciom poprzez ograniczenie liczby żądań w oknie czasowym. |
| **Monitorowanie świeżości** | Generuje alerty, gdy zdarzenia webhook przestają napływać (wykrywanie nieaktualności). |

Skonfiguruj bezpieczeństwo webhooków w `/settings/system` > Stan konwersji.

## Sprawdzenie gotowości

Przed poleganiem na danych konwersji zweryfikuj gotowość:

1. Przejdź do `/settings/system` lub listy kontrolnej konfiguracji.
2. Sprawdź **Gotowość konwersji**: pokazuje, czy źródło jest podłączone i
   dostarcza zdarzenia w oczekiwanym oknie świeżości.
3. Sprawdź **Statystyki importu**: liczby zdarzeń wg typu źródła i okresu.

## Stan konwersji

Panel Stanu konwersji pokazuje:

- Status importu (zdarzenia napływają lub nie)
- Status agregacji (zdarzenia są przetwarzane na metryki)
- Znacznik czasu ostatniego zdarzenia
- Liczba błędów (jeśli występują)

## Powiązane

- [Optymalizator](07-optimizer.md): dane konwersji poprawiają dokładność
  scoringu
- [Import danych](09-data-import.md): kolejna ścieżka importu danych
- Dla DevOps: konfiguracja endpointu webhook i rozwiązywanie problemów,
  zobacz [Integracje](17-integrations.md).
