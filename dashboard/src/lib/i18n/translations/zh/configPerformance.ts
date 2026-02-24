import type { PartialTranslations } from '../../types';

const value: PartialTranslations['configPerformance'] = {
  failedToLoad: '加载配置性能数据失败',
  noDataAvailable:
    '没有可用的配置数据。请导入包含预定向配置（`billing_id`）维度的竞价指标 CSV。',
  pretargetingConfigs: '预定向配置',
  clickToExpand: '点击展开设置和尺寸明细',
  total: '总计',
  totalReached: '触达 {count}',
  winPctValue: '赢率 {pct}%',
  wastePctValue: '浪费 {pct}%',
  configFallbackName: '配置 {id}',
  settingFormat: '格式',
  settingGeos: '地理',
  settingPlatform: '平台',
  settingQps: 'QPS',
  settingBudget: '预算',
  budgetPerDayValue: '${amount}/天',
  size: '尺寸',
  reached: '触达',
  winPct: '赢率%',
  waste: '浪费',
};

export default value;
