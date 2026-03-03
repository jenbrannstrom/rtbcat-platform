# Kapitel 2: Navigering i dashboardet

*Målgruppe: alle*

## Sidebjælkens opbygning

Sidebjælken er din primære navigation. Den kan foldes sammen (kun ikoner)
eller udvides. Din præference huskes på tværs af sessioner.

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

Sektioner udvides automatisk, når du navigerer ind i dem.

## Begrænsede brugere

Nogle konti er markeret som "begrænset" af en administrator. Begrænsede brugere
ser kun kernesiderne: startside, kreativer, kampagner, import og historik. QPS-
analyse, indstillinger og admin-sektionerne er skjulte.

## Opsætningschecklisten

Nye konti ser en opsætningscheckliste på `/setup`, der guider gennem den
indledende konfiguration:

1. Tilslut køber-konti (upload GCP-legitimationsoplysninger, opdag pladser)
2. Validér datasundhed (tjek at CSV-importer ankommer)
3. Registrer en optimeringsmodel (BYOM-endpoint)
4. Validér model-endpointet (testkald)
5. Angiv hostingomkostnings-baseline (til økonomiberegninger)
6. Tilslut en konverteringskilde (pixel eller webhook)

Fuldførelsesprocenten spores. Hvert trin linker til den relevante indstillingsside.

## Sprogunderstøttelse

Cat-Scan understøtter engelsk, hollandsk og kinesisk (forenklet). Sprogvælgeren
er i sidebjælken. Din præference gemmes pr. bruger.

## Næste skridt

- Mediekøbere: start med [Forstå din QPS-tragt](03-qps-funnel.md)
- DevOps: start med [Arkitekturoversigt](11-architecture.md)
