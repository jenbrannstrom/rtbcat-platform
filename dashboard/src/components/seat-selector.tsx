"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, RefreshCw, Check, AlertCircle } from "lucide-react";
import { getSeats, syncSeat } from "@/lib/api";
import type { BuyerSeat } from "@/types/api";
import { cn } from "@/lib/utils";

interface SeatSelectorProps {
  selectedSeatId: string | null;
  onSeatChange: (seatId: string | null) => void;
}

function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return "Never synced";

  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} min${diffMins === 1 ? "" : "s"} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
  return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
}

export function SeatSelector({ selectedSeatId, onSeatChange }: SeatSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [syncMessage, setSyncMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const queryClient = useQueryClient();

  const {
    data: seats,
    isLoading: seatsLoading,
    error: seatsError,
  } = useQuery({
    queryKey: ["seats"],
    queryFn: () => getSeats({ active_only: true }),
  });

  const syncMutation = useMutation({
    mutationFn: (buyerId: string) => syncSeat(buyerId),
    onSuccess: (data) => {
      setSyncMessage({ type: "success", text: data.message });
      queryClient.invalidateQueries({ queryKey: ["creatives"] });
      queryClient.invalidateQueries({ queryKey: ["seats"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      setTimeout(() => setSyncMessage(null), 5000);
    },
    onError: (error) => {
      setSyncMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Sync failed",
      });
      setTimeout(() => setSyncMessage(null), 5000);
    },
  });

  const selectedSeat = seats?.find((s) => s.buyer_id === selectedSeatId);
  const totalCreatives = seats?.reduce((sum, s) => sum + s.creative_count, 0) ?? 0;

  const handleSeatSelect = (seatId: string | null) => {
    onSeatChange(seatId);
    setIsOpen(false);
  };

  const handleSync = () => {
    if (selectedSeatId) {
      syncMutation.mutate(selectedSeatId);
    }
  };

  if (seatsLoading) {
    return (
      <div className="flex items-center gap-3">
        <div className="h-10 w-48 bg-gray-200 rounded-md animate-pulse" />
        <div className="h-10 w-20 bg-gray-200 rounded-md animate-pulse" />
      </div>
    );
  }

  if (seatsError) {
    return (
      <div className="flex items-center gap-2 text-sm text-red-600">
        <AlertCircle className="h-4 w-4" />
        <span>Failed to load seats</span>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        {/* Seat Dropdown */}
        <div className="relative">
          <button
            onClick={() => setIsOpen(!isOpen)}
            className={cn(
              "flex items-center justify-between gap-2 px-4 py-2 min-w-[200px]",
              "bg-white border border-gray-300 rounded-lg shadow-sm",
              "hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500",
              "text-sm font-medium text-gray-700"
            )}
            aria-haspopup="listbox"
            aria-expanded={isOpen}
            aria-label="Select buyer seat"
          >
            <span className="truncate">
              {selectedSeat ? selectedSeat.display_name || `Buyer ${selectedSeat.buyer_id}` : "All Seats"}
            </span>
            <ChevronDown className={cn("h-4 w-4 text-gray-400 transition-transform", isOpen && "rotate-180")} />
          </button>

          {isOpen && (
            <div
              className="absolute z-10 mt-1 w-72 bg-white border border-gray-200 rounded-lg shadow-lg"
              role="listbox"
            >
              <div className="py-1 max-h-64 overflow-y-auto">
                {/* All Seats Option */}
                <button
                  onClick={() => handleSeatSelect(null)}
                  className={cn(
                    "w-full flex items-center justify-between px-4 py-2 text-left text-sm",
                    "hover:bg-gray-50",
                    !selectedSeatId && "bg-primary-50 text-primary-700"
                  )}
                  role="option"
                  aria-selected={!selectedSeatId}
                >
                  <div>
                    <div className="font-medium">All Seats</div>
                    <div className="text-xs text-gray-500">{totalCreatives} total creatives</div>
                  </div>
                  {!selectedSeatId && <Check className="h-4 w-4 text-primary-600" />}
                </button>

                {seats && seats.length > 0 && (
                  <div className="border-t border-gray-100 my-1" />
                )}

                {/* Individual Seats */}
                {seats?.map((seat) => (
                  <button
                    key={seat.buyer_id}
                    onClick={() => handleSeatSelect(seat.buyer_id)}
                    className={cn(
                      "w-full flex items-center justify-between px-4 py-2 text-left text-sm",
                      "hover:bg-gray-50",
                      selectedSeatId === seat.buyer_id && "bg-primary-50 text-primary-700"
                    )}
                    role="option"
                    aria-selected={selectedSeatId === seat.buyer_id}
                  >
                    <div>
                      <div className="font-medium">
                        {seat.display_name || `Buyer ${seat.buyer_id}`}
                      </div>
                      <div className="text-xs text-gray-500">
                        {seat.creative_count} creative{seat.creative_count !== 1 ? "s" : ""}
                        {seat.last_synced && ` · ${formatRelativeTime(seat.last_synced)}`}
                      </div>
                    </div>
                    {selectedSeatId === seat.buyer_id && <Check className="h-4 w-4 text-primary-600" />}
                  </button>
                ))}

                {(!seats || seats.length === 0) && (
                  <div className="px-4 py-3 text-sm text-gray-500 text-center">
                    No seats discovered yet
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Sync Button */}
        {selectedSeatId && (
          <button
            onClick={handleSync}
            disabled={syncMutation.isPending}
            className={cn(
              "flex items-center gap-2 px-4 py-2",
              "bg-primary-600 text-white rounded-lg shadow-sm",
              "hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "text-sm font-medium"
            )}
            aria-label="Sync this seat"
          >
            <RefreshCw className={cn("h-4 w-4", syncMutation.isPending && "animate-spin")} />
            <span>{syncMutation.isPending ? "Syncing..." : "Sync"}</span>
          </button>
        )}
      </div>

      {/* Seat Info Bar */}
      <div className="flex items-center gap-4 text-sm text-gray-600">
        <span className="font-medium">
          {selectedSeat ? selectedSeat.creative_count : totalCreatives} creative
          {(selectedSeat ? selectedSeat.creative_count : totalCreatives) !== 1 ? "s" : ""}
        </span>
        {selectedSeat && selectedSeat.last_synced && (
          <>
            <span className="text-gray-300">·</span>
            <span>Last synced: {formatRelativeTime(selectedSeat.last_synced)}</span>
          </>
        )}
      </div>

      {/* Sync Message */}
      {syncMessage && (
        <div
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-md text-sm",
            syncMessage.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
          )}
          role="alert"
        >
          {syncMessage.type === "success" ? (
            <Check className="h-4 w-4" />
          ) : (
            <AlertCircle className="h-4 w-4" />
          )}
          <span>{syncMessage.text}</span>
        </div>
      )}
    </div>
  );
}
