# Kapitel 17: Integrationer

*Målgruppe: DevOps, platformingeniører*

## GCP-tjenestekonti

Cat-Scan har brug for GCP-tjenestekontolegitimationsoplysninger for at interagere med Google API'er.

**Opsætning:**
1. Opret en tjenestekonto i dit GCP-projekt med adgang til Authorized Buyers API.
2. Download JSON-nøglefilen.
3. Upload den på `/settings/accounts` > API Connection-fanen.
4. Validér forbindelsen: Cat-Scan tester tilgængelighed og rettigheder.

**Hvad det muliggør:**
- Sædeopdagelse (`discoverSeats`)
- Pretargeting-konfigurationssynkronisering (`syncPretargetingConfigs`)
- RTB-endpoint-synkronisering (`syncRTBEndpoints`)
- Kreativindsamling (`collectCreatives`)

**Projektstatus:**
Tjek GCP-projektsundhed på `/settings/accounts` eller via
`GET /integrations/gcp/project-status`. Dette verificerer, at tjenestekontoen er gyldig, projektet er tilgængeligt, og de nødvendige API'er er aktiveret.

## Google Authorized Buyers API

Cat-Scan synkroniserer data fra Authorized Buyers API:

| Operation | Hvad den henter | Hvornår den skal køres |
|-----------|----------------|----------------------|
| **Sædeopdagelse** | Køberkonti tilknyttet tjenestekontoen | Indledende opsætning, når nye sæder tilføjes |
| **Pretargeting-synkronisering** | Aktuel pretargeting-konfigurationstilstand fra Google | Efter eksterne ændringer i AB-brugerfladen |
| **RTB-endpoint-synkronisering** | Bidder-endpoint-URL'er og status | Indledende opsætning, efter endpointændringer |
| **Kreativsynkronisering** | Kreativmetadata (formater, størrelser, destinationer) | Periodisk, via "Sync All" i sidebaren |

## Gmail-integration

Google Authorized Buyers sender daglige CSV-rapporter via e-mail. Cat-Scan kan indlæse disse automatisk.

**Opsætning:**
1. Gå til `/settings/accounts` > Gmail Reports-fanen.
2. Autoriser Cat-Scan til at tilgå den Gmail-konto, der modtager AB-rapporter.
3. Cat-Scan poller efter nye rapportmails og importerer vedhæftede CSV-filer.

**Overvågning:**
- `GET /gmail/status`: aktuel tilstand, antal ulæste, seneste årsag
- `POST /gmail/import/start`: udløs manuelt en importcyklus
- `POST /gmail/import/stop`: stop en kørende import
- `GET /gmail/import/history`: tidligere importposter

**Fejlfinding:**
- Stort antal ulæste (30+): importefterslæb, kan kræve manuel indgriben
- `last_reason: error`: tjek logfiler, kan kræve genautorisation
- Se [Fejlfinding](15-troubleshooting.md) for detaljerede trin.

## Sprog-AI-udbydere

Cat-Scan bruger AI til at detektere kreativsprog og markere geo-lingvistiske uoverensstemmelser (f.eks. spansk annonce på et arabisk marked).

**Understøttede udbydere:**

| Udbyder | Konfiguration |
|---------|---------------|
| Gemini | API-nøgle på `/settings/accounts` |
| Claude | API-nøgle på `/settings/accounts` |
| Grok | API-nøgle på `/settings/accounts` |

Konfigurér via `GET/PUT /integrations/language-ai/config`. Kun én udbyder behøver at være aktiv.

## Konverteringswebhooks

Eksterne systemer sender konverteringsbegivenheder til Cat-Scan via webhooks.

**Sikkerhedslag:**

| Lag | Formål | Konfiguration |
|-----|--------|---------------|
| **HMAC-verifikation** | Sikrer at forespørgsler er autentiske (signeret med delt hemmelighed) | Delt hemmelighed konfigureret i webhook-indstillinger |
| **Hastighedsbegrænsning** | Forhindrer misbrug | Automatisk, med konfigurerbare tærskler |
| **Friskheds­overvågning** | Alerter når begivenheder holder op med at ankomme | Konfigurerbart forældelsesvindue |

**Overvågning:**
- `GET /conversions/security/status`: HMAC-status, hastighedsbegrænsningstatus, friskheds­status
- `GET /conversions/health`: overordnet indlæsnings- og aggregeringssundhed
- `GET /conversions/readiness`: om konverteringsdata er friske nok til at stole på

## Relateret

- [Arkitekturoversigt](11-architecture.md): hvor integrationer passer ind
- [Brugeradministration](16-user-admin.md): administration af tjenestekonti
- For mediekøbere: [Konverteringer og attribution](08-conversions.md) dækker den købervendte konverteringsopsætning.
