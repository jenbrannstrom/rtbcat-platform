# Capítulo 16: Administración de usuarios y permisos

*Audiencia: DevOps, administradores de sistemas*

## Panel de administración (`/admin`)

El panel de administración solo es visible para los usuarios con la marca `is_sudo`. Proporciona gestión de usuarios, configuración del sistema y registro de auditoría.

## Gestión de usuarios (`/admin/users`)

### Creación de usuarios

Dos métodos:

| Método | Cuándo usarlo |
|--------|---------------|
| **Cuenta local** | Para usuarios que iniciarán sesión con email y contraseña. Usted establece la contraseña inicial. |
| **Pre-creación OAuth** | Para usuarios que iniciarán sesión con Google OAuth. Pre-crear el registro permite asignar permisos antes de su primer inicio de sesión. |

Campos: email (obligatorio), nombre para mostrar, rol, método de autenticación, contraseña (solo para cuentas locales).

### Roles y permisos

**Permisos globales** controlan lo que un usuario puede hacer a nivel de todo el sistema:
- Usuario estándar: acceso a las funciones principales
- Usuario restringido: barra lateral limitada (sin secciones de ajustes, administración ni QPS)
- Administrador (`is_sudo`): acceso completo incluyendo el panel de administración

**Permisos por asiento** controlan qué cuentas de comprador puede ver un usuario:
- Otorgar acceso a valores específicos de `buyer_account_id`
- Los niveles de acceso pueden variar por asiento
- Un usuario sin permisos de asiento no ve ningún dato

### Gestión de permisos

1. Ir a `/admin/users`
2. Seleccionar un usuario
3. En "Seat Permissions": otorgar o revocar acceso a asientos de comprador
4. En "Global Permissions": otorgar o revocar acceso a nivel de sistema
5. Los cambios se aplican en la siguiente carga de página del usuario

### Desactivación de usuarios

Desactivar un usuario preserva su registro (para la trazabilidad de auditoría) pero impide el inicio de sesión. No elimina sus datos ni permisos; puede ser reactivado.

## Cuentas de servicio (`/settings/accounts`)

Las cuentas de servicio representan credenciales de GCP que permiten a Cat-Scan comunicarse con las APIs de Google.

### Carga de credenciales

1. Ir a `/settings/accounts` > pestaña API Connection
2. Subir el archivo de clave JSON de la cuenta de servicio de GCP
3. Cat-Scan valida las credenciales y muestra el estado de la conexión

**Nota de seguridad:** Solo agregue el archivo de clave JSON de la cuenta de servicio al final de la configuración para minimizar el riesgo de exposición.

### Qué desbloquean las cuentas de servicio

- **Descubrimiento de asientos**: encontrar cuentas de comprador asociadas a las credenciales
- **Sincronización de pretargeting**: obtener el estado actual de configuración desde Google
- **Sincronización de endpoints RTB**: descubrir los endpoints del bidder
- **Recopilación de creativos**: obtener metadatos de creativos

## Registro de auditoría (`/admin/audit-log`)

Cada acción significativa se registra:

| Acción | Qué la activa |
|--------|---------------|
| `login` | Autenticación exitosa |
| `login_failed` | Intento de autenticación fallido |
| `login_blocked` | Inicio de sesión rechazado (usuario desactivado, etc.) |
| `create_user` | Nuevo usuario creado |
| `update_user` | Perfil de usuario modificado |
| `deactivate_user` | Usuario desactivado |
| `reset_password` | Restablecimiento de contraseña |
| `change_password` | Contraseña cambiada |
| `grant_permission` | Permiso otorgado |
| `revoke_permission` | Permiso revocado |
| `update_setting` | Configuración del sistema cambiada |
| `create_initial_admin` | Primer administrador creado durante la configuración |

Filtros: por usuario, tipo de acción, tipo de recurso, ventana de tiempo (días), con paginación.

## Configuración del sistema (`/admin/configuration`)

Configuraciones globales de clave-valor que controlan el comportamiento del sistema. Editables por administradores. Los cambios se registran en el log de auditoría.

## Relacionado

- [Inicio de sesión](01-logging-in.md): experiencia de autenticación del usuario
- [Visión general de la arquitectura](11-architecture.md): detalles de la cadena de confianza de autenticación
