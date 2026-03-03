# Hoofdstuk 16: Gebruikers- en rechtenbeheer

*Doelgroep: DevOps, systeembeheerders*

## Beheerpaneel (`/admin`)

Het beheerpaneel is alleen zichtbaar voor gebruikers met de `is_sudo`-vlag. Het biedt gebruikersbeheer, systeemconfiguratie en auditlogging.

## Gebruikersbeheer (`/admin/users`)

### Gebruikers aanmaken

Twee methoden:

| Methode | Wanneer te gebruiken |
|---------|----------------------|
| **Lokaal account** | Voor gebruikers die inloggen met e-mail en wachtwoord. Je stelt het initiële wachtwoord in. |
| **OAuth vooraanmaken** | Voor gebruikers die inloggen met Google OAuth. Door het account vooraf aan te maken kun je rechten toewijzen voordat ze voor het eerst inloggen. |

Velden: e-mail (verplicht), weergavenaam, rol, authenticatiemethode, wachtwoord (alleen bij lokaal account).

### Rollen en rechten

**Globale rechten** bepalen wat een gebruiker systeembreed kan doen:
- Standaardgebruiker: toegang tot de hoofdfunctionaliteiten
- Beperkte gebruiker: beperkte zijbalk (geen instellingen, beheer of QPS-secties)
- Beheerder (`is_sudo`): volledige toegang inclusief het beheerpaneel

**Rechten per seat** bepalen welke kopersaccounts een gebruiker kan zien:
- Ken toegang toe tot specifieke `buyer_account_id`-waarden
- Toegangsniveaus kunnen per seat verschillen
- Een gebruiker zonder seat-rechten ziet geen data

### Rechten beheren

1. Ga naar `/admin/users`
2. Selecteer een gebruiker
3. Onder "Seat-rechten": ken toegang tot kopersseats toe of trek deze in
4. Onder "Globale rechten": ken systeemrechten toe of trek deze in
5. Wijzigingen worden van kracht bij de volgende paginalading van de gebruiker

### Gebruikers deactiveren

Het deactiveren van een gebruiker bewaart het record (voor de audittrail), maar voorkomt inloggen. Het verwijdert geen data of rechten; de gebruiker kan opnieuw worden geactiveerd.

## Serviceaccounts (`/settings/accounts`)

Serviceaccounts vertegenwoordigen GCP-inloggegevens waarmee Cat-Scan kan communiceren met Google API's.

### Inloggegevens uploaden

1. Ga naar `/settings/accounts` > tabblad API-verbinding
2. Upload het GCP-serviceaccount JSON-sleutelbestand
3. Cat-Scan valideert de inloggegevens en toont de verbindingsstatus

**Beveiligingsopmerking:** Voeg het JSON-sleutelbestand van het serviceaccount pas toe aan het einde van de configuratie om het blootstellingsrisico te minimaliseren.

### Wat serviceaccounts mogelijk maken

- **Seat-ontdekking**: kopersaccounts vinden die gekoppeld zijn aan de inloggegevens
- **Pretargeting-synchronisatie**: huidige configuratiestatus ophalen bij Google
- **RTB-endpoint-synchronisatie**: bidder-endpoints ontdekken
- **Creative-verzameling**: creative-metadata ophalen

## Auditlog (`/admin/audit-log`)

Elke significante actie wordt gelogd:

| Actie | Wat het triggert |
|-------|-----------------|
| `login` | Geslaagde authenticatie |
| `login_failed` | Mislukte authenticatiepoging |
| `login_blocked` | Inlogpoging geweigerd (gedeactiveerde gebruiker, enz.) |
| `create_user` | Nieuwe gebruiker aangemaakt |
| `update_user` | Gebruikersprofiel gewijzigd |
| `deactivate_user` | Gebruiker gedeactiveerd |
| `reset_password` | Wachtwoord gereset |
| `change_password` | Wachtwoord gewijzigd |
| `grant_permission` | Recht toegekend |
| `revoke_permission` | Recht ingetrokken |
| `update_setting` | Systeeminstelling gewijzigd |
| `create_initial_admin` | Eerste beheerder aangemaakt tijdens de setup |

Filters: op gebruiker, actietype, resourcetype, tijdvenster (dagen), met paginering.

## Systeemconfiguratie (`/admin/configuration`)

Globale sleutel-waarde-instellingen die het systeemgedrag bepalen. Bewerkbaar door beheerders. Wijzigingen worden vastgelegd in het auditlog.

## Gerelateerd

- [Inloggen](01-logging-in.md): de gebruikerservaring bij authenticatie
- [Architectuuroverzicht](11-architecture.md): details van de authenticatievertrouwensketen
