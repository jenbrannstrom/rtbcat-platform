import type { PartialTranslations } from '../../types';

const value: PartialTranslations['history'] = {
  title: 'Historial de Cambios',
  changeHistory: 'Historial de Cambios',
  trackAndRollback:
    'Rastrea y revierte cambios en la configuración de pretargeting',
  noChanges: 'No se registraron cambios',
  noChangesFound: 'No se encontraron cambios',
  tryAdjustingFilters: 'Prueba ajustando tus filtros.',
  changesWillAppear: 'Los cambios de configuración aparecerán aquí.',
  change: 'Cambio',
  user: 'Usuario',
  timestamp: 'Marca de tiempo',
  export: 'Exportar',
  filters: 'Filtros:',
  period: 'Período:',
  lastDays: 'Últimos {count} días',
  config: 'Config:',
  allConfigs: 'Todas las configs',
  type: 'Tipo:',
  allTypes: 'Todos los tipos',
  clearFilters: 'Limpiar filtros',
  showingChanges:
    'Mostrando {count} cambio de los últimos {days} días',
  showingChangesPlural:
    'Mostrando {count} cambios de los últimos {days} días',
  rollback: 'Rollback',
  rollbackChange: 'Revertir cambio',
  aboutToRollback: 'Estás a punto de revertir:',
  field: 'Campo:',
  current: 'Actual:',
  restoreTo: 'Restaurar a:',
  empty: '(vacío)',
  rollbackWarning:
    'Esto restaurará el ajuste anterior. Tendrás que aplicar el cambio manualmente en Google Authorized Buyers.',
  noSnapshotAvailableForChange:
    'No hay snapshot disponible para este cambio. El rollback requiere un auto-snapshot creado antes del push. Los cambios antiguos pueden no tener snapshots.',
  previewingRollback: 'Previsualizando rollback...',
  failedToPreviewRollback: 'No se pudo previsualizar el rollback',
  noDifferencesFoundBetweenCurrentAndSnapshot:
    'No se encontraron diferencias entre la config actual y el snapshot. La config pudo haberse modificado desde entonces.',
  changesWillBeReversedOnGoogle:
    'Estos cambios se revertirán en Google:',
  rollbackPushesToGoogleImmediately:
    'Esto hace push a Google inmediatamente. Se registrará una nueva entrada “ROLLBACK” en el historial.',
  reasonForRollback: 'Motivo del rollback',
  whyRollingBack: '¿Por qué estás revirtiendo este cambio?',
  cancel: 'Cancelar',
  rollbackNow: 'Revertir ahora',
  on: 'en',
  value: 'Valor:',
  manual: 'manual',
  daysAgo: 'd atrás',
  hoursAgo: 'h atrás',
  minutesAgo: 'm atrás',
  justNow: 'ahora',
  rollbackFailed: 'Falló el rollback',
};

export default value;
