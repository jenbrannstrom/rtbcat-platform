# Kapitel 0: Hvad er Cat-Scan?

*Målgruppe: alle*

Cat-Scan er en QPS-optimeringsplatform til Google Authorized Buyers. Den giver
dig indsigt i, hvordan din budgivers forespørgsler-per-sekund-allokering bliver
brugt (og spildt), og stiller værktøjerne til rådighed for at forbedre den.

![QPS-tragt](/docs/qps-funnel.svg)

## Kerneproblemet

Når du driver en plads på Googles Authorized Buyers-børs, sender Google en
strøm af budforespørgsler til din budgivers endpoint. Du betaler for denne
strøm: den forbruger din tildelte QPS, din budgivers beregningskraft og din
netværksbåndbredde.

Men ikke alle budforespørgsler er nyttige. Mange ankommer for inventar, du
aldrig ville købe: lande du ikke målretter mod, udgivere du aldrig har hørt om,
annoncestørrelser du ikke har kreativer til. Din budgiver skal stadig modtage
og afvise hver enkelt.

I et typisk setup er **mere end halvdelen af din QPS spild.**

## Hvad Cat-Scan gør ved det

Cat-Scan fungerer sideløbende med din budgiver og leverer tre ting:

### 1. Synlighed

Den genopbygger performance-rapportering fra Googles CSV-eksporter (da der ikke
er nogen Reporting API) og viser dig den fulde RTB-tragt: fra rå QPS gennem
bud, vindere, visninger, klik og forbrug. Den opdeler dette efter geografi,
udgiver, annoncestørrelse, kreativ og pretargeting-konfiguration.

Dette gør det muligt at besvare spørgsmål som:
- Hvilke lande forbruger QPS, men genererer ingen vindere?
- Hvilke udgivere har høj QPS, men nul forbrug?
- Hvilke annoncestørrelser modtager trafik, men har ingen matchende kreativ?
- Hvilke pretargeting-konfigurationer klarer sig godt vs. dårligt?

### 2. Kontrol

Google giver dig 10 pretargeting-konfigurationer pr. plads. Disse er dit
primære værktøj til at fortælle Google, hvilken trafik der skal sendes, og hvad
der skal filtreres fra. Cat-Scan tilbyder:
- En konfigurationseditor med dry-run forhåndsvisning
- En ændringshistorik-tidslinje med et-klik-tilbagerulning
- Udgivertilladelse/blokeringslister pr. konfiguration
- En optimeringsmotor, der scorer segmenter og foreslår konfigurationsændringer

### 3. Sikkerhed

Enhver pretargeting-ændring registreres. Du kan forhåndsvise, hvad en ændring
vil gøre, før den anvendes. Hvis noget går galt, kan du rulle tilbage øjeblikkeligt.
Optimeringsmotoren bruger workflow-forudindstillinger (sikker, balanceret,
aggressiv), så ingen automatiseret ændring går i produktion uden menneskelig
gennemgang.

## Nøglebegreber

Sørg for, at disse begreber er klare, før du fortsætter:

| Begreb | Hvad det betyder |
|--------|------------------|
| **Plads (Seat)** | En køber-konto på Google Authorized Buyers, identificeret ved et `buyer_account_id`. En organisation kan have flere pladser. |
| **QPS** | Queries Per Second: den maksimale hastighed af budforespørgsler, du beder Google om at sende til din budgiver. Google begrænser det faktiske volumen baseret på dit kontoniveau, så du ønsker at bruge hver forespørgsel effektivt. |
| **Pretargeting** | Serverside-filtre, der fortæller Google, hvilke budforespørgsler der skal sendes til dig. Styrer: geografier, annoncestørrelser, formater, platforme, kreativtyper. Du får 10 pr. plads. |
| **RTB-tragt** | Forløbet fra modtaget budforespørgsel, til afgivet bud, til vundet auktion, til vist annonce, til klik, til konvertering. Hvert trin har frafald; Cat-Scan viser dig hvor. |
| **Spild** | QPS forbrugt af budforespørgsler, din budgiver ikke kan eller vil bruge. Målet er at reducere spild uden at miste værdifuld trafik. |
| **Konfiguration** | Kort for pretargeting-konfiguration. Hver har en tilstand (aktiv/suspenderet), en maks-QPS og inklusions-/eksklusionsregler for geografier, størrelser, formater og platforme. |

## Næste skridt

- [Log ind](01-logging-in.md): få adgang til dashboardet
- [Navigering i dashboardet](02-navigating-the-dashboard.md): find rundt i systemet
