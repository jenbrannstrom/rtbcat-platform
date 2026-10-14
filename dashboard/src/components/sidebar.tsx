"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import NextImage from "next/image";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ExternalLink,
  LogOut,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getSeats, syncAllData } from "@/lib/api";
import { useAccount } from "@/contexts/account-context";
import { useAuth } from "@/contexts/auth-context";
import { useTranslation } from "@/contexts/i18n-context";
import { LanguageSelector } from "@/components/language-selector";
import { VersionPopover } from "@/components/version-popover";
import { AnchoredPopover } from "@/components/anchored-popover";
import {
  isBuyerScopedPath,
  replaceBuyerInPath,
  splitBuyerPath,
  toBuyerScopedPath,
} from "@/lib/buyer-routes";
import { isRestrictedUser } from "@/lib/feature-gates";
import { getDocsHomeUrl } from "@/lib/docs-url";
import {
  buildNavTree,
  readLabel,
  resolveActiveNav,
  type NavLeaf,
  type NavParent,
} from "@/lib/nav-tree";

const SIDEBAR_COLLAPSED_KEY = "rtbcat-sidebar-collapsed";

function getRetryDelay(attemptIndex: number): number {
  return Math.min(1000 * 2 ** attemptIndex, 5000);
}

type AnchorRef = { current: HTMLElement | null };

/**
 * Left navigation rail.
 *
 * Structure comes from `buildNavTree` (lib/nav-tree.ts). This component only
 * renders it: one interaction model for every row (label navigates, chevron
 * toggles), an accordion for parents (opening one closes the others, nothing
 * persisted except the rail's collapsed state), and fixed-position popovers
 * so the collapsed rail still reaches every page.
 */
export function Sidebar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { selectedBuyerId, setSelectedBuyerId } = useAccount();
  const { user, isSudo, seatPermissions, logout } = useAuth();
  const { t } = useTranslation();

  const restricted = isRestrictedUser(user);
  const hasSeatAdminAccess =
    isSudo || Object.values(seatPermissions).some((level) => level === "admin");

  const groups = useMemo(
    () => buildNavTree({ restricted, hasSeatAdminAccess, isSudo }),
    [restricted, hasSeatAdminAccess, isSudo],
  );

  const currentBuyerId = selectedBuyerId;
  const { pathWithoutBuyer } = splitBuyerPath(pathname || "/");
  const queryString = searchParams.toString();
  const isBuyerScopedRoute = isBuyerScopedPath(pathWithoutBuyer);

  const active = useMemo(
    () => resolveActiveNav(pathWithoutBuyer, groups),
    [pathWithoutBuyer, groups],
  );
  const parentKeys = useMemo(
    () =>
      new Set(
        groups.flatMap((g) => g.items.filter((i) => i.kind === "parent").map((i) => i.key)),
      ),
    [groups],
  );
  // One anchor object per parent row for the collapsed-rail flyouts. Plain
  // objects (not useRef) so render never reads a ref; the ref callback on each
  // button fills `current`.
  const flyoutAnchors = useMemo(
    () => Object.fromEntries([...parentKeys].map((key) => [key, { current: null } as AnchorRef])),
    [parentKeys],
  );
  const activeParentKey =
    active.parentKey ?? (active.itemKey && parentKeys.has(active.itemKey) ? active.itemKey : null);

  // --- rail state -----------------------------------------------------------
  const [collapsed, setCollapsed] = useState(false);
  const [openParentKey, setOpenParentKey] = useState<string | null>(null);
  const [flyoutKey, setFlyoutKey] = useState<string | null>(null);
  const [seatMenuOpen, setSeatMenuOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [syncMessage, setSyncMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);

  const seatAnchorRef = useRef<HTMLButtonElement>(null);
  const accountAnchorRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const stored = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
    if (stored !== null) setCollapsed(stored === "true");
  }, []);

  // Accordion follows the route: the group holding the active page opens,
  // and because only one key is stored, the others close.
  useEffect(() => {
    if (activeParentKey) setOpenParentKey(activeParentKey);
  }, [activeParentKey]);

  // Route changes close any transient menu.
  useEffect(() => {
    setFlyoutKey(null);
    setSeatMenuOpen(false);
    setAccountMenuOpen(false);
  }, [pathname]);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    setFlyoutKey(null);
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
  };

  const toggleParent = (key: string) =>
    setOpenParentKey((current) => (current === key ? null : key));

  const closeFlyout = useCallback(() => setFlyoutKey(null), []);
  const closeSeatMenu = useCallback(() => setSeatMenuOpen(false), []);
  const closeAccountMenu = useCallback(() => setAccountMenuOpen(false), []);

  // --- seats ----------------------------------------------------------------
  const {
    data: seats,
    isError: seatsError,
    refetch: refetchSeats,
  } = useQuery({
    queryKey: ["seats"],
    queryFn: () => getSeats({ active_only: true }),
    retry: 5,
    retryDelay: getRetryDelay,
    retryOnMount: true,
    refetchOnReconnect: true,
  });

  const syncMutation = useMutation({
    mutationFn: async () => {
      // Run sync and a minimum 1 second delay in parallel for visual feedback
      const [result] = await Promise.all([
        syncAllData(),
        new Promise((resolve) => setTimeout(resolve, 1000)),
      ]);
      return result;
    },
    onMutate: () => setIsSyncing(true),
    onSuccess: (data) => {
      const msg = `${data.creatives_synced} creatives, ${data.endpoints_synced} endpoints, ${data.pretargeting_synced} configs`;
      setSyncMessage({
        type: data.status === "partial" ? "error" : "success",
        text: data.status === "partial" ? data.message : msg,
      });
      queryClient.invalidateQueries({ queryKey: ["creatives"] });
      queryClient.invalidateQueries({ queryKey: ["seats"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["rtb-endpoints"] });
      queryClient.invalidateQueries({ queryKey: ["pretargeting-configs"] });
      setTimeout(() => setSyncMessage(null), 5000);
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : t.common.failed;
      setSyncMessage({ type: "error", text: message });
      setTimeout(() => setSyncMessage(null), 3000);
    },
    onSettled: () => setIsSyncing(false),
  });

  const scopedBuyerId = isSudo ? currentBuyerId : (currentBuyerId ?? seats?.[0]?.buyer_id ?? null);
  const getSeatScopedHref = (href: string) => toBuyerScopedPath(href, scopedBuyerId);

  const selectedSeat =
    seats?.find((s) => s.buyer_id === currentBuyerId) ?? (!isSudo ? seats?.[0] : undefined);
  const totalCreatives = seats?.reduce((sum, s) => sum + s.creative_count, 0) ?? 0;
  const canViewAllSeats = isSudo;
  const canSwitchSeat = !!seats && (seats.length > 1 || (canViewAllSeats && seats.length > 0));

  const formatRelativeTime = (dateString: string | null): string => {
    if (!dateString) return t.common.never;
    const now = new Date();
    const diffMs = now.getTime() - new Date(dateString).getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    if (diffMins < 1) return t.relativeTime.justNow;
    if (diffMins < 60) return `${diffMins}${t.relativeTime.minutesAgo}`;
    if (diffHours < 24) return `${diffHours}${t.relativeTime.hoursAgo}`;
    return `${diffDays}${t.relativeTime.daysAgo}`;
  };

  const seatLabel = (seat: { display_name: string | null; buyer_id: string }) =>
    seat.display_name || `${t.sidebar.buyer} ${seat.buyer_id}`;

  const handleSeatSelect = (seatId: string | null) => {
    setSeatMenuOpen(false);

    const currentPath = pathname || "/";
    const nextPath = replaceBuyerInPath(currentPath, seatId);
    const nextUrl = queryString ? `${nextPath}?${queryString}` : nextPath;
    const currentUrl = queryString ? `${currentPath}?${queryString}` : currentPath;

    // On buyer-scoped pages, let the URL change drive the context update to avoid
    // a race with BuyerRouteSync's URL->context effect that can snap the seat back.
    const deferContextToRouteSync = !!seatId && isBuyerScopedRoute && nextUrl !== currentUrl;
    if (!deferContextToRouteSync) {
      setSelectedBuyerId(seatId);
    }

    if (nextUrl !== currentUrl) {
      router.push(nextUrl, { scroll: false });
    }

    // Invalidate queries so they refetch with new buyer_id
    queryClient.invalidateQueries({ queryKey: ["creatives"] });
    queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    queryClient.invalidateQueries({ queryKey: ["stats"] });
    queryClient.invalidateQueries({ queryKey: ["thumbnailStatus"] });
    queryClient.invalidateQueries({ queryKey: ["all-creatives"] });
    queryClient.invalidateQueries({ queryKey: ["unclustered"] });
    // Also invalidate RTB-related queries since they depend on seat/bidder
    queryClient.invalidateQueries({ queryKey: ["rtb-endpoints"] });
    queryClient.invalidateQueries({ queryKey: ["pretargeting-configs"] });
  };

  // --- version --------------------------------------------------------------
  const releaseVersion = process.env.NEXT_PUBLIC_RELEASE_VERSION;
  const buildVersion =
    process.env.NEXT_PUBLIC_APP_VERSION && process.env.NEXT_PUBLIC_APP_VERSION !== "unknown"
      ? process.env.NEXT_PUBLIC_APP_VERSION
      : process.env.NEXT_PUBLIC_GIT_SHA && process.env.NEXT_PUBLIC_GIT_SHA !== "unknown"
        ? `sha-${process.env.NEXT_PUBLIC_GIT_SHA}`
        : "dev";
  const versionLabel =
    releaseVersion && releaseVersion !== "unknown" ? `v${releaseVersion} (${buildVersion})` : buildVersion;
  const versionRelease = releaseVersion && releaseVersion !== "unknown" ? `v${releaseVersion}` : null;
  const versionBuild =
    process.env.NEXT_PUBLIC_GIT_SHA && process.env.NEXT_PUBLIC_GIT_SHA !== "unknown"
      ? process.env.NEXT_PUBLIC_GIT_SHA
      : null;

  const label = (key: string) => readLabel(t, key);
  const userInitial = (user?.display_name || user?.email || "?").charAt(0).toUpperCase();

  // --- row renderers --------------------------------------------------------
  const leafHref = (item: NavLeaf) => (item.buyerScoped ? getSeatScopedHref(item.href) : item.href);

  const renderLeaf = (item: NavLeaf, depth: 0 | 1) => {
    const isActive = active.itemKey === item.key;
    const name = label(item.labelKey);
    return (
      <li key={item.key}>
        <Link
          href={leafHref(item)}
          aria-current={isActive ? "page" : undefined}
          title={collapsed ? name : undefined}
          className={cn(
            "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            depth === 1 && "py-1.5 text-[13px] font-normal",
            isActive
              ? "bg-primary-50 text-primary-700"
              : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
            collapsed && "justify-center px-2",
          )}
        >
          <item.icon
            className={cn(
              "shrink-0",
              depth === 1 ? "h-4 w-4" : "h-5 w-5",
              isActive ? "text-primary-600" : "text-gray-400",
            )}
          />
          {!collapsed && <span className="min-w-0 flex-1 truncate">{name}</span>}
        </Link>
      </li>
    );
  };

  const renderParent = (item: NavParent) => {
    const name = label(item.labelKey);
    const tag = item.tagKey ? label(item.tagKey) : null;
    const isSelf = active.itemKey === item.key;
    const hasActiveChild = active.parentKey === item.key;

    if (collapsed) {
      const isOpen = flyoutKey === item.key;
      const anchor = flyoutAnchors[item.key];
      return (
        <li key={item.key}>
          <button
            type="button"
            ref={(node) => {
              anchor.current = node;
            }}
            onClick={() => setFlyoutKey(isOpen ? null : item.key)}
            aria-haspopup="dialog"
            aria-expanded={isOpen}
            title={name}
            className={cn(
              "flex w-full items-center justify-center rounded-md px-2 py-2 transition-colors",
              isSelf || hasActiveChild
                ? "bg-primary-50 text-primary-700"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
            )}
          >
            <item.icon
              className={cn(
                "h-5 w-5 shrink-0",
                isSelf || hasActiveChild ? "text-primary-600" : "text-gray-400",
              )}
            />
          </button>
          <AnchoredPopover
            anchorRef={anchor}
            open={isOpen}
            onClose={closeFlyout}
            placement="right-start"
            label={name}
            className="w-56 py-1"
          >
            {item.href ? (
              <Link
                href={item.href}
                onClick={closeFlyout}
                className="flex items-center justify-between px-3 py-2 text-sm font-semibold text-gray-900 hover:bg-gray-50"
              >
                {name}
                {tag && <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">{tag}</span>}
              </Link>
            ) : (
              <div className="px-3 py-2 text-sm font-semibold text-gray-900">{name}</div>
            )}
            <ul className="border-t border-gray-100 py-1">
              {item.children.map((child) => {
                const childActive = active.itemKey === child.key;
                return (
                  <li key={child.key}>
                    <Link
                      href={leafHref(child)}
                      onClick={closeFlyout}
                      aria-current={childActive ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-2 px-3 py-2 text-sm",
                        childActive
                          ? "bg-primary-50 text-primary-700"
                          : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                      )}
                    >
                      <child.icon className={cn("h-4 w-4", childActive ? "text-primary-600" : "text-gray-400")} />
                      {label(child.labelKey)}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </AnchoredPopover>
        </li>
      );
    }

    const isOpen = openParentKey === item.key;
    const rowClass = cn(
      "flex min-w-0 flex-1 items-center gap-3 px-3 py-2 text-left text-sm font-medium",
    );
    const rowContent = (
      <>
        <item.icon
          className={cn("h-5 w-5 shrink-0", isSelf ? "text-primary-600" : hasActiveChild ? "text-gray-600" : "text-gray-400")}
        />
        <span className="min-w-0 flex-1 truncate">{name}</span>
        {tag && (
          <span className="shrink-0 rounded border border-gray-200 px-1 text-[10px] font-semibold uppercase tracking-wide text-gray-400">
            {tag}
          </span>
        )}
      </>
    );
    const toggleLabel = (isOpen ? t.navigation.collapseGroup : t.navigation.expandGroup).replace("{group}", name);

    return (
      <li key={item.key}>
        <div
          className={cn(
            "flex items-center rounded-md transition-colors",
            isSelf
              ? "bg-primary-50 text-primary-700"
              : hasActiveChild
                ? "text-gray-900"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
          )}
        >
          {item.href ? (
            <Link href={item.href} aria-current={isSelf ? "page" : undefined} className={rowClass}>
              {rowContent}
            </Link>
          ) : (
            <button type="button" onClick={() => toggleParent(item.key)} aria-expanded={isOpen} className={rowClass}>
              {rowContent}
            </button>
          )}
          <button
            type="button"
            onClick={() => toggleParent(item.key)}
            aria-expanded={isOpen}
            aria-label={toggleLabel}
            className={cn(
              "mr-1 shrink-0 rounded-md p-1 text-gray-400 transition-colors hover:text-gray-700",
              isSelf ? "hover:bg-primary-100" : "hover:bg-gray-100",
            )}
          >
            <ChevronDown className={cn("h-4 w-4 transition-transform", isOpen && "rotate-180")} />
          </button>
        </div>
        {isOpen && (
          <ul className="ml-5 mt-0.5 space-y-0.5 border-l border-gray-100 pl-2">
            {item.children.map((child) => renderLeaf(child, 1))}
          </ul>
        )}
      </li>
    );
  };

  // --- seat card ------------------------------------------------------------
  const syncButton = hasSeatAdminAccess && seats && seats.length > 0 && (
    <button
      type="button"
      onClick={() => syncMutation.mutate()}
      disabled={isSyncing}
      title={isSyncing ? t.common.syncing : t.common.syncAll}
      aria-label={t.common.syncAll}
      className="shrink-0 rounded-md p-1.5 text-gray-400 transition-colors hover:bg-primary-50 hover:text-primary-600 disabled:opacity-50"
    >
      <RefreshCw className={cn("h-4 w-4", isSyncing && "animate-spin")} />
    </button>
  );

  const seatMenu = (
    <AnchoredPopover
      anchorRef={seatAnchorRef}
      open={seatMenuOpen}
      onClose={closeSeatMenu}
      placement={collapsed ? "right-start" : "bottom-end"}
      label={t.navigation.switchSeat}
      className="w-64 max-h-80 overflow-y-auto py-1"
    >
      {canViewAllSeats && (
        <button
          type="button"
          onClick={() => handleSeatSelect(null)}
          className={cn(
            "flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50",
            !currentBuyerId && "bg-primary-50 text-primary-700",
          )}
        >
          <div>
            <div className="font-medium">{t.sidebar.allSeats}</div>
            <div className="text-xs text-gray-500">{totalCreatives} {t.sidebar.creatives}</div>
          </div>
          {!currentBuyerId && <Check className="h-4 w-4 text-primary-600" />}
        </button>
      )}
      {seats?.map((seat) => {
        const isSelected = currentBuyerId === seat.buyer_id;
        return (
          <button
            key={seat.buyer_id}
            type="button"
            onClick={() => handleSeatSelect(seat.buyer_id)}
            className={cn(
              "flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50",
              isSelected && "bg-primary-50 text-primary-700",
            )}
          >
            <div className="min-w-0">
              <div className="truncate font-medium">{seatLabel(seat)}</div>
              <div className="text-xs text-gray-500">
                {seat.creative_count} {t.sidebar.creatives} · {formatRelativeTime(seat.last_synced)}
              </div>
            </div>
            {isSelected && <Check className="h-4 w-4 shrink-0 text-primary-600" />}
          </button>
        );
      })}
    </AnchoredPopover>
  );

  const renderSeatCard = () => {
    if (seatsError) {
      if (collapsed) {
        return (
          <button type="button" onClick={() => refetchSeats()} title={t.sidebar.unableToLoadSeats} className="mx-auto flex h-8 w-8 items-center justify-center rounded-full bg-red-50 text-red-600">
            <AlertCircle className="h-4 w-4" />
          </button>
        );
      }
      return (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <p className="font-medium">{t.sidebar.unableToLoadSeats}</p>
          <button type="button" onClick={() => refetchSeats()} className="mt-2 rounded-sm bg-red-100 px-2 py-1 text-xs font-medium hover:bg-red-200">
            {t.common.retry}
          </button>
        </div>
      );
    }

    if (!seats || seats.length === 0) {
      if (collapsed) {
        return (
          <div title={t.sidebar.noSeatsConnected} className="mx-auto flex h-8 w-8 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-500">
            0
          </div>
        );
      }
      return (
        <div className="py-1 text-center text-sm text-gray-500">
          <p className="font-medium text-gray-700">{t.sidebar.noSeatsConnected}</p>
          <p className="mt-1 text-xs">{t.sidebar.goToSettingsToConnect}</p>
          <button type="button" onClick={() => refetchSeats()} className="mt-2 rounded-sm bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200">
            {t.common.retry}
          </button>
        </div>
      );
    }

    const title = selectedSeat ? seatLabel(selectedSeat) : t.sidebar.allSeats;
    const subtitle = selectedSeat
      ? `${selectedSeat.creative_count} ${t.sidebar.creatives} · ${formatRelativeTime(selectedSeat.last_synced)}`
      : `${totalCreatives} ${t.sidebar.creatives}`;

    if (collapsed) {
      return (
        <>
          <button
            ref={seatAnchorRef}
            type="button"
            onClick={() => canSwitchSeat && setSeatMenuOpen((open) => !open)}
            aria-haspopup={canSwitchSeat ? "dialog" : undefined}
            aria-expanded={canSwitchSeat ? seatMenuOpen : undefined}
            title={title}
            className={cn(
              "mx-auto flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700",
              canSwitchSeat && "hover:bg-primary-200",
            )}
          >
            {selectedSeat ? title.charAt(0).toUpperCase() : seats.length}
          </button>
          {seatMenu}
        </>
      );
    }

    return (
      <>
        <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 pl-3 pr-1">
          <button
            ref={seatAnchorRef}
            type="button"
            onClick={() => canSwitchSeat && setSeatMenuOpen((open) => !open)}
            aria-haspopup={canSwitchSeat ? "dialog" : undefined}
            aria-expanded={canSwitchSeat ? seatMenuOpen : undefined}
            disabled={!canSwitchSeat}
            className="flex min-w-0 flex-1 items-center gap-2 py-2 text-left disabled:cursor-default"
          >
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-gray-800">{title}</span>
              <span className="block truncate text-xs text-gray-500">{subtitle}</span>
            </span>
            {canSwitchSeat && (
              <ChevronDown className={cn("h-4 w-4 shrink-0 text-gray-400 transition-transform", seatMenuOpen && "rotate-180")} />
            )}
          </button>
          {syncButton}
        </div>
        {seatMenu}
        {syncMessage && (
          <div
            role="status"
            className={cn(
              "mt-2 flex items-center gap-1 rounded-sm px-2 py-1 text-xs",
              syncMessage.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700",
            )}
          >
            {syncMessage.type === "success" ? <Check className="h-3 w-3 shrink-0" /> : <AlertCircle className="h-3 w-3 shrink-0" />}
            <span className="min-w-0 truncate">{syncMessage.text}</span>
          </div>
        )}
      </>
    );
  };

  // --- account menu ---------------------------------------------------------
  const accountMenu = (
    <AnchoredPopover
      anchorRef={accountAnchorRef}
      open={accountMenuOpen}
      onClose={closeAccountMenu}
      placement={collapsed ? "right-start" : "top-start"}
      label={t.navigation.accountMenu}
      className="w-60 py-1"
    >
      {user && (
        <div className="border-b border-gray-100 px-3 py-2">
          <p className="text-[11px] uppercase tracking-wide text-gray-400">{t.navigation.signedInAs}</p>
          <p className="truncate text-sm font-medium text-gray-900">{user.display_name || user.email}</p>
          {user.display_name && <p className="truncate text-xs text-gray-500">{user.email}</p>}
        </div>
      )}
      <a
        href={getDocsHomeUrl()}
        target="_blank"
        rel="noopener noreferrer"
        onClick={closeAccountMenu}
        className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
      >
        <ExternalLink className="h-4 w-4 text-gray-400" />
        {t.navigation.docs}
      </a>
      <button
        type="button"
        onClick={() => {
          closeAccountMenu();
          logout();
        }}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 hover:bg-red-50 hover:text-red-600"
      >
        <LogOut className="h-4 w-4 text-gray-400" />
        {t.navigation.logout}
      </button>
    </AnchoredPopover>
  );

  const accountButton = (
    <button
      ref={accountAnchorRef}
      type="button"
      onClick={() => setAccountMenuOpen((open) => !open)}
      aria-haspopup="dialog"
      aria-expanded={accountMenuOpen}
      title={collapsed ? user?.display_name || user?.email : undefined}
      className={cn(
        "flex items-center gap-2 rounded-md transition-colors hover:bg-gray-50",
        collapsed ? "mx-auto p-1" : "min-w-0 flex-1 px-2 py-1.5",
      )}
    >
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700">
        {userInitial}
      </span>
      {!collapsed && (
        <>
          <span className="min-w-0 flex-1 truncate text-left text-sm text-gray-700">
            {user?.display_name || user?.email}
          </span>
          <ChevronUp className={cn("h-3.5 w-3.5 shrink-0 text-gray-400 transition-transform", accountMenuOpen && "rotate-180")} />
        </>
      )}
    </button>
  );

  // --- render ---------------------------------------------------------------
  return (
    <div
      className={cn(
        "flex min-h-0 shrink-0 flex-col overflow-hidden bg-white border-r border-gray-200 transition-all duration-300",
        collapsed ? "w-16" : "w-64",
      )}
    >
      {/* Brand */}
      <div className="flex h-16 shrink-0 items-center border-b border-gray-200 px-4">
        <NextImage
          src="/cat-scanning-stats.webp"
          alt={t.auth.catScan}
          width={40}
          height={40}
          className="h-10 w-10 shrink-0 rounded-lg"
          priority
        />
        {!collapsed && <span className="ml-3 truncate text-xl font-bold text-primary-600">{t.auth.catScan}</span>}
      </div>

      {/* Seat */}
      <div className={cn("shrink-0 border-b border-gray-200", collapsed ? "px-2 py-2" : "px-3 py-3")}>
        {renderSeatCard()}
      </div>

      {/* Navigation: three groups, System pinned to the bottom of the scroll area */}
      <nav
        aria-label={t.navigation.mainNavigation}
        className="flex min-h-0 min-w-0 flex-1 flex-col gap-4 overflow-x-hidden overflow-y-auto px-2 py-3"
      >
        {groups.map((group, index) => (
          <div
            key={group.key}
            className={cn(
              group.key === "system" && "mt-auto border-t border-gray-100 pt-3",
              collapsed && index > 0 && group.key !== "system" && "border-t border-gray-100 pt-3",
            )}
          >
            {!collapsed && (
              <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                {label(group.labelKey)}
              </div>
            )}
            <ul className="space-y-0.5">
              {group.items.map((item) => (item.kind === "leaf" ? renderLeaf(item, 0) : renderParent(item)))}
            </ul>
          </div>
        ))}
      </nav>

      {/* Footer: account, language, version, collapse */}
      <div className="shrink-0 overflow-hidden border-t border-gray-200 px-2 py-2">
        {collapsed ? (
          <div className="flex flex-col items-center gap-1">
            {accountButton}
            <LanguageSelector collapsed />
            <button
              type="button"
              onClick={toggleCollapsed}
              className="flex w-full items-center justify-center rounded-md p-2 text-gray-400 transition-colors hover:bg-gray-50 hover:text-gray-600"
              title={t.navigation.expand}
              aria-label={t.navigation.expand}
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>
        ) : (
          <>
            <div className="flex min-w-0 items-center gap-1">
              {accountButton}
              <LanguageSelector compact />
              <button
                type="button"
                onClick={toggleCollapsed}
                className="shrink-0 rounded-md p-1.5 text-gray-400 transition-colors hover:bg-gray-50 hover:text-gray-600"
                title={t.navigation.collapse}
                aria-label={t.navigation.collapse}
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-1 flex min-w-0 items-center px-2 text-xs text-gray-400">
              <VersionPopover label={versionLabel} release={versionRelease} build={versionBuild} />
            </div>
          </>
        )}
        {accountMenu}
      </div>
    </div>
  );
}
