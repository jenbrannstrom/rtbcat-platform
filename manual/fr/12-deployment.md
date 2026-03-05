# Chapitre 12 : Déploiement

*Public visé : DevOps, ingénieurs plateforme*

## Pipeline CI/CD

```
Push to unified-platform
         │
         ▼
build-and-push.yml (automatic)
  ├── Run contract & recovery tests
  ├── Build API image
  ├── Build Dashboard image
  └── Push to Artifact Registry
         │
         ▼ (manual trigger)
deploy.yml (workflow_dispatch)
  ├── SSH into VM via IAP tunnel
  ├── git pull on VM
  ├── docker compose pull (prebuilt images)
  ├── docker compose up -d --force-recreate
  ├── Health check (60s wait + curl localhost:8000/health)
  └── Post-deploy contract check
```

### Pourquoi le déploiement est manuel

Le déploiement automatique au push a été désactivé à la suite d'un incident
survenu en janvier 2026, au cours duquel des déploiements automatiques entraient
en conflit avec des déploiements manuels via SSH, corrompant les conteneurs et
provoquant des pertes de données. Le workflow de déploiement exige désormais :

1. Un déclenchement manuel via l'interface GitHub Actions (« Run workflow »)
2. La sélection explicite de la cible (staging ou production)
3. La saisie de `DEPLOY` comme confirmation
4. Un champ optionnel de motif pour la traçabilité

### Tags des images

Les images sont taguées avec le SHA git abrégé : `sha-XXXXXXX`. L'étape de
déploiement utilise `GITHUB_SHA` pour construire le tag, de sorte que la version
déployée correspond toujours à un commit précis.

## Comment déployer

1. Vérifier que le build a réussi : `gh run list --workflow=build-and-push.yml --limit=1`
2. Déclencher le déploiement :
   ```bash
   gh workflow run deploy.yml \
     --ref unified-platform \
     -f target=production \
     -f confirm=DEPLOY \
     -f reason="your reason here"
   ```
3. Suivre l'avancement : `gh run watch <run_id> --exit-status`
4. Vérifier : `curl -sS https://your-deployment.example.com/api/health | jq -r '.git_sha,.version'`

## Vérification d'un déploiement

Le endpoint `/api/health` renvoie :

```json
{
  "git_sha": "94e9cbb0",
  "version": "sha-94e9cbb"
}
```

Comparez `git_sha` avec le commit que vous souhaitiez déployer.

## Vérification des contrats post-déploiement

Après le déploiement, le workflow exécute `scripts/contracts_check.py` à
l'intérieur du conteneur API. Ce script valide que les contrats de données
(règles non négociables de l'import jusqu'à la sortie API) sont respectés.
En cas d'échec de la vérification :

- Avec `ALLOW_CONTRACT_FAILURE=false` (par défaut) : le déploiement est marqué
  comme échoué.
- Avec `ALLOW_CONTRACT_FAILURE=true` (contournement temporaire) : le
  déploiement réussit avec un avertissement. Ce contournement doit être retiré
  après investigation.

## Staging vs. production

| Environnement | Nom de la VM | Domaine |
|----------------|--------------|---------|
| Staging | `catscan-vm` | (interne) |
| Production | `catscan-vm` | `your-deployment.example.com` |

Déployez d'abord sur le staging, vérifiez, puis déployez en production.

## Retour en arrière

Pour revenir en arrière, déployez un commit antérieur dont le bon fonctionnement
est connu :

1. Identifiez le dernier SHA fonctionnel à partir du journal git ou des
   exécutions de déploiement précédentes.
2. Positionnez-vous sur ce SHA sur unified-platform (ou utilisez `--ref` avec
   le commit).
3. Déclenchez le workflow de déploiement.

Il n'existe pas de mécanisme de rollback dédié. Il s'agit simplement de
déployer une version antérieure.

## Ressources connexes

- [Vue d'ensemble de l'architecture](11-architecture.md) : ce qui est déployé
- [Surveillance de la santé](13-health-monitoring.md) : vérifier que le déploiement a fonctionné
