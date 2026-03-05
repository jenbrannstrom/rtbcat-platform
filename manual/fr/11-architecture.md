# Chapitre 11 : Vue d'ensemble de l'architecture

*Public : DevOps, ingenieurs plateforme*

## Topologie du systeme

```
                                    Internet
                                       |
                                 +-----+-----+
                                 |   nginx    |  :443 (terminaison TLS)
                                 +--+------+--+
                                    |      |
                          +---------+      +---------+
                          |                          |
                  +-------+--------+       +---------+---------+
                  |  OAuth2 Proxy  |       |  Next.js Dashboard |  :3000
                  |  (Google SSO)  |       |  (statique + SSR)  |
                  +-------+--------+       +-------------------+
                          |
                  +-------+--------+
                  |   FastAPI API  |  :8000
                  |  (118+ routes) |
                  +-------+--------+
                          |
              +-----------+-----------+
              |                       |
    +---------+----------+   +--------+--------+
    | Cloud SQL Proxy    |   |   BigQuery       |
    | (sidecar Postgres) |   | (analytique batch)|
    +---------+----------+   +-----------------+
              |
    +---------+----------+
    |  Cloud SQL         |
    |  (Postgres 15)     |
    +--------------------+
```

## Disposition des conteneurs

La production s'execute sur une seule VM GCP (`catscan-vm`, zone
`asia-southeast1-b`) en utilisant `docker-compose.gcp.yml`.

| Conteneur | Image | Port | Role |
|-----------|-------|------|------|
| `catscan-api` | `asia-southeast1-docker.pkg.dev/.../api:sha-XXXXXXX` | 8000 | Backend FastAPI |
| `catscan-dashboard` | `asia-southeast1-docker.pkg.dev/.../dashboard:sha-XXXXXXX` | 3000 | Frontend Next.js |
| `oauth2-proxy` | image oauth2-proxy standard | 4180 | Authentification Google OAuth2 |
| `cloudsql-proxy` | Google Cloud SQL Auth Proxy | 5432 | Proxy de connexion Postgres |
| `nginx` | nginx standard avec configuration | 80/443 | Reverse proxy, TLS, routage |

## Chaine de confiance d'authentification

```
Browser → nginx → OAuth2 Proxy → sets X-Email header → nginx → API
```

1. Le navigateur contacte nginx.
2. nginx route `/oauth2/*` vers OAuth2 Proxy.
3. OAuth2 Proxy authentifie via Google et definit l'en-tete `X-Email`.
4. Les requetes suivantes passent par nginx avec `X-Email` intact.
5. L'API lit `X-Email` et lui fait confiance (quand `OAUTH2_PROXY_ENABLED=true`).

**Important :** L'API ne fait confiance a `X-Email` que pour le trafic interne. Les requetes externes avec un en-tete `X-Email` falsifie sont rejetees par nginx.

## Pourquoi deux bases de donnees

Cat-Scan utilise a la fois Postgres et BigQuery pour des roles differents :

| Aspect | Postgres (Cloud SQL) | BigQuery |
|--------|---------------------|----------|
| **Role** | Base de donnees operationnelle : alimente l'application | Entrepot de donnees : stocke les donnees brutes, execute les analyses par lots |
| **Modele de cout** | Cout d'hebergement fixe, requetes illimitees | Paiement a la requete base sur les donnees analysees |
| **Latence** | Reponses en millisecondes | 1 a 3 secondes de surcharge meme pour des requetes simples |
| **Concurrence** | Gere des centaines de connexions API | Non concu pour des rafraichissements concurrents du tableau de bord |
| **Donnees** | Resumes pre-agreges, configurations, donnees utilisateur | Lignes granulaires brutes (des millions par jour) |

Le principe : BigQuery est l'entrepot d'archivage ; Postgres est le rayon du magasin. On n'envoie pas les clients fouiller dans l'entrepot.

## Structure cle du code source

```
/api/routers/       Gestionnaires de routes FastAPI (118+ endpoints)
/services/          Couche de logique metier
/storage/           Acces aux donnees (repos Postgres, clients BigQuery)
/dashboard/src/     Frontend Next.js 14 (App Router)
/scripts/           Scripts operationnels et de diagnostic
/docs/              Documentation d'architecture et journaux des agents IA
```

Le backend suit le pattern **Router -> Service -> Repository**. Les routers gerent le HTTP ; les services contiennent la logique metier ; les repositories executent le SQL.

## Voir aussi

- [Deploiement](12-deployment.md) : comment le systeme est deploye
- [Operations de base de donnees](14-database.md) : specificites Postgres
- [Integrations](17-integrations.md) : connexions aux services externes
