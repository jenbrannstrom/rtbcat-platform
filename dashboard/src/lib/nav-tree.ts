/**
 * Declarative sidebar navigation tree.
 *
 * The tree is pure data so it can be unit-tested per role without rendering.
 * Labels are translation-key paths resolved by the sidebar at render time;
 * icons are lucide components (plain objects, safe to import in node tests).
 *
 * Three groups:
 *   optimize  - bidstream waste work (QPS overview, QPS breakdowns, pretargeting history)
 *   creatives - creative library health (library, clusters, audits, import)
 *   system    - configuration, pinned to the bottom, gated by permission
 */

import type { LucideIcon } from "lucide-react";
import {
  ClipboardCheck,
  Gauge,
  History,
  Image,
  KeyRound,
  Languages,
  Layers,
  Link2,
  Map,
  MousePointerClick,
  Newspaper,
  Ruler,
  ScrollText,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Target,
  Clock,
  Activity,
  Upload,
  Users,
} from "lucide-react";

export type NavGroupKey = "optimize" | "creatives" | "system";

export type NavMatch = "exact" | "prefix";

export interface NavLeaf {
  kind: "leaf";
  key: string;
  /** Dot path into the translations object, e.g. "navigation.overview". */
  labelKey: string;
  href: string;
  /** Extra paths that also count as this item (route aliases). */
  aliases?: string[];
  icon: LucideIcon;
  match: NavMatch;
  /** Prefix the href with the selected buyer id (see buyer-routes). */
  buyerScoped: boolean;
}

export interface NavParent {
  kind: "parent";
  key: string;
  labelKey: string;
  /** Index page the label navigates to; omitted when the row is a pure toggle. */
  href?: string;
  icon: LucideIcon;
  children: NavLeaf[];
  /** Short permission tag shown next to the label (translation key path). */
  tagKey?: string;
}

export type NavItem = NavLeaf | NavParent;

export interface NavGroup {
  key: NavGroupKey;
  labelKey: string;
  items: NavItem[];
}

export interface NavRoleFlags {
  /** Emergency restricted user: home only. */
  restricted: boolean;
  /** Sudo or admin on at least one seat. */
  hasSeatAdminAccess: boolean;
  isSudo: boolean;
}

export interface ActiveNav {
  /** Key of the highlighted leaf or parent, or null when nothing matches. */
  itemKey: string | null;
  /** Key of the parent whose child is active, or null. */
  parentKey: string | null;
  /** Group that contains the active item, or null. */
  groupKey: NavGroupKey | null;
}

function leaf(
  key: string,
  labelKey: string,
  href: string,
  icon: LucideIcon,
  options: { match?: NavMatch; buyerScoped?: boolean; aliases?: string[] } = {},
): NavLeaf {
  return {
    kind: "leaf",
    key,
    labelKey,
    href,
    icon,
    match: options.match ?? "prefix",
    buyerScoped: options.buyerScoped ?? true,
    aliases: options.aliases,
  };
}

const OPTIMIZE_ITEMS: NavItem[] = [
  leaf("overview", "navigation.overview", "/", Gauge, { match: "exact" }),
  leaf("publisherQps", "qpsNav.publisher", "/qps/publisher", Newspaper),
  leaf("geoQps", "qpsNav.geo", "/qps/geo", Map),
  leaf("sizeQps", "qpsNav.size", "/qps/size", Ruler),
  leaf("pretargetingHistory", "navigation.pretargetingHistory", "/history", History),
];

const CREATIVE_ITEMS: NavItem[] = [
  leaf("library", "navigation.library", "/creatives", Image, { match: "exact" }),
  leaf("clusters", "navigation.clusters", "/campaigns", Layers, { aliases: ["/clusters"] }),
  {
    kind: "parent",
    key: "audits",
    labelKey: "navigation.audits",
    icon: ClipboardCheck,
    children: [
      leaf("clickMacros", "navigation.clickMacros", "/creatives/click-macros", MousePointerClick),
      leaf("languageFlags", "navigation.languageFlags", "/creatives/language-flags", Languages),
      leaf(
        "attributionReadiness",
        "navigation.attributionReadiness",
        "/creatives/attribution-readiness",
        Target,
      ),
    ],
  },
  leaf("import", "navigation.import", "/import", Upload, { aliases: ["/uploads"] }),
];

const SETTINGS_PARENT: NavParent = {
  kind: "parent",
  key: "settings",
  labelKey: "navigation.settings",
  href: "/settings",
  icon: Settings,
  tagKey: "navigation.seatAdminTag",
  children: [
    leaf("connectedAccounts", "settingsNav.connectedAccounts", "/settings/accounts", Link2, {
      buyerScoped: false,
      aliases: ["/connect"],
    }),
    leaf("dataRetention", "settingsNav.dataRetention", "/settings/retention", Clock, {
      buyerScoped: false,
    }),
    leaf("systemStatus", "settingsNav.systemStatus", "/settings/system", Activity, {
      buyerScoped: false,
    }),
  ],
};

const ADMIN_PARENT: NavParent = {
  kind: "parent",
  key: "admin",
  labelKey: "navigation.admin",
  href: "/admin",
  icon: ShieldCheck,
  tagKey: "navigation.sudoTag",
  children: [
    leaf("users", "adminNav.users", "/admin/users", Users, { buyerScoped: false }),
    leaf("agentTokens", "adminNav.agentTokens", "/admin/agent-tokens", KeyRound, {
      buyerScoped: false,
    }),
    leaf("configuration", "adminNav.configuration", "/admin/configuration", SlidersHorizontal, {
      buyerScoped: false,
      aliases: ["/admin/settings"],
    }),
    leaf("auditLog", "adminNav.auditLog", "/admin/audit-log", ScrollText, { buyerScoped: false }),
  ],
};

/** Build the visible tree for a user. Groups with no visible items are omitted. */
export function buildNavTree(flags: NavRoleFlags): NavGroup[] {
  if (flags.restricted) {
    return [{ key: "optimize", labelKey: "navigation.groupOptimize", items: [OPTIMIZE_ITEMS[0]] }];
  }

  const system: NavItem[] = [];
  if (flags.hasSeatAdminAccess) system.push(SETTINGS_PARENT);
  if (flags.isSudo) system.push(ADMIN_PARENT);

  const groups: NavGroup[] = [
    { key: "optimize", labelKey: "navigation.groupOptimize", items: OPTIMIZE_ITEMS },
    { key: "creatives", labelKey: "navigation.groupCreatives", items: CREATIVE_ITEMS },
  ];
  if (system.length > 0) {
    groups.push({ key: "system", labelKey: "navigation.groupSystem", items: system });
  }
  return groups;
}

function pathMatches(path: string, href: string, match: NavMatch): boolean {
  if (match === "exact") return path === href;
  if (href === "/") return path === "/";
  return path === href || path.startsWith(`${href}/`);
}

export function leafMatches(path: string, item: NavLeaf): boolean {
  if (pathMatches(path, item.href, item.match)) return true;
  return (item.aliases ?? []).some((alias) => pathMatches(path, alias, item.match));
}

/**
 * Resolve which row is active for a buyer-stripped pathname.
 *
 * Leaves win over parents: on /settings/accounts the leaf is active and the
 * Settings parent is only its container; on /settings itself the parent is
 * active. At most one leaf and one parent are ever reported.
 */
export function resolveActiveNav(path: string, groups: NavGroup[]): ActiveNav {
  for (const group of groups) {
    for (const item of group.items) {
      if (item.kind === "leaf") {
        if (leafMatches(path, item)) {
          return { itemKey: item.key, parentKey: null, groupKey: group.key };
        }
        continue;
      }
      for (const child of item.children) {
        if (leafMatches(path, child)) {
          return { itemKey: child.key, parentKey: item.key, groupKey: group.key };
        }
      }
      if (item.href && path === item.href) {
        return { itemKey: item.key, parentKey: null, groupKey: group.key };
      }
    }
  }
  return { itemKey: null, parentKey: null, groupKey: null };
}

/** Walk a dot path like "qpsNav.publisher" through the translations object. */
export function readLabel(translations: unknown, labelKey: string): string {
  let node: unknown = translations;
  for (const segment of labelKey.split(".")) {
    if (node && typeof node === "object" && segment in (node as Record<string, unknown>)) {
      node = (node as Record<string, unknown>)[segment];
    } else {
      return labelKey;
    }
  }
  return typeof node === "string" ? node : labelKey;
}
