# Capítulo 14: Operaciones de base de datos

*Audiencia: DevOps, ingenieros de plataforma*

## Postgres en producción

Cat-Scan utiliza Cloud SQL (Postgres 15) como su única base de datos operativa. La API se conecta a través de un contenedor sidecar de Cloud SQL Auth Proxy en `localhost:5432`.

### Tablas principales y escala

| Tabla | Filas aproximadas | Qué almacena |
|-------|-------------------|--------------|
| `rtb_daily` | ~84 millones | Rendimiento RTB diario por comprador, creativo, geo, etc. |
| `rtb_bidstream` | ~21 millones | Desglose del bidstream por publisher, geo |
| `rtb_quality` | variable | Métricas de calidad (visibilidad, seguridad de marca) |
| `rtb_bid_filtering` | ~188 mil | Motivos y volúmenes de filtrado de ofertas |
| `pretargeting_configs` | pequeña | Snapshots de configuración de pretargeting |
| `creatives` | pequeña | Metadatos de creativos y miniaturas |
| `import_history` | pequeña | Registros de importación de CSV |
| `users`, `permissions`, `audit_log` | pequeña | Datos de autenticación y administración |

### Índices críticos

El patrón de índice más sensible al rendimiento es:

```sql
CREATE INDEX idx_<table>_buyer_metric_date_desc
    ON <table> (buyer_account_id, metric_date DESC);
```

Este existe en `rtb_daily`, `rtb_bidstream`, `rtb_quality` y
`rtb_bid_filtering`. Soporta la consulta de frescura de datos y las analíticas con alcance por comprador.

Otros índices importantes:
- `(metric_date, buyer_account_id)`: para filtros de rango de fechas + comprador
- `(metric_date, billing_id)`: para consultas con alcance de facturación
- `(row_hash)` UNIQUE: deduplicación en la importación

### Deduplicación

Cada fila importada se hashea (columna `row_hash`). La restricción de unicidad en `row_hash` previene inserciones duplicadas, haciendo que la reimportación sea segura.

## Modelo de conexión

La API utiliza **conexiones por solicitud** (sin pool de conexiones). Cada consulta crea una llamada fresca a `psycopg.connect()`, envuelta en `run_in_executor` para compatibilidad asíncrona.

```python
async def pg_query(sql, params=()):
    loop = asyncio.get_event_loop()
    def _execute():
        with _get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    return await loop.run_in_executor(None, _execute)
```

Para cargas de trabajo en producción, considere agregar `psycopg_pool` si la sobrecarga de conexión se convierte en un cuello de botella.

## Tiempos de espera de sentencias

Para consultas costosas (por ejemplo, frescura de datos en tablas grandes), la API utiliza `pg_query_with_timeout`:

```python
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
cursor = conn.execute(sql, params)
```

Detalles clave:
- `SET LOCAL` limita el timeout a la transacción actual y se reinicia automáticamente cuando la transacción termina (commit o rollback).
- Timeout por defecto de frescura de datos: 30 segundos.
- Configurable mediante la variable de entorno `UPLOADS_DATA_FRESHNESS_QUERY_TIMEOUT_MS` (mínimo 1000ms).
- `SET LOCAL` evita el problema de transacción abortada que ocurre al usar `SET` + `RESET` en un bloque `try/finally` (si la consulta es cancelada por el timeout, la transacción entra en estado abortado y `RESET` falla).

## Patrón de consulta de frescura de datos

El endpoint de frescura de datos necesita saber qué fechas tienen datos para cada tipo de informe. El patrón eficiente utiliza `generate_series` + `EXISTS`:

```sql
SELECT d::date AS metric_date, 'bidsinauction' AS csv_type, 1 AS row_count
FROM generate_series(%s::date, CURRENT_DATE - 1, '1 day'::interval) AS d
WHERE EXISTS (
    SELECT 1 FROM rtb_daily
    WHERE metric_date = d::date AND buyer_account_id = %s
    LIMIT 1
)
```

Esto realiza N búsquedas por índice (una por día en la ventana) en lugar de escanear millones de filas. Para una ventana de 14 días: 14 búsquedas a ~0,1ms cada una vs. un escaneo secuencial paralelo completo que tarda más de 160 segundos.

**Por qué GROUP BY no funciona aquí:** Incluso con `1 AS row_count` (sin COUNT), el planificador elige un escaneo secuencial cuando el conjunto de resultados del GROUP BY es grande en relación con la tabla. El índice `(buyer_account_id, metric_date DESC)` existe pero el planificador estima que es más barato escanear 84M de filas que realizar 4,4M de lecturas por índice.

## Rol de BigQuery

BigQuery almacena datos crudos y granulares, y ejecuta trabajos de analítica por lotes. No se utiliza para consultas API en tiempo real. El patrón es:

1. Los datos CSV crudos se cargan en tablas de BigQuery.
2. Los trabajos por lotes agregan los datos.
3. Los resultados pre-agregados se escriben en Postgres.
4. La API sirve desde Postgres.

## Retención de datos

Configurable en `/settings/retention`. Controla cuánto tiempo se mantienen los datos históricos en Postgres antes de ser purgados.

## Relacionado

- [Visión general de la arquitectura](11-architecture.md): dónde encaja la base de datos
- [Solución de problemas](15-troubleshooting.md): patrones de fallo de base de datos
- Para media buyers: [Importación de datos](09-data-import.md) cubre la cuadrícula de frescura de datos orientada al usuario.
