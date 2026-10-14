import type { PartialTranslations } from '../../types';

// Keys not listed here fall back to English (see withEnglishFallback).
// TODO(i18n): translate the Optimize / Creatives / System group labels and
// the new row labels added in the 2026-10 sidebar rebuild.
const value: PartialTranslations['navigation'] = {
  import: '导入',
  admin: '管理',
  docs: '文档',
  logout: '退出登录',
  collapse: '收起',
  expand: '展开',
  settings: '设置',
};

export default value;
