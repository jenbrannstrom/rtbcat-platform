import type { PartialTranslations } from '../../types';

// Keys not listed here fall back to English (see withEnglishFallback).
// TODO(i18n): translate the Optimize / Creatives / System group labels and
// the new row labels added in the 2026-10 sidebar rebuild.
const value: PartialTranslations['navigation'] = {
  import: 'Импорт',
  admin: 'Администрирование',
  docs: 'Документация',
  logout: 'Выход',
  collapse: 'Свернуть',
  expand: 'Развернуть',
  settings: 'Настройки',
};

export default value;
