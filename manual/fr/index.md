# Manuel d'utilisation Cat-Scan

## Le problème en une image

![Entonnoir QPS](../assets/qps-funnel.svg)

Google envoie à votre bidder un torrent de requêtes d'enchères. Chaque seconde,
des dizaines de milliers de requêtes affluent depuis l'exchange Authorized Buyers
vers votre endpoint. Votre bidder évalue chacune d'entre elles, décide s'il doit
enchérir, et répond — le tout en quelques millisecondes.

Voici ce que la plupart des gens ne voient pas : **la grande majorité de ce
signal est du bruit.** Un siège typique ingérant 50 000 QPS pourrait constater
que 30 000 de ces requêtes concernent un inventaire que l'acheteur média n'aurait
jamais acheté : mauvaises zones géographiques, domaines d'éditeurs non
pertinents, formats publicitaires sans créative correspondante. Votre bidder doit
quand même recevoir, analyser et rejeter chacune d'elles. Cela coûte en bande
passante, en calcul et en argent.

Le schéma ci-dessus illustre cela comme une pluie. Le QPS de Google est la buse
en haut ; les gouttes se dispersent sur une large surface. Votre bidder est le
petit seau en bas. Tout ce qui rate le seau (les gouttes qui tombent à gauche et
à droite) est du gaspillage. Vous avez payé pour cela. Vous n'avez rien obtenu
en retour.

**Cat-Scan existe pour élargir le seau et rétrécir la pluie.**

Il y parvient en vous offrant une visibilité sur l'origine du gaspillage (quelles
zones géographiques, quels éditeurs, quels formats, quelles créatives) et les
contrôles pour l'arrêter à la source, en utilisant les configurations de
prétargeting que Google fournit.

### Pourquoi c'est plus difficile qu'il n'y paraît

Google Authorized Buyers ne vous accorde que **10 configurations de prétargeting
par siège**, ainsi que des regroupements géographiques grossiers (Est des
États-Unis, Ouest des États-Unis, Europe, Asie). Il n'y a pas d'API de
reporting. Toutes les données de performance proviennent d'exports CSV envoyés
par e-mail. L'interface de prétargeting d'AB est fonctionnelle mais rend
difficile la vision d'ensemble entre les configurations, ou l'annulation d'une
modification qui s'est mal passée.

Cat-Scan comble ces lacunes :

- Il **reconstruit le reporting à partir d'exports CSV** (import manuel ou
  ingestion automatique via Gmail), avec dédoublonnage à l'import pour que le
  retraitement ne compte jamais en double.
- Il affiche **l'entonnoir RTB complet**, du QPS brut jusqu'aux enchères,
  victoires, impressions, clics et dépenses, ventilé par n'importe quelle
  dimension : géographie, éditeur, format publicitaire, créative, configuration.
- Il offre une **gestion sécurisée du prétargeting** avec historique,
  modifications par étapes, aperçu en simulation, et retour en arrière en un
  clic.
- Il exécute un **optimiseur** qui note les segments et propose des modifications
  de configuration, avec des garde-fous de workflow (prudent / équilibré /
  agressif) afin qu'aucun changement ne soit appliqué sans révision.

### À qui s'adresse ce manuel

Ce manuel comporte deux parcours car Cat-Scan s'adresse à deux rôles très
différents :

**Les acheteurs média et responsables de campagnes** utilisent Cat-Scan pour
comprendre où va leur budget, identifier le gaspillage, gérer les créatives,
ajuster le prétargeting et approuver les propositions d'optimisation. Ils
raisonnent en CPM, taux de victoire et ROAS. Leurs chapitres se concentrent sur
ce que l'interface affiche, ce que les chiffres signifient, et les actions à
entreprendre.

**Les ingénieurs DevOps et plateformes** utilisent Cat-Scan pour déployer,
surveiller et dépanner le système. Ils raisonnent en conteneurs, endpoints de
santé et plans de requêtes. Leurs chapitres se concentrent sur l'architecture,
les pipelines de déploiement, les opérations de base de données et les runbooks
d'incidents.

Les deux parcours partagent un socle commun (prise en main, glossaire) et les
chapitres se renvoient les uns aux autres lorsque les workflows se recoupent. Un
acheteur média signalant « la fraîcheur des données est cassée » et un ingénieur
DevOps déboguant la requête sous-jacente devraient pouvoir pointer vers la même
entrée du glossaire et se comprendre mutuellement.

---

## Comment lire ce manuel

- **Partie 0** est destinée à tout le monde. Commencez ici.
- **Partie I** est le parcours acheteur média. Si vous travaillez dans les
  campagnes, l'optimisation ou l'achat, c'est votre chemin.
- **Partie II** est le parcours DevOps. Si vous déployez, surveillez ou
  administrez Cat-Scan, c'est votre chemin.
- **Partie III** est la référence partagée : glossaire, FAQ et index API.

Vous n'avez pas besoin de lire de manière linéaire. Chaque chapitre est
autonome. Suivez les liens qui correspondent à votre rôle.

---

## Table des matières

### Partie 0 : Prise en main

Tout le monde lit cette partie.

- [Chapitre 0 : Qu'est-ce que Cat-Scan ?](00-what-is-cat-scan.md)
  Ce que fait la plateforme, à qui elle s'adresse, et les concepts
  fondamentaux à connaître avant tout : sièges, QPS, prétargeting, l'entonnoir
  RTB.

- [Chapitre 1 : Connexion](01-logging-in.md)
  Méthodes d'authentification (Google OAuth, comptes locaux), la page de
  connexion, que faire en cas d'échec de connexion, et comment fonctionne le
  sélecteur de siège.

- [Chapitre 2 : Naviguer dans le tableau de bord](02-navigating-the-dashboard.md)
  La barre latérale, le changement de siège, le sélecteur de langue, la
  checklist de configuration pour les nouveaux comptes, et l'organisation des
  pages.

### Partie I : Parcours acheteur média

Pour les acheteurs média, responsables de campagnes et ingénieurs en
optimisation.

- [Chapitre 3 : Comprendre votre entonnoir QPS](03-qps-funnel.md)
  La page d'accueil. Comment lire la ventilation de l'entonnoir : impressions,
  enchères, victoires, dépenses, taux de victoire, CTR, CPM. Ce que signifie
  le « gaspillage » en termes concrets. Les cartes de configuration et ce que
  leurs champs contrôlent.

- [Chapitre 4 : Analyser le gaspillage par dimension](04-analyzing-waste.md)
  Les trois vues d'analyse du gaspillage et quand utiliser chacune :
  - **Géographique** (`/qps/geo`) : quels pays et villes consomment du QPS
    sans convertir.
  - **Éditeur** (`/qps/publisher`) : quels domaines et applications
    sous-performent.
  - **Format** (`/qps/size`) : quels formats publicitaires reçoivent du trafic
    mais n'ont pas de créative correspondante. Google envoie environ 400
    formats différents ; la plupart ne sont pas pertinents pour les annonces
    display à taille fixe.

- [Chapitre 5 : Gestion des créatives](05-managing-creatives.md)
  La galerie des créatives (`/creatives`) : navigation par format, filtrage par
  niveau de performance, recherche par ID. Miniatures, badges de format,
  diagnostics de destination. Regroupement en campagnes (`/campaigns`) :
  glisser-déposer, auto-clustering par IA, le pool non assigné.

- [Chapitre 6 : Configuration du prétargeting](06-pretargeting.md)
  Ce que contrôle une configuration de prétargeting (zones géographiques,
  formats, types, plateformes, QPS maximum). Comment lire une carte de
  configuration. Appliquer des modifications avec aperçu en simulation.
  L'historique des modifications (`/history`). Retour en arrière : comment cela
  fonctionne, pourquoi cela existe, et quand l'utiliser.

- [Chapitre 7 : L'optimiseur (BYOM)](07-optimizer.md)
  Bring Your Own Model : enregistrer un endpoint de scoring externe, le
  valider, l'activer. Le cycle de vie score-proposition-approbation-application.
  Préréglages de workflow : prudent, équilibré, agressif. Économie : CPM
  effectif, coût d'hébergement de référence, résumé d'efficacité. À quoi
  ressemble une proposition et comment l'évaluer.

- [Chapitre 8 : Conversions et attribution](08-conversions.md)
  Connecter une source de conversion. Intégration pixel. Configuration de
  webhook : signatures HMAC, secrets partagés, limitation de débit. Vérifications
  de disponibilité. Statistiques d'ingestion. Ce que signifie la « santé des
  conversions » et comment lire la page d'état de sécurité.

- [Chapitre 9 : Import de données](09-data-import.md)
  Comment les données arrivent dans Cat-Scan, et pourquoi c'est important.
  Import CSV manuel (`/import`) : glisser-déposer, correspondance de colonnes,
  validation, import par morceaux pour les gros fichiers. Auto-import Gmail :
  comment cela fonctionne, comment vérifier le statut, ce qui se passe en cas
  d'échec. La grille de fraîcheur des données : ce que « importé » vs
  « manquant » signifie par date et type de rapport. Garanties de
  dédoublonnage.

- [Chapitre 10 : Lire vos rapports](10-reading-reports.md)
  Statistiques de dépenses, panneaux de performance des configurations,
  métriques d'efficacité des endpoints. Comment interpréter les tendances. Ce
  que montre la ventilation quotidienne. Comparaisons d'instantanés : avant et
  après une modification de prétargeting.

### Partie II : Parcours DevOps

Pour les ingénieurs plateforme, SRE et administrateurs système.

- [Chapitre 11 : Vue d'ensemble de l'architecture](11-architecture.md)
  Topologie du système : backend FastAPI, frontend Next.js 14, Postgres
  (Cloud SQL), BigQuery. Pourquoi deux bases de données coexistent (coût,
  latence, pré-agrégation, gestion des connexions). Organisation des
  conteneurs : api, dashboard, oauth2-proxy, cloudsql-proxy, nginx. La chaîne
  de confiance d'authentification : OAuth2 Proxy définit `X-Email`, nginx le
  transmet, l'API lui fait confiance.

- [Chapitre 12 : Déploiement](12-deployment.md)
  Pipeline CI/CD : GitHub Actions `build-and-push.yml` construit les images au
  push ; `deploy.yml` est à déclenchement manuel uniquement (avec confirmation
  `DEPLOY`). Tags d'images Artifact Registry (`sha-XXXXXXX`). La séquence de
  déploiement : git pull sur la VM, docker compose pull, recréation, nettoyage.
  Vérification post-déploiement : health check, vérification de contrat.
  Pourquoi le déploiement automatique est désactivé (incident de janvier 2026).
  Comment vérifier un déploiement : `curl /api/health | jq .git_sha`.

- [Chapitre 13 : Surveillance de santé et diagnostics](13-health-monitoring.md)
  Endpoints de santé : `/api/health` (disponibilité), `/system/data-health`
  (complétude des données). La page État du système
  (`/settings/system`) : Python, Node, FFmpeg, base de données, disque,
  miniatures. Scripts de santé en runtime :
  `diagnose_v1_buyer_report_coverage.sh`,
  `run_v1_runtime_health_strict_dispatch.sh`. Authentification canari :
  `CATSCAN_CANARY_EMAIL`, `CATSCAN_BEARER_TOKEN`. Workflows CI :
  `v1-runtime-health-strict.yml` et la signification de PASS/FAIL/BLOCKED.

- [Chapitre 14 : Opérations de base de données](14-database.md)
  Production exclusivement Postgres. Cloud SQL via conteneur proxy. Tables
  principales et leur volume : `rtb_daily` (~84M de lignes), `rtb_bidstream`
  (~21M de lignes), `rtb_quality`, `rtb_bid_filtering`. Index critiques :
  `(buyer_account_id, metric_date DESC)`. Modèle de connexion : par requête
  (pas de pool), `run_in_executor` pour l'asynchrone. Délais d'expiration des
  requêtes (`SET LOCAL statement_timeout`). Paramètres de rétention des
  données. Rôle de BigQuery : entrepôt par lots pour les données brutes ;
  Postgres sert les données pré-agrégées à l'application.

- [Chapitre 15 : Runbook de dépannage](15-troubleshooting.md)
  Schémas de défaillance connus et comment les résoudre :
  - **Boucle de connexion** : Cloud SQL Proxy en panne,
    `_get_or_create_oauth2_user` échoue silencieusement, `/auth/check` renvoie
    `{authenticated:false}`, boucle de redirection du frontend. Correctif à
    trois niveaux. Comment détecter : compteur de redirections dans le
    navigateur, 503 de `/auth/check`.
  - **Timeout de fraîcheur des données** : requêtes sur de grandes tables
    effectuant des parcours séquentiels au lieu d'utiliser les index.
    Symptômes : `/uploads/data-freshness` expire ou renvoie 500.
    Diagnostic : `pg_stat_activity`, `EXPLAIN ANALYZE`. Schéma de
    correction : generate_series + EXISTS.
  - **Échec d'import Gmail** : `/gmail/status` affiche une erreur. Vérifier
    le conteneur Cloud SQL Proxy. Vérifier le nombre de messages non lus.
  - **Ordre de redémarrage des conteneurs** : `cloudsql-proxy` doit être sain
    avant que `api` ne démarre. Signes d'un mauvais ordre : « connection
    refused » dans les logs de l'API.

- [Chapitre 16 : Administration des utilisateurs et des permissions](16-user-admin.md)
  Le panneau d'administration (`/admin`) : création d'utilisateurs (comptes
  locaux et pré-création OAuth), gestion des rôles, permissions par siège.
  Comptes de service : import du JSON d'identifiants GCP, ce que cela
  déverrouille (découverte de sièges, synchronisation du prétargeting).
  Utilisateurs restreints : ce qu'ils voient et ce qui est masqué. Le journal
  d'audit : quelles actions sont suivies, comment filtrer, rétention.

- [Chapitre 17 : Intégrations](17-integrations.md)
  Comptes de service GCP et connexion au projet. API Google Authorized
  Buyers : découverte de sièges, synchronisation des configurations de
  prétargeting, synchronisation des endpoints RTB. Intégration Gmail : OAuth2
  pour l'ingestion automatique des rapports. Fournisseurs d'IA linguistique :
  Gemini, Claude, Grok (pour la détection de langue des créatives et les
  alertes de discordance). Webhooks de conversion : enregistrement d'endpoint,
  vérification HMAC, limitation de débit, surveillance de fraîcheur.

### Partie III : Référence

Partagée entre les deux parcours.

- [Glossaire](glossary.md)
  Chaque terme en deux perspectives. Colonne acheteur média : « prétargeting »
  signifie « les règles qui contrôlent quelles requêtes d'enchères atteignent
  votre bidder. » Colonne DevOps : « prétargeting » signifie « une entité
  mutable synchronisée depuis l'API AB, stockée dans `pretargeting_configs`,
  exposée via `/settings/pretargeting`. » Les deux ont besoin du même mot ;
  aucun n'utilise la définition de l'autre.

- [Foire aux questions](faq.md)
  Étiquetée par profil. Les questions que pose un acheteur média (« Pourquoi ma
  couverture est-elle à 74 % ? ») côtoient celles que pose un ingénieur DevOps
  (« Pourquoi le gate de santé runtime strict a-t-il échoué ? »). Les réponses
  renvoient au chapitre pertinent.

- [Référence rapide de l'API](api-reference.md)
  Les 118+ endpoints regroupés par domaine : core, sièges, créatives,
  campagnes, analytique, paramètres, administration, optimiseur, conversions,
  intégrations, imports, instantanés, authentification. Méthode, chemin,
  paramètres clés, et ce que cela retourne. Ne remplace pas la spécification
  OpenAPI disponible à `/api/docs`, mais constitue un index navigable.
