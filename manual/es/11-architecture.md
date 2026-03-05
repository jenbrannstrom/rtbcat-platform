# Capítulo 11: Descripción General de la Arquitectura

*Audiencia: DevOps, ingenieros de plataforma*

## Topología del sistema

```
                                    Internet
                                       │
                                 ┌─────┴─────┐
                                 │   nginx    │  :443 (TLS termination)
                                 └──┬──────┬──┘
                                    │      │
                          ┌─────────┘      └─────────┐
                          │                          │
                  ┌───────┴────────┐       ┌─────────┴─────────┐
                  │  OAuth2 Proxy  │       │  Next.js Dashboard │  :3000
                  │  (Google SSO)  │       │  (static + SSR)    │
                  └───────┬────────┘       └───────────────────┘
                          │
                  ┌───────┴────────┐
                  │   FastAPI API  │  :8000
                  │  (118+ routes) │
                  └───────┬────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
    ┌─────────┴──────────┐   ┌────────┴────────┐
    │ Cloud SQL Proxy    │   │   BigQuery       │
    │ (Postgres sidecar) │   │ (batch analytics)│
    └─────────┬──────────┘   └─────────────────┘
              │
    ┌─────────┴──────────┐
    │  Cloud SQL         │
    │  (Postgres 15)     │
    └────────────────────┘
```

## Disposición de contenedores

La producción se ejecuta en una única VM de GCP (`catscan-vm`, zona
`asia-southeast1-b`) utilizando `docker-compose.gcp.yml`.

| Contenedor | Imagen | Puerto | Función |
|------------|--------|--------|---------|
| `catscan-api` | `asia-southeast1-docker.pkg.dev/.../api:sha-XXXXXXX` | 8000 | Backend FastAPI |
| `catscan-dashboard` | `asia-southeast1-docker.pkg.dev/.../dashboard:sha-XXXXXXX` | 3000 | Frontend Next.js |
| `oauth2-proxy` | imagen estándar de oauth2-proxy | 4180 | Autenticación Google OAuth2 |
| `cloudsql-proxy` | Google Cloud SQL Auth Proxy | 5432 | Proxy de conexión a Postgres |
| `nginx` | nginx estándar con configuración | 80/443 | Proxy inverso, TLS, enrutamiento |

## Cadena de confianza de autenticación

```
Browser → nginx → OAuth2 Proxy → sets X-Email header → nginx → API
```

1. El navegador accede a nginx.
2. nginx enruta `/oauth2/*` a OAuth2 Proxy.
3. OAuth2 Proxy autentica a través de Google y establece el encabezado `X-Email`.
4. Las solicitudes posteriores pasan por nginx con `X-Email` intacto.
5. La API lee `X-Email` y lo considera confiable (cuando `OAUTH2_PROXY_ENABLED=true`).

**Importante:** La API solo confía en `X-Email` proveniente del tráfico interno. Las solicitudes
externas con un encabezado `X-Email` falsificado son rechazadas por nginx.

## Por qué dos bases de datos

Cat-Scan utiliza tanto Postgres como BigQuery para diferentes funciones:

| Aspecto | Postgres (Cloud SQL) | BigQuery |
|---------|---------------------|----------|
| **Función** | Base de datos operativa: sirve a la aplicación | Almacén de datos: guarda datos en bruto, ejecuta analítica por lotes |
| **Modelo de costo** | Costo fijo de alojamiento, consultas ilimitadas | Pago por consulta basado en datos escaneados |
| **Latencia** | Respuestas en milisegundos | 1--3 segundos de sobrecarga incluso para consultas simples |
| **Concurrencia** | Gestiona cientos de conexiones API | No diseñado para refrescos concurrentes del dashboard |
| **Datos** | Resúmenes preagregados, configuraciones, datos de usuario | Filas granulares en bruto (millones por día) |

El patrón: BigQuery es el almacén de archivo; Postgres es el estante de la tienda.
No envías a los clientes a buscar en el almacén.

## Estructura clave del código fuente

```
/api/routers/       FastAPI route handlers (118+ endpoints)
/services/          Business logic layer
/storage/           Database access (Postgres repos, BigQuery clients)
/dashboard/src/     Next.js 14 frontend (App Router)
/scripts/           Operational and diagnostic scripts
docs.rtb.cat/       Public documentation portal
```

El backend sigue un patrón **Router -> Service -> Repository**. Los routers
manejan HTTP; los servicios contienen la lógica de negocio; los repositorios ejecutan SQL.

## Relacionado

- [Despliegue](12-deployment.md): cómo se despliega el sistema
- [Operaciones de base de datos](14-database.md): detalles específicos de Postgres
- [Integraciones](17-integrations.md): conexiones con servicios externos
