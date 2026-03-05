# Référence rapide de l'API

Ceci est un index navigable des 118+ endpoints API de Cat-Scan, regroupés par
domaine. Pour les schémas complets de requête/réponse, consultez la
documentation interactive OpenAPI à `https://your-deployment.example.com/api/docs`.

## Core / Système

| Méthode | Chemin | Objectif |
|---------|--------|----------|
| GET | `/health` | Vérification de disponibilité (git_sha, version) |
| GET | `/stats` | Statistiques système |
| GET | `/sizes` | Formats publicitaires disponibles |
| GET | `/system/status` | État du serveur (Python, Node, FFmpeg, BDD, disque) |
| GET | `/system/data-health` | Complétude des données par acheteur |
| GET | `/system/ui-page-load-metrics` | Métriques de performance frontend |
| GET | `/geo/lookup` | Résolution d'identifiant géographique en nom |
| GET | `/geo/search` | Recherche de pays/villes |

## Auth

| Méthode | Chemin | Objectif |
|---------|--------|----------|
| GET | `/auth/check` | Vérifier si la session en cours est authentifiée |
| POST | `/auth/logout` | Terminer la session |

## Sièges

| Méthode | Chemin | Objectif |
|---------|--------|----------|
| GET | `/seats` | Lister les sièges acheteurs |
| GET | `/seats/{buyer_id}` | Obtenir un siège spécifique |
| PUT | `/seats/{buyer_id}` | Modifier le nom d'affichage du siège |
| POST | `/seats/populate` | Créer automatiquement les sièges à partir des données |
| POST | `/seats/discover` | Découvrir les sièges via l'API Google |
| POST | `/seats/{buyer_id}/sync` | Synchroniser un siège spécifique |
| POST | `/seats/sync-all` | Synchronisation complète (tous les sièges) |
| POST | `/seats/collect-creatives` | Collecter les données des créatives |

## Créatives

| Méthode | Chemin | Objectif |
|---------|--------|----------|
| GET | `/creatives` | Lister les créatives (avec filtres) |
| GET | `/creatives/paginated` | Liste paginée des créatives |
| GET | `/creatives/{id}` | Détails d'une créative |
| GET | `/creatives/{id}/live` | Données créative en direct (avec gestion du cache) |
| GET | `/creatives/{id}/destination-diagnostics` | Santé de l'URL de destination |
| GET | `/creatives/{id}/countries` | Ventilation des performances par pays |
| GET | `/creatives/{id}/geo-linguistic` | Analyse géolinguistique |
| POST | `/creatives/{id}/detect-language` | Détection automatique de la langue |
| PUT | `/creatives/{id}/language` | Forçage manuel de la langue |
| GET | `/creatives/thumbnail-status` | État des miniatures en lot |
| POST | `/creatives/thumbnails/batch` | Générer les miniatures manquantes |

## Campagnes

| Méthode | Chemin | Objectif |
|---------|--------|----------|
| GET | `/campaigns` | Lister les campagnes |
| GET | `/campaigns/{id}` | Détails d'une campagne |
| GET | `/campaigns/ai` | Clusters générés par IA |
| GET | `/campaigns/ai/{id}` | Détails d'une campagne IA |
| PUT | `/campaigns/ai/{id}` | Modifier une campagne |
| DELETE | `/campaigns/ai/{id}` | Supprimer une campagne |
| GET | `/campaigns/ai/{id}/creatives` | Créatives d'une campagne |
| DELETE | `/campaigns/ai/{id}/creatives/{creative_id}` | Retirer une créative d'une campagne |
| POST | `/campaigns/auto-cluster` | Auto-clustering par IA |
| GET | `/campaigns/ai/{id}/performance` | Performance d'une campagne |
| GET | `/campaigns/ai/{id}/daily-trend` | Données de tendance d'une campagne |

## Analytique

| Méthode | Chemin | Objectif |
|---------|--------|----------|
| GET | `/analytics/waste-report` | Métriques globales de gaspillage |
| GET | `/analytics/size-coverage` | Couverture du ciblage par format |
| GET | `/analytics/rtb-funnel` | Ventilation de l'entonnoir RTB |
| GET | `/analytics/rtb-funnel/configs` | Entonnoir par configuration |
| GET | `/analytics/endpoint-efficiency` | Efficacité QPS par endpoint |
| GET | `/analytics/spend-stats` | Statistiques de dépenses |
| GET | `/analytics/config-performance` | Performance des configurations dans le temps |
| GET | `/analytics/config-performance/breakdown` | Ventilation par champ de configuration |
| GET | `/analytics/qps-recommendations` | Recommandations IA |
| GET | `/analytics/performance/batch` | Performance des créatives en lot |
| GET | `/analytics/performance/{creative_id}` | Performance d'une créative |
| GET | `/analytics/publishers` | Métriques par domaine éditeur |
| GET | `/analytics/publishers/search` | Recherche d'éditeurs |
| GET | `/analytics/languages` | Performance par langue |
| GET | `/analytics/languages/multi` | Analyse multilangue |
| GET | `/analytics/geo-performance` | Performance géographique |
| GET | `/analytics/geo-performance/multi` | Analyse multigéographique |
| POST | `/analytics/import` | Import CSV |
| POST | `/analytics/mock-traffic` | Générer des données de test |

## Paramètres / Prétargeting

| Méthode | Chemin | Objectif |
|---------|--------|----------|
| GET | `/settings/rtb-endpoints` | Endpoints RTB du bidder |
| POST | `/settings/rtb-endpoints/sync` | Synchroniser les données d'endpoints |
| GET | `/settings/pretargeting-configs` | Lister les configurations de prétargeting |
| GET | `/settings/pretargeting-configs/{id}` | Détails d'une configuration |
| GET | `/settings/pretargeting-history` | Historique des modifications de configuration |
| POST | `/settings/pretargeting-configs/sync` | Synchroniser les configurations depuis Google |
| POST | `/settings/pretargeting-configs/{id}/apply` | Appliquer une modification de configuration |
| POST | `/settings/pretargeting-configs/apply-all` | Appliquer toutes les modifications en attente |
| PUT | `/settings/pretargeting-configs/{id}` | Mise à jour groupée d'une configuration |

## Imports

| Méthode | Chemin | Objectif |
|---------|--------|----------|
| GET | `/uploads/tracking` | Résumé quotidien des imports |
| GET | `/uploads/import-matrix` | État des imports par type de rapport |
| GET | `/uploads/data-freshness` | Grille de fraîcheur des données (date x type) |
| GET | `/uploads/history` | Historique des imports |

## Optimiseur

| Méthode | Chemin | Objectif |
|---------|--------|----------|
| GET | `/optimizer/models` | Lister les modèles BYOM |
| POST | `/optimizer/models` | Enregistrer un modèle |
| PUT | `/optimizer/models/{id}` | Modifier un modèle |
| POST | `/optimizer/models/{id}/activate` | Activer un modèle |
| POST | `/optimizer/models/{id}/deactivate` | Désactiver un modèle |
| POST | `/optimizer/models/{id}/validate` | Tester l'endpoint du modèle |
| POST | `/optimizer/score-and-propose` | Générer des propositions |
| GET | `/optimizer/proposals` | Lister les propositions actives |
| GET | `/optimizer/proposals/history` | Historique des propositions |
| POST | `/optimizer/proposals/{id}/approve` | Approuver une proposition |
| POST | `/optimizer/proposals/{id}/apply` | Appliquer une proposition |
| POST | `/optimizer/proposals/{id}/sync-status` | Vérifier l'état d'application |
| GET | `/optimizer/segment-scores` | Scores au niveau des segments |
| GET | `/optimizer/economics/efficiency` | Résumé d'efficacité |
| GET | `/optimizer/economics/effective-cpm` | Analyse du CPM |
| GET | `/optimizer/setup` | Configuration de l'optimiseur |
| PUT | `/optimizer/setup` | Modifier la configuration de l'optimiseur |

## Conversions

| Méthode | Chemin | Objectif |
|---------|--------|----------|
| GET | `/conversions/health` | État d'ingestion et d'agrégation |
| GET | `/conversions/readiness` | Vérification de disponibilité des sources |
| GET | `/conversions/ingestion-stats` | Nombre d'événements par source/période |
| GET | `/conversions/security/status` | État de sécurité des webhooks |
| GET | `/conversions/pixel` | Endpoint de suivi par pixel |

## Instantanés

| Méthode | Chemin | Objectif |
|---------|--------|----------|
| GET | `/snapshots` | Lister les instantanés de configuration |
| POST | `/snapshots/rollback` | Restaurer un instantané (avec simulation) |

## Intégrations

| Méthode | Chemin | Objectif |
|---------|--------|----------|
| POST | `/integrations/credentials` | Importer le JSON de compte de service GCP |
| GET | `/integrations/service-accounts` | Lister les comptes de service |
| DELETE | `/integrations/service-accounts/{id}` | Supprimer un compte de service |
| GET | `/integrations/language-ai/config` | État du fournisseur d'IA |
| PUT | `/integrations/language-ai/config` | Configurer le fournisseur d'IA |
| GET | `/integrations/gmail/status` | État de l'import Gmail |
| POST | `/integrations/gmail/import/start` | Déclencher un import manuel |
| POST | `/integrations/gmail/import/stop` | Arrêter la tâche d'import |
| GET | `/integrations/gmail/import/history` | Historique des imports |
| GET | `/integrations/gcp/project-status` | Santé du projet GCP |
| POST | `/integrations/gcp/validate` | Tester la connexion GCP |

## Administration

| Méthode | Chemin | Objectif |
|---------|--------|----------|
| GET | `/admin/users` | Lister les utilisateurs |
| POST | `/admin/users` | Créer un utilisateur |
| GET | `/admin/users/{id}` | Détails d'un utilisateur |
| PUT | `/admin/users/{id}` | Modifier un utilisateur |
| POST | `/admin/users/{id}/deactivate` | Désactiver un utilisateur |
| GET | `/admin/users/{id}/permissions` | Permissions globales d'un utilisateur |
| GET | `/admin/users/{id}/seat-permissions` | Permissions par siège d'un utilisateur |
| POST | `/admin/users/{id}/seat-permissions` | Accorder l'accès à un siège |
| DELETE | `/admin/users/{id}/seat-permissions/{buyer_id}` | Révoquer l'accès à un siège |
| POST | `/admin/users/{id}/permissions` | Accorder une permission globale |
| DELETE | `/admin/users/{id}/permissions/{sa_id}` | Révoquer une permission globale |
| GET | `/admin/audit-log` | Journal d'audit |
| GET | `/admin/stats` | Statistiques du panneau d'administration |
| GET | `/admin/settings` | Configuration système |
| PUT | `/admin/settings/{key}` | Modifier un paramètre système |
