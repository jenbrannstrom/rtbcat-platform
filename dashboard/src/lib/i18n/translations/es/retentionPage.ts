import type { PartialTranslations } from '../../types';

const value: PartialTranslations['retentionPage'] = {
  title: 'Ajustes de Retención de Datos',
  subtitle: 'Configura cuánto tiempo se retienen los datos de rendimiento.',
  saveSuccess: 'Ajustes de retención guardados correctamente.',
  saveFailed: 'No se pudieron guardar los ajustes de retención.',
  runCompleted:
    'Trabajo de retención completado: {aggregatedRows} filas agregadas, {deletedRawRows} filas raw eliminadas.',
  runFailed: 'No se pudo ejecutar el trabajo de retención.',
  currentStorage: 'Almacenamiento actual',
  rawPerformanceRows: 'Filas raw de rendimiento',
  dailySummaryRows: 'Filas de resumen diario',
  dateRangeSpan: '{start} a {end}',
  keepDetailedDataFor: 'Mantener datos detallados durante:',
  keepDailySummariesFor: 'Mantener resúmenes diarios durante:',
  autoAggregateAfter: 'Autoagregar después de:',
  option7Days: '7 días',
  option14Days: '14 días',
  option30Days: '30 días',
  option30DaysRecommended: '30 días (recomendado)',
  option60Days: '60 días',
  option90DaysRecommended: '90 días (recomendado)',
  option180Days: '180 días',
  option1Year: '1 año',
  option6Months: '6 meses',
  option1YearRecommended: '1 año (recomendado)',
  option2Years: '2 años',
  optionForever: 'Siempre',
  detailedDataHelp:
    'Los datos detallados muestran rendimiento por app, país y creative. Después de este período, se agregan en resúmenes diarios.',
  summaryDataHelp:
    'Los resúmenes muestran totales diarios por creative. Son útiles para análisis de tendencias.',
  autoAggregateHelp:
    'Crea resúmenes para datos anteriores a este límite antes de eliminarlos.',
  warningIrreversible:
    'Reducir la retención eliminará datos antiguos permanentemente. Esto no se puede deshacer.',
  howItWorks: 'Cómo funciona:',
  howItWorksItem1:
    'Las filas detalladas se agregan en resúmenes diarios',
  howItWorksItem2:
    'Los resúmenes conservan métricas totales por creative/día',
  howItWorksItem3:
    'Después de agregar, se eliminan las filas detalladas',
  howItWorksItem4:
    'Esto reduce significativamente los requisitos de almacenamiento',
  saving: 'Guardando...',
  saveSettings: 'Guardar ajustes',
  running: 'Ejecutando...',
  runRetentionJobNow: 'Ejecutar trabajo de retención ahora',
};

export default value;
