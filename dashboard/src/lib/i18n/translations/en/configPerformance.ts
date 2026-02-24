import type { Translations } from '../../types';

const value: Translations['configPerformance'] = {
    failedToLoad: 'Failed to load config performance data',
    noDataAvailable: 'No config data available. Import bidding metrics CSV with pretargeting config (`billing_id`) dimension.',
    pretargetingConfigs: 'Pretargeting Configs',
    clickToExpand: 'Click to expand settings and size breakdown',
    total: 'Total',
    totalReached: '{count} reached',
    winPctValue: '{pct}% win',
    wastePctValue: '{pct}% waste',
    configFallbackName: 'Config {id}',
    settingFormat: 'Format',
    settingGeos: 'Geos',
    settingPlatform: 'Platform',
    settingQps: 'QPS',
    settingBudget: 'Budget',
    budgetPerDayValue: '${amount}/d',
    size: 'Size',
    reached: 'Reached',
    winPct: 'Win%',
    waste: 'Waste',
  };

export default value;
