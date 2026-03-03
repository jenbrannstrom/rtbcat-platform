# Chapter 2: Navigating the Dashboard

*Audience: everyone*

## Sidebar layout

The sidebar is your primary navigation. It can be collapsed (icon-only mode)
or expanded. Your preference is remembered across sessions.

```
Seat Selector
 ├── QPS Waste Optimizer         /              (home)
 ├── Creatives                   /creatives
 ├── Campaigns                   /campaigns
 ├── Change History              /history
 ├── Import                      /import
 │
 ├── QPS (expandable)
 │   ├── Publisher                /qps/publisher
 │   ├── Geo                     /qps/geo
 │   └── Size                    /qps/size
 │
 ├── Settings (expandable)
 │   ├── Connected Accounts      /settings/accounts
 │   ├── Data Retention          /settings/retention
 │   └── System Status           /settings/system
 │
 ├── Admin (sudo users only)
 │   ├── Users                   /admin/users
 │   ├── Configuration           /admin/configuration
 │   └── Audit Log               /admin/audit-log
 │
 └── Footer: user email, version, docs link
```

Sections auto-expand when you navigate into them.

## Restricted users

Some accounts are marked as "restricted" by an administrator. Restricted users
see only the core pages: home, creatives, campaigns, import, and history. The
QPS analysis, settings, and admin sections are hidden.

## The setup checklist

New accounts see a setup checklist at `/setup` that walks through initial
configuration:

1. Connect buyer accounts (upload GCP credentials, discover seats)
2. Validate data health (check that CSV imports are arriving)
3. Register an optimizer model (BYOM endpoint)
4. Validate the model endpoint (test call)
5. Set hosting cost baseline (for economics calculations)
6. Connect a conversion source (pixel or webhook)

Completion percentage is tracked. Each step links to the relevant settings page.

## Language support

Cat-Scan supports English, Dutch, and Chinese (Simplified). The language
selector is in the sidebar. Your preference is saved per-user.

## Next steps

- Media buyers: start with [Understanding Your QPS Funnel](03-qps-funnel.md)
- DevOps: start with [Architecture Overview](11-architecture.md)
