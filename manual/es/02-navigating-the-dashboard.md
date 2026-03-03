# Capítulo 2: Navegar por el panel de control

*Audiencia: todos*

## Diseño de la barra lateral

La barra lateral es tu navegación principal. Puede colapsarse (modo solo iconos)
o expandirse. Tu preferencia se recuerda entre sesiones.

```
Seat Selector
 ├── QPS Waste Optimizer         /              (home)
 ├── Creatives                   /creatives
 ├── Campaigns                   /campaigns
 ├── Change History              /history
 ├── Import                      /import
 │
 ├── QPS (expandable)
 │   ├── Publisher                /qps/publisher
 │   ├── Geo                     /qps/geo
 │   └── Size                    /qps/size
 │
 ├── Settings (expandable)
 │   ├── Connected Accounts      /settings/accounts
 │   ├── Data Retention          /settings/retention
 │   └── System Status           /settings/system
 │
 ├── Admin (sudo users only)
 │   ├── Users                   /admin/users
 │   ├── Configuration           /admin/configuration
 │   └── Audit Log               /admin/audit-log
 │
 └── Footer: user email, version, docs link
```

Las secciones se expanden automáticamente cuando navegas hacia ellas.

## Usuarios restringidos

Algunas cuentas están marcadas como "restringidas" por un administrador. Los
usuarios restringidos solo ven las páginas principales: inicio, creatividades,
campañas, importación e historial. Las secciones de análisis de QPS,
configuración y administración están ocultas.

## La lista de verificación de configuración

Las cuentas nuevas ven una lista de verificación en `/setup` que guía la
configuración inicial:

1. Conectar cuentas de comprador (subir credenciales GCP, descubrir seats)
2. Validar la salud de los datos (verificar que las importaciones CSV están llegando)
3. Registrar un modelo de optimización (endpoint BYOM)
4. Validar el endpoint del modelo (llamada de prueba)
5. Establecer la línea base de costos de alojamiento (para cálculos económicos)
6. Conectar una fuente de conversiones (píxel o webhook)

Se registra el porcentaje de completado. Cada paso enlaza a la página de
configuración correspondiente.

## Soporte de idiomas

Cat-Scan admite inglés, holandés y chino (simplificado). El selector de idioma
está en la barra lateral. Tu preferencia se guarda por usuario.

## Próximos pasos

- Compradores de medios: comienza con [Entender tu embudo de QPS](03-qps-funnel.md)
- DevOps: comienza con [Visión general de la arquitectura](11-architecture.md)
