import type { PartialTranslations } from '../../types';

const value: PartialTranslations['configPerformance'] = {
  failedToLoad: 'Не удалось загрузить данные эффективности конфигурации',
  noDataAvailable: 'Данные конфигурации недоступны. Импортируйте CSV с метриками ставок и измерением претаргетинга (`billing_id`).',
  pretargetingConfigs: 'Конфигурации претаргетинга',
  clickToExpand: 'Нажмите для просмотра настроек и разбивки по размерам',
  total: 'Всего',
  totalReached: '{count} достигнуто',
  winPctValue: '{pct}% побед',
  wastePctValue: '{pct}% потерь',
  configFallbackName: 'Конфигурация {id}',
  settingFormat: 'Формат',
  settingGeos: 'Регионы',
  settingPlatform: 'Платформа',
  settingQps: 'QPS',
  settingBudget: 'Бюджет',
  budgetPerDayValue: '${amount}/д',
  size: 'Размер',
  reached: 'Достигнуто',
  winPct: '% побед',
  waste: 'Потери',
};

export default value;
