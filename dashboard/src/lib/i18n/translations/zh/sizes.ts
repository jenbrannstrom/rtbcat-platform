import type { PartialTranslations } from '../../types';

const value: PartialTranslations['sizes'] = {
  title: '尺寸分析',
  subtitle: '哪些尺寸能转化为展示？',
  coverage: '覆盖率',
  requests: '请求',
  trafficDistribution: '流量分布',
  creatives: '创意',
  noCreative: '无创意',
  ads: '广告',
  noCreativesForSizes: '{count} 个尺寸没有创意',
  receivingTrafficNoCreatives:
    '你正在接收这些尺寸的流量，但没有可投放的创意。请添加创意，或从预定向中移除这些尺寸。',
  copySizes: '复制尺寸',
  noSizeDataAvailable: '尺寸数据不可用',
  importCsvWithSize:
    '导入一个以 Creative size 为第一维度的 CSV 以查看尺寸明细。',
  util: '利用率',
};

export default value;
