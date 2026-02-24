import type { PartialTranslations } from '../../types';

const value: PartialTranslations['aiControl'] = {
  aiModeLabel: 'AI 模式：',
  title: 'AI 控制设置',
  manualOnly: '仅手动',
  manualShort: '手动',
  manualDescription: '所有更改都由我手动完成',
  aiProposes: 'AI 提议',
  aiShort: 'AI',
  assistedDescription: 'AI 提建议，我来审批',
  autoOptimize: '自动优化',
  autoShort: '自动',
  autonomousDescription: 'AI 在限制范围内自动优化',
  comingSoon: '即将推出',
  assistedHint:
    'AI 会分析你的数据并提出优化建议。每项变更在应用前都由你审核并批准。',
};

export default value;
