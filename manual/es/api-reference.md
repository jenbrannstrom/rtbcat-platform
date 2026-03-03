# Referencia Rápida de la API

Este es un índice navegable de los más de 118 endpoints de la API de Cat-Scan, agrupados por
dominio. Para los esquemas completos de solicitud/respuesta, consulte la documentación interactiva
OpenAPI en `https://scan.rtb.cat/api/docs`.

## Sistema / Core

| Método | Ruta | Propósito |
|--------|------|-----------|
| GET | `/health` | Verificación de disponibilidad (git_sha, versión) |
| GET | `/stats` | Estadísticas del sistema |
| GET | `/sizes` | Tamaños de anuncios disponibles |
| GET | `/system/status` | Estado del servidor (Python, Node, FFmpeg, BD, disco) |
| GET | `/system/data-health` | Completitud de datos por comprador |
| GET | `/system/ui-page-load-metrics` | Métricas de rendimiento del frontend |
| GET | `/geo/lookup` | Resolución de ID geográfico a nombre |
| GET | `/geo/search` | Búsqueda de países/ciudades |

## Auth

| Método | Ruta | Propósito |
|--------|------|-----------|
| GET | `/auth/check` | Verificar si la sesión actual está autenticada |
| POST | `/auth/logout` | Cerrar sesión |

## Seats

| Método | Ruta | Propósito |
|--------|------|-----------|
| GET | `/seats` | Listar seats de compradores |
| GET | `/seats/{buyer_id}` | Obtener un seat específico |
| PUT | `/seats/{buyer_id}` | Actualizar nombre visible del seat |
| POST | `/seats/populate` | Crear seats automáticamente a partir de datos |
| POST | `/seats/discover` | Descubrir seats desde la API de Google |
| POST | `/seats/{buyer_id}/sync` | Sincronizar un seat específico |
| POST | `/seats/sync-all` | Sincronización completa (todos los seats) |
| POST | `/seats/collect-creatives` | Recopilar datos de creatividades |

## Creatividades

| Método | Ruta | Propósito |
|--------|------|-----------|
| GET | `/creatives` | Listar creatividades (con filtros) |
| GET | `/creatives/paginated` | Lista paginada de creatividades |
| GET | `/creatives/{id}` | Detalles de una creatividad |
| GET | `/creatives/{id}/live` | Datos en vivo de la creatividad (con caché) |
| GET | `/creatives/{id}/destination-diagnostics` | Estado de la URL de destino |
| GET | `/creatives/{id}/countries` | Desglose de rendimiento por país |
| GET | `/creatives/{id}/geo-linguistic` | Análisis geolingüístico |
| POST | `/creatives/{id}/detect-language` | Detección automática de idioma |
| PUT | `/creatives/{id}/language` | Anulación manual de idioma |
| GET | `/creatives/thumbnail-status` | Estado de miniaturas en lote |
| POST | `/creatives/thumbnails/batch` | Generar miniaturas faltantes |

## Campañas

| Método | Ruta | Propósito |
|--------|------|-----------|
| GET | `/campaigns` | Listar campañas |
| GET | `/campaigns/{id}` | Detalles de la campaña |
| GET | `/campaigns/ai` | Clusters generados por IA |
| GET | `/campaigns/ai/{id}` | Detalles de campaña IA |
| PUT | `/campaigns/ai/{id}` | Actualizar campaña |
| DELETE | `/campaigns/ai/{id}` | Eliminar campaña |
| GET | `/campaigns/ai/{id}/creatives` | Creatividades de la campaña |
| DELETE | `/campaigns/ai/{id}/creatives/{creative_id}` | Eliminar creatividad de la campaña |
| POST | `/campaigns/auto-cluster` | Agrupación automática por IA |
| GET | `/campaigns/ai/{id}/performance` | Rendimiento de la campaña |
| GET | `/campaigns/ai/{id}/daily-trend` | Datos de tendencia de la campaña |

## Analítica

| Método | Ruta | Propósito |
|--------|------|-----------|
| GET | `/analytics/waste-report` | Métricas generales de desperdicio |
| GET | `/analytics/size-coverage` | Cobertura de segmentación por tamaño |
| GET | `/analytics/rtb-funnel` | Desglose del embudo RTB |
| GET | `/analytics/rtb-funnel/configs` | Embudo a nivel de configuración |
| GET | `/analytics/endpoint-efficiency` | Eficiencia de QPS por endpoint |
| GET | `/analytics/spend-stats` | Estadísticas de gasto |
| GET | `/analytics/config-performance` | Rendimiento de configuración a lo largo del tiempo |
| GET | `/analytics/config-performance/breakdown` | Desglose por campo de configuración |
| GET | `/analytics/qps-recommendations` | Recomendaciones de IA |
| GET | `/analytics/performance/batch` | Rendimiento de creatividades en lote |
| GET | `/analytics/performance/{creative_id}` | Rendimiento de una creatividad individual |
| GET | `/analytics/publishers` | Métricas de dominios de editores |
| GET | `/analytics/publishers/search` | Buscar editores |
| GET | `/analytics/languages` | Rendimiento por idioma |
| GET | `/analytics/languages/multi` | Análisis de múltiples idiomas |
| GET | `/analytics/geo-performance` | Rendimiento geográfico |
| GET | `/analytics/geo-performance/multi` | Análisis de múltiples geografías |
| POST | `/analytics/import` | Importación de CSV |
| POST | `/analytics/mock-traffic` | Generar datos de prueba |

## Configuración / Pretargeting

| Método | Ruta | Propósito |
|--------|------|-----------|
| GET | `/settings/rtb-endpoints` | Endpoints RTB del bidder |
| POST | `/settings/rtb-endpoints/sync` | Sincronizar datos de endpoints |
| GET | `/settings/pretargeting-configs` | Listar configuraciones de pretargeting |
| GET | `/settings/pretargeting-configs/{id}` | Detalles de la configuración |
| GET | `/settings/pretargeting-history` | Historial de cambios de configuración |
| POST | `/settings/pretargeting-configs/sync` | Sincronizar configuraciones desde Google |
| POST | `/settings/pretargeting-configs/{id}/apply` | Aplicar un cambio de configuración |
| POST | `/settings/pretargeting-configs/apply-all` | Aplicar todos los cambios pendientes |
| PUT | `/settings/pretargeting-configs/{id}` | Actualización masiva de configuración |

## Cargas

| Método | Ruta | Propósito |
|--------|------|-----------|
| GET | `/uploads/tracking` | Resumen diario de cargas |
| GET | `/uploads/import-matrix` | Estado de importación por tipo de informe |
| GET | `/uploads/data-freshness` | Cuadrícula de frescura de datos (fecha x tipo) |
| GET | `/uploads/history` | Historial de importaciones |

## Optimizador

| Método | Ruta | Propósito |
|--------|------|-----------|
| GET | `/optimizer/models` | Listar modelos BYOM |
| POST | `/optimizer/models` | Registrar modelo |
| PUT | `/optimizer/models/{id}` | Actualizar modelo |
| POST | `/optimizer/models/{id}/activate` | Activar modelo |
| POST | `/optimizer/models/{id}/deactivate` | Desactivar modelo |
| POST | `/optimizer/models/{id}/validate` | Probar endpoint del modelo |
| POST | `/optimizer/score-and-propose` | Generar propuestas |
| GET | `/optimizer/proposals` | Listar propuestas activas |
| GET | `/optimizer/proposals/history` | Historial de propuestas |
| POST | `/optimizer/proposals/{id}/approve` | Aprobar propuesta |
| POST | `/optimizer/proposals/{id}/apply` | Aplicar propuesta |
| POST | `/optimizer/proposals/{id}/sync-status` | Verificar estado de aplicación |
| GET | `/optimizer/segment-scores` | Puntuaciones a nivel de segmento |
| GET | `/optimizer/economics/efficiency` | Resumen de eficiencia |
| GET | `/optimizer/economics/effective-cpm` | Análisis de CPM |
| GET | `/optimizer/setup` | Configuración del optimizador |
| PUT | `/optimizer/setup` | Actualizar configuración del optimizador |

## Conversiones

| Método | Ruta | Propósito |
|--------|------|-----------|
| GET | `/conversions/health` | Estado de ingesta y agregación |
| GET | `/conversions/readiness` | Verificación de preparación de fuentes |
| GET | `/conversions/ingestion-stats` | Conteo de eventos por fuente/período |
| GET | `/conversions/security/status` | Estado de seguridad de webhooks |
| GET | `/conversions/pixel` | Endpoint de seguimiento por píxel |

## Snapshots

| Método | Ruta | Propósito |
|--------|------|-----------|
| GET | `/snapshots` | Listar snapshots de configuración |
| POST | `/snapshots/rollback` | Restaurar un snapshot (con simulación) |

## Integraciones

| Método | Ruta | Propósito |
|--------|------|-----------|
| POST | `/integrations/credentials` | Subir JSON de cuenta de servicio GCP |
| GET | `/integrations/service-accounts` | Listar cuentas de servicio |
| DELETE | `/integrations/service-accounts/{id}` | Eliminar cuenta de servicio |
| GET | `/integrations/language-ai/config` | Estado del proveedor de IA |
| PUT | `/integrations/language-ai/config` | Configurar proveedor de IA |
| GET | `/integrations/gmail/status` | Estado de importación de Gmail |
| POST | `/integrations/gmail/import/start` | Iniciar importación manual |
| POST | `/integrations/gmail/import/stop` | Detener tarea de importación |
| GET | `/integrations/gmail/import/history` | Historial de importaciones |
| GET | `/integrations/gcp/project-status` | Estado del proyecto GCP |
| POST | `/integrations/gcp/validate` | Probar conexión GCP |

## Administración

| Método | Ruta | Propósito |
|--------|------|-----------|
| GET | `/admin/users` | Listar usuarios |
| POST | `/admin/users` | Crear usuario |
| GET | `/admin/users/{id}` | Detalles del usuario |
| PUT | `/admin/users/{id}` | Actualizar usuario |
| POST | `/admin/users/{id}/deactivate` | Desactivar usuario |
| GET | `/admin/users/{id}/permissions` | Permisos globales del usuario |
| GET | `/admin/users/{id}/seat-permissions` | Permisos por seat del usuario |
| POST | `/admin/users/{id}/seat-permissions` | Otorgar acceso a un seat |
| DELETE | `/admin/users/{id}/seat-permissions/{buyer_id}` | Revocar acceso a un seat |
| POST | `/admin/users/{id}/permissions` | Otorgar permiso global |
| DELETE | `/admin/users/{id}/permissions/{sa_id}` | Revocar permiso global |
| GET | `/admin/audit-log` | Registro de auditoría |
| GET | `/admin/stats` | Estadísticas del panel de administración |
| GET | `/admin/settings` | Configuración del sistema |
| PUT | `/admin/settings/{key}` | Actualizar configuración del sistema |
