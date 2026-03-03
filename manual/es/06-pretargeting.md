# Capítulo 6: Configuración de Pretargeting

*Audiencia: compradores de medios, gestores de campañas*

Las configuraciones de pretargeting son tu principal herramienta para controlar qué envía Google
a tu bidder. Este capítulo explica cómo gestionarlas de forma segura en Cat-Scan.

## Qué controla una configuración de pretargeting

Cada configuración es un conjunto de reglas que le indica a Google: "envíame solo las
solicitudes de puja que cumplan estos criterios". Dispones de **10 configuraciones por seat**.

| Campo | Qué filtra |
|-------|------------|
| **Estado** | Activo (recibiendo tráfico) o Suspendido (en pausa). |
| **Max QPS** | Límite superior de consultas por segundo que acepta esta configuración. |
| **Geos (incluidos)** | Países, regiones o ciudades de los que se recibirá tráfico. |
| **Geos (excluidos)** | Geografías a bloquear aunque coincidan con las inclusiones. |
| **Tamaños (incluidos)** | Tamaños de anuncio a aceptar (p. ej., 300x250, 728x90). |
| **Formatos** | Tipos de creativo: VIDEO, DISPLAY_IMAGE, DISPLAY_HTML, NATIVE. |
| **Plataformas** | Tipos de dispositivo: DESKTOP, MOBILE_APP, MOBILE_WEB, CONNECTED_TV. |
| **Editores** | Listas de permitidos/bloqueados para dominios o aplicaciones de editores específicos. |

## Lectura de una tarjeta de configuración

En la página de inicio y en la sección de ajustes, cada configuración aparece como una tarjeta
que muestra su estado actual.

![Tarjetas de configuración de pretargeting mostrando estados activo y en pausa](images/screenshot-pretargeting-configs.png)

Aspectos clave a observar:

- **Activo + max QPS alto + geos amplios** = esta configuración está captando mucho
  tráfico. Si además genera mucho desperdicio, es tu principal objetivo de optimización.
- **Suspendido** = no recibe tráfico. Útil para preparar cambios antes de
  activarlos.
- **Tamaños incluidos: (todos)** = acepta todos los tamaños de anuncio que envía Google. Para
  display de tamaño fijo, esto es casi seguro un desperdicio.

## Realizar cambios

### El flujo de prueba en seco (dry-run)

1. Navega a la configuración que deseas modificar (página de inicio o
   `/settings/system`).
2. Selecciona el campo a modificar (p. ej., geos excluidos, tamaños incluidos).
3. Introduce los nuevos valores.
4. Haz clic en **Preview** (prueba en seco). Cat-Scan te muestra exactamente qué cambiará
   sin aplicarlo.
5. Si la vista previa es correcta, haz clic en **Apply**.
6. El cambio se registra en el historial con una marca de tiempo y tu identidad.

### Editor de permitidos/bloqueados de editores

Para el bloqueo a nivel de editor, Cat-Scan proporciona un editor dedicado por configuración.
Puedes:
- Buscar editores por nombre de dominio
- Bloquear dominios o aplicaciones individuales
- Permitir dominios específicos que anulen bloqueos más amplios
- Aplicar cambios de forma masiva

Esto es significativamente más sencillo que gestionar editores a través de la
interfaz de Authorized Buyers.

## Historial de cambios (`/history`)

Cada cambio de pretargeting se registra en una línea de tiempo en `/history`.

![Línea de tiempo del historial de cambios con filtros y exportación](images/screenshot-change-history.png)

Para cada entrada se muestra:
- **Cuándo**: marca de tiempo del cambio
- **Quién**: el usuario que lo realizó
- **Qué**: nombre del campo, valor anterior, valor nuevo
- **Tipo**: la clase de cambio (agregar, eliminar, actualizar)

## Reversión

Si un cambio causa problemas (p. ej., el desperdicio aumenta, la tasa de ganancia cae), puedes
revertirlo:

1. Ve a `/history`.
2. Busca el cambio que deseas deshacer.
3. Haz clic en **Preview rollback**. Esto muestra una prueba en seco de la reversión al
   estado anterior.
4. Opcionalmente, añade un motivo para la reversión.
5. Haz clic en **Confirm rollback**.

La reversión en sí se registra como una nueva entrada en el historial, de modo que cuentas
con un rastro de auditoría completo.

## Relacionado

- [Análisis de desperdicio por dimensión](04-analyzing-waste.md): descubre qué cambiar
- [El Optimizador](07-optimizer.md): sugerencias automatizadas para cambios de configuración
- Para DevOps: las instantáneas de configuración se almacenan como entidades versionadas. Consulta
  [Operaciones de base de datos](14-database.md).
