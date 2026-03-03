# API Snelreferentie

Dit is een navigeerbare index van de 118+ API-endpoints van Cat-Scan, gegroepeerd
per domein. Zie de interactieve OpenAPI-documentatie op
`https://scan.rtb.cat/api/docs` voor volledige request/response-schema's.

## Kern / Systeem

| Methode | Pad | Doel |
|---------|-----|------|
| GET | `/health` | Liveness-check (git_sha, versie) |
| GET | `/stats` | Systeemstatistieken |
| GET | `/sizes` | Beschikbare advertentieformaten |
| GET | `/system/status` | Serverstatus (Python, Node, FFmpeg, DB, schijf) |
| GET | `/system/data-health` | Datavolledigheid per koper |
| GET | `/system/ui-page-load-metrics` | Prestatiemetingen frontend |
| GET | `/geo/lookup` | Geo-ID naar naamresolutie |
| GET | `/geo/search` | Zoeken in landen/steden |

## Auth

| Methode | Pad | Doel |
|---------|-----|------|
| GET | `/auth/check` | Controleer of de huidige sessie geauthenticeerd is |
| POST | `/auth/logout` | Sessie beëindigen |

## Seats

| Methode | Pad | Doel |
|---------|-----|------|
| GET | `/seats` | Koperstoelen weergeven |
| GET | `/seats/{buyer_id}` | Specifieke stoel ophalen |
| PUT | `/seats/{buyer_id}` | Weergavenaam van stoel bijwerken |
| POST | `/seats/populate` | Stoelen automatisch aanmaken vanuit data |
| POST | `/seats/discover` | Stoelen ontdekken via Google API |
| POST | `/seats/{buyer_id}/sync` | Specifieke stoel synchroniseren |
| POST | `/seats/sync-all` | Volledige synchronisatie (alle stoelen) |
| POST | `/seats/collect-creatives` | Creatieve data verzamelen |

## Creatives

| Methode | Pad | Doel |
|---------|-----|------|
| GET | `/creatives` | Creatives weergeven (met filters) |
| GET | `/creatives/paginated` | Gepagineerde creativelijst |
| GET | `/creatives/{id}` | Creative-details |
| GET | `/creatives/{id}/live` | Live creative-data (cache-bewust) |
| GET | `/creatives/{id}/destination-diagnostics` | Gezondheid bestemmings-URL |
| GET | `/creatives/{id}/countries` | Prestatie-uitsplitsing per land |
| GET | `/creatives/{id}/geo-linguistic` | Geo-linguïstische analyse |
| POST | `/creatives/{id}/detect-language` | Taal automatisch detecteren |
| PUT | `/creatives/{id}/language` | Handmatige taaloverschrijving |
| GET | `/creatives/thumbnail-status` | Batch thumbnailstatus |
| POST | `/creatives/thumbnails/batch` | Ontbrekende thumbnails genereren |

## Campagnes

| Methode | Pad | Doel |
|---------|-----|------|
| GET | `/campaigns` | Campagnes weergeven |
| GET | `/campaigns/{id}` | Campagnedetails |
| GET | `/campaigns/ai` | Door AI gegenereerde clusters |
| GET | `/campaigns/ai/{id}` | AI-campagnedetails |
| PUT | `/campaigns/ai/{id}` | Campagne bijwerken |
| DELETE | `/campaigns/ai/{id}` | Campagne verwijderen |
| GET | `/campaigns/ai/{id}/creatives` | Creatives van campagne |
| DELETE | `/campaigns/ai/{id}/creatives/{creative_id}` | Creative uit campagne verwijderen |
| POST | `/campaigns/auto-cluster` | AI auto-clustering |
| GET | `/campaigns/ai/{id}/performance` | Campagneprestaties |
| GET | `/campaigns/ai/{id}/daily-trend` | Campagnetrenddata |

## Analytics

| Methode | Pad | Doel |
|---------|-----|------|
| GET | `/analytics/waste-report` | Totaaloverzicht verspillingsmetingen |
| GET | `/analytics/size-coverage` | Dekking formaat-targeting |
| GET | `/analytics/rtb-funnel` | RTB-funneluitsplitsing |
| GET | `/analytics/rtb-funnel/configs` | Funnel per configuratie |
| GET | `/analytics/endpoint-efficiency` | QPS-efficiëntie per endpoint |
| GET | `/analytics/spend-stats` | Bestedingsstatistieken |
| GET | `/analytics/config-performance` | Configuratieprestaties over tijd |
| GET | `/analytics/config-performance/breakdown` | Uitsplitsing configuratievelden |
| GET | `/analytics/qps-recommendations` | AI-aanbevelingen |
| GET | `/analytics/performance/batch` | Batch creative-prestaties |
| GET | `/analytics/performance/{creative_id}` | Prestaties van één creative |
| GET | `/analytics/publishers` | Metingen per uitgeversdomein |
| GET | `/analytics/publishers/search` | Uitgevers zoeken |
| GET | `/analytics/languages` | Taalprestaties |
| GET | `/analytics/languages/multi` | Meervoudige taalanalyse |
| GET | `/analytics/geo-performance` | Geografische prestaties |
| GET | `/analytics/geo-performance/multi` | Meervoudige geo-analyse |
| POST | `/analytics/import` | CSV-import |
| POST | `/analytics/mock-traffic` | Testdata genereren |

## Instellingen / Pretargeting

| Methode | Pad | Doel |
|---------|-----|------|
| GET | `/settings/rtb-endpoints` | RTB-endpoints van de bidder |
| POST | `/settings/rtb-endpoints/sync` | Endpointdata synchroniseren |
| GET | `/settings/pretargeting-configs` | Pretargeting-configuraties weergeven |
| GET | `/settings/pretargeting-configs/{id}` | Configuratiedetails |
| GET | `/settings/pretargeting-history` | Wijzigingsgeschiedenis configuraties |
| POST | `/settings/pretargeting-configs/sync` | Configuraties synchroniseren vanuit Google |
| POST | `/settings/pretargeting-configs/{id}/apply` | Configuratiewijziging toepassen |
| POST | `/settings/pretargeting-configs/apply-all` | Alle openstaande wijzigingen toepassen |
| PUT | `/settings/pretargeting-configs/{id}` | Configuratie batch-bijwerken |

## Uploads

| Methode | Pad | Doel |
|---------|-----|------|
| GET | `/uploads/tracking` | Dagelijks uploadsoverzicht |
| GET | `/uploads/import-matrix` | Importstatus per rapporttype |
| GET | `/uploads/data-freshness` | Dataversheidsraster (datum x type) |
| GET | `/uploads/history` | Importgeschiedenis |

## Optimizer

| Methode | Pad | Doel |
|---------|-----|------|
| GET | `/optimizer/models` | BYOM-modellen weergeven |
| POST | `/optimizer/models` | Model registreren |
| PUT | `/optimizer/models/{id}` | Model bijwerken |
| POST | `/optimizer/models/{id}/activate` | Model activeren |
| POST | `/optimizer/models/{id}/deactivate` | Model deactiveren |
| POST | `/optimizer/models/{id}/validate` | Model-endpoint testen |
| POST | `/optimizer/score-and-propose` | Voorstellen genereren |
| GET | `/optimizer/proposals` | Actieve voorstellen weergeven |
| GET | `/optimizer/proposals/history` | Voorstelgeschiedenis |
| POST | `/optimizer/proposals/{id}/approve` | Voorstel goedkeuren |
| POST | `/optimizer/proposals/{id}/apply` | Voorstel toepassen |
| POST | `/optimizer/proposals/{id}/sync-status` | Toepassingsstatus controleren |
| GET | `/optimizer/segment-scores` | Scores op segmentniveau |
| GET | `/optimizer/economics/efficiency` | Samenvatting efficiëntie |
| GET | `/optimizer/economics/effective-cpm` | CPM-analyse |
| GET | `/optimizer/setup` | Optimizer-configuratie |
| PUT | `/optimizer/setup` | Optimizer-configuratie bijwerken |

## Conversies

| Methode | Pad | Doel |
|---------|-----|------|
| GET | `/conversions/health` | Ingestie- en aggregatiestatus |
| GET | `/conversions/readiness` | Gereedheidscheck bron |
| GET | `/conversions/ingestion-stats` | Aantal events per bron/periode |
| GET | `/conversions/security/status` | Beveiligingsstatus webhooks |
| GET | `/conversions/pixel` | Pixel tracking-endpoint |

## Snapshots

| Methode | Pad | Doel |
|---------|-----|------|
| GET | `/snapshots` | Configuratie-snapshots weergeven |
| POST | `/snapshots/rollback` | Snapshot herstellen (met dry-run) |

## Integraties

| Methode | Pad | Doel |
|---------|-----|------|
| POST | `/integrations/credentials` | GCP-serviceaccount-JSON uploaden |
| GET | `/integrations/service-accounts` | Serviceaccounts weergeven |
| DELETE | `/integrations/service-accounts/{id}` | Serviceaccount verwijderen |
| GET | `/integrations/language-ai/config` | Status AI-provider |
| PUT | `/integrations/language-ai/config` | AI-provider configureren |
| GET | `/integrations/gmail/status` | Gmail-importstatus |
| POST | `/integrations/gmail/import/start` | Handmatige import starten |
| POST | `/integrations/gmail/import/stop` | Importtaak stoppen |
| GET | `/integrations/gmail/import/history` | Importgeschiedenis |
| GET | `/integrations/gcp/project-status` | GCP-projectgezondheid |
| POST | `/integrations/gcp/validate` | GCP-verbinding testen |

## Admin

| Methode | Pad | Doel |
|---------|-----|------|
| GET | `/admin/users` | Gebruikers weergeven |
| POST | `/admin/users` | Gebruiker aanmaken |
| GET | `/admin/users/{id}` | Gebruikersdetails |
| PUT | `/admin/users/{id}` | Gebruiker bijwerken |
| POST | `/admin/users/{id}/deactivate` | Gebruiker deactiveren |
| GET | `/admin/users/{id}/permissions` | Globale rechten van gebruiker |
| GET | `/admin/users/{id}/seat-permissions` | Rechten per stoel van gebruiker |
| POST | `/admin/users/{id}/seat-permissions` | Stoeltoegang verlenen |
| DELETE | `/admin/users/{id}/seat-permissions/{buyer_id}` | Stoeltoegang intrekken |
| POST | `/admin/users/{id}/permissions` | Globaal recht verlenen |
| DELETE | `/admin/users/{id}/permissions/{sa_id}` | Globaal recht intrekken |
| GET | `/admin/audit-log` | Audittrail |
| GET | `/admin/stats` | Admin-dashboardstatistieken |
| GET | `/admin/settings` | Systeemconfiguratie |
| PUT | `/admin/settings/{key}` | Systeeminstelling bijwerken |
