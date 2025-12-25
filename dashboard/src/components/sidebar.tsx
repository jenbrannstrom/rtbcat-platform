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
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getSeats, syncSeat } from "@/lib/api";
import { useAccount } from "@/contexts/account-context";

const SIDEBAR_COLLAPSED_KEY = "rtbcat-sidebar-collapsed";

const navigation = [
  { name: "Waste Optimizer", href: "/", icon: TrendingDown },
  { name: "Creatives", href: "/creatives", icon: Image },
  { name: "Campaigns", href: "/campaigns", icon: FolderKanban },
  { name: "Change History", href: "/history", icon: History },
  { name: "Import", href: "/import", icon: RefreshCw },
  { name: "Setup", href: "/setup", icon: Settings },
];

function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return "Never";
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { selectedBuyerId, setSelectedBuyerId } = useAccount();

  const [collapsed, setCollapsed] = useState(false);
  const [seatDropdownOpen, setSeatDropdownOpen] = useState(false);
  const [syncMessage, setSyncMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Use context for buyer_id (persistent across pages)
  const currentBuyerId = selectedBuyerId;

  // Load collapsed state from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
    if (stored !== null) {
      setCollapsed(stored === "true");
    }
  }, []);

  const toggleCollapsed = () => {
    const newValue = !collapsed;
    setCollapsed(newValue);
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(newValue));
  };

  const { data: seats } = useQuery({
    queryKey: ["seats"],
    queryFn: () => getSeats({ active_only: true }),
  });

  const syncMutation = useMutation({
    mutationFn: (buyerId: string) => syncSeat(buyerId),
    onSuccess: (data) => {
      setSyncMessage({ type: "success", text: "Synced!" });
      queryClient.invalidateQueries({ queryKey: ["creatives"] });
      queryClient.invalidateQueries({ queryKey: ["seats"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      setTimeout(() => setSyncMessage(null), 3000);
    },
    onError: (error) => {
      setSyncMessage({ type: "error", text: "Failed" });
      setTimeout(() => setSyncMessage(null), 3000);
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
            <p className="font-medium text-gray-700">No seats connected</p>
            <p className="text-xs mt-1">Go to Settings to connect</p>
          </div>
        ) : seats.length === 1 ? (
          /* Single seat - show as title with sync button */
          <div>
            <div className="flex items-center justify-between gap-2 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg">
              <div className="min-w-0 flex-1">
                <div className="font-medium text-sm text-gray-700 truncate">
                  {seats[0].display_name || `Buyer ${seats[0].buyer_id}`}
                </div>
                <div className="text-xs text-gray-500">
                  {seats[0].creative_count} creatives
                </div>
              </div>
              <button
                onClick={() => syncMutation.mutate(seats[0].buyer_id)}
                disabled={syncMutation.isPending}
                className={cn(
                  "p-1.5 rounded-md text-gray-500 hover:text-primary-600 hover:bg-primary-50",
                  "disabled:opacity-50 flex-shrink-0"
                )}
                title="Sync creatives"
              >
                <RefreshCw className={cn("h-4 w-4", syncMutation.isPending && "animate-spin")} />
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
                {selectedSeat ? selectedSeat.display_name || `Buyer ${selectedSeat.buyer_id}` : "All Seats"}
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
                    <div className="font-medium">All Seats</div>
                    <div className="text-xs text-gray-500">{totalCreatives} creatives</div>
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
                      <div className="font-medium">{seat.display_name || `Buyer ${seat.buyer_id}`}</div>
                      <div className="text-xs text-gray-500">
                        {seat.creative_count} · {formatRelativeTime(seat.last_synced)}
                      </div>
                    </div>
                    {currentBuyerId === seat.buyer_id && <Check className="h-4 w-4 text-primary-600" />}
                  </button>
                ))}
              </div>
            )}

            {/* Sync button when seat is selected */}
            {currentBuyerId && (
              <button
                onClick={() => syncMutation.mutate(currentBuyerId)}
                disabled={syncMutation.isPending}
                className={cn(
                  "mt-2 w-full flex items-center justify-center gap-2 px-3 py-1.5",
                  "bg-primary-600 text-white rounded-md text-sm font-medium",
                  "hover:bg-primary-700 disabled:opacity-50"
                )}
              >
                <RefreshCw className={cn("h-3.5 w-3.5", syncMutation.isPending && "animate-spin")} />
                {syncMutation.isPending ? "Syncing..." : "Sync"}
              </button>
            )}

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
      <nav className="flex-1 px-2 py-4 space-y-1">
        {navigation.map((item) => {
          // Handle exact match for home, prefix match for other routes
          const isActive = item.href === "/"
            ? pathname === "/"
            : pathname.startsWith(item.href);
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors",
                isActive
                  ? "bg-primary-50 text-primary-700"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                collapsed && "justify-center px-2"
              )}
              title={collapsed ? item.name : undefined}
            >
              <item.icon
                className={cn(
                  "h-5 w-5 flex-shrink-0",
                  isActive ? "text-primary-600" : "text-gray-400",
                  !collapsed && "mr-3"
                )}
              />
              {!collapsed && item.name}
            </Link>
          );
        })}
      </nav>

      {/* Footer with collapse toggle */}
      <div className="px-2 py-4 border-t border-gray-200">
        {!collapsed && (
          <a
            href="https://rtb.cat"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center px-3 py-2 text-sm font-medium text-gray-600 hover:text-primary-600 rounded-md hover:bg-gray-50 transition-colors"
          >
            <ExternalLink className="mr-3 h-5 w-5 text-gray-400" />
            Docs
          </a>
        )}
        <button
          onClick={toggleCollapsed}
          className={cn(
            "flex items-center w-full px-3 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 rounded-md hover:bg-gray-50 transition-colors",
            collapsed && "justify-center px-2"
          )}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="h-5 w-5 text-gray-400" />
          ) : (
            <>
              <ChevronLeft className="mr-3 h-5 w-5 text-gray-400" />
              Collapse
            </>
          )}
        </button>
        {!collapsed && <p className="mt-2 px-3 text-xs text-gray-500">v0.1.0</p>}
      </div>
    </div>
  );
}
