# Hoofdstuk 6: Pretargeting-configuratie

*Doelgroep: media-inkopers, campagnemanagers*

Pretargeting-configuraties zijn uw belangrijkste middel om te bepalen wat Google
naar uw bidder stuurt. Dit hoofdstuk behandelt hoe u deze veilig beheert in Cat-Scan.

## Wat een pretargeting-configuratie bepaalt

Elke configuratie is een set regels die Google vertelt: "stuur mij alleen
biedverzoeken die aan deze criteria voldoen." U krijgt **10 configuraties per seat**.

| Veld | Wat het filtert |
|------|----------------|
| **Status** | Actief (ontvangt verkeer) of Onderbroken (gepauzeerd). |
| **Max QPS** | Bovengrens voor het aantal queries per seconde dat deze configuratie accepteert. |
| **Geo's (opgenomen)** | Landen, regio's of steden waaruit verkeer ontvangen wordt. |
| **Geo's (uitgesloten)** | Geografische gebieden die geblokkeerd worden, ook als ze aan de inclusies voldoen. |
| **Formaten (opgenomen)** | Advertentieformaten die geaccepteerd worden (bijv. 300x250, 728x90). |
| **Typen** | Creatieve typen: VIDEO, DISPLAY_IMAGE, DISPLAY_HTML, NATIVE. |
| **Platforms** | Apparaattypen: DESKTOP, MOBILE_APP, MOBILE_WEB, CONNECTED_TV. |
| **Uitgevers** | Toestaan/blokkeren-lijsten voor specifieke uitgeversdomeinen of apps. |

## Een configuratiekaart lezen

Op de startpagina en in de instellingen verschijnt elke configuratie als een kaart
met de huidige status.

![Pretargeting-configuratiekaarten met actieve en gepauzeerde statussen](images/screenshot-pretargeting-configs.png)

Waar u op moet letten:

- **Actief + hoge max QPS + brede geo's** = deze configuratie vangt veel verkeer
  op. Als er ook veel verspilling is, is dit uw grootste optimalisatiedoel.
- **Onderbroken** = ontvangt geen verkeer. Handig om wijzigingen klaar te zetten
  voordat u live gaat.
- **Opgenomen formaten: (alle)** = accepteert elk advertentieformaat dat Google
  stuurt. Voor display met vaste afmetingen is dit vrijwel zeker verspillend.

## Wijzigingen aanbrengen

### De dry-run-werkwijze

1. Navigeer naar de configuratie die u wilt wijzigen (startpagina of
   `/settings/system`).
2. Selecteer een veld om aan te passen (bijv. uitgesloten geo's, opgenomen formaten).
3. Voer uw nieuwe waarden in.
4. Klik op **Preview** (dry-run). Cat-Scan toont u precies wat er verandert
   zonder het daadwerkelijk toe te passen.
5. Als het voorbeeld er correct uitziet, klik dan op **Apply**.
6. De wijziging wordt vastgelegd in de geschiedenis met een tijdstempel en uw identiteit.

### Uitgevers toestaan/blokkeren-editor

Voor blokkering op uitgeversniveau biedt Cat-Scan een speciale editor per configuratie.
U kunt:
- Uitgevers zoeken op domeinnaam
- Individuele domeinen of apps blokkeren
- Specifieke domeinen toestaan die bredere blokkeringen overschrijven
- Wijzigingen in bulk toepassen

Dit is aanzienlijk eenvoudiger dan uitgevers beheren via de Authorized Buyers-interface.

## Wijzigingsgeschiedenis (`/history`)

Elke pretargeting-wijziging wordt vastgelegd in een tijdlijn op `/history`.

![Tijdlijn van wijzigingsgeschiedenis met filters en export](images/screenshot-change-history.png)

Per vermelding ziet u:
- **Wanneer**: tijdstempel van de wijziging
- **Wie**: de gebruiker die de wijziging heeft aangebracht
- **Wat**: veldnaam, oude waarde, nieuwe waarde
- **Type**: het soort wijziging (toevoegen, verwijderen, bijwerken)

## Terugdraaien

Als een wijziging problemen veroorzaakt (bijv. verspilling neemt toe, winratio daalt),
kunt u deze terugdraaien:

1. Ga naar `/history`.
2. Zoek de wijziging die u ongedaan wilt maken.
3. Klik op **Preview rollback**. Dit toont een dry-run van het terugkeren naar de
   vorige status.
4. Voeg optioneel een reden toe voor het terugdraaien.
5. Klik op **Confirm rollback**.

Het terugdraaien zelf wordt als een nieuwe vermelding in de geschiedenis vastgelegd,
zodat u een volledige audittrail hebt.

## Gerelateerd

- [Verspilling analyseren per dimensie](04-analyzing-waste.md): ontdek wat u moet wijzigen
- [De Optimizer](07-optimizer.md): geautomatiseerde suggesties voor configuratiewijzigingen
- Voor DevOps: configuratie-snapshots worden opgeslagen als versie-entiteiten. Zie
  [Databasebeheer](14-database.md).
