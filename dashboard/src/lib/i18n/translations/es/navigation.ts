import type { PartialTranslations } from '../../types';

// Keys not listed here fall back to English (see withEnglishFallback).
// TODO(i18n): translate the Optimize / Creatives / System group labels and
// the new row labels added in the 2026-10 sidebar rebuild.
const value: PartialTranslations['navigation'] = {
  import: 'Importar',
  admin: 'Administración',
  docs: 'Docs',
  logout: 'Cerrar sesión',
  collapse: 'Colapsar',
  expand: 'Expandir',
  settings: 'Ajustes',
};

export default value;
