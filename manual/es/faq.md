# Preguntas Frecuentes

Las preguntas están etiquetadas por audiencia: **[Comprador]** para compradores de medios y
gestores de campañas, **[DevOps]** para ingenieros de plataforma, **[Ambos]** para preguntas
compartidas.

---

### [Comprador] ¿Por qué mi porcentaje de cobertura está por debajo del 100%?

La cobertura mide cuántas celdas de fecha x tipo de informe tienen datos en comparación con
cuántas se esperan. Razones comunes de los vacíos:

- **Google no envió un informe** para esa fecha (día festivo, retraso en la exportación).
- **La importación de Gmail no capturó el correo** (verifique el estado de Gmail).
- **Un tipo de informe específico no está disponible** para su seat (por ejemplo, los datos
  de calidad pueden no existir para todos los compradores).

Consulte la cuadrícula de frescura de datos en `/import` para ver exactamente qué celdas
faltan. Vea [Importación de Datos](09-data-import.md).

### [Comprador] ¿Cuál es la diferencia entre "desperdicio" y "baja tasa de ganancia"?

**Desperdicio** = solicitudes de puja que su bidder *rechazó* sin pujar. Esto es QPS
por el que pagó pero que no pudo utilizar en absoluto. Corríjalo con pretargeting.

**Baja tasa de ganancia** = solicitudes de puja sobre las que su bidder *pujó* pero perdió
la subasta. Esto significa que sus pujas no son lo suficientemente competitivas. Corríjalo
con la estrategia de puja, no con pretargeting.

Ambos aparecen en el embudo pero requieren acciones diferentes. Vea
[Comprendiendo Su Embudo de QPS](03-qps-funnel.md).

### [Comprador] ¿Puedo deshacer un cambio de pretargeting?

Sí. Vaya a `/history`, encuentre el cambio, haga clic en "Vista previa de reversión" para
ver qué se revertirá y luego confirme. La reversión en sí queda registrada. Vea
[Configuración de Pretargeting](06-pretargeting.md).

### [Comprador] ¿Con qué frecuencia debería reimportar datos?

Diariamente. La importación automática de Gmail se encarga de esto automáticamente. Si está
importando manualmente, hágalo una vez al día después de que lleguen los informes. Los datos
desactualizados llevan a decisiones desactualizadas.

### [Comprador] ¿Qué cambia realmente el optimizador?

El optimizador propone cambios en sus configuraciones de pretargeting: agregar o eliminar
geografías, tamaños, editores, etc. Nunca aplica cambios automáticamente. Usted revisa y
aprueba cada propuesta. Vea [El Optimizador](07-optimizer.md).

---

### [DevOps] ¿Por qué falló la compuerta estricta de salud en tiempo de ejecución?

Verifique los registros del workflow: `gh run view <id> --log-failed`. Busque FAIL vs.
BLOCKED:

- **FAIL** = algo se rompió. Los problemas de timeout de frescura de datos y de
  `SET statement_timeout` son causas comunes. Vea
  [Resolución de Problemas](15-troubleshooting.md).
- **BLOCKED** = falta una dependencia, no necesariamente un error de código. Ejemplos:
  sin datos de calidad para este comprador, la propuesta no tiene billing_id. Compare con
  ejecuciones anteriores para distinguir regresiones de vacíos preexistentes.

### [DevOps] ¿Por qué el endpoint de frescura de datos es lento?

La consulta escanea `rtb_daily` (~84M filas) y `rtb_bidstream` (~21M filas). Si el plan
de consulta degenera a un escaneo secuencial en lugar de usar los índices
`(buyer_account_id, metric_date DESC)`, tardará minutos.

Solución: asegúrese de que las consultas usen el patrón `generate_series + EXISTS` (14
búsquedas por índice en lugar de un escaneo completo de tabla). Vea
[Operaciones de Base de Datos](14-database.md).

### [DevOps] ¿Cómo verifico qué versión está desplegada?

```bash
curl -sS https://scan.rtb.cat/api/health | jq -r '.git_sha,.version'
```

Esto devuelve el SHA del commit de git y la etiqueta de imagen. Compárelo con su registro
de commits.

### [DevOps] ¿Cómo despliego una corrección?

1. Haga push a `unified-platform`
2. Espere a que `build-and-push.yml` tenga éxito
3. Ejecute `deploy.yml` mediante `gh workflow run` con `confirm=DEPLOY`
4. Verifique con `/api/health`

Vea [Despliegue](12-deployment.md) para el procedimiento completo.

### [DevOps] Los usuarios están atrapados en un bucle de inicio de sesión. ¿Qué hago?

Verifique Cloud SQL Proxy: `sudo docker ps | grep cloudsql`. Si está caído,
reinícielo, espere 10 segundos y luego reinicie el contenedor de la API. Vea
[Resolución de Problemas](15-troubleshooting.md) para el procedimiento completo.

---

### [Ambos] ¿De dónde provienen los datos de Cat-Scan?

De las exportaciones CSV de Google Authorized Buyers. No hay una API de informes. Los datos
llegan ya sea por carga manual de CSV o por ingesta automática de Gmail. Vea
[Importación de Datos](09-data-import.md).

### [Ambos] ¿Es seguro reimportar el mismo CSV?

Sí. Cada fila se hashea y se deduplica. Reimportar nunca cuenta dos veces.

### [Ambos] ¿Qué idiomas soporta la interfaz?

Inglés, neerlandés y chino (simplificado). El selector de idioma está en la barra lateral.
