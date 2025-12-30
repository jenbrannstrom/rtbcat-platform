# Internationalization (i18n) Implementation Plan

## Overview

Add language support to the Cat-Scan Dashboard with:
- English (EN) as the initial and default language
- A language dropdown selector in the sidebar
- Full UI refactoring to support dynamic language switching

## Technology Stack (Current)

- **Next.js 16.0.5** with React 19.2.0
- **TypeScript 5.9.3**
- **Tailwind CSS 3.4.15**
- **React Context** for client state

## Chosen Approach: React Context + Custom i18n

Since the user wants a simple, maintainable solution for now (English only with future extensibility), we'll implement a **lightweight custom i18n system** using React Context rather than a heavy library. This provides:

1. Zero additional dependencies
2. Full TypeScript support with type-safe translation keys
3. Easy to extend with more languages later
4. Client-side language switching
5. LocalStorage persistence for language preference

---

## Implementation Steps

### Phase 1: i18n Infrastructure

#### Step 1.1: Create Translation Types and Structure
Create `/dashboard/src/lib/i18n/types.ts`:
- Define TranslationKeys type
- Define Language type ('en' | 'es' | 'de' | 'sv' etc.)
- Export translation structure interface

#### Step 1.2: Create English Translations
Create `/dashboard/src/lib/i18n/translations/en.ts`:
- Navigation strings (sidebar)
- Authentication strings (login page)
- Dashboard strings (waste optimizer)
- Common UI strings (buttons, labels, status)
- Admin strings
- Campaign/Creative strings
- Import/Settings strings
- Error messages

#### Step 1.3: Create i18n Context
Create `/dashboard/src/contexts/i18n-context.tsx`:
- LanguageProvider component
- useTranslation hook (returns t() function)
- useLanguage hook (returns current language + setter)
- Persist language preference to localStorage

#### Step 1.4: Create Language Selector Component
Create `/dashboard/src/components/language-selector.tsx`:
- Dropdown with flag icons or language codes
- Uses useLanguage hook
- Compact design for sidebar placement

---

### Phase 2: Provider Integration

#### Step 2.1: Add LanguageProvider to App
Update `/dashboard/src/app/providers.tsx`:
- Wrap existing providers with LanguageProvider
- Ensure it's high enough in tree for all components

---

### Phase 3: Migrate UI Components

#### Step 3.1: Sidebar (Primary Navigation)
Update `/dashboard/src/components/sidebar.tsx`:
- Replace all hardcoded strings with t() calls
- Add language selector to sidebar footer
- Translate: menu items, sync messages, tooltips

#### Step 3.2: Login Page
Update `/dashboard/src/app/login/page.tsx`:
- Replace form labels, button text, error messages

#### Step 3.3: Authenticated Layout
Update `/dashboard/src/components/authenticated-layout.tsx`:
- Replace loading/redirect messages

#### Step 3.4: Main Dashboard (Waste Optimizer)
Update `/dashboard/src/app/page.tsx`:
- Replace all dashboard strings (~100+ strings)
- Section headers, tooltips, metrics labels

#### Step 3.5: Campaigns Page
Update `/dashboard/src/app/campaigns/page.tsx`:
- Campaign management labels
- Drag-drop instructions
- Filter/sort labels

#### Step 3.6: Creatives Page
Update `/dashboard/src/app/creatives/page.tsx`:
- Sort options, filter labels
- Format names, status labels

#### Step 3.7: Import Page
Update `/dashboard/src/app/import/page.tsx`:
- Upload instructions
- Status messages
- Error messages

#### Step 3.8: Admin Pages
Update `/dashboard/src/app/admin/` pages:
- Admin dashboard labels
- User management strings
- Settings labels

#### Step 3.9: Settings Pages
Update `/dashboard/src/app/settings/` pages:
- Configuration labels
- Status indicators

#### Step 3.10: Other Pages
- History page
- Connect page
- Waste analysis page
- Setup page

#### Step 3.11: Shared Components
Update components in `/dashboard/src/components/`:
- error.tsx
- loading.tsx
- RTB components
- Campaign components
- QPS components
- Recommendation components

---

### Phase 4: Number/Date Formatting

#### Step 4.1: Update formatNumber utility
Update `/dashboard/src/lib/utils.ts`:
- Make number formatting locale-aware
- Use Intl.NumberFormat where appropriate

#### Step 4.2: Update relative time formatting
- Make "Just now", "m ago", "h ago" translatable

---

## File Changes Summary

### New Files:
1. `/dashboard/src/lib/i18n/types.ts`
2. `/dashboard/src/lib/i18n/translations/en.ts`
3. `/dashboard/src/lib/i18n/index.ts`
4. `/dashboard/src/contexts/i18n-context.tsx`
5. `/dashboard/src/components/language-selector.tsx`

### Modified Files:
1. `/dashboard/src/app/providers.tsx`
2. `/dashboard/src/components/sidebar.tsx`
3. `/dashboard/src/app/login/page.tsx`
4. `/dashboard/src/components/authenticated-layout.tsx`
5. `/dashboard/src/app/page.tsx`
6. `/dashboard/src/app/campaigns/page.tsx`
7. `/dashboard/src/app/creatives/page.tsx`
8. `/dashboard/src/app/import/page.tsx`
9. `/dashboard/src/app/admin/page.tsx`
10. `/dashboard/src/app/admin/users/page.tsx`
11. `/dashboard/src/app/admin/settings/page.tsx`
12. `/dashboard/src/app/admin/audit-log/page.tsx`
13. `/dashboard/src/app/settings/page.tsx`
14. `/dashboard/src/app/settings/retention/page.tsx`
15. `/dashboard/src/app/settings/seats/page.tsx`
16. `/dashboard/src/app/history/page.tsx`
17. `/dashboard/src/app/connect/page.tsx`
18. `/dashboard/src/app/waste-analysis/page.tsx`
19. `/dashboard/src/app/setup/page.tsx`
20. `/dashboard/src/components/error.tsx`
21. `/dashboard/src/components/loading.tsx`
22. Various component files as needed

---

## Translation Structure

```typescript
// translations/en.ts structure
export const en = {
  common: {
    loading: "Loading...",
    error: "Error",
    save: "Save",
    cancel: "Cancel",
    delete: "Delete",
    edit: "Edit",
    create: "Create",
    search: "Search",
    filter: "Filter",
    refresh: "Refresh",
    // ...
  },
  navigation: {
    wasteOptimizer: "Waste Optimizer",
    creatives: "Creatives",
    campaigns: "Campaigns",
    changeHistory: "Change History",
    import: "Import",
    setup: "Setup",
    admin: "Admin",
    docs: "Docs",
    logout: "Logout",
    collapse: "Collapse",
    // ...
  },
  auth: {
    signIn: "Sign in to your account",
    email: "Email address",
    password: "Password",
    loginFailed: "Login failed. Please check your credentials.",
    // ...
  },
  dashboard: {
    title: "Waste Optimizer",
    subtitle: "Understand your RTB funnel and optimize QPS waste",
    rtbFunnel: "The RTB Funnel",
    // ...
  },
  // ... more namespaces
}
```

---

## Language Selector Design

The language selector will be a small dropdown in the sidebar footer:
- Shows current language code (EN, ES, DE, SV)
- Dropdown with available languages
- Persists to localStorage
- Triggers immediate UI re-render on change

---

## Future Extensibility

This architecture easily supports:
1. Adding new languages (just create new translation file)
2. Server-side language detection
3. URL-based language routing if needed
4. Integration with professional translation services
5. RTL support (Arabic, Hebrew) by adding dir="rtl" conditionally

---

## Estimated Scope

- ~300-400 translation strings for English
- ~20-25 files to modify
- Incremental migration approach (start with sidebar, then expand)
