# Chapitre 15 : Guide de dépannage

*Public visé : DevOps, ingénieurs plateforme*

## Boucle de connexion

**Symptômes :** L'utilisateur arrive sur la page de connexion, s'authentifie,
est redirigé vers la page de connexion, et la boucle se répète indéfiniment.

**Schéma de la cause racine :** Toute défaillance de la base de données
provoque l'échec silencieux de `_get_or_create_oauth2_user()`. `/auth/check`
renvoie `{authenticated: false}`. Le frontend redirige vers `/oauth2/sign_in`.
Boucle.

**Déclencheurs courants :**
- Le conteneur Cloud SQL Proxy s'est arrêté ou a été redémarré sans redémarrer
  l'API
- Partition réseau entre la VM et l'instance Cloud SQL
- Maintenance ou redémarrage de l'instance Cloud SQL

**Détection :**
- Navigateur : le compteur de redirections se déclenche après 2 redirections
  en 30 secondes, affichant une interface d'erreur/réessai au lieu de boucler
- API : `/auth/check` renvoie HTTP 503 (et non 200) lorsque la base de données
  est injoignable, avec `auth_error` dans la réponse
- Journaux : rechercher les erreurs de connexion refusée ou de dépassement de
  délai dans les logs de catscan-api

**Correction :**
1. Vérifier Cloud SQL Proxy : `sudo docker ps | grep cloudsql`
2. S'il est arrêté : `sudo docker compose -f docker-compose.gcp.yml restart cloudsql-proxy`
3. Attendre 10 secondes, puis redémarrer l'API :
   `sudo docker compose -f docker-compose.gcp.yml restart api`
4. Vérifier : `curl -sS http://localhost:8000/health`

**Prévention :** Le correctif à trois couches (appliqué en février 2026) :
1. Le backend propage les erreurs de base de données via `request.state.auth_error`
2. `/auth/check` renvoie 503 lorsque la base de données est injoignable
3. Le frontend dispose d'un compteur de redirections (max 2 en 30 s) + interface d'erreur/réessai

## Dépassement du délai de fraîcheur des données

**Symptômes :** `/uploads/data-freshness` renvoie 500, expire, ou la porte
de santé à l'exécution affiche BLOCKED sur la santé des données.

**Schéma de la cause racine :** La requête de fraîcheur des données parcourt
de grandes tables (`rtb_daily` à 84 millions de lignes, `rtb_bidstream` à
21 millions de lignes). Si le plan de requête se dégrade en scan séquentiel
au lieu d'utiliser les index, cela peut prendre plus de 160 secondes.

**Détection :**
1. Appeler le endpoint directement depuis la VM :
   ```bash
   curl -sS --max-time 60 -H 'X-Email: cat-scan@rtb.cat' \
     'http://localhost:8000/uploads/data-freshness?days=14&buyer_id=<ID>'
   ```
2. En cas d'expiration ou de réponse 500, vérifier le plan de requête :
   ```bash
   sudo docker exec catscan-api python -c "
   import os, psycopg
   conn = psycopg.connect(os.environ['POSTGRES_DSN'])
   for r in conn.execute('EXPLAIN (ANALYZE, BUFFERS) <query>').fetchall():
       print(list(r.values())[0])
   "
   ```
3. Rechercher `Parallel Seq Scan` sur les grandes tables. C'est le problème.

**Schéma de correction :**
- Réécrire les requêtes GROUP BY en `generate_series + EXISTS` pour forcer
  les recherches par index. Voir [Opérations de base de données](14-database.md)
  pour le modèle.
- S'assurer que `SET LOCAL statement_timeout` est utilisé (et non `SET` + `RESET`).
- Vérifier que les index `(buyer_account_id, metric_date DESC)` existent sur
  toutes les tables cibles.

## Échec de l'import Gmail

**Symptômes :** La grille de fraîcheur des données affiche des cellules
« manquantes » pour les dates récentes. L'historique d'import ne contient pas
d'entrées récentes.

**Détection :**
```bash
curl -sS -H 'X-Email: cat-scan@rtb.cat' \
  http://localhost:8000/gmail/status
```

Vérifier : `last_reason`, compteur `unread`, `latest_metric_date`.

**Causes courantes :**
- Le jeton OAuth Gmail a expiré : ré-autoriser dans `/settings/accounts` >
  onglet Gmail
- Cloud SQL Proxy arrêté : l'import Gmail écrit dans Postgres, la base de
  données doit donc être joignable
- Compteur `unread` élevé (30+) : l'import peut être bloqué en cours de
  traitement ou la boîte de réception a un arriéré

**Correction :**
1. Si `last_reason` indique une erreur : redémarrer la tâche d'import depuis
   l'interface ou l'API
2. Si le jeton a expiré : ré-autoriser l'intégration Gmail
3. Si Cloud SQL est en panne : corriger d'abord la connexion à la base de
   données (voir boucle de connexion)

## Ordre de redémarrage des conteneurs

**Symptôme :** Les journaux de l'API affichent « connection refused » sur le
port 5432 au démarrage.

**Cause :** Le conteneur API a démarré avant que Cloud SQL Proxy ne soit prêt.

**Correction :** Redémarrer dans le bon ordre :
```bash
sudo docker compose -f docker-compose.gcp.yml up -d cloudsql-proxy
sleep 10
sudo docker compose -f docker-compose.gcp.yml up -d api
```

Ou tout redémarrer (compose gère les dépendances) :
```bash
sudo docker compose -f docker-compose.gcp.yml up -d --force-recreate
```

## Erreur de syntaxe SET statement_timeout

**Symptôme :** Le endpoint renvoie 500 avec l'erreur :
`syntax error at or near "$1" LINE 1: SET statement_timeout = $1`

**Cause :** psycopg3 convertit `%s` en `$1` pour la liaison de paramètres côté
serveur, mais la commande PostgreSQL `SET` ne prend pas en charge les espaces
réservés aux paramètres.

**Correction :** Utiliser une f-string avec un entier validé :
```python
# Wrong:
conn.execute("SET statement_timeout = %s", (timeout_ms,))

# Right:
timeout_ms = max(int(statement_timeout_ms), 1)  # validated int
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
```

## Échec de la porte de santé à l'exécution

**Symptôme :** Le workflow `v1-runtime-health-strict.yml` échoue.

**Procédure de tri :**
1. Consulter les journaux du workflow : `gh run view <id> --log-failed`
2. Distinguer FAIL et BLOCKED :
   - **FAIL** = quelque chose est cassé, à investiguer
   - **BLOCKED** = dépendance manquante (pas de données, pas de endpoint),
     peut être préexistant
3. Raisons BLOCKED préexistantes courantes :
   - « rtb_quality_freshness state is unavailable » : pas de données de qualité
     pour cet acheteur/cette période
   - « proposal has no billing_id » : problème de configuration des données
   - « QPS page API rollup missing required paths » : endpoint d'analyse pas
     encore alimenté
4. Comparer avec les exécutions précédentes pour identifier les régressions
   par rapport aux problèmes préexistants.

## Ressources connexes

- [Surveillance de la santé](13-health-monitoring.md) : outils de surveillance
- [Opérations de base de données](14-database.md) : détails des requêtes et des index
- [Déploiement](12-deployment.md) : déployer les correctifs
