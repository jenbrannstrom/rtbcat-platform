# Hoofdstuk 17: Integraties

*Doelgroep: DevOps, platform-engineers*

## GCP-serviceaccounts

Cat-Scan heeft GCP-serviceaccountinloggegevens nodig om te communiceren met Google API's.

**Configuratie:**
1. Maak een serviceaccount aan in je GCP-project met toegang tot de Authorized Buyers API.
2. Download het JSON-sleutelbestand.
3. Upload het via `/settings/accounts` > tabblad API-verbinding.
4. Valideer de verbinding: Cat-Scan test de bereikbaarheid en rechten.

**Wat het mogelijk maakt:**
- Seat-ontdekking (`discoverSeats`)
- Pretargeting-configuratiesynchronisatie (`syncPretargetingConfigs`)
- RTB-endpoint-synchronisatie (`syncRTBEndpoints`)
- Creative-verzameling (`collectCreatives`)

**Projectstatus:**
Controleer de gezondheid van het GCP-project via `/settings/accounts` of via
`GET /integrations/gcp/project-status`. Dit verifieert dat het serviceaccount geldig is, het project toegankelijk is en de vereiste API's zijn ingeschakeld.

## Google Authorized Buyers API

Cat-Scan synchroniseert data vanuit de Authorized Buyers API:

| Bewerking | Wat het ophaalt | Wanneer uitvoeren |
|-----------|-----------------|-------------------|
| **Seat-ontdekking** | Kopersaccounts gekoppeld aan het serviceaccount | Initiële setup, wanneer nieuwe seats worden toegevoegd |
| **Pretargeting-synchronisatie** | Huidige pretargeting-configuratiestatus van Google | Na externe wijzigingen in de AB-interface |
| **RTB-endpoint-synchronisatie** | Bidder-endpoint-URL's en status | Initiële setup, na endpoint-wijzigingen |
| **Creative-synchronisatie** | Creative-metadata (formaten, afmetingen, bestemmingen) | Periodiek, via "Sync All" in de zijbalk |

## Gmail-integratie

Google Authorized Buyers stuurt dagelijks CSV-rapporten per e-mail. Cat-Scan kan deze automatisch verwerken.

**Configuratie:**
1. Ga naar `/settings/accounts` > tabblad Gmail-rapporten.
2. Autoriseer Cat-Scan om toegang te krijgen tot het Gmail-account dat AB-rapporten ontvangt.
3. Cat-Scan pollt voor nieuwe rapportmails en importeert bijgevoegde CSV's.

**Monitoring:**
- `GET /gmail/status`: huidige status, aantal ongelezen, laatste reden
- `POST /gmail/import/start`: handmatig een importcyclus starten
- `POST /gmail/import/stop`: een lopende import stoppen
- `GET /gmail/import/history`: eerdere importrecords

**Probleemoplossing:**
- Hoog aantal ongelezen (30+): importachterstand, mogelijk handmatige actie nodig
- `last_reason: error`: controleer de logs, mogelijk opnieuw autoriseren
- Zie [Probleemoplossing](15-troubleshooting.md) voor gedetailleerde stappen.

## Taal-AI-providers

Cat-Scan gebruikt AI om de taal van creatives te detecteren en geo-linguistische mismatches te signaleren (bijv. een Spaanse advertentie in een Arabische markt).

**Ondersteunde providers:**

| Provider | Configuratie |
|----------|--------------|
| Gemini | API-sleutel via `/settings/accounts` |
| Claude | API-sleutel via `/settings/accounts` |
| Grok | API-sleutel via `/settings/accounts` |

Configureer via `GET/PUT /integrations/language-ai/config`. Er hoeft slechts een provider actief te zijn.

## Conversie-webhooks

Externe systemen sturen conversiegebeurtenissen naar Cat-Scan via webhooks.

**Beveiligingslagen:**

| Laag | Doel | Configuratie |
|------|------|--------------|
| **HMAC-verificatie** | Garandeert dat verzoeken authentiek zijn (ondertekend met gedeeld geheim) | Gedeeld geheim geconfigureerd in webhook-instellingen |
| **Snelheidsbeperking** | Voorkomt misbruik | Automatisch, configureerbare drempels |
| **Versheidsmonitoring** | Waarschuwt wanneer gebeurtenissen ophouden te arriveren | Configureerbaar verouderingsvenster |

**Monitoring:**
- `GET /conversions/security/status`: HMAC-status, snelheidsbeperkingsstatus, versheidssstatus
- `GET /conversions/health`: algehele gezondheid van inname en aggregatie
- `GET /conversions/readiness`: of conversiedata vers genoeg is om te vertrouwen

## Gerelateerd

- [Architectuuroverzicht](11-architecture.md): waar integraties passen
- [Gebruikersbeheer](16-user-admin.md): serviceaccounts beheren
- Voor mediakopers: [Conversies en attributie](08-conversions.md) behandelt de kopersgerichte conversie-inrichting.
