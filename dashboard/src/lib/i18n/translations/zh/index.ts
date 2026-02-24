import type { PartialTranslations } from '../../types';

import ns_adminNav from './adminNav';
import ns_admin from './admin';
import ns_aiControl from './aiControl';
import ns_auth from './auth';
import ns_campaigns from './campaigns';
import ns_common from './common';
import ns_configPerformance from './configPerformance';
import ns_connect from './connect';
import ns_creatives from './creatives';
import ns_dashboard from './dashboard';
import ns_errors from './errors';
import ns_geo from './geo';
import ns_history from './history';
import ns_import from './import';
import ns_language from './language';
import ns_navigation from './navigation';
import ns_pretargeting from './pretargeting';
import ns_previewModal from './previewModal';
import ns_publishers from './publishers';
import ns_qpsNav from './qpsNav';
import ns_recommendations from './recommendations';
import ns_relativeTime from './relativeTime';
import ns_reports from './reports';
import ns_retentionPage from './retentionPage';
import ns_settings from './settings';
import ns_settingsNav from './settingsNav';
import ns_setup from './setup';
import ns_sidebar from './sidebar';
import ns_sizes from './sizes';
import ns_wasteAnalysis from './wasteAnalysis';

// Chinese locale scaffold. Missing keys intentionally fall back to English via deep merge.
export const zh: PartialTranslations = {
  common: ns_common,
  campaigns: ns_campaigns,
  aiControl: ns_aiControl,
  configPerformance: ns_configPerformance,
  connect: ns_connect,
  creatives: ns_creatives,
  geo: ns_geo,
  relativeTime: ns_relativeTime,
  navigation: ns_navigation,
  pretargeting: ns_pretargeting,
  previewModal: ns_previewModal,
  publishers: ns_publishers,
  qpsNav: ns_qpsNav,
  recommendations: ns_recommendations,
  reports: ns_reports,
  settingsNav: ns_settingsNav,
  setup: ns_setup,
  sizes: ns_sizes,
  adminNav: ns_adminNav,
  admin: ns_admin,
  sidebar: ns_sidebar,
  auth: ns_auth,
  dashboard: ns_dashboard,
  errors: ns_errors,
  history: ns_history,
  import: ns_import,
  language: ns_language,
  retentionPage: ns_retentionPage,
  settings: ns_settings,
  wasteAnalysis: ns_wasteAnalysis,
};
