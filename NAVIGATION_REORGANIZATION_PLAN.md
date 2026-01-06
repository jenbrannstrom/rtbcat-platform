# Navigation Reorganization Plan: Settings & Admin

## Current State Analysis

### Problems with Current Structure

1. **Overlapping Concerns**: "Settings" and "Admin > Settings" create confusion
   - `/settings` - General settings (seats, retention)
   - `/admin/settings` - System settings (multi-user mode, audit retention)

2. **Inconsistent Hierarchy**:
   - `/setup` exists as top-level (initial configuration/onboarding)
   - `/connect` is accessed from settings but isn't under /settings
   - Admin has sub-pages but Settings navigation is less discoverable

3. **Poor Discoverability**:
   - Settings sub-pages (seats, retention) are only accessible from the settings hub
   - No sidebar sub-navigation for Settings section
   - Users must know to click into Settings to find sub-options

4. **Mixed Purposes in Settings**:
   - System status/health checks (operational)
   - Database stats (informational)
   - Video thumbnail management (operational)
   - Seat management (account configuration)
   - Data retention (policy configuration)
   - API credentials/Connect (integrations)

### Current Navigation Tree
```
/                     - Waste Optimizer (Dashboard)
/creatives            - Creatives
/campaigns            - Campaigns
/history              - Change History
/import               - Import
/setup                - Setup (onboarding)
/connect              - API Credentials (disconnected from hierarchy)
/settings             - Settings Hub
  /settings/seats     - Buyer Seats
  /settings/retention - Data Retention
/admin                - Admin Dashboard (admin-only)
  /admin/users        - User Management
  /admin/settings     - System Settings
  /admin/audit-log    - Audit Log
```

---

## Proposed Reorganization

### Option A: Unified Settings with Sections (Recommended)

Consolidate all configuration into a single **Settings** section with clear sub-categories:

```
/                       - Waste Optimizer (Dashboard)
/creatives              - Creatives
/campaigns              - Campaigns
/history                - Change History
/import                 - Import

/settings               - Settings (with sidebar sub-nav)
  /settings/accounts    - Connected Accounts (renamed from /connect)
  /settings/seats       - Buyer Seats
  /settings/retention   - Data Retention
  /settings/system      - System Status & Health

/admin                  - Administration (admin-only, with sidebar sub-nav)
  /admin/users          - User Management
  /admin/configuration  - System Configuration (renamed from /admin/settings)
  /admin/audit-log      - Audit Log
```

**Key Changes:**
1. Move `/connect` to `/settings/accounts` for logical grouping
2. Rename `/admin/settings` to `/admin/configuration` to avoid "Settings > Settings" confusion
3. Remove `/setup` as top-level (merge into onboarding flow or make it a modal/wizard)
4. Add sidebar sub-navigation for both Settings and Admin sections

**Pros:**
- Clear separation: Settings = user/account config, Admin = system/user management
- No naming conflicts
- Discoverable sub-pages via sidebar
- Follows common SaaS patterns (Stripe, Notion, Linear)

**Cons:**
- Requires moving /connect route (potential bookmark breakage)
- More extensive sidebar changes

---

### Option B: Minimal Restructure

Keep current routes but improve navigation clarity:

```
/                       - Waste Optimizer (Dashboard)
/creatives              - Creatives
/campaigns              - Campaigns
/history                - Change History
/import                 - Import
/setup                  - Setup

/settings               - Account Settings (rename in nav)
  /settings/accounts    - Connected Accounts (move /connect here)
  /settings/seats       - Buyer Seats
  /settings/retention   - Data Retention

/admin                  - Administration (admin-only)
  /admin/users          - Users
  /admin/system         - System Settings (rename for clarity)
  /admin/audit-log      - Audit Log
```

**Key Changes:**
1. Rename sidebar labels for clarity (not URLs)
2. Move /connect to /settings/accounts
3. Rename /admin/settings to /admin/system in UI

**Pros:**
- Minimal route changes
- Quick to implement

**Cons:**
- Still has /setup floating at top level
- Less comprehensive reorganization

---

### Option C: Feature-Grouped Navigation

Group by feature area rather than settings/admin split:

```
/                       - Dashboard
/creatives              - Creatives
/campaigns              - Campaigns
/history                - Change History
/import                 - Import

/account                - Account & Billing
  /account/seats        - Buyer Seats
  /account/connections  - Connected Accounts (API credentials)

/preferences            - Preferences
  /preferences/retention - Data Retention
  /preferences/display   - Display Settings (future)

/admin                  - Administration (admin-only)
  /admin/users          - User Management
  /admin/system         - System Configuration
  /admin/audit-log      - Audit Log
  /admin/health         - System Health & Status
```

**Pros:**
- Very clear mental model
- Scales well for future features

**Cons:**
- Most disruptive change
- May be over-engineered for current scope

---

## Recommendation: Option A

Option A provides the best balance of:
- **Clarity**: Clear Settings vs Admin distinction
- **Discoverability**: Sidebar sub-navigation
- **Best Practices**: Follows patterns from successful SaaS products
- **Scalability**: Easy to add new settings/admin pages

---

## Implementation Plan

### Phase 1: Navigation Component Updates

1. **Update Sidebar Component** (`dashboard/src/components/sidebar.tsx`)
   - Add expandable sections for Settings and Admin
   - Show sub-items when section is active or expanded
   - Add chevron indicators for sections with children

2. **Update Navigation Items Array**
   ```typescript
   const navigationItems = [
     { key: "wasteOptimizer", href: "/", icon: TrendingDown },
     { key: "creatives", href: "/creatives", icon: Image },
     { key: "campaigns", href: "/campaigns", icon: FolderKanban },
     { key: "changeHistory", href: "/history", icon: History },
     { key: "import", href: "/import", icon: RefreshCw },
     {
       key: "settings",
       href: "/settings",
       icon: Settings,
       children: [
         { key: "accounts", href: "/settings/accounts" },
         { key: "seats", href: "/settings/seats" },
         { key: "retention", href: "/settings/retention" },
         { key: "system", href: "/settings/system" },
       ]
     },
   ];

   // Admin items (shown separately, admin-only)
   const adminItems = [
     {
       key: "admin",
       href: "/admin",
       icon: Shield,
       children: [
         { key: "users", href: "/admin/users" },
         { key: "configuration", href: "/admin/configuration" },
         { key: "auditLog", href: "/admin/audit-log" },
       ]
     }
   ];
   ```

### Phase 2: Route Changes

1. **Move /connect to /settings/accounts**
   - Create `/dashboard/src/app/settings/accounts/page.tsx`
   - Copy content from `/dashboard/src/app/connect/page.tsx`
   - Add redirect from `/connect` to `/settings/accounts` for backwards compatibility

2. **Rename /admin/settings to /admin/configuration**
   - Rename folder from `admin/settings` to `admin/configuration`
   - Update all internal links

3. **Create /settings/system page**
   - Extract system status content from main settings page
   - Include: API status, system health, database stats

4. **Update main /settings page**
   - Convert to a hub/overview page with cards linking to sub-sections
   - Remove detailed content (moved to sub-pages)

### Phase 3: Handle /setup

**Option 3a**: Remove from nav, keep as onboarding-only route
- Only show /setup link when account is not fully configured
- After setup complete, hide from navigation

**Option 3b**: Merge into /settings/accounts
- Setup is essentially "connect your first account"
- Make it part of the accounts page with empty state

**Recommendation**: Option 3a - keeps setup as a guided onboarding flow

### Phase 4: Translation Updates

Update `/dashboard/src/lib/i18n/translations/en.ts`:

```typescript
navigation: {
  wasteOptimizer: 'Waste Optimizer',
  creatives: 'Creatives',
  campaigns: 'Campaigns',
  changeHistory: 'Change History',
  import: 'Import',
  settings: 'Settings',
  admin: 'Administration',
  // ... sub-items
},
settings: {
  title: 'Settings',
  accounts: 'Connected Accounts',
  seats: 'Buyer Seats',
  retention: 'Data Retention',
  system: 'System Status',
},
admin: {
  title: 'Administration',
  users: 'Users',
  configuration: 'Configuration',
  auditLog: 'Audit Log',
}
```

### Phase 5: UI Polish

1. Add section headers in sidebar for collapsed state
2. Ensure active state highlights work for nested routes
3. Add breadcrumbs to sub-pages for context
4. Test responsive/mobile navigation

---

## Visual Mockup: New Sidebar Structure

```
+----------------------------------+
|  [Logo] RTBcat                   |
+----------------------------------+
|  Seat Selector Dropdown          |
+----------------------------------+
|                                  |
|  Waste Optimizer        [icon]   |
|  Creatives              [icon]   |
|  Campaigns              [icon]   |
|  Change History         [icon]   |
|  Import                 [icon]   |
|                                  |
+----------------------------------+
|  SETTINGS               [v]      |
|    Connected Accounts            |
|    Buyer Seats                   |
|    Data Retention                |
|    System Status                 |
+----------------------------------+
|  ADMINISTRATION         [v]      |  <- Admin only
|    Users                         |
|    Configuration                 |
|    Audit Log                     |
+----------------------------------+
|  [Docs]  [Logout]  [Collapse]    |
+----------------------------------+
```

---

## Migration Checklist

- [ ] Create new route structure
- [ ] Update sidebar component with nested navigation
- [ ] Move /connect content to /settings/accounts
- [ ] Add redirect from /connect to /settings/accounts
- [ ] Rename /admin/settings to /admin/configuration
- [ ] Create /settings/system page
- [ ] Update /settings hub page
- [ ] Update translations
- [ ] Handle /setup visibility logic
- [ ] Update any hardcoded links throughout the app
- [ ] Test all navigation paths
- [ ] Update any documentation referencing old routes

---

## Best Practices Referenced

1. **Stripe Dashboard**: Settings contains account-level config, separate admin for team management
2. **Notion**: Settings for personal/workspace, Admin for workspace-wide policies
3. **Linear**: Settings grouped by category with clear sidebar navigation
4. **GitHub**: Settings vs Admin (for org admins) pattern

All follow the principle: **Settings = "my stuff", Admin = "everyone's stuff"**
