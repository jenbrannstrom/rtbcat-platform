# Capítulo 1: Iniciar sesión

*Audiencia: todos*

## Métodos de autenticación

Cat-Scan admite tres métodos de inicio de sesión:

| Método | Cómo funciona | Cuándo usarlo |
|--------|---------------|---------------|
| **Google OAuth** | Haz clic en "Sign in with Google", que redirige a través de OAuth2 Proxy | La mayoría de los usuarios. Usa tu cuenta de Google Workspace. |
| **Authing (OIDC)** | Haz clic en "Sign in with Authing", que redirige al proveedor OIDC | Organizaciones que usan Authing como proveedor de identidad. |
| **Correo y contraseña** | Introduce las credenciales directamente en la página de inicio de sesión | Cuentas locales creadas por un administrador. |

## Primer inicio de sesión

1. Navega a `https://scan.rtb.cat` (o la URL de tu despliegue).
2. Verás la página de inicio de sesión con las opciones disponibles.
3. Elige tu método y autentícate.
4. En el primer inicio de sesión, el sistema crea tu registro de usuario
   automáticamente (para los métodos OAuth). Es posible que tu administrador
   necesite otorgarte acceso a cuentas de comprador específicas.

## El selector de cuenta (seat)

Después de iniciar sesión, verás la barra lateral con un **selector de cuenta**
en la parte superior. Si tu cuenta tiene acceso a múltiples seats de comprador,
usa el desplegable para alternar entre ellos. Todos los datos en cada página
están delimitados por el seat seleccionado.

- **Cuenta única**: el selector muestra directamente el nombre y el ID de tu seat.
- **Múltiples cuentas**: un desplegable te permite cambiar entre ellas. Cada
  entrada muestra el nombre del comprador, el `buyer_account_id` y un conteo de
  creatividades.
- **Botón "Sync All"**: actualiza las creatividades, endpoints y configuraciones
  de pretargeting desde la API de Google para el seat seleccionado.

## Cuando el inicio de sesión falla

| Síntoma | Causa probable | Qué hacer |
|---------|----------------|-----------|
| Bucle de redirección (la página sigue recargándose) | Base de datos inaccesible, por lo que la verificación de autenticación falla silenciosamente | Verifica el contenedor de Cloud SQL Proxy. Consulta [Solución de problemas](15-troubleshooting.md). |
| "Server unavailable" (502/503/504) | El contenedor de la API o de nginx está caído | Contacta a tu equipo de DevOps. Consulta [Monitoreo de salud](13-health-monitoring.md). |
| "Authentication required" | Sesión expirada o cookie eliminada | Inicia sesión nuevamente. |
| "You don't have access to this buyer account" | Permisos no otorgados para este seat | Consulta a tu administrador. Consulta [Administración de usuarios](16-user-admin.md). |

## Próximos pasos

- [Navegar por el panel](02-navigating-the-dashboard.md)
