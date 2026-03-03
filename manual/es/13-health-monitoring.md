# Capítulo 13: Monitoreo de salud y diagnósticos

*Audiencia: DevOps, ingenieros de plataforma*

## Endpoints de salud

### `/api/health`: disponibilidad

Devuelve el estado básico de la API, el SHA de git y la versión. Utilizado por el flujo de despliegue y el monitoreo externo.

```bash
curl -sS https://scan.rtb.cat/api/health | jq .
```

### `/system/data-health`: completitud de datos

Devuelve el estado de salud de los datos por comprador, incluyendo el estado de frescura para cada tipo de informe. Acepta los parámetros `days`, `buyer_id` y `availability_state`.

Utilizado por la lista de verificación de configuración y la puerta de salud en tiempo de ejecución.

## Página de estado del sistema (`/settings/system`)

La interfaz muestra:

| Verificación | Qué monitorea |
|--------------|---------------|
| Python | Versión del runtime y disponibilidad |
| Node | Build de Next.js y estado de SSR |
| FFmpeg | Capacidad de generación de miniaturas de video |
| Database | Conexión a Postgres y conteo de registros |
| Thumbnails | Estado de generación por lotes y cola |
| Disk space | Uso de disco de la VM |

## Scripts de salud en tiempo de ejecución

Estos scripts son la columna vertebral operativa para verificar que el sistema funciona de extremo a extremo.

### `diagnose_v1_buyer_report_coverage.sh`

Diagnostica por qué un comprador específico tiene cobertura de CSV faltante.

```bash
export CATSCAN_CANARY_EMAIL="cat-scan@rtb.cat"
scripts/diagnose_v1_buyer_report_coverage.sh \
  --buyer-id 1487810529 \
  --timeout 180 \
  --days 14
```

Verificaciones (en orden):
1. Mapeo de asientos: buyer_id -> bidder_id
2. Matriz de importación: aprobado/fallido/no_importado por tipo de CSV
3. Frescura de datos: cobertura de celdas importadas/faltantes
4. Historial de importación: registros de importación recientes
5. Estado de Gmail: cantidad de no leídos, último motivo, última fecha de métrica

Resultado: PASS o FAIL con diagnóstico específico.

### `run_v1_runtime_health_strict_dispatch.sh`

Ejecuta la puerta de salud completa en tiempo de ejecución, que verifica:

- Salud de la API
- Salud de los datos (frescura y cobertura de dimensiones)
- Salud y preparación de conversiones
- Latencia de inicio de QPS
- Resumen de SLO de la página de QPS
- Economía y modelos del optimizador
- Validación de endpoints del modelo
- Flujo de score+propose
- Ciclo de vida de propuestas
- Simulación de rollback (dry-run)

Cada verificación devuelve PASS, FAIL o BLOCKED (con motivo).

### Flujo de CI: `v1-runtime-health-strict.yml`

Ejecuta la puerta estricta en CI. Se activa manualmente a través de workflow_dispatch.

```bash
gh workflow run v1-runtime-health-strict.yml \
  --ref unified-platform \
  -f api_base_url="https://scan.rtb.cat/api" \
  -f buyer_id="1487810529" \
  -f canary_profile="balanced" \
  -f canary_timeout_seconds="180"
```

## Autenticación canary

Los scripts de tiempo de ejecución se autentican mediante variables de entorno:

| Variable | Propósito |
|----------|-----------|
| `CATSCAN_CANARY_EMAIL` | Encabezado X-Email para llamadas directas a la API (local en la VM) |
| `CATSCAN_BEARER_TOKEN` | Token bearer (entorno de CI, almacenado en GitHub secrets) |
| `CATSCAN_SESSION_COOKIE` | Cookie de sesión de OAuth2 Proxy (entorno de CI) |

Desde el host de la VM, use `CATSCAN_CANARY_EMAIL` con `http://localhost:8000`.
Desde CI (externo), use `CATSCAN_BEARER_TOKEN` o `CATSCAN_SESSION_COOKIE`
con `https://scan.rtb.cat/api`.

## Interpretación de resultados

| Estado | Significado |
|--------|-------------|
| **PASS** | La verificación fue exitosa, el sistema está sano |
| **FAIL** | La verificación falló, investigue de inmediato |
| **BLOCKED** | La verificación no pudo completarse debido a una dependencia (por ejemplo, no hay datos para este comprador, endpoint faltante). No necesariamente es un error de código. |

## Relacionado

- [Despliegue](12-deployment.md): verificación de despliegues
- [Solución de problemas](15-troubleshooting.md): cuando las verificaciones de salud fallan
- Para media buyers: [Importación de datos](09-data-import.md) explica la cuadrícula de frescura de datos en términos orientados al comprador.
