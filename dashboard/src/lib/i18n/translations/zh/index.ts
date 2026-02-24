import type { PartialTranslations } from '../../types';

import ns_adminNav from './adminNav';
import ns_auth from './auth';
import ns_common from './common';
import ns_dashboard from './dashboard';
import ns_errors from './errors';
import ns_import from './import';
import ns_language from './language';
import ns_navigation from './navigation';
import ns_pretargeting from './pretargeting';
import ns_qpsNav from './qpsNav';
import ns_relativeTime from './relativeTime';
import ns_settingsNav from './settingsNav';
import ns_sidebar from './sidebar';

// Chinese locale scaffold. Missing keys intentionally fall back to English via deep merge.
export const zh: PartialTranslations = {
  common: ns_common,
  relativeTime: ns_relativeTime,
  navigation: ns_navigation,
  pretargeting: ns_pretargeting,
  qpsNav: ns_qpsNav,
  settingsNav: ns_settingsNav,
  adminNav: ns_adminNav,
  sidebar: ns_sidebar,
  auth: ns_auth,
  dashboard: ns_dashboard,
  errors: ns_errors,
  import: ns_import,
  language: ns_language,
};
