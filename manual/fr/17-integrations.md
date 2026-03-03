# Chapitre 17 : Intégrations

*Public visé : DevOps, ingénieurs plateforme*

## Comptes de service GCP

Cat-Scan a besoin d'identifiants de compte de service GCP pour interagir avec
les API Google.

**Configuration :**
1. Créer un compte de service dans votre projet GCP avec accès à l'API
   Authorized Buyers.
2. Télécharger le fichier de clé JSON.
3. Le charger dans `/settings/accounts` > onglet API Connection.
4. Valider la connexion : Cat-Scan teste l'accessibilité et les permissions.

**Ce que cela active :**
- Découverte des sièges (`discoverSeats`)
- Synchronisation de la configuration de pretargeting (`syncPretargetingConfigs`)
- Synchronisation des endpoints RTB (`syncRTBEndpoints`)
- Collecte des créatifs (`collectCreatives`)

**Statut du projet :**
Vérifier la santé du projet GCP dans `/settings/accounts` ou via
`GET /integrations/gcp/project-status`. Cela confirme que le compte de service
est valide, que le projet est accessible et que les API requises sont activées.

## API Google Authorized Buyers

Cat-Scan synchronise les données depuis l'API Authorized Buyers :

| Opération | Ce qu'elle récupère | Quand l'exécuter |
|-----------|---------------------|------------------|
| **Découverte des sièges** | Comptes acheteurs liés au compte de service | Configuration initiale, lorsque de nouveaux sièges sont ajoutés |
| **Synchronisation du pretargeting** | État actuel de la configuration de pretargeting depuis Google | Après des modifications externes dans l'interface AB |
| **Synchronisation des endpoints RTB** | URL et état des endpoints du bidder | Configuration initiale, après des modifications d'endpoints |
| **Synchronisation des créatifs** | Métadonnées des créatifs (formats, tailles, destinations) | Périodiquement, via « Sync All » dans la barre latérale |

## Intégration Gmail

Google Authorized Buyers envoie par e-mail des rapports CSV quotidiens.
Cat-Scan peut les ingérer automatiquement.

**Configuration :**
1. Accéder à `/settings/accounts` > onglet Gmail Reports.
2. Autoriser Cat-Scan à accéder au compte Gmail qui reçoit les rapports AB.
3. Cat-Scan interrogera la boîte de réception pour détecter les nouveaux
   e-mails de rapport et importera les CSV en pièce jointe.

**Surveillance :**
- `GET /gmail/status` : état actuel, nombre de non-lus, dernier motif
- `POST /gmail/import/start` : déclencher manuellement un cycle d'import
- `POST /gmail/import/stop` : arrêter un import en cours
- `GET /gmail/import/history` : historique des imports passés

**Dépannage :**
- Nombre élevé de non-lus (30+) : arriéré d'import, peut nécessiter une
  intervention manuelle
- `last_reason: error` : vérifier les journaux, une ré-autorisation peut être
  nécessaire
- Voir [Dépannage](15-troubleshooting.md) pour les étapes détaillées.

## Fournisseurs d'IA linguistique

Cat-Scan utilise l'IA pour détecter la langue des créatifs et signaler les
incohérences géo-linguistiques (par ex. une publicité en espagnol sur un marché
arabophone).

**Fournisseurs pris en charge :**

| Fournisseur | Configuration |
|-------------|---------------|
| Gemini | Clé API dans `/settings/accounts` |
| Claude | Clé API dans `/settings/accounts` |
| Grok | Clé API dans `/settings/accounts` |

Configuration via `GET/PUT /integrations/language-ai/config`. Un seul
fournisseur doit être actif.

## Webhooks de conversion

Les systèmes externes envoient des événements de conversion à Cat-Scan via
des webhooks.

**Couches de sécurité :**

| Couche | Fonction | Configuration |
|--------|----------|---------------|
| **Vérification HMAC** | Garantit l'authenticité des requêtes (signées avec un secret partagé) | Secret partagé configuré dans les paramètres du webhook |
| **Limitation de débit** | Prévient les abus | Automatique, seuils configurables |
| **Surveillance de la fraîcheur** | Alerte lorsque les événements cessent d'arriver | Fenêtre de péremption configurable |

**Surveillance :**
- `GET /conversions/security/status` : statut HMAC, statut de la limitation
  de débit, statut de la fraîcheur
- `GET /conversions/health` : santé globale de l'ingestion et de l'agrégation
- `GET /conversions/readiness` : indique si les données de conversion sont
  suffisamment récentes pour être fiables

## Ressources connexes

- [Vue d'ensemble de l'architecture](11-architecture.md) : positionnement des intégrations
- [Administration des utilisateurs](16-user-admin.md) : gestion des comptes de service
- Pour les acheteurs média : [Conversions et attribution](08-conversions.md)
  couvre la configuration des conversions côté acheteur.
