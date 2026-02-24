import type { PartialTranslations } from '../../types';

const value: PartialTranslations['retentionPage'] = {
  title: '数据保留设置',
  subtitle: '配置性能数据保留时长。',
  saveSuccess: '保留设置保存成功。',
  saveFailed: '保存保留设置失败。',
  runCompleted:
    '保留任务已完成：聚合 {aggregatedRows} 行，删除 {deletedRawRows} 行原始数据。',
  runFailed: '执行保留任务失败。',
  currentStorage: '当前存储',
  rawPerformanceRows: '原始性能行数',
  dailySummaryRows: '每日汇总行数',
  dateRangeSpan: '{start} 到 {end}',
  keepDetailedDataFor: '详细数据保留：',
  keepDailySummariesFor: '每日汇总保留：',
  autoAggregateAfter: '自动聚合时间：',
  option7Days: '7 天',
  option14Days: '14 天',
  option30Days: '30 天',
  option30DaysRecommended: '30 天（推荐）',
  option60Days: '60 天',
  option90DaysRecommended: '90 天（推荐）',
  option180Days: '180 天',
  option1Year: '1 年',
  option6Months: '6 个月',
  option1YearRecommended: '1 年（推荐）',
  option2Years: '2 年',
  optionForever: '永久',
  detailedDataHelp:
    '详细数据按应用、国家和创意显示性能。超过该周期后，数据会聚合为每日汇总。',
  summaryDataHelp: '汇总显示每个创意每日总量，适合趋势分析。',
  autoAggregateHelp: '删除前先为超过该时长的数据创建汇总。',
  warningIrreversible: '缩短保留期会永久删除旧数据，无法撤销。',
  howItWorks: '工作原理：',
  howItWorksItem1: '详细行会聚合到每日汇总',
  howItWorksItem2: '汇总会保留每个创意/每天的总指标',
  howItWorksItem3: '聚合后，详细行会被删除',
  howItWorksItem4: '这会显著减少存储需求',
  saving: '保存中...',
  saveSettings: '保存设置',
  running: '运行中...',
  runRetentionJobNow: '立即运行保留任务',
};

export default value;

