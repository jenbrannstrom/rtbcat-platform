# Capítulo 7: El Optimizador (BYOM)

*Audiencia: compradores de medios, ingenieros de optimización*

El optimizador es el motor de optimización automatizada de Cat-Scan. "BYOM" significa
Bring Your Own Model (trae tu propio modelo): registras un endpoint externo de puntuación y
Cat-Scan lo utiliza para generar propuestas de cambio de configuración.

## Cómo funciona

```
  Score          Propose          Review          Apply
────────────> ────────────> ────────────> ────────────>
Your model     Cat-Scan       You (human)    Google AB
evaluates      generates      approve or     config is
segments       config         reject         updated
               changes
```

1. **Score**: Cat-Scan envía datos de segmentos a tu endpoint de modelo. El modelo
   devuelve una puntuación para cada segmento (geo, tamaño, editor).
2. **Propose**: Basándose en las puntuaciones, Cat-Scan genera cambios específicos de
   pretargeting (p. ej., "excluir estos 5 geos", "añadir estos 3 tamaños").
3. **Review**: Ves la propuesta con el impacto proyectado. Apruebas o rechazas.
4. **Apply**: Las propuestas aprobadas se aplican a la configuración de pretargeting en
   el lado de Google. El cambio se registra en el historial.

## Gestión de modelos

### Registrar un modelo

Ve a `/settings/system` y busca la sección del Optimizador.

1. Haz clic en **Register Model**.
2. Completa: nombre, tipo de modelo, URL del endpoint (tu servicio de puntuación).
3. El endpoint debe aceptar solicitudes POST con datos de segmentos y devolver
   resultados puntuados.
4. Guarda.

### Validar el endpoint

Antes de activar, prueba tu modelo:

1. Haz clic en **Validate endpoint** en la tarjeta del modelo.
2. Cat-Scan envía un payload de prueba a tu endpoint.
3. Los resultados muestran: tiempo de respuesta, validez del formato de respuesta, distribución de puntuaciones.
4. Corrige cualquier problema antes de activar.

### Activar y desactivar

- **Activar**: el modelo se convierte en el evaluador activo para este seat.
- **Desactivar**: el modelo deja de usarse, pero su configuración se
  conserva. Solo un modelo puede estar activo por seat a la vez.

## Presets de flujo de trabajo

Al ejecutar score-and-propose, eliges un preset:

| Preset | Comportamiento | Cuándo usarlo |
|--------|---------------|---------------|
| **Safe** | Solo propone cambios con alta confianza y bajo riesgo. Mejoras más pequeñas, menor probabilidad de errores. | Primera vez usando el optimizador, o cuentas conservadoras. |
| **Balanced** | Umbral de confianza moderado. Buen equilibrio entre impacto y seguridad. | Opción predeterminada para la mayoría de los usos. |
| **Aggressive** | Propone cambios más amplios con mayor impacto potencial. Mayor riesgo de sobre-optimización. | Usuarios experimentados que monitorean a diario y pueden revertir rápidamente. |

## Economía

El optimizador también rastrea la economía de la optimización:

- **Effective CPM**: lo que realmente pagas por cada mil impresiones,
  teniendo en cuenta el desperdicio.
- **Hosting cost baseline**: el costo de infraestructura de tu bidder, configurado en
  la configuración del optimizador. Se utiliza para calcular si el ahorro por reducción de QPS
  compensa el alojamiento.
- **Efficiency summary**: ratio global de QPS útil sobre QPS total.

Configura tu costo de alojamiento en `/settings/system` > Optimizer Setup.

## Revisión de propuestas

Cada propuesta muestra:
- **Puntuaciones de segmentos** que motivaron la recomendación
- **Cambios específicos** en los campos de pretargeting (adiciones, eliminaciones, actualizaciones)
- **Impacto proyectado** sobre QPS, ratio de desperdicio y gasto

Puedes:
- **Approve**: marca la propuesta como aceptada
- **Apply**: envía los cambios aprobados a Google
- **Reject**: descarta la propuesta
- **Check apply status**: verifica que los cambios se hayan aplicado del lado de Google

## Relacionado

- [Configuración de pretargeting](06-pretargeting.md): las configuraciones que el optimizador
  modifica
- [Conversiones y atribución](08-conversions.md): los datos de conversión alimentan
  la calidad de la puntuación
- [Lectura de informes](10-reading-reports.md): seguimiento del impacto del optimizador
