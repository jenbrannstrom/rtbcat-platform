# Capítulo 17: Integraciones

*Audiencia: DevOps, ingenieros de plataforma*

## Cuentas de servicio de GCP

Cat-Scan necesita credenciales de cuenta de servicio de GCP para interactuar con las APIs de Google.

**Configuración:**
1. Crear una cuenta de servicio en su proyecto de GCP con acceso a la API de Authorized Buyers.
2. Descargar el archivo de clave JSON.
3. Subirlo en `/settings/accounts` > pestaña API Connection.
4. Validar la conexión: Cat-Scan comprueba la accesibilidad y los permisos.

**Qué habilita:**
- Descubrimiento de asientos (`discoverSeats`)
- Sincronización de configuración de pretargeting (`syncPretargetingConfigs`)
- Sincronización de endpoints RTB (`syncRTBEndpoints`)
- Recopilación de creativos (`collectCreatives`)

**Estado del proyecto:**
Verifique la salud del proyecto de GCP en `/settings/accounts` o a través de
`GET /integrations/gcp/project-status`. Esto verifica que la cuenta de servicio sea válida, que el proyecto sea accesible y que las APIs requeridas estén habilitadas.

## API de Google Authorized Buyers

Cat-Scan sincroniza datos desde la API de Authorized Buyers:

| Operación | Qué obtiene | Cuándo ejecutarla |
|-----------|-------------|-------------------|
| **Descubrimiento de asientos** | Cuentas de comprador vinculadas a la cuenta de servicio | Configuración inicial, cuando se agregan nuevos asientos |
| **Sincronización de pretargeting** | Estado actual de configuración de pretargeting desde Google | Después de cambios externos en la interfaz de AB |
| **Sincronización de endpoints RTB** | URLs de endpoints del bidder y estado | Configuración inicial, después de cambios en endpoints |
| **Sincronización de creativos** | Metadatos de creativos (formatos, tamaños, destinos) | Periódicamente, a través de "Sync All" en la barra lateral |

## Integración con Gmail

Google Authorized Buyers envía informes CSV diarios por correo electrónico. Cat-Scan puede ingerirlos automáticamente.

**Configuración:**
1. Ir a `/settings/accounts` > pestaña Gmail Reports.
2. Autorizar a Cat-Scan para acceder a la cuenta de Gmail que recibe los informes de AB.
3. Cat-Scan consultará periódicamente los nuevos emails de informes e importará los CSV adjuntos.

**Monitoreo:**
- `GET /gmail/status`: estado actual, conteo de no leídos, último motivo
- `POST /gmail/import/start`: activar manualmente un ciclo de importación
- `POST /gmail/import/stop`: detener una importación en ejecución
- `GET /gmail/import/history`: registros de importaciones anteriores

**Solución de problemas:**
- Conteo alto de no leídos (30+): backlog de importación, puede necesitar intervención manual
- `last_reason: error`: verificar logs, puede necesitar reautorización
- Consulte [Solución de problemas](15-troubleshooting.md) para pasos detallados.

## Proveedores de IA de lenguaje

Cat-Scan utiliza IA para detectar el idioma de los creativos y señalar discrepancias geolingüísticas (por ejemplo, un anuncio en español en un mercado árabe).

**Proveedores soportados:**

| Proveedor | Configuración |
|-----------|---------------|
| Gemini | Clave de API en `/settings/accounts` |
| Claude | Clave de API en `/settings/accounts` |
| Grok | Clave de API en `/settings/accounts` |

Configure a través de `GET/PUT /integrations/language-ai/config`. Solo un proveedor necesita estar activo.

## Webhooks de conversiones

Los sistemas externos envían eventos de conversión a Cat-Scan a través de webhooks.

**Capas de seguridad:**

| Capa | Propósito | Configuración |
|------|-----------|---------------|
| **Verificación HMAC** | Garantiza que las solicitudes sean auténticas (firmadas con secreto compartido) | Secreto compartido configurado en los ajustes del webhook |
| **Limitación de tasa** | Previene abuso | Automática, con umbrales configurables |
| **Monitoreo de frescura** | Alerta cuando los eventos dejan de llegar | Ventana de obsolescencia configurable |

**Monitoreo:**
- `GET /conversions/security/status`: estado de HMAC, estado de limitación de tasa, estado de frescura
- `GET /conversions/health`: salud general de ingestión y agregación
- `GET /conversions/readiness`: si los datos de conversión son lo suficientemente frescos como para ser confiables

## Relacionado

- [Visión general de la arquitectura](11-architecture.md): dónde encajan las integraciones
- [Administración de usuarios](16-user-admin.md): gestión de cuentas de servicio
- Para media buyers: [Conversiones y atribución](08-conversions.md) cubre la configuración de conversiones orientada al comprador.
