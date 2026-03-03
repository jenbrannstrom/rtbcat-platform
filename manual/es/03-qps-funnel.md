# Capítulo 3: Entender tu embudo de QPS

*Audiencia: compradores de medios, gestores de campañas*

Esta es la página de inicio de Cat-Scan (`/`). Todo comienza aquí.

## Qué ves

La página del QPS Waste Optimizer muestra tu embudo RTB (el recorrido desde la
solicitud de puja hasta el gasto) y resalta dónde se pierde volumen.

![Página de inicio del QPS Waste Optimizer](images/screenshot-qps-home.png)

### El embudo

| Etapa | Qué significa |
|-------|---------------|
| **QPS** | Las solicitudes de puja máximas por segundo que le pides a Google que envíe. Google regula el volumen real según el nivel de tu cuenta, por lo que normalmente recibes menos de tu límite. |
| **Bids** | Cuántas de esas solicitudes tu bidder decidió pujar. El resto fueron rechazadas (inventario inadecuado, sin creatividad compatible, precio por debajo del piso). |
| **Wins** | Subastas que tu bidder ganó. Solo pagas por las victorias. |
| **Impressions** | Anuncios realmente servidos a los usuarios tras ganar la subasta. |
| **Clicks** | Interacciones de los usuarios con tus anuncios servidos. |
| **Spend** | Dinero total gastado en impresiones ganadas. |

La brecha entre cada etapa es donde existe oportunidad de optimización. Una gran
caída entre QPS y Bids significa que tu bidder rechaza la mayor parte de lo que
Google le envía: desperdicio clásico que el pretargeting puede corregir.

### Métricas clave

- **Win rate**: Wins / Bids. Qué tan competitivas son tus pujas.
- **CTR**: Clicks / Impressions. Qué tan atractivas son tus creatividades.
- **CPM**: Costo por mil impresiones. Lo que pagas por visibilidad.
- **Waste ratio**: (QPS - Bids) / QPS. La fracción de tráfico que no puedes utilizar.

### Tarjetas de configuración de pretargeting

Debajo del embudo verás tarjetas para cada una de tus configuraciones de
pretargeting (hasta 10 por seat). Cada tarjeta muestra:

- **State**: Activa o Suspendida
- **Max QPS**: El límite de solicitudes de puja que acepta esta configuración
- **Formats**: VIDEO, DISPLAY_IMAGE, DISPLAY_HTML, NATIVE
- **Platforms**: DESKTOP, MOBILE_APP, MOBILE_WEB, CONNECTED_TV
- **Geos**: Objetivos geográficos incluidos y excluidos
- **Sizes**: Tamaños de anuncio incluidos (o todos si no hay filtro)

### Controles

- **Selector de período**: 7, 14 o 30 días de datos
- **Filtro de cuenta**: delimitar a un seat de comprador específico
- **Alternador de configuración**: profundizar en una configuración de pretargeting específica

## Cómo interpretarlo

Comienza con el waste ratio. Si está por encima del 50%, tienes un margen
significativo de mejora. Luego observa qué configuraciones generan más
desperdicio. Haz clic en los análisis por dimensión
([Geo](04-analyzing-waste.md), [Publisher](04-analyzing-waste.md),
[Tamaño](04-analyzing-waste.md)) para encontrar las fuentes específicas.

## Relacionado

- [Análisis de desperdicio por dimensión](04-analyzing-waste.md): profundiza en
  geo, publisher y tamaño
- [Configuración de pretargeting](06-pretargeting.md): actúa según tus hallazgos
