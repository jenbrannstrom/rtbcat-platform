import type { PartialTranslations } from '../../types';

import ns_common from './common';
import ns_relativeTime from './relativeTime';
import ns_navigation from './navigation';
import ns_qpsNav from './qpsNav';
import ns_settingsNav from './settingsNav';
import ns_adminNav from './adminNav';
import ns_sidebar from './sidebar';
import ns_auth from './auth';
import ns_dashboard from './dashboard';
import ns_publishers from './publishers';
import ns_sizes from './sizes';
import ns_geo from './geo';
import ns_pretargeting from './pretargeting';
import ns_import from './import';
import ns_setup from './setup';
import ns_campaigns from './campaigns';
import ns_creatives from './creatives';
import ns_admin from './admin';
import ns_recommendations from './recommendations';
import ns_errors from './errors';
import ns_reports from './reports';
import ns_settings from './settings';
import ns_retentionPage from './retentionPage';
import ns_history from './history';
import ns_connect from './connect';
import ns_aiControl from './aiControl';
import ns_configPerformance from './configPerformance';
import ns_wasteAnalysis from './wasteAnalysis';
import ns_previewModal from './previewModal';
import ns_language from './language';

// Danish locale. Missing keys fall back to English via deep merge.
export const da: PartialTranslations = {
  common: ns_common,
  relativeTime: ns_relativeTime,
  navigation: ns_navigation,
  qpsNav: ns_qpsNav,
  settingsNav: ns_settingsNav,
  adminNav: ns_adminNav,
  sidebar: ns_sidebar,
  auth: ns_auth,
  dashboard: ns_dashboard,
  publishers: ns_publishers,
  sizes: ns_sizes,
  geo: ns_geo,
  pretargeting: ns_pretargeting,
  import: ns_import,
  setup: ns_setup,
  campaigns: ns_campaigns,
  creatives: ns_creatives,
  admin: ns_admin,
  recommendations: ns_recommendations,
  errors: ns_errors,
  reports: ns_reports,
  settings: ns_settings,
  retentionPage: ns_retentionPage,
  history: ns_history,
  connect: ns_connect,
  aiControl: ns_aiControl,
  configPerformance: ns_configPerformance,
  wasteAnalysis: ns_wasteAnalysis,
  previewModal: ns_previewModal,
  language: ns_language,
};
