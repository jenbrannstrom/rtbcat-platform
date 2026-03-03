# Capítulo 9: Importación de Datos

*Audiencia: compradores de medios, gestores de campañas*

El análisis de Cat-Scan depende completamente de los datos de rendimiento de Google Authorized
Buyers. Dado que Google no proporciona una API de informes, todos los datos provienen de
exportaciones CSV. Este capítulo explica cómo introducir datos en Cat-Scan y cómo verificar
que están llegando.

## Por qué esto importa

Sin datos importados, Cat-Scan no tiene nada que analizar. El embudo, las vistas de desperdicio,
el rendimiento de creativos y el optimizador dependen de datos CSV actualizados. Si tus datos
están desactualizados, tus decisiones se basan en información antigua.

## Dos formas en que llegan los datos

### 1. Carga manual de CSV (`/import`)

Arrastra y suelta un archivo CSV exportado desde Google Authorized Buyers.

![Página de importación de datos con zona de carga y cuadrícula de frescura](images/screenshot-import.png)

**Flujo de trabajo:**

1. Exporta el informe desde tu cuenta de Google Authorized Buyers.
2. Ve a `/import` en Cat-Scan.
3. Arrastra el archivo a la zona de carga (o haz clic para examinar).
4. Cat-Scan **detecta automáticamente el tipo de informe** y muestra una vista previa:
   - Columnas requeridas vs. columnas encontradas
   - Cantidad de filas y rango de fechas
   - Errores de validación, si los hay
5. Revisa la vista previa. Si es necesario reasignar columnas, usa el editor de
   mapeo de columnas.
6. Haz clic en **Import**.
7. La barra de progreso muestra el estado de la carga. Los archivos de más de 5 MB se cargan
   en fragmentos automáticamente.
8. Los resultados muestran: filas importadas, duplicados omitidos, errores si los hay.

**Tipos de informe** detectados automáticamente:

| Tipo | Patrón de nombre CSV | Qué contiene |
|------|---------------------|--------------|
| bidsinauction | `catscan-report-*` | Rendimiento RTB diario: impresiones, pujas, ganados, gasto |
| quality | `catscan-report-*` (métricas de calidad) | Señales de calidad: visibilidad, fraude, seguridad de marca |
| pipeline-geo | `*-pipeline-geo-*` | Desglose geográfico del flujo de pujas |
| pipeline-publisher | `*-pipeline-publisher-*` | Desglose por dominio de editor |
| bid-filtering | `*-bid-filtering-*` | Razones y volúmenes del filtrado de pujas |

### 2. Importación automática desde Gmail

Cat-Scan puede ingerir automáticamente informes desde una cuenta de Gmail conectada.

- Google Authorized Buyers envía informes diarios por correo electrónico.
- La integración de Gmail de Cat-Scan lee estos correos e importa los archivos CSV
  adjuntos automáticamente.
- Verifica el estado en `/settings/accounts` > pestaña Gmail Reports, o a través de
  `/gmail/status` en la API.

**Para verificar que la importación de Gmail funciona:**
- Revisa el panel de Estado de Gmail: `last_reason` debería ser `running`.
- Revisa el conteo de `unread`: un gran número de correos no leídos puede indicar que la
  importación está atascada.
- Revisa el historial de importación en busca de entradas recientes.

## Cuadrícula de frescura de datos

La cuadrícula de frescura de datos (visible en `/import` y utilizada por la puerta de salud
en tiempo de ejecución) muestra una **matriz fecha x tipo de informe**:

```
              bidsinauction   quality   pipeline-geo   pipeline-publisher   bid-filtering
2026-03-02    imported        missing   imported       imported             imported
2026-03-01    imported        missing   imported       imported             imported
2026-02-28    imported        imported  imported       imported             imported
...
```

- **imported**: Cat-Scan tiene datos para esta fecha y tipo de informe.
- **missing**: no se encontraron datos. O bien el informe no se exportó, no fue
  recibido por Gmail, o la importación falló.

**Porcentaje de cobertura** resume qué tan completos están tus datos dentro de la
ventana de retrospectiva. La puerta de salud en tiempo de ejecución usa este dato para determinar
si el sistema está operativo.

## Deduplicación

Reimportar el mismo CSV (o que Gmail reprocese el mismo correo) **no**
duplica los datos. Cada fila se hashea y los duplicados se omiten al insertar.
Esto significa que siempre es seguro reimportar.

## Historial de importación

La tabla de historial de importación en `/import` muestra las últimas 20 importaciones:

- Marca de tiempo
- Nombre de archivo
- Cantidad de filas
- Origen de la importación (carga manual vs. gmail-auto)
- Estado (completo, fallido, duplicado)

## Resolución de problemas

| Problema | Qué verificar |
|----------|--------------|
| Celdas "Missing" en la cuadrícula de frescura | ¿Se exportó el informe desde Google en esa fecha? Revisa Gmail en busca del correo. |
| La importación falla con error de validación | Desajuste de columnas. Compara la tabla de columnas requeridas con tu CSV. |
| La importación de Gmail muestra "stopped" | Revisa `/settings/accounts` > pestaña Gmail. Puede ser necesario reiniciar o reautorizar. |
| Porcentaje de cobertura disminuyendo | Los informes llegan, pero para menos fechas de lo esperado. Verifica el calendario de exportación en Google AB. |

## Relacionado

- [Entender tu embudo de QPS](03-qps-funnel.md): depende de los datos importados
- [Lectura de informes](10-reading-reports.md): qué puedes hacer con los datos
  una vez importados
- Para DevOps: detalles internos de la consulta de frescura de datos y resolución de problemas, consulta
  [Operaciones de base de datos](14-database.md) y [Resolución de problemas](15-troubleshooting.md).
