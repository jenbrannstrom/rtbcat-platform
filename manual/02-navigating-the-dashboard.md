# Chapter 2: Navigating the Dashboard

*Audience: everyone*

## Sidebar layout

The sidebar is the primary navigation. It is organised around the two jobs
Cat-Scan does: cutting bidstream waste, and keeping the creative library
healthy. Configuration sits in a third group pinned to the bottom of the rail.

```
Seat card (name · creative count · last sync · switch seat · sync)

OPTIMIZE
 ├── QPS Overview              /               (home)
 ├── Publisher QPS             /qps/publisher
 ├── Geo QPS                   /qps/geo
 ├── Size QPS                  /qps/size
 └── Pretargeting History      /history

CREATIVES
 ├── Library                   /creatives
 ├── Clusters                  /campaigns
 ├── Audits ▸
 │    ├── Click Macros         /creatives/click-macros
 │    ├── Language Flags       /creatives/language-flags
 │    └── Attribution Readiness /creatives/attribution-readiness
 └── Import                    /import

SYSTEM  (pinned to the bottom)
 ├── Settings ▸  [seat admin]  /settings
 │    ├── Connected Accounts   /settings/accounts
 │    ├── Data Retention       /settings/retention
 │    └── System Status        /settings/system
 └── Administration ▸  [sudo]  /admin
      ├── Users                /admin/users
      ├── Agent Tokens         /admin/agent-tokens
      ├── Configuration        /admin/configuration
      └── Audit Log            /admin/audit-log

Footer: account menu (docs, logout) · language · version · collapse
```

### How rows behave

- Every row with a chevron (▸) can be opened or closed. Clicking the **label**
  navigates to that section's index page; clicking the **chevron** toggles the
  list. Audits has no index page, so its label toggles the list.
- Only one expandable row is open at a time. Navigating to a page inside a
  group opens that group and closes the others. Nothing about expansion is
  remembered between visits.
- The highlighted row is always the page you are on. On a sub-page (for
  example Connected Accounts) only that sub-page is highlighted; its parent
  row is shown in darker text to mark the group.
- The small tag next to Settings and Administration names the permission that
  unlocks the group. Users without that permission do not see the row.

### Collapsed rail

Click the ‹ chevron in the footer to collapse the sidebar to icons. The
preference is remembered across sessions. In the collapsed rail:

- Each icon shows its label on hover.
- Audits, Settings and Administration open a small flyout with their sub-pages.
- The seat initial opens the seat switcher.
- The avatar opens the account menu.

### Seat card

The card under the logo shows the selected seat, its creative count and when it
was last synced. If you have access to more than one seat (or you are a sudo
user, who can also pick **All Seats**), click the card to switch. Seat admins
see a small sync icon on the card; it runs **Sync All** (creatives, endpoints
and pretargeting configs) and reports the result underneath.

## Restricted users

Some accounts are marked as "restricted" by an administrator. Restricted users
see the QPS Overview only; every other route redirects to it.

## The setup checklist

The setup checklist at `/setup` walks new accounts through initial
configuration. It is reachable from **Settings → Setup checklist**:

1. Connect buyer accounts (upload GCP credentials, discover seats)
2. Validate data health (check that CSV imports are arriving)
3. Register an optimizer model (BYOM endpoint)
4. Validate the model endpoint (test call)
5. Set hosting cost baseline (for economics calculations)
6. Connect a conversion source (pixel or webhook)

Completion percentage is tracked. Each step links to the relevant settings page.

## Language support

Cat-Scan ships eleven interface languages: English, Spanish, French, Polish,
Chinese (Simplified), Russian, Ukrainian, Danish, Dutch, Hebrew and Arabic. The
language flag in the sidebar footer switches between them. Any string that has
not yet been translated falls back to English. Your preference is saved per
user.

## Next steps

- Media buyers: start with [Understanding Your QPS Funnel](03-qps-funnel.md)
- DevOps: start with [Architecture Overview](11-architecture.md)
