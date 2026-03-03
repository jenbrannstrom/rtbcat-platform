# Hoofdstuk 1: Inloggen

*Doelgroep: iedereen*

## Authenticatiemethoden

Cat-Scan ondersteunt drie inlogmethoden:

| Methode | Hoe het werkt | Wanneer te gebruiken |
|--------|-------------|-------------|
| **Google OAuth** | Klik op "Inloggen met Google", waarna u via OAuth2 Proxy wordt doorgestuurd | De meeste gebruikers. Gebruikt uw Google Workspace-account. |
| **Authing (OIDC)** | Klik op "Inloggen met Authing", waarna u naar de OIDC-provider wordt doorgestuurd | Organisaties die Authing als identiteitsprovider gebruiken. |
| **E-mail en wachtwoord** | Voer inloggegevens rechtstreeks in op de inlogpagina | Lokale accounts aangemaakt door een beheerder. |

## Eerste keer inloggen

1. Navigeer naar `https://scan.rtb.cat` (of de URL van uw implementatie).
2. U ziet de inlogpagina met de beschikbare inlogopties.
3. Kies uw methode en authenticeer.
4. Bij de eerste keer inloggen maakt het systeem automatisch uw
   gebruikersrecord aan (bij OAuth-methoden). Uw beheerder moet u mogelijk
   toegang verlenen tot specifieke buyer-seats.

## De seat-selector

Na het inloggen ziet u de zijbalk met bovenaan een **seat-selector**.
Als uw account toegang heeft tot meerdere buyer-seats, gebruik dan het
keuzemenu om hiertussen te schakelen. Alle gegevens op elke pagina zijn
gekoppeld aan de geselecteerde seat.

- **Enkele seat**: de selector toont direct uw seat-naam en ID.
- **Meerdere seats**: een keuzemenu laat u schakelen. Elke vermelding toont
  de weergavenaam van de koper, het `buyer_account_id` en het aantal creatives.
- **Knop "Alles synchroniseren"**: vernieuwt creatives, endpoints en
  pretargeting-configuraties vanuit Google's API voor de geselecteerde seat.

## Wanneer inloggen mislukt

| Symptoom | Waarschijnlijke oorzaak | Wat te doen |
|---------|-------------|------------|
| Doorverwijslus (pagina blijft herladen) | Database niet bereikbaar, waardoor de authenticatiecontrole stilzwijgend mislukt | Controleer de Cloud SQL Proxy-container. Zie [Probleemoplossing](15-troubleshooting.md). |
| "Server niet beschikbaar" (502/503/504) | API- of nginx-container is gestopt | Neem contact op met uw DevOps-team. Zie [Gezondheidsmonitoring](13-health-monitoring.md). |
| "Authenticatie vereist" | Sessie verlopen of cookie gewist | Log opnieuw in. |
| "U heeft geen toegang tot dit koperaccount" | Machtigingen niet verleend voor deze seat | Vraag uw beheerder. Zie [Gebruikersbeheer](16-user-admin.md). |

## Volgende stappen

- [Navigeren door het dashboard](02-navigating-the-dashboard.md)
