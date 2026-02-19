"use client";

import type { EndpointEfficiencyResponse } from "@/lib/api/analytics";
import { Info } from "lucide-react";

function formatNum(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toLocaleString();
}

function InfoTooltip({ text }: { text: string }) {
  return (
    <span className="relative inline-flex items-center ml-1 group">
      <Info className="h-4 w-4 text-gray-500 hover:text-gray-700 cursor-help" />
      <span className="pointer-events-none absolute right-full top-1/2 z-[9999] mr-2 hidden w-80 -translate-y-1/2 rounded-md border border-gray-300 bg-white p-3 text-sm font-normal normal-case leading-snug text-gray-800 shadow-2xl group-hover:block">
        {text}
      </span>
    </span>
  );
}

export function EndpointEfficiencyPanel({ data }: { data: EndpointEfficiencyResponse }) {
  const summary = data.summary;
  const bridge = data.funnel_breakout;
  const coverage = data.data_coverage;
  const requestedWindow = coverage?.requested_window;
  const requestedDays = requestedWindow?.days ?? data.period_days;
  const deliveryCoverage = coverage?.home_seat_daily;
  const bidstreamCoverage = coverage?.rtb_bidstream;
  const endpointFeedRows = coverage?.endpoint_feed?.rows_with_positive_qps ?? 0;
  const deliveryWinRatePct = summary.delivery_win_rate_pct ?? summary.win_rate_pct;
  const bids = summary.bids ?? 0;
  const bidsInAuction = summary.bids_in_auction ?? 0;
  const auctionsWon = summary.auctions_won ?? 0;
  const filteredBids = summary.filtered_bids ?? Math.max(bids - bidsInAuction, 0);
  const usedPctFromOvershoot = summary.allocation_overshoot_x
    ? (100 / summary.allocation_overshoot_x)
    : null;

  return (
    <section className="bg-white rounded-lg border p-3 space-y-3 overflow-visible">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Endpoint Efficiency</h3>
      </div>

      {data.alerts.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {data.alerts.map((alert) => (
            <span
              key={alert.code}
              className={
                alert.severity === "high"
                  ? "px-2 py-1 rounded border border-red-200 bg-red-50 text-red-800 text-xs"
                  : "px-2 py-1 rounded border border-yellow-200 bg-yellow-50 text-yellow-800 text-xs"
              }
            >
              {alert.message}
            </span>
          ))}
        </div>
      )}

      <div className="grid grid-cols-3 gap-2">
        <div className={`rounded border px-2.5 py-2 ${summary.endpoint_delivery_state === "missing" ? "bg-red-50 border-red-200" : "bg-slate-50 border-slate-200"}`}>
          <div className="text-[10px] uppercase text-slate-600">
            Observed QPS
            <InfoTooltip text="Measured endpoint delivery rate from rtb_endpoints_current." />
          </div>
          {summary.observed_query_rate_qps !== null ? (
            <div className="text-lg font-bold text-slate-900">{summary.observed_query_rate_qps.toLocaleString()}</div>
          ) : (
            <div className="text-sm font-medium text-red-700">Missing</div>
          )}
          <div className="text-[10px] text-gray-400">
            Proxy: {summary.funnel_proxy_qps_avg.toLocaleString()}
          </div>
        </div>
        <div className="rounded border bg-amber-50 border-amber-200 px-2.5 py-2">
          <div className="text-[10px] uppercase text-amber-700">
            Utilization
            <InfoTooltip text="Observed QPS / Allocated QPS. Low = underused capacity." />
          </div>
          <div className="text-lg font-bold text-amber-900">
            {summary.qps_utilization_pct !== null ? `${summary.qps_utilization_pct.toFixed(2)}%` : "N/A"}
          </div>
        </div>
        <div className="rounded border bg-emerald-50 border-emerald-200 px-2.5 py-2">
          <div className="text-[10px] uppercase text-emerald-700">
            Reserved / Used
            <InfoTooltip text="Capacity reserved vs actually used. E.g. 607x = 607 reserved per 1 used." />
          </div>
          <div className="text-lg font-bold text-emerald-900">
            {summary.allocation_overshoot_x ? `${summary.allocation_overshoot_x.toFixed(1)}x` : "N/A"}
            {usedPctFromOvershoot !== null && (
              <span className="text-[11px] font-normal text-emerald-700 ml-1">({usedPctFromOvershoot.toFixed(2)}%)</span>
            )}
          </div>
        </div>
      </div>

      <div className="rounded border p-2">
        <div className="text-xs font-medium text-gray-900 mb-1.5">Win Rates</div>
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div className="rounded bg-purple-50 border border-purple-100 px-2 py-1.5">
            <div className="text-[10px] text-purple-700 uppercase">Delivery Win</div>
            <div className="font-semibold">
              {typeof deliveryWinRatePct === "number" ? `${deliveryWinRatePct.toFixed(2)}%` : "N/A"}
            </div>
            <div className="text-[10px] text-gray-500">Impr / Reached ({formatNum(summary.total_impressions ?? 0)} / {formatNum(summary.total_reached_queries ?? 0)})</div>
          </div>
          <div className="rounded bg-cyan-50 border border-cyan-100 px-2 py-1.5">
            <div className="text-[10px] text-cyan-700 uppercase">Auction Win</div>
            <div className="font-semibold">
              {summary.auction_win_rate_over_bids_pct != null
                ? `${summary.auction_win_rate_over_bids_pct.toFixed(2)}%`
                : "N/A"}
            </div>
            <div className="text-[10px] text-gray-500">
              Won / Bids ({formatNum(auctionsWon)} / {formatNum(bids)})
            </div>
          </div>
          <div className="rounded bg-orange-50 border border-orange-100 px-2 py-1.5">
            <div className="text-[10px] text-orange-700 uppercase">Filtered Bids</div>
            <div className="font-semibold">
              {summary.filtered_bid_rate_pct != null
                ? `${summary.filtered_bid_rate_pct.toFixed(2)}%`
                : "N/A"}
            </div>
            <div className="text-[10px] text-gray-500">
              {formatNum(filteredBids)} filtered
            </div>
          </div>
        </div>
      </div>

      <div className="rounded border p-2">
        <div className="text-xs font-medium text-gray-900 mb-1.5">Funnel Bridge (proxy)</div>
        <div className="grid grid-cols-5 gap-2 text-sm">
          <div>
            <div className="text-[10px] text-gray-500">Available Impr</div>
            <div className="font-semibold">{formatNum(bridge.available_impressions)}</div>
          </div>
          <div>
            <div className="text-[10px] text-gray-500">Inv Matches</div>
            <div className="font-semibold">{formatNum(bridge.inventory_matches)}</div>
          </div>
          <div>
            <div className="text-[10px] text-gray-500">Filtered Impr</div>
            <div className="font-semibold">{formatNum(bridge.filtered_impressions)}</div>
          </div>
          <div>
            <div className="text-[10px] text-gray-500">PTGT Loss</div>
            <div className="font-semibold">
              {bridge.pretargeting_loss_pct !== null ? `${bridge.pretargeting_loss_pct.toFixed(1)}%` : "N/A"}
            </div>
          </div>
          <div>
            <div className="text-[10px] text-gray-500">Supply Capture</div>
            <div className="font-semibold">
              {bridge.supply_capture_pct !== null ? `${bridge.supply_capture_pct.toFixed(1)}%` : "N/A"}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
