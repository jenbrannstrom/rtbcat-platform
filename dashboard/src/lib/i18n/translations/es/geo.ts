import type { PartialTranslations } from '../../types';

const value: PartialTranslations['geo'] = {
  title: 'Rendimiento Geográfico',
  subtitle: '¿Qué geos tienen las tasas de win más altas?',
  winRatesByCountry: 'Tasas de win por país',
  avgWinRate: 'tasa de win prom.',
  countries: 'Países',
  reached: 'Reached',
  bids: 'Bids',
  wins: 'Wins',
  highWinRate: 'Alta tasa de win (>80%)',
  lowerWinRate: 'Baja tasa de win (<50%)',
  optimizeThese: 'Optimizar estos',
  geoDataNotAvailable: 'Datos geográficos no disponibles',
  importCreativeBiddingReport:
    'Importa un reporte de actividad de pujas por creatividad para ver tasas de win geográficas.',
  country: 'País',
  geoWasteActionExclude: 'Excluir',
  geoWasteActionMonitor: 'Monitorizar',
  geoWasteActionOk: 'OK',
  geoWasteActionExpand: 'Expandir',
  geoWasteFailedToLoad: 'No se pudo cargar el análisis geo de desperdicio',
  geoWasteTitle: 'Análisis Geográfico',
  geoWasteSubtitle:
    'Identifica geos con bajo rendimiento para excluir del pretargeting',
  geoWasteGeosAnalyzed: 'geos analizados',
  geoWastePerformingWell: 'Rindiendo bien',
  geoWasteWastedLabel: 'Desperdiciado',
  geoWasteExcludeFromPretargetingCount: 'Excluir de Pretargeting ({count})',
  geoWasteGeoBadgeTooltip: 'CTR: {ctr}%, Gasto: ${spend}',
  geoWasteClicks: 'Clics',
  geoWasteCtr: 'CTR',
  geoWasteSpend: 'Gasto',
  geoWasteCpm: 'CPM',
  geoWasteActionHeader: 'Acción',
};

export default value;
