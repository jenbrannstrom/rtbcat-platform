# Capítulo 15: Guía de solución de problemas

*Audiencia: DevOps, ingenieros de plataforma*

## Bucle de inicio de sesión

**Síntomas:** El usuario llega a la página de inicio de sesión, se autentica, es redirigido de vuelta a la página de inicio de sesión, y el ciclo se repite indefinidamente.

**Patrón de causa raíz:** Cualquier fallo de base de datos provoca que `_get_or_create_oauth2_user()` falle silenciosamente. `/auth/check` devuelve `{authenticated: false}`. El frontend redirige a `/oauth2/sign_in`. Bucle.

**Causas comunes:**
- El contenedor de Cloud SQL Proxy murió o fue reiniciado sin reiniciar la API
- Partición de red entre la VM y la instancia de Cloud SQL
- Mantenimiento o reinicio de la instancia de Cloud SQL

**Detección:**
- Navegador: el contador de redirecciones se activa después de 2 redirecciones en 30 segundos, mostrando una interfaz de error/reintento en lugar del bucle
- API: `/auth/check` devuelve HTTP 503 (no 200) cuando la base de datos es inalcanzable, con `auth_error` en la respuesta
- Logs: busque errores de conexión rechazada o timeout en los logs de catscan-api

**Solución:**
1. Verificar Cloud SQL Proxy: `sudo docker ps | grep cloudsql`
2. Si está caído: `sudo docker compose -f docker-compose.gcp.yml restart cloudsql-proxy`
3. Esperar 10 segundos, luego reiniciar la API:
   `sudo docker compose -f docker-compose.gcp.yml restart api`
4. Verificar: `curl -sS http://localhost:8000/health`

**Prevención:** La corrección en tres capas (aplicada en febrero de 2026):
1. El backend propaga errores de BD a través de `request.state.auth_error`
2. `/auth/check` devuelve 503 cuando la BD es inalcanzable
3. El frontend tiene un contador de redirecciones (máximo 2 en 30s) + interfaz de error/reintento

## Timeout de frescura de datos

**Síntomas:** `/uploads/data-freshness` devuelve 500, se agota el tiempo de espera, o la puerta de salud en tiempo de ejecución muestra BLOCKED en salud de datos.

**Patrón de causa raíz:** La consulta de frescura de datos escanea tablas grandes (`rtb_daily` con 84M de filas, `rtb_bidstream` con 21M de filas). Si el plan de consulta se degrada a un escaneo secuencial en lugar de usar índices, puede tardar más de 160 segundos.

**Detección:**
1. Consulte el endpoint directamente desde la VM:
   ```bash
   curl -sS --max-time 60 -H 'X-Email: cat-scan@rtb.cat' \
     'http://localhost:8000/uploads/data-freshness?days=14&buyer_id=<ID>'
   ```
2. Si se agota el tiempo o devuelve 500, verifique el plan de consulta:
   ```bash
   sudo docker exec catscan-api python -c "
   import os, psycopg
   conn = psycopg.connect(os.environ['POSTGRES_DSN'])
   for r in conn.execute('EXPLAIN (ANALYZE, BUFFERS) <query>').fetchall():
       print(list(r.values())[0])
   "
   ```
3. Busque `Parallel Seq Scan` en tablas grandes. Ese es el problema.

**Patrón de solución:**
- Reescriba las consultas con GROUP BY como `generate_series + EXISTS` para forzar búsquedas por índice. Consulte [Operaciones de base de datos](14-database.md) para ver el patrón.
- Asegúrese de que se use `SET LOCAL statement_timeout` (no `SET` + `RESET`).
- Verifique que los índices `(buyer_account_id, metric_date DESC)` existan en todas las tablas objetivo.

## Fallo de importación de Gmail

**Síntomas:** La cuadrícula de frescura de datos muestra celdas "faltantes" para fechas recientes. El historial de importación no tiene entradas recientes.

**Detección:**
```bash
curl -sS -H 'X-Email: cat-scan@rtb.cat' \
  http://localhost:8000/gmail/status
```

Verifique: `last_reason`, conteo de `unread`, `latest_metric_date`.

**Causas comunes:**
- Token de OAuth de Gmail expirado: reautorizar en `/settings/accounts` > pestaña Gmail
- Cloud SQL Proxy caído: la importación de Gmail escribe en Postgres, por lo que la BD debe estar accesible
- Conteo alto de `unread` (30+): la importación puede estar atascada procesando o el buzón tiene un backlog

**Solución:**
1. Si `last_reason` muestra un error: reinicie el trabajo de importación desde la interfaz o la API
2. Si el token expiró: reautorizar la integración de Gmail
3. Si Cloud SQL está caído: solucione primero la conexión a la base de datos (vea bucle de inicio de sesión)

## Orden de reinicio de contenedores

**Síntoma:** Los logs de la API muestran "connection refused" al puerto 5432 durante el inicio.

**Causa:** El contenedor de la API inició antes de que Cloud SQL Proxy estuviera listo.

**Solución:** Reiniciar con el orden correcto:
```bash
sudo docker compose -f docker-compose.gcp.yml up -d cloudsql-proxy
sleep 10
sudo docker compose -f docker-compose.gcp.yml up -d api
```

O reiniciar todo (compose gestiona las dependencias):
```bash
sudo docker compose -f docker-compose.gcp.yml up -d --force-recreate
```

## Error de sintaxis en SET statement_timeout

**Síntoma:** El endpoint devuelve 500 con el error:
`syntax error at or near "$1" LINE 1: SET statement_timeout = $1`

**Causa:** psycopg3 convierte `%s` a `$1` para el enlace de parámetros del lado del servidor, pero el comando `SET` de PostgreSQL no soporta marcadores de parámetros.

**Solución:** Usar f-string con un entero validado:
```python
# Wrong:
conn.execute("SET statement_timeout = %s", (timeout_ms,))

# Right:
timeout_ms = max(int(statement_timeout_ms), 1)  # validated int
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
```

## Fallo en la puerta de salud en tiempo de ejecución

**Síntoma:** El flujo de trabajo `v1-runtime-health-strict.yml` falla.

**Triaje:**
1. Verifique los logs del flujo de trabajo: `gh run view <id> --log-failed`
2. Busque FAIL vs. BLOCKED:
   - **FAIL** = algo se rompió, investigue
   - **BLOCKED** = dependencia faltante (sin datos, sin endpoint), puede ser preexistente
3. Motivos comunes de BLOCKED preexistentes:
   - "rtb_quality_freshness state is unavailable": no hay datos de calidad para este comprador/período
   - "proposal has no billing_id": problema de configuración de datos
   - "QPS page API rollup missing required paths": endpoint de analítica aún no poblado
4. Compare con ejecuciones anteriores para identificar regresiones vs. problemas preexistentes.

## Relacionado

- [Monitoreo de salud](13-health-monitoring.md): herramientas de monitoreo
- [Operaciones de base de datos](14-database.md): detalles de consultas e índices
- [Despliegue](12-deployment.md): desplegar correcciones
