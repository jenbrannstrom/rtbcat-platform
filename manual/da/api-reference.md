# API-hurtigreference

Dette er et navigerbart indeks over Cat-Scans 118+ API-endpoints, grupperet
efter domæne. For fulde request/response-skemaer, se den interaktive
OpenAPI-dokumentation på `https://scan.rtb.cat/api/docs`.

## Core / System

| Metode | Sti | Formål |
|--------|-----|--------|
| GET | `/health` | Liveness-tjek (git_sha, version) |
| GET | `/stats` | Systemstatistik |
| GET | `/sizes` | Tilgængelige annonceformater |
| GET | `/system/status` | Serverstatus (Python, Node, FFmpeg, DB, disk) |
| GET | `/system/data-health` | Datakomplethed per køber |
| GET | `/system/ui-page-load-metrics` | Frontend-performancemålinger |
| GET | `/geo/lookup` | Geo-ID til navneopløsning |
| GET | `/geo/search` | Søg i lande/byer |

## Auth

| Metode | Sti | Formål |
|--------|-----|--------|
| GET | `/auth/check` | Tjek om den aktuelle session er autentificeret |
| POST | `/auth/logout` | Afslut session |

## Seats

| Metode | Sti | Formål |
|--------|-----|--------|
| GET | `/seats` | Liste over køber-seats |
| GET | `/seats/{buyer_id}` | Hent specifikt seat |
| PUT | `/seats/{buyer_id}` | Opdatér seats visningsnavn |
| POST | `/seats/populate` | Auto-opret seats fra data |
| POST | `/seats/discover` | Opdag seats fra Google API |
| POST | `/seats/{buyer_id}/sync` | Synkronisér specifikt seat |
| POST | `/seats/sync-all` | Fuld synkronisering (alle seats) |
| POST | `/seats/collect-creatives` | Indsaml kreativdata |

## Creatives

| Metode | Sti | Formål |
|--------|-----|--------|
| GET | `/creatives` | Liste over kreativer (med filtre) |
| GET | `/creatives/paginated` | Pagineret kreativliste |
| GET | `/creatives/{id}` | Kreativdetaljer |
| GET | `/creatives/{id}/live` | Live kreativdata (cache-bevidst) |
| GET | `/creatives/{id}/destination-diagnostics` | Destinations-URL-sundhed |
| GET | `/creatives/{id}/countries` | Landeopdelt performance |
| GET | `/creatives/{id}/geo-linguistic` | Geo-lingvistisk analyse |
| POST | `/creatives/{id}/detect-language` | Automatisk sprogdetektion |
| PUT | `/creatives/{id}/language` | Manuel sprogtilsidesættelse |
| GET | `/creatives/thumbnail-status` | Batch-thumbnailstatus |
| POST | `/creatives/thumbnails/batch` | Generér manglende thumbnails |

## Campaigns

| Metode | Sti | Formål |
|--------|-----|--------|
| GET | `/campaigns` | Liste over kampagner |
| GET | `/campaigns/{id}` | Kampagnedetaljer |
| GET | `/campaigns/ai` | AI-genererede klynger |
| GET | `/campaigns/ai/{id}` | AI-kampagnedetaljer |
| PUT | `/campaigns/ai/{id}` | Opdatér kampagne |
| DELETE | `/campaigns/ai/{id}` | Slet kampagne |
| GET | `/campaigns/ai/{id}/creatives` | Kampagnens kreativer |
| DELETE | `/campaigns/ai/{id}/creatives/{creative_id}` | Fjern kreativ fra kampagne |
| POST | `/campaigns/auto-cluster` | AI-autoklyngning |
| GET | `/campaigns/ai/{id}/performance` | Kampagneperformance |
| GET | `/campaigns/ai/{id}/daily-trend` | Kampagnetrenddata |

## Analytics

| Metode | Sti | Formål |
|--------|-----|--------|
| GET | `/analytics/waste-report` | Overordnede spildmetrikker |
| GET | `/analytics/size-coverage` | Formatmæssig targeting-dækning |
| GET | `/analytics/rtb-funnel` | RTB-tragtopsplitning |
| GET | `/analytics/rtb-funnel/configs` | Konfigurationsniveau-tragt |
| GET | `/analytics/endpoint-efficiency` | QPS-effektivitet per endpoint |
| GET | `/analytics/spend-stats` | Forbrugsstatistik |
| GET | `/analytics/config-performance` | Konfigurationsperformance over tid |
| GET | `/analytics/config-performance/breakdown` | Konfigurationsfelt-opdeling |
| GET | `/analytics/qps-recommendations` | AI-anbefalinger |
| GET | `/analytics/performance/batch` | Batch kreativperformance |
| GET | `/analytics/performance/{creative_id}` | Enkelt kreativperformance |
| GET | `/analytics/publishers` | Publisher-domænemetrikker |
| GET | `/analytics/publishers/search` | Søg i publishers |
| GET | `/analytics/languages` | Sprogperformance |
| GET | `/analytics/languages/multi` | Analyse af flere sprog |
| GET | `/analytics/geo-performance` | Geografisk performance |
| GET | `/analytics/geo-performance/multi` | Analyse af flere geografier |
| POST | `/analytics/import` | CSV-import |
| POST | `/analytics/mock-traffic` | Generér testdata |

## Settings / Pretargeting

| Metode | Sti | Formål |
|--------|-----|--------|
| GET | `/settings/rtb-endpoints` | Bidder RTB-endpoints |
| POST | `/settings/rtb-endpoints/sync` | Synkronisér endpoint-data |
| GET | `/settings/pretargeting-configs` | Liste over pretargeting-konfigurationer |
| GET | `/settings/pretargeting-configs/{id}` | Konfigurationsdetaljer |
| GET | `/settings/pretargeting-history` | Konfigurationsændringshistorik |
| POST | `/settings/pretargeting-configs/sync` | Synkronisér konfigurationer fra Google |
| POST | `/settings/pretargeting-configs/{id}/apply` | Anvend en konfigurationsændring |
| POST | `/settings/pretargeting-configs/apply-all` | Anvend alle ventende ændringer |
| PUT | `/settings/pretargeting-configs/{id}` | Batch-opdatering af konfiguration |

## Uploads

| Metode | Sti | Formål |
|--------|-----|--------|
| GET | `/uploads/tracking` | Daglig upload-oversigt |
| GET | `/uploads/import-matrix` | Importstatus per rapporttype |
| GET | `/uploads/data-freshness` | Datafriskheds-gitter (dato x type) |
| GET | `/uploads/history` | Importhistorik |

## Optimizer

| Metode | Sti | Formål |
|--------|-----|--------|
| GET | `/optimizer/models` | Liste over BYOM-modeller |
| POST | `/optimizer/models` | Registrér model |
| PUT | `/optimizer/models/{id}` | Opdatér model |
| POST | `/optimizer/models/{id}/activate` | Aktivér model |
| POST | `/optimizer/models/{id}/deactivate` | Deaktivér model |
| POST | `/optimizer/models/{id}/validate` | Test model-endpoint |
| POST | `/optimizer/score-and-propose` | Generér forslag |
| GET | `/optimizer/proposals` | Liste over aktive forslag |
| GET | `/optimizer/proposals/history` | Forslagshistorik |
| POST | `/optimizer/proposals/{id}/approve` | Godkend forslag |
| POST | `/optimizer/proposals/{id}/apply` | Anvend forslag |
| POST | `/optimizer/proposals/{id}/sync-status` | Tjek anvendelsesstatus |
| GET | `/optimizer/segment-scores` | Segmentniveau-scores |
| GET | `/optimizer/economics/efficiency` | Effektivitetsresumé |
| GET | `/optimizer/economics/effective-cpm` | CPM-analyse |
| GET | `/optimizer/setup` | Optimizer-konfiguration |
| PUT | `/optimizer/setup` | Opdatér optimizer-konfiguration |

## Conversions

| Metode | Sti | Formål |
|--------|-----|--------|
| GET | `/conversions/health` | Indlæsnings- og aggregeringsstatus |
| GET | `/conversions/readiness` | Kildeklarhedstjek |
| GET | `/conversions/ingestion-stats` | Hændelsesantal per kilde/periode |
| GET | `/conversions/security/status` | Webhook-sikkerhedsstatus |
| GET | `/conversions/pixel` | Pixel-tracking-endpoint |

## Snapshots

| Metode | Sti | Formål |
|--------|-----|--------|
| GET | `/snapshots` | Liste over konfigurationssnapshots |
| POST | `/snapshots/rollback` | Gendannelse af et snapshot (med dry-run) |

## Integrations

| Metode | Sti | Formål |
|--------|-----|--------|
| POST | `/integrations/credentials` | Upload GCP-servicekonto-JSON |
| GET | `/integrations/service-accounts` | Liste over servicekonti |
| DELETE | `/integrations/service-accounts/{id}` | Slet servicekonto |
| GET | `/integrations/language-ai/config` | AI-udbyderstatus |
| PUT | `/integrations/language-ai/config` | Konfigurér AI-udbyder |
| GET | `/integrations/gmail/status` | Gmail-importstatus |
| POST | `/integrations/gmail/import/start` | Udløs manuel import |
| POST | `/integrations/gmail/import/stop` | Stop importjob |
| GET | `/integrations/gmail/import/history` | Importhistorik |
| GET | `/integrations/gcp/project-status` | GCP-projektsundhed |
| POST | `/integrations/gcp/validate` | Test GCP-forbindelse |

## Admin

| Metode | Sti | Formål |
|--------|-----|--------|
| GET | `/admin/users` | Liste over brugere |
| POST | `/admin/users` | Opret bruger |
| GET | `/admin/users/{id}` | Brugerdetaljer |
| PUT | `/admin/users/{id}` | Opdatér bruger |
| POST | `/admin/users/{id}/deactivate` | Deaktivér bruger |
| GET | `/admin/users/{id}/permissions` | Brugerens globale rettigheder |
| GET | `/admin/users/{id}/seat-permissions` | Brugerens per-seat-rettigheder |
| POST | `/admin/users/{id}/seat-permissions` | Tildel seat-adgang |
| DELETE | `/admin/users/{id}/seat-permissions/{buyer_id}` | Fjern seat-adgang |
| POST | `/admin/users/{id}/permissions` | Tildel global rettighed |
| DELETE | `/admin/users/{id}/permissions/{sa_id}` | Fjern global rettighed |
| GET | `/admin/audit-log` | Auditspor |
| GET | `/admin/stats` | Admin-dashboardstatistik |
| GET | `/admin/settings` | Systemkonfiguration |
| PUT | `/admin/settings/{key}` | Opdatér systemindstilling |
