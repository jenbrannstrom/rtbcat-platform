"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Image,
  FolderKanban,
  Settings,
  ExternalLink,
  TrendingDown,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  Check,
  AlertCircle,
  History,
  LogOut,
  Users,
  Shield,
  Link2,
  Clock,
  Activity,
  FileText,
  Wrench,
  Map,
  BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getSeats, syncAllData } from "@/lib/api";
import { useAccount } from "@/contexts/account-context";
import { useAuth } from "@/contexts/auth-context";
import { useTranslation } from "@/contexts/i18n-context";
import { LanguageSelector } from "@/components/language-selector";

const SIDEBAR_COLLAPSED_KEY = "rtbcat-sidebar-collapsed";
const SIDEBAR_SETTINGS_EXPANDED_KEY = "rtbcat-sidebar-settings-expanded";
const SIDEBAR_ADMIN_EXPANDED_KEY = "rtbcat-sidebar-admin-expanded";
const SIDEBAR_QPS_EXPANDED_KEY = "rtbcat-sidebar-qps-expanded";

// Main navigation items
const navigationItems = [
  { key: "creatives" as const, href: "/creatives", icon: Image },
  { key: "campaigns" as const, href: "/campaigns", icon: FolderKanban },
  { key: "changeHistory" as const, href: "/history", icon: History },
  { key: "import" as const, href: "/import", icon: RefreshCw },
];

const qpsItems = [
  { key: "publisher" as const, href: "/qps/publisher", icon: Users },
  { key: "geo" as const, href: "/qps/geo", icon: Map },
  { key: "size" as const, href: "/qps/size", icon: BarChart3 },
];

// Settings sub-navigation
const settingsItems = [
  { key: "connectedAccounts" as const, href: "/settings/accounts", icon: Link2 },
  { key: "dataRetention" as const, href: "/settings/retention", icon: Clock },
  { key: "systemStatus" as const, href: "/settings/system", icon: Activity },
];

// Admin sub-navigation
const adminItems = [
  { key: "users" as const, href: "/admin/users", icon: Users },
  { key: "configuration" as const, href: "/admin/configuration", icon: Wrench },
  { key: "auditLog" as const, href: "/admin/audit-log", icon: FileText },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { selectedBuyerId, setSelectedBuyerId } = useAccount();
  const { user, isAdmin, logout } = useAuth();
  const { t } = useTranslation();

  // Helper for relative time formatting with translations
  const formatRelativeTime = (dateString: string | null): string => {
    if (!dateString) return t.common.never;
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    if (diffMins < 1) return t.relativeTime.justNow;
    if (diffMins < 60) return `${diffMins}${t.relativeTime.minutesAgo}`;
    if (diffHours < 24) return `${diffHours}${t.relativeTime.hoursAgo}`;
    return `${diffDays}${t.relativeTime.daysAgo}`;
  };

  const [collapsed, setCollapsed] = useState(false);
  const [seatDropdownOpen, setSeatDropdownOpen] = useState(false);
  const [syncMessage, setSyncMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [settingsExpanded, setSettingsExpanded] = useState(false);
  const [adminExpanded, setAdminExpanded] = useState(false);
  const [qpsExpanded, setQpsExpanded] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  // Use context for buyer_id (persistent across pages)
  const currentBuyerId = selectedBuyerId;

  // Check if current path is in settings or admin section
  const isInSettings = pathname?.startsWith("/settings");
  const isInAdmin = pathname?.startsWith("/admin");
  const isInQps = pathname?.startsWith("/qps");

  // Load collapsed and expanded states from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
    if (stored !== null) {
      setCollapsed(stored === "true");
    }
    const settingsStored = localStorage.getItem(SIDEBAR_SETTINGS_EXPANDED_KEY);
    if (settingsStored !== null) {
      setSettingsExpanded(settingsStored === "true");
    }
    const adminStored = localStorage.getItem(SIDEBAR_ADMIN_EXPANDED_KEY);
    if (adminStored !== null) {
      setAdminExpanded(adminStored === "true");
    }
    const qpsStored = localStorage.getItem(SIDEBAR_QPS_EXPANDED_KEY);
    if (qpsStored !== null) {
      setQpsExpanded(qpsStored === "true");
    }
  }, []);

  // Auto-expand sections when navigating to them
  useEffect(() => {
    if (isInSettings && !settingsExpanded) {
      setSettingsExpanded(true);
      localStorage.setItem(SIDEBAR_SETTINGS_EXPANDED_KEY, "true");
    }
    if (isInAdmin && !adminExpanded) {
      setAdminExpanded(true);
      localStorage.setItem(SIDEBAR_ADMIN_EXPANDED_KEY, "true");
    }
    if (isInQps && !qpsExpanded) {
      setQpsExpanded(true);
      localStorage.setItem(SIDEBAR_QPS_EXPANDED_KEY, "true");
    }
  }, [pathname]);

  const toggleCollapsed = () => {
    const newValue = !collapsed;
    setCollapsed(newValue);
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(newValue));
  };

  const toggleSettingsExpanded = () => {
    const newValue = !settingsExpanded;
    setSettingsExpanded(newValue);
    localStorage.setItem(SIDEBAR_SETTINGS_EXPANDED_KEY, String(newValue));
  };

  const toggleAdminExpanded = () => {
    const newValue = !adminExpanded;
    setAdminExpanded(newValue);
    localStorage.setItem(SIDEBAR_ADMIN_EXPANDED_KEY, String(newValue));
  };

  const toggleQpsExpanded = () => {
    const newValue = !qpsExpanded;
    setQpsExpanded(newValue);
    localStorage.setItem(SIDEBAR_QPS_EXPANDED_KEY, String(newValue));
  };

  const { data: seats } = useQuery({
    queryKey: ["seats"],
    queryFn: () => getSeats({ active_only: true }),
  });

  const syncMutation = useMutation({
    mutationFn: async () => {
      // Run sync and minimum 1 second delay in parallel for visual feedback
      const [result] = await Promise.all([
        syncAllData(),
        new Promise(resolve => setTimeout(resolve, 1000)),
      ]);
      return result;
    },
    onMutate: () => {
      setIsSyncing(true);
    },
    onSuccess: (data) => {
      const msg = `${data.creatives_synced} creatives, ${data.endpoints_synced} endpoints, ${data.pretargeting_synced} configs`;
      setSyncMessage({ type: "success", text: msg });
      queryClient.invalidateQueries({ queryKey: ["creatives"] });
      queryClient.invalidateQueries({ queryKey: ["seats"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["rtb-endpoints"] });
      queryClient.invalidateQueries({ queryKey: ["pretargeting-configs"] });
      setTimeout(() => setSyncMessage(null), 5000);
    },
    onError: (error) => {
      setSyncMessage({ type: "error", text: t.common.failed });
      setTimeout(() => setSyncMessage(null), 3000);
    },
    onSettled: () => {
      setIsSyncing(false);
    },
  });

  const selectedSeat = seats?.find((s) => s.buyer_id === currentBuyerId);
  const totalCreatives = seats?.reduce((sum, s) => sum + s.creative_count, 0) ?? 0;

  const handleSeatSelect = (seatId: string | null) => {
    setSeatDropdownOpen(false);
    // Update the context (persisted to localStorage)
    setSelectedBuyerId(seatId);
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

  return (
    <div className={cn(
      "flex flex-col bg-white border-r border-gray-200 transition-all duration-300",
      collapsed ? "w-16" : "w-64"
    )}>
      {/* Header with logo */}
      <div className="flex items-center h-16 px-4 border-b border-gray-200">
        <img
          src="/cat-scanning-stats.webp"
          alt="Cat-Scan"
          className="h-10 w-10 rounded-lg flex-shrink-0"
        />
        {!collapsed && (
          <span className="ml-3 text-xl font-bold text-primary-600">Cat-Scan</span>
        )}
      </div>

      {/* Seat Selector - Conditional based on seat count */}
      <div className={cn("border-b border-gray-200", collapsed ? "px-2 py-2" : "px-4 py-3")}>
        {collapsed ? (
          /* Collapsed view - show icon */
          <div
            className="w-full p-2 rounded-md"
            title={seats?.length === 1 ? seats[0].display_name || `Buyer ${seats[0].buyer_id}` : "Seats"}
          >
            <div className="h-6 w-6 mx-auto rounded-full bg-primary-100 flex items-center justify-center text-xs font-medium text-primary-700">
              {seats?.length === 1 ? (seats[0].display_name?.charAt(0) || "S") : (seats?.length || 0)}
            </div>
          </div>
        ) : !seats || seats.length === 0 ? (
          /* No seats - show connect message */
          <div className="text-sm text-gray-500 text-center py-2">
            <p className="font-medium text-gray-700">{t.sidebar.noSeatsConnected}</p>
            <p className="text-xs mt-1">{t.sidebar.goToSettingsToConnect}</p>
          </div>
        ) : seats.length === 1 ? (
          /* Single seat - show as title with sync all button */
          <div>
            <div className="flex items-center justify-between gap-2 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg">
              <div className="min-w-0 flex-1">
                <div className="font-medium text-sm text-gray-700 truncate">
                  {seats[0].display_name || `${t.sidebar.buyer} ${seats[0].buyer_id}`}
                </div>
                <div className="text-xs text-gray-500">
                  {seats[0].creative_count} {t.sidebar.creatives}
                </div>
              </div>
              <button
                onClick={() => syncMutation.mutate()}
                disabled={isSyncing}
                className={cn(
                  "p-1.5 rounded-md text-gray-500 hover:text-primary-600 hover:bg-primary-50",
                  "disabled:opacity-50 flex-shrink-0"
                )}
                title={t.common.syncAll || "Sync All Data"}
              >
                <RefreshCw className={cn("h-4 w-4", isSyncing && "animate-spin")} />
              </button>
            </div>

            {syncMessage && (
              <div className={cn(
                "mt-2 px-2 py-1 rounded text-xs flex items-center gap-1",
                syncMessage.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
              )}>
                {syncMessage.type === "success" ? <Check className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}
                {syncMessage.text}
              </div>
            )}
          </div>
        ) : (
          /* Multiple seats - show dropdown */
          <div className="relative">
            <button
              onClick={() => setSeatDropdownOpen(!seatDropdownOpen)}
              className={cn(
                "w-full flex items-center justify-between gap-2 px-3 py-2",
                "bg-gray-50 border border-gray-200 rounded-lg",
                "hover:bg-gray-100 text-sm font-medium text-gray-700"
              )}
            >
              <span className="truncate">
                {selectedSeat ? selectedSeat.display_name || `${t.sidebar.buyer} ${selectedSeat.buyer_id}` : t.sidebar.allSeats}
              </span>
              <ChevronDown className={cn("h-4 w-4 text-gray-400 transition-transform flex-shrink-0", seatDropdownOpen && "rotate-180")} />
            </button>

            {seatDropdownOpen && (
              <div className="absolute z-50 mt-1 left-0 right-0 bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-y-auto">
                <button
                  onClick={() => handleSeatSelect(null)}
                  className={cn(
                    "w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50",
                    !currentBuyerId && "bg-primary-50 text-primary-700"
                  )}
                >
                  <div>
                    <div className="font-medium">{t.sidebar.allSeats}</div>
                    <div className="text-xs text-gray-500">{totalCreatives} {t.sidebar.creatives}</div>
                  </div>
                  {!currentBuyerId && <Check className="h-4 w-4 text-primary-600" />}
                </button>
                {seats?.map((seat) => (
                  <button
                    key={seat.buyer_id}
                    onClick={() => handleSeatSelect(seat.buyer_id)}
                    className={cn(
                      "w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50",
                      currentBuyerId === seat.buyer_id && "bg-primary-50 text-primary-700"
                    )}
                  >
                    <div>
                      <div className="font-medium">{seat.display_name || `${t.sidebar.buyer} ${seat.buyer_id}`}</div>
                      <div className="text-xs text-gray-500">
                        {seat.creative_count} · {formatRelativeTime(seat.last_synced)}
                      </div>
                    </div>
                    {currentBuyerId === seat.buyer_id && <Check className="h-4 w-4 text-primary-600" />}
                  </button>
                ))}
              </div>
            )}

            {/* Sync All button - always visible when seats exist */}
            <button
              onClick={() => syncMutation.mutate()}
              disabled={isSyncing}
              className={cn(
                "mt-2 w-full flex items-center justify-center gap-2 px-3 py-1.5",
                "bg-primary-600 text-white rounded-md text-sm font-medium",
                "hover:bg-primary-700 disabled:opacity-50"
              )}
            >
              <RefreshCw className={cn("h-3.5 w-3.5", isSyncing && "animate-spin")} />
              {isSyncing ? t.common.syncing : (t.common.syncAll || "Sync All")}
            </button>

            {syncMessage && (
              <div className={cn(
                "mt-2 px-2 py-1 rounded text-xs flex items-center gap-1",
                syncMessage.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
              )}>
                {syncMessage.type === "success" ? <Check className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}
                {syncMessage.text}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
        {/* QPS Section */}
        <div className="pt-1">
          {!collapsed && (
            <div className="px-3 mb-1">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                {t.navigation.wasteOptimizer}
              </span>
            </div>
          )}
          <button
            onClick={() => {
              toggleQpsExpanded();
              if (pathname !== "/") {
                router.push("/");
              }
            }}
            className={cn(
              "flex items-center w-full px-3 py-2 text-sm font-medium rounded-md transition-colors",
              isInQps
                ? "bg-primary-50 text-primary-700"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
              collapsed && "justify-center px-2"
            )}
            title={collapsed ? t.navigation.wasteOptimizer : undefined}
          >
            <TrendingDown
              className={cn(
                "h-5 w-5 flex-shrink-0",
                isInQps ? "text-primary-600" : "text-gray-400",
                !collapsed && "mr-3"
              )}
            />
            {!collapsed && (
              <>
                <span className="flex-1 text-left">{t.navigation.wasteOptimizer}</span>
                <ChevronDown
                  className={cn(
                    "h-4 w-4 transition-transform",
                    qpsExpanded && "rotate-180"
                  )}
                />
              </>
            )}
          </button>
          {(!collapsed && qpsExpanded) && (
            <div className="ml-6 space-y-1">
              {qpsItems.map((item) => {
                const isActive = pathname?.startsWith(item.href);
                const itemName = t.qpsNav?.[item.key] || item.key;
                return (
                  <Link
                    key={item.key}
                    href={item.href}
                    className={cn(
                      "flex items-center px-3 py-2 text-sm rounded-md transition-colors",
                      isActive
                        ? "bg-primary-50 text-primary-700"
                        : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                    )}
                  >
                    <item.icon className={cn("h-4 w-4 mr-2", isActive ? "text-primary-600" : "text-gray-400")} />
                    {itemName}
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* Main navigation items */}
        {navigationItems.map((item) => {
          const isActive = item.href === "/"
            ? pathname === "/"
            : pathname.startsWith(item.href);
          const itemName = t.navigation[item.key];
          return (
            <Link
              key={item.key}
              href={item.href}
              className={cn(
                "flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors",
                isActive
                  ? "bg-primary-50 text-primary-700"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                collapsed && "justify-center px-2"
              )}
              title={collapsed ? itemName : undefined}
            >
              <item.icon
                className={cn(
                  "h-5 w-5 flex-shrink-0",
                  isActive ? "text-primary-600" : "text-gray-400",
                  !collapsed && "mr-3"
                )}
              />
              {!collapsed && itemName}
            </Link>
          );
        })}

        {/* Settings Section */}
        <div className="pt-4">
          {!collapsed && (
            <div className="px-3 mb-1">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                {t.navigation.settings}
              </span>
            </div>
          )}
          <button
            onClick={toggleSettingsExpanded}
            className={cn(
              "flex items-center w-full px-3 py-2 text-sm font-medium rounded-md transition-colors",
              isInSettings
                ? "bg-primary-50 text-primary-700"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
              collapsed && "justify-center px-2"
            )}
            title={collapsed ? t.navigation.settings : undefined}
          >
            <Settings
              className={cn(
                "h-5 w-5 flex-shrink-0",
                isInSettings ? "text-primary-600" : "text-gray-400",
                !collapsed && "mr-3"
              )}
            />
            {!collapsed && (
              <>
                <span className="flex-1 text-left">{t.navigation.settings}</span>
                <ChevronDown
                  className={cn(
                    "h-4 w-4 text-gray-400 transition-transform",
                    settingsExpanded && "rotate-180"
                  )}
                />
              </>
            )}
          </button>
          {settingsExpanded && !collapsed && (
            <div className="mt-1 ml-4 space-y-1">
              {settingsItems.map((item) => {
                const isActive = pathname === item.href;
                const itemName = t.settingsNav?.[item.key] || item.key;
                return (
                  <Link
                    key={item.key}
                    href={item.href}
                    className={cn(
                      "flex items-center px-3 py-2 text-sm rounded-md transition-colors",
                      isActive
                        ? "bg-primary-50 text-primary-700 font-medium"
                        : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                    )}
                  >
                    <item.icon
                      className={cn(
                        "h-4 w-4 flex-shrink-0 mr-3",
                        isActive ? "text-primary-600" : "text-gray-400"
                      )}
                    />
                    {itemName}
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* Admin Section (only for admins) */}
        {isAdmin && (
          <div className="pt-2">
            {!collapsed && (
              <div className="px-3 mb-1">
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  {t.navigation.admin}
                </span>
              </div>
            )}
            <button
              onClick={toggleAdminExpanded}
              className={cn(
                "flex items-center w-full px-3 py-2 text-sm font-medium rounded-md transition-colors",
                isInAdmin
                  ? "bg-primary-50 text-primary-700"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                collapsed && "justify-center px-2"
              )}
              title={collapsed ? t.navigation.admin : undefined}
            >
              <Shield
                className={cn(
                  "h-5 w-5 flex-shrink-0",
                  isInAdmin ? "text-primary-600" : "text-gray-400",
                  !collapsed && "mr-3"
                )}
              />
              {!collapsed && (
                <>
                  <span className="flex-1 text-left">{t.navigation.admin}</span>
                  <ChevronDown
                    className={cn(
                      "h-4 w-4 text-gray-400 transition-transform",
                      adminExpanded && "rotate-180"
                    )}
                  />
                </>
              )}
            </button>
            {adminExpanded && !collapsed && (
              <div className="mt-1 ml-4 space-y-1">
                {adminItems.map((item) => {
                  const isActive = pathname === item.href;
                  const itemName = t.adminNav?.[item.key] || item.key;
                  return (
                    <Link
                      key={item.key}
                      href={item.href}
                      className={cn(
                        "flex items-center px-3 py-2 text-sm rounded-md transition-colors",
                        isActive
                          ? "bg-primary-50 text-primary-700 font-medium"
                          : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                      )}
                    >
                      <item.icon
                        className={cn(
                          "h-4 w-4 flex-shrink-0 mr-3",
                          isActive ? "text-primary-600" : "text-gray-400"
                        )}
                      />
                      {itemName}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Logout - at bottom of nav */}
        <div className="pt-4 mt-auto">
          <button
            onClick={logout}
            className={cn(
              "flex items-center w-full px-3 py-2 text-sm font-medium text-gray-600 hover:text-red-600 rounded-md hover:bg-red-50 transition-colors",
              collapsed && "justify-center px-2"
            )}
            title={collapsed ? t.navigation.logout : undefined}
          >
            <LogOut className={cn("h-5 w-5 text-gray-400", !collapsed && "mr-3")} />
            {!collapsed && t.navigation.logout}
          </button>

          {/* Language selector */}
          <div className={cn("mt-2", collapsed ? "flex justify-center" : "px-3")}>
            <LanguageSelector compact />
          </div>
        </div>
      </nav>

      {/* Footer with user info and collapse */}
      <div className="px-2 py-3 border-t border-gray-200">
        {/* User info, version, docs, and collapse toggle in a clean row */}
        {!collapsed ? (
          <div className="flex items-center justify-between px-2">
            <div className="flex-1 min-w-0">
              {user && (
                <p className="text-xs text-gray-500 truncate" title={user.email}>
                  {user.display_name || user.email}
                </p>
              )}
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <span
                  title={
                    process.env.NEXT_PUBLIC_GIT_SHA && process.env.NEXT_PUBLIC_GIT_SHA !== "unknown"
                      ? `Build: ${process.env.NEXT_PUBLIC_GIT_SHA}`
                      : undefined
                  }
                >
                  {process.env.NEXT_PUBLIC_APP_VERSION && process.env.NEXT_PUBLIC_APP_VERSION !== "0.9.0"
                    ? `v${process.env.NEXT_PUBLIC_APP_VERSION}`
                    : process.env.NEXT_PUBLIC_GIT_SHA && process.env.NEXT_PUBLIC_GIT_SHA !== "unknown"
                      ? `sha-${process.env.NEXT_PUBLIC_GIT_SHA}`
                      : `v${process.env.NEXT_PUBLIC_APP_VERSION || "0.9.0"}`}
                </span>
                <span>·</span>
                <a
                  href="https://docs.rtb.cat"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-primary-600 transition-colors"
                >
                  {t.navigation.docs}
                </a>
              </div>
            </div>
            <button
              onClick={toggleCollapsed}
              className="flex items-center justify-center p-1.5 text-gray-400 hover:text-gray-600 rounded-md hover:bg-gray-50 transition-colors flex-shrink-0"
              title={t.navigation.collapse}
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <button
            onClick={toggleCollapsed}
            className="flex items-center justify-center w-full p-2 text-gray-400 hover:text-gray-600 rounded-md hover:bg-gray-50 transition-colors"
            title={t.navigation.expand}
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        )}
      </div>
    </div>
  );
}
