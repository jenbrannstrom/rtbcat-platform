# Manual de Usuario de Cat-Scan

## El problema en una imagen

![Embudo de QPS](../assets/qps-funnel.svg)

Google envía a su bidder un torrente de solicitudes de puja. Cada segundo, decenas de
miles de consultas salen del exchange de Authorized Buyers hacia su endpoint. Su bidder
evalúa cada una, decide si pujar y responde, todo en cuestión de milisegundos.

Esto es lo que la mayoría pasa por alto: **la gran mayoría de esa señal es
ruido.** Un seat típico que ingiere 50,000 QPS podría encontrar que 30,000 de esas
consultas son para inventario que el comprador de medios nunca iba a adquirir: geografías
incorrectas, dominios de editores irrelevantes, tamaños de anuncios sin creatividad
compatible. Su bidder aún tiene que recibir, analizar y rechazar cada una. Eso cuesta
ancho de banda, cómputo y dinero.

El diagrama de arriba lo muestra como lluvia. El QPS de Google es la boquilla en la
parte superior; las gotas se dispersan por un área amplia. Su bidder es el pequeño balde
en la parte inferior. Todo lo que no cae en el balde (las gotas que caen a izquierda y
derecha) es desperdicio. Usted pagó por ello. No obtuvo nada a cambio.

**Cat-Scan existe para hacer el balde más ancho y la lluvia más estrecha.**

Lo logra dándole visibilidad sobre dónde ocurre el desperdicio (qué geografías, qué
editores, qué tamaños de anuncios, qué creatividades) y los controles para detenerlo
en la fuente, usando las configuraciones de pretargeting que Google proporciona.

### Por qué esto es más difícil de lo que parece

Google Authorized Buyers le da solo **10 configuraciones de pretargeting por seat**, más
regiones geográficas amplias (este de EE. UU., oeste de EE. UU., Europa, Asia). No hay
una API de informes. Todos los datos de rendimiento provienen de exportaciones CSV que
llegan por correo electrónico. La interfaz de pretargeting de AB en sí es funcional pero
dificulta ver el panorama completo entre configuraciones, o deshacer un cambio que salió
mal.

Cat-Scan cierra estas brechas:

- **Reconstruye los informes a partir de exportaciones CSV** (carga manual o ingesta
  automática de Gmail), deduplicando en la importación para que el reprocesamiento nunca
  cuente dos veces.
- Muestra el **embudo RTB completo**, desde el QPS sin procesar pasando por pujas,
  victorias, impresiones, clics y gasto, desglosado por cualquier dimensión: geografía,
  editor, tamaño de anuncio, creatividad, configuración.
- Proporciona **gestión segura de pretargeting** con historial, cambios por etapas,
  vista previa de simulación y reversión con un solo clic.
- Ejecuta un **optimizador** que puntúa segmentos y propone cambios de configuración,
  con protecciones de workflow (seguro / equilibrado / agresivo) para que ningún cambio
  entre en producción sin revisión.

### Para quién es este manual

Este manual tiene dos pistas porque Cat-Scan sirve a dos roles muy diferentes:

**Compradores de medios y gestores de campañas** usan Cat-Scan para entender a dónde va
su presupuesto, encontrar desperdicio, gestionar creatividades, ajustar pretargeting y
aprobar propuestas de optimización. Piensan en CPM, tasas de ganancia y ROAS. Sus
capítulos se centran en lo que muestra la interfaz, qué significan los números y qué
acciones tomar.

**DevOps e ingenieros de plataforma** usan Cat-Scan para desplegar, monitorear y
solucionar problemas del sistema. Piensan en contenedores, endpoints de salud y planes
de consulta. Sus capítulos se centran en arquitectura, pipelines de despliegue,
operaciones de base de datos y runbooks de incidentes.

Ambas pistas comparten una base común (primeros pasos, glosario) y los capítulos se
referencian mutuamente donde los flujos de trabajo se superponen. Un comprador de medios
que reporta "la frescura de datos está rota" y un ingeniero DevOps que depura la consulta
detrás de ello deberían poder señalar la misma entrada del glosario y entenderse
mutuamente.

---

## Cómo leer este manual

- **Parte 0** es para todos. Comience aquí.
- **Parte I** es la pista del comprador de medios. Si trabaja en campañas, optimización
  o compra, este es su camino.
- **Parte II** es la pista de DevOps. Si despliega, monitorea o administra Cat-Scan,
  este es su camino.
- **Parte III** es referencia compartida: glosario, preguntas frecuentes e índice de la API.

No necesita leer de forma lineal. Cada capítulo es autónomo. Siga los enlaces que
correspondan a su rol.

---

## Tabla de Contenidos

### Parte 0: Primeros Pasos

Todos leen esto.

- [Capítulo 0: ¿Qué es Cat-Scan?](00-what-is-cat-scan.md)
  Qué hace la plataforma, para quién es y los conceptos clave que necesita antes de
  cualquier otra cosa: seats, QPS, pretargeting, el embudo RTB.

- [Capítulo 1: Inicio de Sesión](01-logging-in.md)
  Métodos de autenticación (Google OAuth, cuentas locales), la página de inicio de sesión,
  qué hacer cuando el inicio de sesión falla y cómo funciona el selector de seats.

- [Capítulo 2: Navegando el Dashboard](02-navigating-the-dashboard.md)
  La barra lateral, cambio de seat, selector de idioma, la lista de verificación de
  configuración para cuentas nuevas y cómo están organizadas las páginas.

### Parte I: Pista del Comprador de Medios

Para compradores de medios, gestores de campañas e ingenieros de optimización.

- [Capítulo 3: Comprendiendo Su Embudo de QPS](03-qps-funnel.md)
  La página principal. Cómo leer el desglose del embudo: impresiones, pujas, victorias,
  gasto, tasa de ganancia, CTR, CPM. Qué significa "desperdicio" en términos concretos.
  Tarjetas de configuración y qué controlan sus campos.

- [Capítulo 4: Análisis del Desperdicio por Dimensión](04-analyzing-waste.md)
  Las tres vistas de análisis de desperdicio y cuándo usar cada una:
  - **Geográfico** (`/qps/geo`): qué países y ciudades consumen QPS sin
    convertir.
  - **Editor** (`/qps/publisher`): qué dominios y aplicaciones tienen bajo
    rendimiento.
  - **Tamaño** (`/qps/size`): qué tamaños de anuncios reciben tráfico pero no tienen
    creatividades compatibles. Google envía ~400 tamaños diferentes; la mayoría son
    irrelevantes para anuncios de display de tamaño fijo.

- [Capítulo 5: Gestión de Creatividades](05-managing-creatives.md)
  La galería de creatividades (`/creatives`): navegación por formato, filtrado por
  nivel de rendimiento, búsqueda por ID. Miniaturas, insignias de formato, diagnósticos
  de destino. Agrupación de campañas (`/campaigns`): arrastrar y soltar, agrupación
  automática por IA, el grupo de no asignadas.

- [Capítulo 6: Configuración de Pretargeting](06-pretargeting.md)
  Qué controla una configuración de pretargeting (geografías, tamaños, formatos,
  plataformas, QPS máximo). Cómo leer una tarjeta de configuración. Aplicar cambios con
  vista previa de simulación. La línea de tiempo del historial de cambios (`/history`).
  Reversión: cómo funciona, por qué existe y cuándo usarla.

- [Capítulo 7: El Optimizador (BYOM)](07-optimizer.md)
  Traiga Su Propio Modelo: registrar un endpoint de puntuación externo, validarlo,
  activarlo. El ciclo de vida puntuar-proponer-aprobar-aplicar. Presets de workflow:
  seguro, equilibrado, agresivo. Economía: CPM efectivo, línea base de costo de
  alojamiento, resumen de eficiencia. Cómo luce una propuesta y cómo evaluarla.

- [Capítulo 8: Conversiones y Atribución](08-conversions.md)
  Conectar una fuente de conversiones. Integración de píxel. Configuración de webhooks:
  firmas HMAC, secretos compartidos, limitación de tasa. Verificaciones de preparación.
  Estadísticas de ingesta. Qué significa "salud de conversiones" y cómo leer la página
  de estado de seguridad.

- [Capítulo 9: Importación de Datos](09-data-import.md)
  Cómo entran los datos a Cat-Scan y por qué esto importa. Carga manual de CSV
  (`/import`): arrastrar y soltar, mapeo de columnas, validación, carga fragmentada para
  archivos grandes. Importación automática de Gmail: cómo funciona, cómo verificar el
  estado, qué sucede cuando falla. La cuadrícula de frescura de datos: qué significa
  "importado" vs. "faltante" por fecha y tipo de informe. Garantías de deduplicación.

- [Capítulo 10: Lectura de Sus Informes](10-reading-reports.md)
  Estadísticas de gasto, paneles de rendimiento de configuración, métricas de eficiencia
  de endpoints. Cómo interpretar tendencias. Qué muestra el desglose diario. Comparaciones
  de snapshots: antes y después de un cambio de pretargeting.

### Parte II: Pista de DevOps

Para ingenieros de plataforma, SREs y administradores de sistemas.

- [Capítulo 11: Descripción General de la Arquitectura](11-architecture.md)
  Topología del sistema: backend FastAPI, frontend Next.js 14, Postgres (Cloud SQL),
  BigQuery. Por qué existen ambas bases de datos (costo, latencia, pre-agregación,
  gestión de conexiones). Disposición de contenedores: api, dashboard, oauth2-proxy,
  cloudsql-proxy, nginx. La cadena de confianza de autenticación: OAuth2 Proxy establece
  `X-Email`, nginx lo pasa, la API confía en él.

- [Capítulo 12: Despliegue](12-deployment.md)
  Pipeline CI/CD: GitHub Actions `build-and-push.yml` construye imágenes al hacer push;
  `deploy.yml` solo se ejecuta manualmente (con confirmación `DEPLOY`). Etiquetas de
  imagen de Artifact Registry (`sha-XXXXXXX`). La secuencia de despliegue: git pull en
  la VM, docker compose pull, recrear, podar. Verificación post-despliegue: health check,
  verificación de contratos. Por qué el auto-deploy está deshabilitado (incidente de
  enero 2026). Cómo verificar un despliegue: `curl /api/health | jq .git_sha`.

- [Capítulo 13: Monitoreo de Salud y Diagnósticos](13-health-monitoring.md)
  Endpoints de salud: `/api/health` (disponibilidad), `/system/data-health` (completitud
  de datos). La página de Estado del Sistema (`/settings/system`): Python, Node, FFmpeg,
  base de datos, disco, miniaturas. Scripts de salud en tiempo de ejecución:
  `diagnose_v1_buyer_report_coverage.sh`,
  `run_v1_runtime_health_strict_dispatch.sh`. Autenticación canary:
  `CATSCAN_CANARY_EMAIL`, `CATSCAN_BEARER_TOKEN`. Workflows CI:
  `v1-runtime-health-strict.yml` y qué significan PASS/FAIL/BLOCKED.

- [Capítulo 14: Operaciones de Base de Datos](14-database.md)
  Producción solo con Postgres. Cloud SQL vía contenedor proxy. Tablas clave y su
  escala: `rtb_daily` (~84M filas), `rtb_bidstream` (~21M filas), `rtb_quality`,
  `rtb_bid_filtering`. Índices críticos: `(buyer_account_id, metric_date
  DESC)`. Modelo de conexión: por solicitud (sin pool), `run_in_executor` para async.
  Timeouts de sentencias (`SET LOCAL statement_timeout`). Configuración de retención de
  datos. El rol de BigQuery: almacén batch para datos crudos; Postgres sirve datos
  pre-agregados a la aplicación.

- [Capítulo 15: Runbook de Resolución de Problemas](15-troubleshooting.md)
  Patrones de fallo conocidos y cómo resolverlos:
  - **Bucle de inicio de sesión**: Cloud SQL Proxy caído, `_get_or_create_oauth2_user`
    falla silenciosamente, `/auth/check` devuelve `{authenticated:false}`, bucle de
    redirección del frontend. Corrección de tres capas. Cómo detectar: contador de
    redirecciones en el navegador, 503 de `/auth/check`.
  - **Timeout de frescura de datos**: Tablas grandes haciendo escaneos secuenciales en
    lugar de usar índices. Síntomas: `/uploads/data-freshness` expira o devuelve 500.
    Diagnóstico: `pg_stat_activity`, `EXPLAIN ANALYZE`. Patrón de solución:
    generate_series + EXISTS.
  - **Fallo de importación de Gmail**: `/gmail/status` muestra error. Verifique el
    contenedor Cloud SQL Proxy. Verifique el conteo de no leídos.
  - **Orden de reinicio de contenedores**: `cloudsql-proxy` debe estar en buen estado
    antes de que `api` arranque. Señales de orden incorrecto: conexión rechazada en los
    registros de la API.

- [Capítulo 16: Administración de Usuarios y Permisos](16-user-admin.md)
  El panel de administración (`/admin`): creación de usuarios (locales y pre-creación
  OAuth), gestión de roles, permisos por seat. Cuentas de servicio: carga del JSON de
  credenciales GCP, qué desbloquea (descubrimiento de seats, sincronización de
  pretargeting). Usuarios restringidos: qué ven y qué se oculta. El registro de
  auditoría: qué acciones se rastrean, cómo filtrar, retención.

- [Capítulo 17: Integraciones](17-integrations.md)
  Cuentas de servicio GCP y conexión de proyectos. API de Google Authorized Buyers:
  descubrimiento de seats, sincronización de configuraciones de pretargeting,
  sincronización de endpoints RTB. Integración de Gmail: OAuth2 para ingesta automática
  de informes. Proveedores de IA de lenguaje: Gemini, Claude, Grok (para detección de
  idioma de creatividades y alertas de discrepancia). Webhooks de conversiones: registro
  de endpoints, verificación HMAC, limitación de tasa, monitoreo de frescura.

### Parte III: Referencia

Compartida por ambas pistas.

- [Glosario](glossary.md)
  Cada término en dos perspectivas. Columna del comprador de medios: "pretargeting" es
  "las reglas que controlan qué solicitudes de puja llegan a su bidder". Columna DevOps:
  "pretargeting" es "una entidad mutable sincronizada desde la API de AB, almacenada en
  `pretargeting_configs`, expuesta vía `/settings/pretargeting`". Ambos necesitan la
  misma palabra; ninguno usa la definición del otro.

- [Preguntas Frecuentes](faq.md)
  Etiquetadas por persona. Preguntas que hace un comprador de medios ("¿Por qué mi
  cobertura está al 74%?") junto a preguntas que hace un ingeniero DevOps ("¿Por qué
  falló la compuerta estricta de salud en tiempo de ejecución?"). Las respuestas
  enlazan al capítulo relevante.

- [Referencia Rápida de la API](api-reference.md)
  Los más de 118 endpoints agrupados por dominio: core, seats, creatividades, campañas,
  analítica, configuración, administración, optimizador, conversiones, integraciones,
  cargas, snapshots, auth. Método, ruta, parámetros clave y qué devuelve. No sustituye
  la especificación OpenAPI en `/api/docs`, pero es un índice navegable.
