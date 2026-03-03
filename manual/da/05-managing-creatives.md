# Kapitel 5: Håndtering af kreativer

*Målgruppe: mediekøbere, kampagneansvarlige*

## Kreativgalleri (`/creatives`)

Galleriet viser alle kreativer tilknyttet din valgte plads.

![Kreativgalleri med formatmærker og performance-niveauer](images/screenshot-creatives.png)

### Hvad du ser

Hver kreativ vises som et kort med:

- **Miniaturebillede**: automatisk genereret forhåndsvisning af annoncen
  (videobillede eller display-skærmbillede)
- **Formatmærke**: VIDEO, DISPLAY_IMAGE, DISPLAY_HTML eller NATIVE
- **Kreativ-ID**: den kreative identifikator i Authorized Buyers
- **Kanonisk størrelse**: den primære annoncestørrelse (f.eks. 300x250, 728x90)
- **Performance-niveau**: HIGH, MEDIUM, LOW eller NO_DATA, baseret på
  forbrugspercentil-rangering inden for din plads

### Filtrering og søgning

- **Formatfilter**: vis kun Video, Display Image, Display HTML eller Native
- **Performance-niveau-filter**: isoler høj- eller lavt-performende kreativer
- **Søgning**: find en kreativ efter dens ID
- **Periodevælger**: 7, 14 eller 30 dages performance-data

### Miniaturebilleder

Miniaturebilleder genereres i batcher. Hvis du ser pladsholderbilleder, kan du
bruge knappen til batch-miniaturegenerering for at sætte manglende
miniaturebilleder i kø. Status vises i brugerfladen.

### Kreativdetaljer

Klik på en kreativ for at åbne forhåndsvisningsmodalen med:

- Destinations-URL og diagnostik (er landingssiden tilgængelig?)
- Sprogregistrering (automatisk registreret + mulighed for manuel tilsidesættelse)
- Performance-opdeling pr. land (hvilke geografier denne kreativ klarer sig i)
- Geolingvistisk rapport (registrering af uoverensstemmelse mellem sprog og geografi)

**Registrering af sproglig uoverensstemmelse** er en markant funktion: Cat-Scan
kan markere tilfælde som en spansksproget annonce, der kører på arabiske
markeder, eller priser i AED rettet mod brugere i Indien. Dette bruger din
konfigurerede AI-udbyder (Gemini, Claude eller Grok).

## Kampagnegruppering (`/campaigns`)

Kampagner giver dig mulighed for at organisere kreativer i logiske grupper.

### Visninger

- **Gittervisning**: kampagnekort med antal kreativer, forbrug, visninger, klik
- **Listevisning**: kompakt tabelformat

### Handlinger

- **Træk og slip**: flyt kreativer mellem kampagner eller til den ikke-tildelte pulje
- **Opret kampagne**: navngiv en ny gruppe og træk kreativer ind i den
- **AI-autogruppering**: lad Cat-Scan foreslå grupperinger baseret på kreative
  attributter (format, størrelse, destination, sprog)
- **Slet kampagne**: fjerner grupperingen (kreativer returneres til den ikke-tildelte pulje)

### Filtre

- **Sorter efter**: navn, forbrug, visninger, klik, antal kreativer
- **Landefilter**: vis kun kampagner med kreativer, der kører i en specifik
  geografi
- **Problemfilter**: fremhæv kampagner med problemer (uoverensstemmelser, lavt-
  performende kreativer)

## Relateret

- [Analyse af spild pr. størrelse](04-analyzing-waste.md): størrelsesspild er
  direkte knyttet til, hvilke kreativer du har
- [Læs dine rapporter](10-reading-reports.md): performance på kampagneniveau
