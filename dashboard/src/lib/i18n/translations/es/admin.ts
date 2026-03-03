import type { PartialTranslations } from '../../types';

const value: PartialTranslations['admin'] = {
  dashboard: 'Panel de Administración',
  manageUsers: 'Gestiona usuarios, permisos y ajustes del sistema',
  totalUsers: 'Usuarios totales',
  activeUsers: 'Usuarios activos',
  adminUsers: 'Usuarios sudo',
  userManagement: 'Gestión de usuarios',
  manageUsersLink: 'Gestionar usuarios',
  createNewUser: 'Crear nuevo usuario',
  viewAuditLog: 'Ver registro de auditoría',
  systemSettings: 'Ajustes del sistema',
  systemConfiguration: 'Configuración y estado del sistema',
  reportHealthTitle: 'Salud de reportes',
  reportHealthDesc:
    'Se esperan {count} reportes por seat para la fecha de reporte más reciente.',
  reportHealthNoAlerts:
    'Todos los seats recibieron los reportes esperados.',
  reportHealthSeat: 'Seat',
  reportHealthDate: 'Última fecha',
  reportHealthMissing: 'Reportes faltantes',
  reportHealthFailed: 'Reportes fallidos',
  multiUserMode: 'Modo multiusuario',
  multipleUsersCanAccess:
    'Múltiples usuarios pueden acceder al sistema',
  singleUserMode: 'Modo de un solo usuario (open-source)',
  enabled: 'Habilitado',
  disabled: 'Deshabilitado',
  auditLogRetention: 'Retención del registro de auditoría',
  howLongToKeep: 'Cuánto tiempo conservar los registros de auditoría',
  allSettings: 'Todos los ajustes',
  yourAccount: 'Tu cuenta',
  email: 'Correo',
  displayName: 'Nombre visible',
  active: 'Activo',
  apiStatus: 'Estado API',
  systemStatus: 'Estado del sistema',
  python: 'Python',
  nodejs: 'Node.js',
  configured: 'Configurado',
  retention: 'Retención',
  unlimited: 'Ilimitado',
  auditLog: 'Registro de auditoría',
  role: 'Rol',
  permissions: 'Permisos',
  lastLogin: 'Último acceso',
  createUser: 'Crear usuario',
  editUser: 'Editar usuario',
  deleteUser: 'Eliminar usuario',
  status: 'Estado',
  // Users page
  users: 'Usuarios',
  usersCount: '{count} usuario',
  usersCountPlural: '{count} usuarios',
  activeOnly: '(solo activos)',
  withRole: 'con rol {role}',
  loadingUsers: 'Cargando usuarios...',
  noUsersFound: 'No se encontraron usuarios',
  user: 'Usuario',
  created: 'Creado',
  inactive: 'Inactivo',
  resetPassword: 'Restablecer contraseña',
  deactivate: 'Desactivar',
  managePermissions: 'Gestionar permisos',
  emailAddress: 'Correo electrónico',
  emailPlaceholder: 'usuario@ejemplo.com',
  displayNameOptional: 'Nombre visible (opcional)',
  displayNamePlaceholder: 'Juan Pérez',
  sudoRole: 'Sudo',
  readRole: 'Lectura',
  userRole: 'Lectura',
  adminRole: 'Admin',
  authMethod: 'Método de autenticación',
  localPasswordAuth: 'Contraseña local',
  oauthPrecreateAuth: 'Pre-registro de auth externa',
  localPasswordHelp:
    'Crea una cuenta local con usuario/contraseña que puede iniciar sesión de inmediato.',
  oauthPrecreateHelp:
    'Crea solo el registro de usuario. Debe iniciar sesión más tarde mediante auth externa.',
  defaultLanguage: 'Idioma predeterminado',
  defaultLanguageHelp:
    'Este es el idioma inicial para este usuario.',
  seatAccess: 'Acceso a seat (opcional)',
  seatAccessHelp:
    'Concede acceso explícito a buyer seats ahora o ajústalo luego en Gestionar permisos.',
  noSeatsConfigured:
    'Aún no se encontraron buyer seats. Sincroniza seats primero en Ajustes.',
  seatAccessManageHelp:
    'Concede acceso a buyer seats específicos para este usuario.',
  buyerIdLabel: 'Buyer ID: {buyerId}',
  bidderLabel: 'Bidder: {bidderId}',
  legacyServiceAccountAccess:
    'Acceso a Service Account (legacy)',
  legacyServiceAccountAccessHelp:
    'Modelo de permisos legacy. Prefiere el Acceso a Seat explícito de arriba.',
  oauthInviteNote:
    'Los usuarios inician sesión con autenticación externa. No se requiere contraseña local.',
  confirmPassword: 'Confirmar contraseña',
  confirmPasswordHelp:
    'Introduce la misma contraseña otra vez para evitar errores de escritura.',
  passwordMinLengthHelp:
    'La contraseña debe tener al menos 8 caracteres.',
  passwordMismatch:
    'La contraseña y su confirmación deben coincidir.',
  passwordGenerated:
    'Se generará automáticamente una contraseña segura.',
  creating: 'Creando...',
  userCreatedSuccessfully: 'Usuario creado correctamente',
  shareCredentials:
    'Comparte estas credenciales de forma segura con el usuario.',
  password: 'Contraseña',
  passwordOnlyShownOnce:
    'Esta contraseña solo se mostrará una vez. Asegúrate de guardarla de forma segura.',
  permissionsFor: 'Permisos para {email}',
  permissionsHelp:
    'Gestiona el acceso a buyer seats y el acceso legacy a service accounts para este usuario.',
  createUserFailed: 'No se pudo crear el usuario',
  noAccess: 'Sin acceso',
  readAccess: 'Lectura',
  writeAccess: 'Escritura',
  adminAccess: 'Admin',
  noServiceAccounts:
    'Aún no hay service accounts configuradas.',
  done: 'Listo',
  // Settings page
  configureSettings:
    'Configura ajustes y funciones a nivel de sistema.',
  settingUpdated: 'Ajuste "{key}" actualizado correctamente',
  multiUserDescription:
    'Permite crear cuentas de usuario adicionales. Cuando está deshabilitado, solo la cuenta sudo puede acceder al sistema.',
  multiUserInfo:
    'El inicio de sesión siempre es obligatorio. Este ajuste controla si puedes agregar más cuentas además de la cuenta sudo. Actívalo para acceso en equipo, desactívalo para uso personal.',
  retentionDescription:
    'Configura cuánto tiempo conservar entradas del registro de auditoría antes de la limpieza automática.',
  retentionUnlimited: 'Ilimitado',
  retentionUnlimitedDesc:
    'Conservar los registros de auditoría para siempre',
  retention30: '30 días',
  retention30Desc:
    'Eliminar registros de más de 30 días',
  retention60: '60 días',
  retention60Desc:
    'Eliminar registros de más de 60 días (recomendado)',
  retention90: '90 días',
  retention90Desc:
    'Eliminar registros de más de 90 días',
  retention120: '120 días',
  retention120Desc:
    'Eliminar registros de más de 120 días',
  sessionSettings: 'Ajustes de sesión',
  sessionSettingsDesc:
    'Ajustes predeterminados de sesión y seguridad.',
  sessionDuration: 'Duración de sesión',
  sessionDurationValue: '30 días',
  authProvider: 'Proveedor de auth',
  authProviderValue: 'Google OAuth (OAuth2 Proxy)',
  loginAttempts: 'Intentos de login antes del bloqueo',
  lockoutDuration: 'Duración del bloqueo',
  passwordHashing: 'Hash de contraseña',
  rawSettingsView:
    'Vista raw de todos los ajustes del sistema.',
  key: 'Clave',
  value: 'Valor',
  // Audit log page
  eventsCount: '{count} evento',
  eventsCountPlural: '{count} eventos',
  inLastDays: 'en los últimos {days} días',
  inLastDay: 'en el último día',
  filters: 'Filtros',
  timeRange: 'Rango de tiempo',
  last24Hours: 'Últimas 24 horas',
  last7Days: 'Últimos 7 días',
  last30Days: 'Últimos 30 días',
  last60Days: 'Últimos 60 días',
  last90Days: 'Últimos 90 días',
  actionType: 'Tipo de acción',
  allActions: 'Todas las acciones',
  auditActionLogin: 'login',
  auditActionLogout: 'logout',
  auditActionLoginFailed: 'login fallido',
  auditActionLoginBlocked: 'login bloqueado',
  auditActionCreateUser: 'crear usuario',
  auditActionUpdateUser: 'actualizar usuario',
  auditActionDeactivateUser: 'desactivar usuario',
  auditActionResetPassword: 'restablecer contraseña',
  auditActionChangePassword: 'cambiar contraseña',
  auditActionGrantPermission: 'conceder permiso',
  auditActionRevokePermission: 'revocar permiso',
  auditActionUpdateSetting: 'actualizar ajuste',
  auditActionCreateInitialAdmin: 'crear admin inicial',
  loadingAuditLogs: 'Cargando registros de auditoría...',
  noAuditLogs:
    'No se encontraron entradas en el registro de auditoría',
  timestamp: 'Marca de tiempo',
  action: 'Acción',
  resource: 'Recurso',
  details: 'Detalles',
  ipAddress: 'Dirección IP',
  redirectingToConfiguration:
    'Redirigiendo a Configuración...',
};

export default value;
