# Capítulo 5: Gestión de creatividades

*Audiencia: compradores de medios, gestores de campañas*

## Galería de creatividades (`/creatives`)

La galería muestra todas las creatividades asociadas al seat seleccionado.

![Galería de creatividades con insignias de formato y niveles de rendimiento](images/screenshot-creatives.png)

### Qué ves

Cada creatividad aparece como una tarjeta con:

- **Miniatura**: vista previa generada automáticamente del anuncio (fotograma de
  video o captura de pantalla de display)
- **Insignia de formato**: VIDEO, DISPLAY_IMAGE, DISPLAY_HTML o NATIVE
- **Creative ID**: el identificador de creatividad de Authorized Buyers
- **Tamaño canónico**: el tamaño principal del anuncio (por ejemplo, 300x250, 728x90)
- **Nivel de rendimiento**: HIGH, MEDIUM, LOW o NO_DATA, basado en la
  clasificación por percentil de gasto dentro de tu seat

### Filtrado y búsqueda

- **Filtro de formato**: mostrar solo Video, Display Image, Display HTML o Native
- **Filtro de nivel de rendimiento**: aislar los de alto o bajo rendimiento
- **Búsqueda**: encontrar una creatividad por su ID
- **Selector de período**: 7, 14 o 30 días de datos de rendimiento

### Miniaturas

Las miniaturas se generan por lotes. Si ves imágenes de marcador de posición,
usa el botón de generación de miniaturas por lotes para encolar las que faltan.
El estado se muestra en la interfaz.

### Detalles de la creatividad

Haz clic en cualquier creatividad para abrir el modal de vista previa con:

- URL de destino y diagnósticos (¿es accesible la página de aterrizaje?)
- Detección de idioma (detección automática + opción de anulación manual)
- Desglose de rendimiento por país (en qué geos rinde esta creatividad)
- Informe geolingüístico (detección de desajuste entre idioma y geografía)

**La detección de desajuste lingüístico** es una funcionalidad distintiva:
Cat-Scan puede señalar casos como un anuncio en español publicándose en mercados
árabes, o precios en AED dirigidos a usuarios en India. Esto utiliza tu proveedor
de IA configurado (Gemini, Claude o Grok).

## Agrupación de campañas (`/campaigns`)

Las campañas te permiten organizar creatividades en grupos lógicos.

### Vistas

- **Vista de cuadrícula**: tarjetas de campaña con conteo de creatividades, gasto, impresiones, clics
- **Vista de lista**: formato de tabla compacto

### Acciones

- **Arrastrar y soltar**: mover creatividades entre campañas o al grupo sin asignar
- **Crear campaña**: nombrar un nuevo grupo y arrastrar creatividades a él
- **Agrupación automática con IA**: dejar que Cat-Scan sugiera agrupaciones
  basadas en atributos de las creatividades (formato, tamaño, destino, idioma)
- **Eliminar campaña**: elimina la agrupación (las creatividades vuelven al grupo sin asignar)

### Filtros

- **Ordenar por**: nombre, gasto, impresiones, clics, conteo de creatividades
- **Filtro de país**: mostrar solo campañas con creatividades activas en un geo
  específico
- **Filtro de problemas**: resaltar campañas con incidencias (desajustes, bajo
  rendimiento)

## Relacionado

- [Análisis de desperdicio por tamaño](04-analyzing-waste.md): el desperdicio por
  tamaño está directamente vinculado a las creatividades que tienes
- [Leer tus informes](10-reading-reports.md): rendimiento a nivel de campaña
