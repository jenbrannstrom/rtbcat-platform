# Kapitel 6: Pretargeting-konfiguration

*Målgruppe: medieindkøbere, kampagneansvarlige*

Pretargeting-konfigurationer er dit vigtigste redskab til at styre, hvad Google sender
til din bidder. Dette kapitel forklarer, hvordan du administrerer dem sikkert i Cat-Scan.

## Hvad en pretargeting-konfiguration styrer

Hver konfiguration er et sæt regler, der fortæller Google: "send mig kun budanmodninger,
der matcher disse kriterier." Du får **10 konfigurationer per seat**.

| Felt | Hvad det filtrerer |
|------|-------------------|
| **Tilstand** | Aktiv (modtager trafik) eller Suspenderet (sat på pause). |
| **Maks QPS** | Øvre grænse for forespørgsler per sekund, som denne konfiguration accepterer. |
| **Geografier (inkluderet)** | Lande, regioner eller byer, du vil modtage trafik fra. |
| **Geografier (ekskluderet)** | Geografier, der blokeres, selvom de matcher inkluderinger. |
| **Størrelser (inkluderet)** | Annoncestørrelser, der accepteres (f.eks. 300x250, 728x90). |
| **Formater** | Kreative typer: VIDEO, DISPLAY_IMAGE, DISPLAY_HTML, NATIVE. |
| **Platforme** | Enhedstyper: DESKTOP, MOBILE_APP, MOBILE_WEB, CONNECTED_TV. |
| **Udgivere** | Tillad-/blokeringslister for specifikke udgiverdomæner eller apps. |

## Læsning af et konfigurationskort

På forsiden og under indstillinger vises hver konfiguration som et kort, der viser
dens aktuelle tilstand.

![Pretargeting-konfigurationskort med aktive og pausede tilstande](images/screenshot-pretargeting-configs.png)

Vigtige ting at se efter:

- **Aktiv + høj maks QPS + brede geografier** = denne konfiguration opfanger meget
  trafik. Hvis den også har højt spild, er det dit største optimeringsmål.
- **Suspenderet** = modtager ikke trafik. Nyttigt til at forberede ændringer, inden
  de sættes i drift.
- **Inkluderede størrelser: (alle)** = accepterer alle annoncestørrelser, Google sender.
  Ved fastformat-display er dette næsten helt sikkert spild.

## Foretag ændringer

### Dry-run-arbejdsgangen

1. Naviger til den konfiguration, du vil ændre (forsiden eller
   `/settings/system`).
2. Vælg det felt, der skal ændres (f.eks. ekskluderede geografier, inkluderede størrelser).
3. Indtast dine nye værdier.
4. Klik på **Preview** (dry-run). Cat-Scan viser dig præcis, hvad der vil ændre sig,
   uden at anvende det.
5. Hvis forhåndsvisningen ser korrekt ud, klik på **Apply**.
6. Ændringen registreres i historikken med et tidsstempel og din identitet.

### Udgiver tillad-/blokeringseditor

Til blokering på udgiverniveau tilbyder Cat-Scan en dedikeret editor per konfiguration.
Du kan:
- Søge efter udgivere via domænenavn
- Blokere individuelle domæner eller apps
- Tillade specifikke domæner, der tilsidesætter bredere blokeringer
- Anvende ændringer samlet

Dette er væsentligt enklere end at administrere udgivere gennem Authorized
Buyers-brugergrænsefladen.

## Ændringshistorik (`/history`)

Enhver pretargeting-ændring registreres i en tidslinje på `/history`.

![Tidslinjevisning af ændringshistorik med filtre og eksport](images/screenshot-change-history.png)

For hver post ser du:
- **Hvornår**: tidsstempel for ændringen
- **Hvem**: brugeren, der foretog den
- **Hvad**: feltnavn, gammel værdi, ny værdi
- **Type**: typen af ændring (tilføj, fjern, opdater)

## Tilbagerulning

Hvis en ændring forårsager problemer (f.eks. spild stiger, vindrate falder), kan du
rulle den tilbage:

1. Gå til `/history`.
2. Find den ændring, du vil fortryde.
3. Klik på **Preview rollback**. Dette viser en dry-run af tilbagevenden til den
   tidligere tilstand.
4. Tilføj eventuelt en begrundelse for tilbagerulningen.
5. Klik på **Confirm rollback**.

Tilbagerulningen registreres selv som en ny post i historikken, så du har
et komplet revisionsspor.

## Relateret

- [Analyse af spild pr. dimension](04-analyzing-waste.md): find hvad der skal ændres
- [Optimeringsværktøjet](07-optimizer.md): automatiserede forslag til konfigurationsændringer
- For DevOps: konfigurationssnapshots gemmes som versionerede entiteter. Se
  [Databaseoperationer](14-database.md).
