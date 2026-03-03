# Capítulo 0: ¿Qué es Cat-Scan?

*Audiencia: todos*

Cat-Scan es una plataforma de optimización de QPS para Google Authorized Buyers.
Te ofrece visibilidad sobre cómo se utiliza (y se desperdicia) la asignación de
consultas por segundo de tu bidder, y proporciona las herramientas para mejorarla.

![Embudo de QPS](/docs/qps-funnel.svg)

## El problema central

Cuando operas una cuenta (seat) en el exchange de Google Authorized Buyers,
Google envía a tu endpoint de bidder un flujo de solicitudes de puja. Pagas por
este flujo: consume tu QPS asignado, la capacidad de cómputo de tu bidder y tu
ancho de banda de red.

Pero no todas las solicitudes de puja son útiles. Muchas llegan para inventario
que nunca comprarías: países que no segmentas, publishers que desconoces, tamaños
de anuncio para los que no tienes creatividades. Tu bidder aún debe recibir y
rechazar cada una de ellas.

En una configuración típica, **más de la mitad de tu QPS es desperdicio.**

## Qué hace Cat-Scan al respecto

Cat-Scan funciona junto a tu bidder y proporciona tres cosas:

### 1. Visibilidad

Reconstruye los informes de rendimiento a partir de las exportaciones CSV de
Google (ya que no existe una API de reporting) y te muestra el embudo RTB
completo: desde el QPS bruto pasando por pujas, victorias, impresiones, clics y
gasto. Lo desglosa por geografía, publisher, tamaño de anuncio, creatividad y
configuración de pretargeting.

Esto te permite responder preguntas como:
- ¿Qué países están consumiendo QPS sin generar victorias?
- ¿Qué publishers tienen alto QPS pero cero gasto?
- ¿Qué tamaños de anuncio reciben tráfico pero no tienen creatividad compatible?
- ¿Qué configuraciones de pretargeting rinden bien frente a las que rinden mal?

### 2. Control

Google te otorga 10 configuraciones de pretargeting por cuenta. Estas son tu
palanca principal para indicarle a Google qué tráfico enviar y qué filtrar.
Cat-Scan proporciona:
- Un editor de configuración con vista previa de prueba en seco
- Una línea temporal del historial de cambios con reversión en un clic
- Listas de inclusión/exclusión de publishers por configuración
- Un optimizador que puntúa segmentos y propone cambios de configuración

### 3. Seguridad

Cada cambio de pretargeting queda registrado. Puedes previsualizar el efecto de
un cambio antes de aplicarlo. Si algo sale mal, puedes revertirlo
instantáneamente. El optimizador utiliza perfiles de flujo de trabajo (seguro,
equilibrado, agresivo) para que ningún cambio automatizado se active sin revisión
humana.

## Conceptos clave

Antes de continuar, asegúrate de tener claros estos términos:

| Concepto | Qué significa |
|----------|---------------|
| **Seat** | Una cuenta de comprador en Google Authorized Buyers, identificada por un `buyer_account_id`. Una organización puede tener múltiples seats. |
| **QPS** | Queries Per Second (consultas por segundo): la tasa máxima de solicitudes de puja que le pides a Google que envíe a tu bidder. Google regula el volumen real según el nivel de tu cuenta, por lo que conviene usar cada solicitud de forma eficiente. |
| **Pretargeting** | Filtros del lado del servidor que le indican a Google qué solicitudes de puja enviarte. Controla: geografías, tamaños de anuncio, formatos, plataformas, tipos de creatividad. Dispones de 10 por seat. |
| **Embudo RTB** | La progresión desde la solicitud de puja recibida, pasando por la puja realizada, la subasta ganada, la impresión servida, el clic y la conversión. Cada paso tiene una caída; Cat-Scan te muestra dónde ocurre. |
| **Desperdicio** | QPS consumido por solicitudes de puja que tu bidder no puede o no quiere utilizar. El objetivo es reducir el desperdicio sin perder tráfico valioso. |
| **Config** | Abreviatura de configuración de pretargeting. Cada una tiene un estado (activa/suspendida), un QPS máximo y reglas de inclusión/exclusión para geos, tamaños, formatos y plataformas. |

## Próximos pasos

- [Iniciar sesión](01-logging-in.md): accede al panel de control
- [Navegar por el panel](02-navigating-the-dashboard.md): oriéntate en la interfaz
