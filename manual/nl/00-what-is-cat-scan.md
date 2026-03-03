# Hoofdstuk 0: Wat is Cat-Scan?

*Doelgroep: iedereen*

Cat-Scan is een QPS-optimalisatieplatform voor Google Authorized Buyers. Het
geeft u inzicht in hoe de queries-per-seconde-toewijzing van uw bidder wordt
gebruikt (en verspild) en biedt de tools om dit te verbeteren.

![QPS-trechter](/docs/qps-funnel.svg)

## Het kernprobleem

Wanneer u een seat op Google's Authorized Buyers-exchange beheert, stuurt
Google een stroom biedverzoeken naar uw bidder-endpoint. U betaalt voor deze
stroom: het verbruikt uw toegewezen QPS, de rekenkracht van uw bidder en uw
netwerkbandbreedte.

Maar niet elk biedverzoek is bruikbaar. Veel verzoeken komen binnen voor
inventaris die u nooit zou kopen: landen die u niet target, uitgevers waar u
nog nooit van heeft gehoord, advertentieformaten waarvoor u geen creatives
heeft. Uw bidder moet elk verzoek toch ontvangen en afwijzen.

In een typische opzet is **meer dan de helft van uw QPS verspilling.**

## Wat Cat-Scan hieraan doet

Cat-Scan werkt naast uw bidder en biedt drie zaken:

### 1. Inzicht

Het reconstrueert prestatierapporten uit Google's CSV-exports (aangezien er
geen Reporting API is) en toont u de volledige RTB-trechter: van ruwe QPS via
biedingen, winsten, impressies, klikken en uitgaven. Dit wordt uitgesplitst
naar geografie, uitgever, advertentieformaat, creative en
pretargeting-configuratie.

Hiermee kunt u vragen beantwoorden zoals:
- Welke landen verbruiken QPS maar genereren geen winsten?
- Welke uitgevers hebben een hoge QPS maar nul uitgaven?
- Welke advertentieformaten ontvangen verkeer maar hebben geen bijpassende creative?
- Welke pretargeting-configuraties presteren goed versus slecht?

### 2. Controle

Google biedt u 10 pretargeting-configuraties per seat. Dit zijn uw
belangrijkste middelen om Google te vertellen welk verkeer het moet sturen en
wat het moet filteren. Cat-Scan biedt:
- Een configuratie-editor met dry-run-preview
- Een tijdlijn van wijzigingsgeschiedenis met rollback in één klik
- Uitgevers-allow/deny-lijsten per configuratie
- Een optimizer die segmenten scoort en configuratiewijzigingen voorstelt

### 3. Veiligheid

Elke pretargeting-wijziging wordt vastgelegd. U kunt een voorbeeld bekijken
van wat een wijziging zal doen voordat u deze toepast. Als er iets misgaat,
kunt u direct terugdraaien. De optimizer gebruikt workflow-presets (veilig,
gebalanceerd, agressief) zodat geen geautomatiseerde wijziging live gaat
zonder menselijke beoordeling.

## Kernbegrippen

Zorg dat de volgende termen duidelijk zijn voordat u verdergaat:

| Begrip | Wat het betekent |
|---------|---------------|
| **Seat** | Een kopersaccount op Google Authorized Buyers, geïdentificeerd door een `buyer_account_id`. Eén organisatie kan meerdere seats hebben. |
| **QPS** | Queries Per Second: het maximale aantal biedverzoeken per seconde dat u Google vraagt naar uw bidder te sturen. Google beperkt het werkelijke volume op basis van uw accountniveau, dus u wilt elk verzoek efficiënt benutten. |
| **Pretargeting** | Server-side filters die Google vertellen welke biedverzoeken het u moet sturen. Bepaalt: geografieën, advertentieformaten, formaten, platformen, creative-types. U krijgt er 10 per seat. |
| **RTB-trechter** | De voortgang van ontvangen biedverzoek, naar geplaatst bod, naar gewonnen veiling, naar vertoonde impressie, naar klik, naar conversie. Elke stap heeft uitval; Cat-Scan laat u zien waar. |
| **Verspilling** | QPS verbruikt door biedverzoeken die uw bidder niet kan of wil gebruiken. Het doel is verspilling te verminderen zonder waardevol verkeer te verliezen. |
| **Config** | Afkorting voor pretargeting-configuratie. Elke configuratie heeft een status (actief/opgeschort), een maximale QPS, en inclusie/exclusieregels voor geo's, formaten, formaten en platformen. |

## Volgende stappen

- [Inloggen](01-logging-in.md): toegang tot het dashboard
- [Navigeren door het dashboard](02-navigating-the-dashboard.md): uw weg vinden
