import type { PartialTranslations } from '../../types';

const value: PartialTranslations['configPerformance'] = {
  failedToLoad: 'Config-performancedata laden mislukt',
  noDataAvailable:
    'Geen configdata beschikbaar. Importeer een bidding-metrics CSV met pretargeting config (`billing_id`) als dimensie.',
  pretargetingConfigs: 'Pretargeting-configs',
  clickToExpand: 'Klik om instellingen en formaatuitsplitsing uit te klappen',
  total: 'Totaal',
  totalReached: '{count} bereikt',
  winPctValue: '{pct}% win',
  wastePctValue: '{pct}% verspilling',
  configFallbackName: 'Config {id}',
  settingFormat: 'Formaat',
  settingGeos: 'Geos',
  settingPlatform: 'Platform',
  settingQps: 'QPS',
  settingBudget: 'Budget',
  budgetPerDayValue: '${amount}/d',
  size: 'Formaat',
  reached: 'Bereikt',
  winPct: 'Win%',
  waste: 'Verspilling',
};

export default value;
