# Capítulo 10: Lectura de Informes

*Audiencia: compradores de medios, gestores de campañas*

Este capítulo explica los paneles de analítica de Cat-Scan y cómo
interpretar las cifras.

## Estadísticas de gasto

Disponibles en la página de inicio y en los desgloses por configuración.

| Métrica | Qué te indica |
|---------|--------------|
| **Total spend** | Gasto bruto durante el período y seat seleccionados. |
| **Spend trend** | Período reciente vs. período anterior. Un gasto creciente con ganados estables = inflación de costos. |
| **Spend by config** | Qué configuración de pretargeting es responsable de cuánto gasto. Ayuda a identificar qué configuraciones optimizar primero. |

## Rendimiento por configuración

Muestra cómo se desempeñó cada configuración de pretargeting a lo largo del tiempo.

- **Desglose diario**: impresiones, clics, gasto, tasa de ganancia, CTR y
  CPM por configuración durante el período seleccionado.
- **Líneas de tendencia**: detecta configuraciones cuyo rendimiento se está degradando.
- **Desglose por campo**: qué campos específicos (geos, tamaños, formatos) dentro de una
  configuración están impulsando los números.

## Eficiencia de endpoints

Muestra la utilización de QPS por endpoint del bidder.

- **Ratio de eficiencia**: QPS útil / QPS total. Cuanto más cercano a 1.0, mejor.
- **Desglose por endpoint**: si tu bidder tiene múltiples endpoints, observa cuáles
  son los más y menos eficientes.
- Úsalo para decidir si consolidar endpoints sería beneficioso.

## Comparaciones de instantáneas

Después de revertir un cambio de pretargeting (o aplicar uno nuevo), el panel de
comparación de instantáneas muestra:

- **Antes**: estado de la configuración previo al cambio
- **Después**: estado de la configuración posterior al cambio
- **Delta**: qué cambió exactamente (campos añadidos/eliminados/modificados)

Esto es útil para el análisis posterior al cambio: "Excluí 5 geos ayer, ¿qué
pasó con mi embudo?"

## Optimizaciones recomendadas

Cat-Scan puede mostrar recomendaciones generadas por IA basadas en tus datos. Estas
sugieren cambios específicos de configuración con un impacto estimado. Son sugerencias,
no acciones automáticas. Siempre decides tú si las aplicas.

## Consejos para leer informes

1. **Siempre revisa el selector de período.** Una vista de 7 días y una de 30 días pueden
   contar historias muy diferentes.
2. **Compara configuraciones, no mires solo los totales.** Una configuración deficiente puede arrastrar
   los números agregados mientras otras configuraciones rinden bien.
3. **Observa las tendencias, no las instantáneas.** Los datos de un solo día son ruidosos. Las tendencias
   a lo largo de 7-14 días son más fiables.
4. **Cruza dimensiones.** Alto desperdicio en la vista de geo + alto desperdicio en la vista de tamaño
   para la misma configuración = dos oportunidades de optimización separadas.

## Relacionado

- [Entender tu embudo de QPS](03-qps-funnel.md): la vista resumen
- [Análisis de desperdicio por dimensión](04-analyzing-waste.md): profundizar en
  fuentes específicas de desperdicio
- [Configuración de pretargeting](06-pretargeting.md): actuar sobre los hallazgos de los informes
