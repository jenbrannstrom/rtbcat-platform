import type { PartialTranslations } from '../../types';

const value: PartialTranslations['configPerformance'] = {
    'failedToLoad': 'Échec du chargement des données de performance de config',
    'noDataAvailable': 'Aucune donnée de config disponible. Importez un CSV avec les métriques d'enchères avec la dimension pretargeting config (`billing_id`).',
    'pretargetingConfigs': 'Configs de pretargeting',
    'clickToExpand': 'Cliquez pour développer les paramètres et la répartition par taille',
    'total': 'Total',
    'totalReached': '{count} atteints',
    'winPctValue': '{pct}% gagné',
    'wastePctValue': '{pct}% gaspillage',
    'configFallbackName': 'Config {id}',
    'settingFormat': 'Format',
    'settingGeos': 'Geos',
    'settingPlatform': 'Plateforme',
    'settingQps': 'QPS',
    'settingBudget': 'Budget',
    'budgetPerDayValue': '${amount}/j',
    'size': 'Taille',
    'reached': 'Atteint',
    'winPct': 'Win%',
    'waste': 'Gaspillage'
};

export default value;
