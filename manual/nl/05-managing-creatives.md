# Hoofdstuk 5: Creatives beheren

*Doelgroep: mediakopers, campagnemanagers*

## Creative-galerij (`/creatives`)

De galerij toont alle creatives die gekoppeld zijn aan uw geselecteerde seat.

![Creative-galerij met formaatbadges en prestatieniveaus](images/screenshot-creatives.png)

### Wat u ziet

Elke creative wordt weergegeven als een kaart met:

- **Thumbnail**: automatisch gegenereerd voorbeeld van de advertentie
  (videoframe of display-screenshot)
- **Formaatbadge**: VIDEO, DISPLAY_IMAGE, DISPLAY_HTML of NATIVE
- **Creative ID**: de Authorized Buyers creative-identifier
- **Canoniek formaat**: het primaire advertentieformaat (bijv. 300x250, 728x90)
- **Prestatieniveau**: HIGH, MEDIUM, LOW of NO_DATA, gebaseerd op de
  percentielrangschikking van uitgaven binnen uw seat

### Filteren en zoeken

- **Formaatfilter**: toon alleen Video, Display Image, Display HTML of Native
- **Prestatieniveaufilter**: isoleer hoge of lage presteerders
- **Zoeken**: vind een creative op basis van het ID
- **Periodeselector**: 7, 14 of 30 dagen aan prestatiegegevens

### Thumbnails

Thumbnails worden in batches gegenereerd. Als u plaatshouderafbeeldingen ziet,
gebruik dan de knop voor batchmatige thumbnail-generatie om ontbrekende
thumbnails in de wachtrij te plaatsen. De status wordt in de interface getoond.

### Creative-details

Klik op een creative om het voorbeeldvenster te openen met:

- Bestemmings-URL en diagnostiek (is de landingspagina bereikbaar?)
- Taalherkenning (automatisch gedetecteerd + optie om handmatig te overschrijven)
- Prestatie-uitsplitsing per land (in welke geo's deze creative presteert)
- Geo-linguïstisch rapport (detectie van taal-geografie-mismatches)

**Taal-mismatch-detectie** is een onderscheidende functie: Cat-Scan kan
gevallen signaleren zoals een Spaanstalige advertentie die draait in Arabische
markten, of prijzen in AED gericht op gebruikers in India. Hiervoor wordt uw
geconfigureerde AI-provider gebruikt (Gemini, Claude of Grok).

## Campagneclustering (`/campaigns`)

Met campagnes kunt u creatives organiseren in logische groepen.

### Weergaven

- **Rasterweergave**: campagnekaarten met aantal creatives, uitgaven,
  impressies, klikken
- **Lijstweergave**: compact tabelformaat

### Acties

- **Slepen en neerzetten**: verplaats creatives tussen campagnes of naar de
  niet-toegewezen pool
- **Campagne aanmaken**: geef een nieuwe groep een naam en sleep creatives erin
- **AI-autoclustering**: laat Cat-Scan groeperingen voorstellen op basis van
  creative-eigenschappen (formaat, grootte, bestemming, taal)
- **Campagne verwijderen**: verwijdert de groepering (creatives keren terug
  naar de niet-toegewezen pool)

### Filters

- **Sorteren op**: naam, uitgaven, impressies, klikken, aantal creatives
- **Landfilter**: toon alleen campagnes met creatives die in een specifieke
  geo draaien
- **Problemenfilter**: markeer campagnes met problemen (mismatches, lage
  presteerders)

## Gerelateerd

- [Verspilling analyseren per formaat](04-analyzing-waste.md): formaatverspilling
  hangt direct samen met welke creatives u heeft
- [Uw rapporten lezen](10-reading-reports.md): prestaties op campagneniveau
