# Capítulo 4: Análisis de desperdicio por dimensión

*Audiencia: compradores de medios, gestores de campañas*

Una vez que sabes *cuánto* desperdicio tienes (desde el [embudo](03-qps-funnel.md)),
estas tres vistas te dicen *de dónde* proviene.

## Desperdicio geográfico (`/qps/geo`)

Muestra el consumo de QPS y el rendimiento por país y ciudad.

![Desglose geográfico de QPS por país](images/screenshot-geo-qps.png)

**Qué buscar:**
- Países con alto QPS pero cero o casi cero victorias. Google te está enviando
  tráfico de regiones que tus compradores no segmentan.
- Ciudades con una participación desproporcionada de QPS pero bajo gasto, lo que
  indica geos de cola larga que añaden volumen pero no valor.

**Qué hacer al respecto:**
- Añade los geos con bajo rendimiento a tu lista de exclusión de pretargeting.
  Consulta [Configuración de pretargeting](06-pretargeting.md).

**Controles:** Selector de período (7/14/30 días), filtro de cuenta.

## Desperdicio por publisher (`/qps/publisher`)

Muestra el rendimiento desglosado por dominio de publisher o aplicación.

![QPS por publisher con análisis de tasa de victoria](images/screenshot-pub-qps.png)

**Qué buscar:**
- Dominios con alto volumen de pujas pero cero impresiones. Tu bidder gasta
  cómputo en inventario que nunca se renderiza.
- Aplicaciones o sitios con tasas de victoria anormalmente bajas. Estás pujando
  pero perdiendo consistentemente, lo que significa que desperdicias tiempo de
  evaluación de pujas.
- Dominios conocidos de baja calidad.

**Qué hacer al respecto:**
- Bloquea publishers específicos en la lista de denegación de tu configuración de
  pretargeting. El editor de publishers de Cat-Scan simplifica esto en comparación
  con la interfaz de Authorized Buyers.

**Controles:** Selector de período, filtro geográfico, búsqueda por dominio.

## Desperdicio por tamaño (`/qps/size`)

Muestra qué tamaños de anuncio reciben tráfico y si tienes creatividades para ellos.

![Desglose de QPS por tamaño](images/screenshot-size-qps.png)

**Qué buscar:**
- Tamaños con alto QPS pero **sin creatividad compatible**. Google envía
  aproximadamente 400 tamaños de anuncio diferentes. Si utilizas anuncios de
  display de tamaño fijo (no HTML), la mayoría de esos tamaños son irrelevantes.
  Cada solicitud para un tamaño sin coincidencia es puro desperdicio.
- Tamaños con creatividades que tienen bajo rendimiento. Considera si los
  recursos creativos son apropiados para ese formato.

**Qué hacer al respecto:**
- Añade los tamaños irrelevantes a la lista de tamaños excluidos de tu
  pretargeting. Esta es la optimización con mayor impacto para compradores de
  display.

**Controles:** Selector de período, filtro de cuenta, gráfico de desglose de cobertura.

## Combinando dimensiones

Las tres vistas son complementarias. Un ciclo de optimización típico:

1. Revisa **geo**: excluye los países que no necesitas.
2. Revisa **publisher**: bloquea los dominios que desperdician pujas.
3. Revisa **tamaño**: excluye los tamaños sin creatividad compatible.
4. Aplica los cambios mediante [Configuración de pretargeting](06-pretargeting.md)
   con vista previa de prueba en seco.
5. Espera un ciclo de datos (normalmente un día) y vuelve a revisar el embudo.

## Relacionado

- [Entender tu embudo de QPS](03-qps-funnel.md): el punto de partida
- [Configuración de pretargeting](06-pretargeting.md): actuar según los hallazgos de desperdicio
- [Leer tus informes](10-reading-reports.md): seguir el impacto
