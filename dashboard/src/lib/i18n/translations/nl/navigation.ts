import type { PartialTranslations } from '../../types';

// Keys not listed here fall back to English (see withEnglishFallback).
// TODO(i18n): translate the Optimize / Creatives / System group labels and
// the new row labels added in the 2026-10 sidebar rebuild.
const value: PartialTranslations['navigation'] = {
  import: 'Import',
  admin: 'Administratie',
  docs: 'Docs',
  logout: 'Uitloggen',
  collapse: 'Inklappen',
  expand: 'Uitklappen',
  settings: 'Instellingen',
};

export default value;
