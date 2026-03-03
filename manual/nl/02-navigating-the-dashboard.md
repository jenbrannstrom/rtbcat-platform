# Hoofdstuk 2: Navigeren door het dashboard

*Doelgroep: iedereen*

## Indeling van de zijbalk

De zijbalk is uw primaire navigatie. Deze kan worden ingeklapt (alleen
pictogrammen) of uitgeklapt. Uw voorkeur wordt onthouden tussen sessies.

```
Seat Selector
 ├── QPS Waste Optimizer         /              (home)
 ├── Creatives                   /creatives
 ├── Campaigns                   /campaigns
 ├── Change History              /history
 ├── Import                      /import
 │
 ├── QPS (expandable)
 │   ├── Publisher                /qps/publisher
 │   ├── Geo                     /qps/geo
 │   └── Size                    /qps/size
 │
 ├── Settings (expandable)
 │   ├── Connected Accounts      /settings/accounts
 │   ├── Data Retention          /settings/retention
 │   └── System Status           /settings/system
 │
 ├── Admin (sudo users only)
 │   ├── Users                   /admin/users
 │   ├── Configuration           /admin/configuration
 │   └── Audit Log               /admin/audit-log
 │
 └── Footer: user email, version, docs link
```

Secties klappen automatisch uit wanneer u erin navigeert.

## Beperkte gebruikers

Sommige accounts zijn door een beheerder als "beperkt" gemarkeerd. Beperkte
gebruikers zien alleen de kernpagina's: home, creatives, campaigns, import
en wijzigingsgeschiedenis. De QPS-analyse, instellingen en beheerderssecties
zijn verborgen.

## De instellingschecklist

Nieuwe accounts zien een instellingschecklist op `/setup` die u door de
initiële configuratie begeleidt:

1. Koperaccounts koppelen (GCP-inloggegevens uploaden, seats ontdekken)
2. Gegevenskwaliteit valideren (controleren of CSV-imports binnenkomen)
3. Een optimizer-model registreren (BYOM-endpoint)
4. Het model-endpoint valideren (testoproep)
5. Hostingkosten-basislijn instellen (voor economische berekeningen)
6. Een conversiebron koppelen (pixel of webhook)

Het voltooiingspercentage wordt bijgehouden. Elke stap linkt naar de
relevante instellingenpagina.

## Taalondersteuning

Cat-Scan ondersteunt Engels, Nederlands en Chinees (vereenvoudigd). De
taalkeuze staat in de zijbalk. Uw voorkeur wordt per gebruiker opgeslagen.

## Volgende stappen

- Mediakopers: begin met [Uw QPS-trechter begrijpen](03-qps-funnel.md)
- DevOps: begin met [Architectuuroverzicht](11-architecture.md)
