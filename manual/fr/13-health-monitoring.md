# Chapitre 13 : Surveillance de la santé et diagnostics

*Public visé : DevOps, ingénieurs plateforme*

## Endpoints de santé

### `/api/health` : vivacité

Renvoie l'état de base de l'API, le SHA git et la version. Utilisé par le
workflow de déploiement et la surveillance externe.

```bash
curl -sS https://your-deployment.example.com/api/health | jq .
```

### `/system/data-health` : complétude des données

Renvoie l'état de santé des données par acheteur, incluant l'état de fraîcheur
pour chaque type de rapport. Accepte les paramètres `days`, `buyer_id` et
`availability_state`.

Utilisé par la checklist de configuration et la porte de santé à l'exécution.

## Page Statut du système (`/settings/system`)

L'interface affiche :

| Vérification | Ce qu'elle surveille |
|--------------|---------------------|
| Python | Version du runtime et disponibilité |
| Node | Build Next.js et état du SSR |
| FFmpeg | Capacité de génération de miniatures vidéo |
| Database | Connexion Postgres et nombre de lignes |
| Thumbnails | État de la génération par lots et file d'attente |
| Disk space | Utilisation du disque de la VM |

## Scripts de santé à l'exécution

Ces scripts constituent l'ossature opérationnelle pour vérifier le bon
fonctionnement du système de bout en bout.

### `diagnose_v1_buyer_report_coverage.sh`

Diagnostique pourquoi un acheteur spécifique présente une couverture CSV
manquante.

```bash
export CATSCAN_CANARY_EMAIL="user.com"
scripts/diagnose_v1_buyer_report_coverage.sh \
  --buyer-id <BUYER_ID> \
  --timeout 180 \
  --days 14
```

Vérifications (dans l'ordre) :
1. Correspondance des sièges : buyer_id -> bidder_id
2. Matrice d'import : réussi/échoué/non importé par type de CSV
3. Fraîcheur des données : couverture des cellules importées/manquantes
4. Historique d'import : lignes d'import récentes
5. Statut Gmail : nombre de non-lus, dernier motif, dernière date de métrique

Résultat : PASS ou FAIL avec un diagnostic précis.

### `run_v1_runtime_health_strict_dispatch.sh`

Exécute la porte de santé complète à l'exécution, qui vérifie :

- Santé de l'API
- Santé des données (fraîcheur et couverture des dimensions)
- Santé et disponibilité des conversions
- Latence de démarrage QPS
- Résumé SLO de la page QPS
- Économie et modèles de l'optimiseur
- Validation du endpoint de modèle
- Workflow score+propose
- Cycle de vie des propositions
- Simulation de retour en arrière (dry-run)

Chaque vérification renvoie PASS, FAIL ou BLOCKED (avec motif).

### Workflow CI : `v1-runtime-health-strict.yml`

Exécute la porte stricte en CI. Déclenché manuellement via workflow_dispatch.

```bash
gh workflow run v1-runtime-health-strict.yml \
  --ref unified-platform \
  -f api_base_url="https://your-deployment.example.com/api" \
  -f buyer_id="<BUYER_ID>" \
  -f canary_profile="balanced" \
  -f canary_timeout_seconds="180"
```

## Authentification canary

Les scripts d'exécution s'authentifient à l'aide de variables d'environnement :

| Variable | Fonction |
|----------|----------|
| `CATSCAN_CANARY_EMAIL` | En-tête X-Email pour les appels API directs (local à la VM) |
| `CATSCAN_BEARER_TOKEN` | Jeton Bearer (environnement CI, stocké dans les secrets GitHub) |
| `CATSCAN_SESSION_COOKIE` | Cookie de session OAuth2 Proxy (environnement CI) |

Depuis l'hôte de la VM, utilisez `CATSCAN_CANARY_EMAIL` avec
`http://localhost:8000`. Depuis la CI (externe), utilisez
`CATSCAN_BEARER_TOKEN` ou `CATSCAN_SESSION_COOKIE` avec
`https://your-deployment.example.com/api`.

## Interprétation des résultats

| Statut | Signification |
|--------|---------------|
| **PASS** | Vérification réussie, système en bonne santé |
| **FAIL** | Vérification échouée, à investiguer immédiatement |
| **BLOCKED** | La vérification n'a pas pu aboutir en raison d'une dépendance (par ex. pas de données pour cet acheteur, endpoint manquant). Pas nécessairement un bug de code. |

## Ressources connexes

- [Déploiement](12-deployment.md) : vérification du déploiement
- [Dépannage](15-troubleshooting.md) : quand les vérifications de santé échouent
- Pour les acheteurs média : [Import de données](09-data-import.md) explique
  la grille de fraîcheur des données en termes adaptés aux acheteurs.
