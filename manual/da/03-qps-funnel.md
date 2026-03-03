# Kapitel 3: Forstå din QPS-tragt

*Målgruppe: mediekøbere, kampagneansvarlige*

Dette er startsiden i Cat-Scan (`/`). Alt begynder her.

## Hvad du ser

Siden QPS Waste Optimizer viser din RTB-tragt (rejsen fra budforespørgsel til
forbrug) og fremhæver, hvor volumen falder.

![QPS Waste Optimizer-startside](images/screenshot-qps-home.png)

### Tragten

| Trin | Hvad det betyder |
|------|------------------|
| **QPS** | Det maksimale antal budforespørgsler pr. sekund, du beder Google om at sende. Google begrænser det faktiske volumen baseret på dit kontoniveau, så du modtager typisk mindre end dit loft. |
| **Bud** | Hvor mange af disse forespørgsler din budgiver valgte at byde på. Resten blev afvist (forkert inventar, ingen matchende kreativ, under bundpris). |
| **Vindere** | Auktioner din budgiver vandt. Du betaler kun for vindere. |
| **Visninger** | Annoncer der faktisk blev vist for brugere efter gevinst. |
| **Klik** | Brugerinteraktioner med dine viste annoncer. |
| **Forbrug** | Samlet beløb brugt på vundne visninger. |

Gabet mellem hvert trin er der, hvor optimeringsmuligheden ligger. Et stort
fald fra QPS til Bud betyder, at din budgiver afviser det meste af, hvad
Google sender -- klassisk spild, som pretargeting kan løse.

### Nøgletal

- **Vinderprocent**: Vindere / Bud. Hvor konkurrencedygtige dine bud er.
- **CTR**: Klik / Visninger. Hvor engagerende dine kreativer er.
- **CPM**: Pris pr. tusind visninger. Hvad du betaler for synlighed.
- **Spildandel**: (QPS - Bud) / QPS. Andelen af trafik, du ikke kan bruge.

### Pretargeting-konfigurationskort

Under tragten ser du kort for hver af dine pretargeting-konfigurationer (op til
10 pr. plads). Hvert kort viser:

- **Tilstand**: Aktiv eller Suspenderet
- **Maks QPS**: Loftet for budforespørgsler, denne konfiguration accepterer
- **Formater**: VIDEO, DISPLAY_IMAGE, DISPLAY_HTML, NATIVE
- **Platforme**: DESKTOP, MOBILE_APP, MOBILE_WEB, CONNECTED_TV
- **Geografier**: Inkluderede og ekskluderede geografiske mål
- **Størrelser**: Inkluderede annoncestørrelser (eller alle, hvis ufiltreret)

### Kontrolelementer

- **Periodevælger**: 7, 14 eller 30 dages data
- **Pladsfilter**: afgræns til en specifik køber-plads
- **Konfigurationsskift**: zoom ind på en specifik pretargeting-konfiguration

## Sådan læser du den

Start med spildandelen. Hvis den er over 50 %, har du et betydeligt
forbedringspotentiale. Se derefter på, hvilke konfigurationer der bidrager
mest til spildet. Klik ind i dimensionsanalyserne ([Geografi](04-analyzing-waste.md),
[Udgiver](04-analyzing-waste.md), [Størrelse](04-analyzing-waste.md)) for at
finde de specifikke kilder.

## Relateret

- [Analyse af spild pr. dimension](04-analyzing-waste.md): zoom ind på
  geografi, udgiver og størrelse
- [Pretargeting-konfiguration](06-pretargeting.md): handl på baggrund af dine fund
