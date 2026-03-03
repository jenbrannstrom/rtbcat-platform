# Chapitre 14 : Opérations de base de données

*Public visé : DevOps, ingénieurs plateforme*

## Postgres en production

Cat-Scan utilise Cloud SQL (Postgres 15) comme unique base de données
opérationnelle. L'API se connecte via un conteneur sidecar Cloud SQL Auth Proxy
sur `localhost:5432`.

### Tables principales et volumétrie

| Table | Nombre approximatif de lignes | Contenu |
|-------|-------------------------------|---------|
| `rtb_daily` | ~84 millions | Performance RTB quotidienne par acheteur, créatif, zone géographique, etc. |
| `rtb_bidstream` | ~21 millions | Répartition du bidstream par éditeur, zone géographique |
| `rtb_quality` | variable | Métriques de qualité (visibilité, sécurité de marque) |
| `rtb_bid_filtering` | ~188 milliers | Raisons de filtrage des enchères et volumes |
| `pretargeting_configs` | faible | Instantanés de la configuration de pretargeting |
| `creatives` | faible | Métadonnées et miniatures des créatifs |
| `import_history` | faible | Enregistrements des imports CSV |
| `users`, `permissions`, `audit_log` | faible | Données d'authentification et d'administration |

### Index critiques

Le modèle d'index le plus sensible en termes de performance est :

```sql
CREATE INDEX idx_<table>_buyer_metric_date_desc
    ON <table> (buyer_account_id, metric_date DESC);
```

Celui-ci existe sur `rtb_daily`, `rtb_bidstream`, `rtb_quality` et
`rtb_bid_filtering`. Il prend en charge la requête de fraîcheur des données et
les analyses par acheteur.

Autres index importants :
- `(metric_date, buyer_account_id)` : pour les filtres par plage de dates + acheteur
- `(metric_date, billing_id)` : pour les requêtes par périmètre de facturation
- `(row_hash)` UNIQUE : dédoublonnage à l'import

### Dédoublonnage

Chaque ligne importée est hachée (colonne `row_hash`). La contrainte d'unicité
sur `row_hash` empêche les insertions en double, rendant la réimportation sûre.

## Modèle de connexion

L'API utilise des **connexions par requête** (pas de pool de connexions). Chaque
requête crée un nouvel appel `psycopg.connect()`, encapsulé dans
`run_in_executor` pour la compatibilité asynchrone.

```python
async def pg_query(sql, params=()):
    loop = asyncio.get_event_loop()
    def _execute():
        with _get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    return await loop.run_in_executor(None, _execute)
```

Pour les charges de travail en production, envisagez d'ajouter `psycopg_pool`
si la surcharge de connexion devient un goulot d'étranglement.

## Délais d'expiration des requêtes

Pour les requêtes coûteuses (par ex. la fraîcheur des données sur des tables
volumineuses), l'API utilise `pg_query_with_timeout` :

```python
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
cursor = conn.execute(sql, params)
```

Points importants :
- `SET LOCAL` limite le délai à la transaction en cours et se réinitialise
  automatiquement à la fin de la transaction (commit ou rollback).
- Délai par défaut pour la fraîcheur des données : 30 secondes.
- Configurable via la variable d'environnement
  `UPLOADS_DATA_FRESHNESS_QUERY_TIMEOUT_MS` (minimum 1000 ms).
- `SET LOCAL` évite le problème de transaction interrompue qui survient
  lors de l'utilisation de `SET` + `RESET` dans un bloc `try/finally`
  (si la requête est annulée par le délai, la transaction passe en état
  interrompu et `RESET` échoue).

## Modèle de requête pour la fraîcheur des données

Le endpoint de fraîcheur des données doit connaître les dates disposant de
données pour chaque type de rapport. Le modèle performant utilise
`generate_series` + `EXISTS` :

```sql
SELECT d::date AS metric_date, 'bidsinauction' AS csv_type, 1 AS row_count
FROM generate_series(%s::date, CURRENT_DATE - 1, '1 day'::interval) AS d
WHERE EXISTS (
    SELECT 1 FROM rtb_daily
    WHERE metric_date = d::date AND buyer_account_id = %s
    LIMIT 1
)
```

Cela effectue N recherches par index (une par jour dans la fenêtre) au lieu
de parcourir des millions de lignes. Pour une fenêtre de 14 jours : 14
recherches à environ 0,1 ms chacune contre un scan séquentiel parallèle
complet qui prend plus de 160 secondes.

**Pourquoi GROUP BY ne fonctionne pas ici :** Même avec `1 AS row_count`
(pas de COUNT), le planificateur choisit un scan séquentiel lorsque le jeu
de résultats du GROUP BY est grand par rapport à la table. L'index
`(buyer_account_id, metric_date DESC)` existe, mais le planificateur estime
qu'il est moins coûteux de parcourir 84 millions de lignes que de faire
4,4 millions de lectures d'index.

## Rôle de BigQuery

BigQuery stocke les données brutes et granulaires et exécute les tâches
d'analyse par lots. Il n'est pas utilisé pour les requêtes API en temps réel.
Le schéma est le suivant :

1. Les données CSV brutes sont chargées dans les tables BigQuery.
2. Des tâches par lots agrègent les données.
3. Les résultats pré-agrégés sont écrits dans Postgres.
4. L'API sert les données depuis Postgres.

## Conservation des données

Configurable dans `/settings/retention`. Contrôle la durée de conservation
des données historiques dans Postgres avant leur suppression.

## Ressources connexes

- [Vue d'ensemble de l'architecture](11-architecture.md) : positionnement de la base de données
- [Dépannage](15-troubleshooting.md) : schémas de défaillance de la base de données
- Pour les acheteurs média : [Import de données](09-data-import.md) couvre la
  grille de fraîcheur des données côté utilisateur.
