import type { PartialTranslations } from '../../types';

const value: PartialTranslations['configPerformance'] = {
  failedToLoad: 'No se pudieron cargar los datos de rendimiento de configs',
  noDataAvailable:
    'No hay datos de config disponibles. Importa un CSV de métricas de puja con dimensión de pretargeting config (`billing_id`).',
  pretargetingConfigs: 'Configs de Pretargeting',
  clickToExpand: 'Haz clic para expandir ajustes y desglose por tamaño',
  total: 'Total',
  totalReached: '{count} reached',
  winPctValue: '{pct}% win',
  wastePctValue: '{pct}% desperdicio',
  configFallbackName: 'Config {id}',
  settingFormat: 'Formato',
  settingGeos: 'Geos',
  settingPlatform: 'Plataforma',
  settingQps: 'QPS',
  settingBudget: 'Presupuesto',
  budgetPerDayValue: '${amount}/d',
  size: 'Tamaño',
  reached: 'Reached',
  winPct: 'Win%',
  waste: 'Desperdicio',
};

export default value;
