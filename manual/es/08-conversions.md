# Capítulo 8: Conversiones y Atribución

*Audiencia: compradores de medios, gestores de campañas*

El seguimiento de conversiones permite a Cat-Scan medir lo que sucede después de una impresión:
¿el usuario realizó una acción valiosa? Estos datos alimentan la puntuación del optimizador
y te ayudan a evaluar el rendimiento real de la campaña.

## Fuentes de conversión

Cat-Scan soporta dos métodos de integración:

### Pixel

Un pixel de seguimiento se activa en tu página de conversión (p. ej., confirmación de compra).

- Endpoint: `/api/conversions/pixel`
- Parámetros: `buyer_id`, `source_type=pixel`, `event_name`, `event_value`,
  `currency`, `event_ts`
- No requiere configuración del lado del servidor más allá de colocar el pixel en tu página.

### Webhook

Tu servidor envía eventos de conversión al endpoint de webhook de Cat-Scan.

- Más fiable que los pixels (sin bloqueadores de anuncios, sin dependencias del lado del cliente).
- Requiere integración del lado del servidor.
- Soporta verificación de firma HMAC para mayor seguridad.

## Seguridad de webhooks

Cat-Scan proporciona seguridad por capas para webhooks:

| Característica | Qué hace |
|---------------|----------|
| **Verificación HMAC** | Cada solicitud de webhook se firma con un secreto compartido. Cat-Scan rechaza las solicitudes sin firma o con firma incorrecta. |
| **Limitación de tasa** | Previene el abuso limitando las solicitudes por ventana de tiempo. |
| **Monitoreo de frescura** | Alerta si los eventos de webhook dejan de llegar (detección de obsolescencia). |

Configura la seguridad del webhook en `/settings/system` > Conversion Health.

## Verificación de preparación

Antes de confiar en los datos de conversión, verifica la preparación:

1. Ve a `/settings/system` o a la lista de verificación de configuración.
2. Comprueba **Conversion Readiness**: muestra si hay una fuente conectada y
   entregando eventos dentro de la ventana de frescura esperada.
3. Comprueba **Ingestion Stats**: conteo de eventos por tipo de fuente y período de tiempo.

## Salud de conversiones

El panel de Conversion Health muestra:

- Estado de ingesta (recibiendo eventos o no)
- Estado de agregación (eventos siendo procesados en métricas)
- Marca de tiempo del último evento
- Conteo de errores, si los hay

## Relacionado

- [El Optimizador](07-optimizer.md): los datos de conversión mejoran la precisión de la puntuación
- [Importación de datos](09-data-import.md): otra vía de entrada de datos
- Para DevOps: configuración y resolución de problemas del endpoint de webhook, consulta
  [Integraciones](17-integrations.md).
