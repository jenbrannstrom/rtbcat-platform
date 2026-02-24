import type { PartialTranslations } from '../../types';

const value: PartialTranslations['history'] = {
  title: '变更历史',
  changeHistory: '变更历史',
  trackAndRollback: '跟踪并回滚预定向配置变更',
  noChanges: '没有记录的变更',
  noChangesFound: '未找到变更',
  tryAdjustingFilters: '请尝试调整筛选条件。',
  changesWillAppear: '配置变更会显示在这里。',
  change: '变更',
  user: '用户',
  timestamp: '时间戳',
  export: '导出',
  filters: '筛选：',
  period: '时间范围：',
  lastDays: '最近 {count} 天',
  config: '配置：',
  allConfigs: '所有配置',
  type: '类型：',
  allTypes: '所有类型',
  clearFilters: '清除筛选',
  showingChanges: '显示最近 {days} 天内的 {count} 条变更',
  showingChangesPlural: '显示最近 {days} 天内的 {count} 条变更',
  rollback: '回滚',
  rollbackChange: '回滚变更',
  aboutToRollback: '你即将回滚：',
  field: '字段：',
  current: '当前值：',
  restoreTo: '恢复为：',
  empty: '（空）',
  rollbackWarning:
    '这会恢复到之前的设置。你仍需在 Google Authorized Buyers 中手动应用该变更。',
  noSnapshotAvailableForChange:
    '该变更没有可用快照。回滚需要推送前自动创建的快照。较早的变更可能没有快照。',
  previewingRollback: '正在预览回滚…',
  failedToPreviewRollback: '预览回滚失败',
  noDifferencesFoundBetweenCurrentAndSnapshot:
    '当前配置与快照之间未发现差异。配置可能已经被修改。',
  changesWillBeReversedOnGoogle: '这些变更将在 Google 中被撤销：',
  rollbackPushesToGoogleImmediately:
    '这会立即推送到 Google。历史中会记录一条新的“ROLLBACK”记录。',
  reasonForRollback: '回滚原因',
  whyRollingBack: '你为什么要回滚该变更？',
  cancel: '取消',
  rollbackNow: '立即回滚',
  on: '在',
  value: '值：',
  manual: '手动',
  daysAgo: '天前',
  hoursAgo: '小时前',
  minutesAgo: '分钟前',
  justNow: '刚刚',
  rollbackFailed: '回滚失败',
};

export default value;

