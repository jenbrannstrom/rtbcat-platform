import type { PartialTranslations } from '../../types';

const value: PartialTranslations['connect'] = {
  title: 'Conectar',
  connectAccount: 'Conectar cuenta',
  serviceAccount: 'Service Account',
  instructions:
    'Sigue las instrucciones para conectar tu cuenta',
  setupComplete: '¡Configuración completada!',
  setUpCatScan: 'Configurar Cat-Scan',
  accountConnectedReady:
    'Tu cuenta está conectada y lista para analizar',
  stepOf: 'Paso {current} de {total}: {title}',
  uploadCredentials: 'Subir credenciales',
  syncCreatives: 'Sincronizar creatividades',
  readyToGo: 'Listo para empezar',
  optionalInstallFfmpeg: 'Opcional: Instalar ffmpeg',
  ffmpegRequired:
    'ffmpeg es obligatorio para generar miniaturas de video. Sin él, las creatividades de video mostrarán iconos placeholder en lugar de frames de vista previa.',
  googleCredentials: 'Credenciales de Google',
  connected: 'Conectado',
  serviceAccountConfigured: 'Service account configurado',
  change: 'Cambiar',
  uploading: 'Subiendo...',
  dropFileHere: 'Suelta el archivo aquí',
  uploadServiceAccountJson: 'Subir JSON de Service Account',
  dragAndDropOrClick: 'Arrastra y suelta o haz clic para explorar',
  howToGetServiceAccountKey:
    'Cómo obtener una clave de service account',
  goToGcpServiceAccounts:
    'Ve a la página de Service Accounts de GCP',
  selectYourProject:
    'Selecciona tu proyecto (o crea uno)',
  clickCreateServiceAccount:
    'Haz clic en + Create Service Account',
  nameIt:
    'Ponle nombre (por ejemplo, "catscan-service-account")',
  clickCreateContinue:
    'Haz clic en Create and Continue, omite roles y haz clic en Done',
  clickOnServiceAccountEmail:
    'Haz clic en el correo del nuevo service account',
  goToKeysTab:
    'Ve a la pestaña Keys -> Add Key -> Create new key',
  selectJsonClick: 'Selecciona JSON y haz clic en Create',
  uploadDownloadedFile:
    'Sube el archivo descargado arriba',
  importantAddServiceAccount:
    'Importante: también debes agregar el correo del service account como usuario en tu cuenta de Authorized Buyers con acceso RTB.',
  noBuyerSeatsFound: 'No se encontraron buyer seats',
  makeSureServiceAccountHasAccess:
    'Asegúrate de que el service account tenga acceso a tu cuenta de Authorized Buyers',
  completeStep1:
    'Completa el paso 1 para sincronizar tus creatividades',
  creatives: 'creatividades',
  lastSynced: 'Última sincronización',
  syncing: 'Sincronizando...',
  syncNow: 'Sincronizar ahora',
  readyToAnalyze: 'Listo para analizar',
  accountSetUpCreativesSynced:
    'Tu cuenta está configurada y las creatividades están sincronizadas. Ahora puedes:',
  viewCreativeStatus:
    'Ver estado y aprobaciones de creatividades',
  importRtbPerformance:
    'Importar datos de rendimiento RTB',
  analyzeQpsWaste:
    'Analizar desperdicio de QPS y oportunidades de optimización',
  goToDashboard: 'Ir al Dashboard',
  completeSteps1And2:
    'Completa los pasos 1 y 2 para continuar',
  discoveredSeats: 'Se descubrieron {count} buyer seat(s)',
  failedToDiscoverSeats: 'No se pudieron descubrir seats',
  connectedAs: 'Conectado como {email}',
  uploadFailed: 'Falló la subida',
  syncedCreatives: 'Se sincronizaron {count} creatividades',
  syncFailed: 'Falló la sincronización',
  pleaseSelectJsonFile: 'Selecciona un archivo JSON',
  invalidJsonFile:
    'Archivo JSON inválido. Sube una clave de service account válida.',
  invalidServiceAccountFormat:
    'Formato de service account inválido. Faltan campos requeridos.',
  invalidCredentialType:
    'Tipo de credencial inválido: "{type}". Se esperaba "service_account".',
  account: 'Cuenta',
};

export default value;
