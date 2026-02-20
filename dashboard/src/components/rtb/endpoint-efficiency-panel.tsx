"use client";

import type { EndpointEfficiencyResponse } from "@/lib/api/analytics";
import { Info } from "lucide-react";

function formatNum(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toLocaleString();
}

function InfoTip({ text }: { text: string }) {
  return (
    <span className="relative inline-flex items-center ml-0.5 group">
      <Info className="h-3 w-3 text-gray-400 hover:text-gray-600 cursor-help" />
      <span className="pointer-events-none absolute right-full top-1/2 z-[9999] mr-1.5 hidden w-64 -translate-y-1/2 rounded border border-gray-200 bg-white p-2 text-[11px] font-normal normal-case leading-snug text-gray-700 shadow-lg group-hover:block">
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
  const deliveryWinRatePct = summary.delivery_win_rate_pct ?? summary.win_rate_pct;
  const bids = summary.bids ?? 0;
  const bidsInAuction = summary.bids_in_auction ?? 0;
  const auctionsWon = summary.auctions_won ?? 0;
  const filteredBids = summary.filtered_bids ?? Math.max(bids - bidsInAuction, 0);
  return (
    <section className="bg-white rounded-lg border p-2.5 space-y-2 overflow-visible">
      {/* Header: title + coverage badges only (date range shown once in top bar) */}
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-gray-900">Efficiency</h3>
        <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-700">
          Delivery {deliveryCoverage?.days_with_data ?? 0}/{requestedDays}d
        </span>
        <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] text-indigo-700">
          Auction {bidstreamCoverage?.days_with_data ?? 0}/{requestedDays}d
        </span>
      </div>

      {/* Alerts - compact */}
      {data.alerts.length > 0 && (
        <div className="space-y-1">
          {data.alerts.map((alert) => (
            <div
              key={alert.code}
              className={
                alert.severity === "high"
                  ? "px-2 py-1.5 rounded border border-red-200 bg-red-50 text-red-800 text-xs"
                  : "px-2 py-1.5 rounded border border-yellow-200 bg-yellow-50 text-yellow-800 text-xs"
              }
            >
              {alert.message}
            </div>
          ))}
        </div>
      )}

      {/* Compact metrics - single flex row */}
      <div className="flex flex-wrap gap-1.5">
        <div className="rounded border bg-slate-50 border-slate-200 px-2 py-1">
          <div className="text-[9px] uppercase text-slate-500 leading-tight">
            Observed QPS
            <InfoTip text="Measured endpoint delivery rate from feed. Not configuration." />
          </div>
          {summary.observed_query_rate_qps !== null ? (
            <div className="text-sm font-bold text-slate-900">{summary.observed_query_rate_qps.toLocaleString()}</div>
          ) : (
            <div className="text-xs font-medium text-red-600">Feed missing</div>
          )}
        </div>
        <div className="rounded border bg-amber-50 border-amber-200 px-2 py-1">
          <div className="text-[9px] uppercase text-amber-600 leading-tight">
            Utilization
            <InfoTip text="Observed QPS / Allocated QPS Cap." />
          </div>
          <div className="text-sm font-bold text-amber-900">
            {summary.qps_utilization_pct !== null ? `${summary.qps_utilization_pct.toFixed(2)}%` : "N/A"}
          </div>
        </div>
        <div className="rounded border bg-emerald-50 border-emerald-200 px-2 py-1">
          <div className="text-[9px] uppercase text-emerald-600 leading-tight">
            Overshoot
            <InfoTip text="How much capacity reserved compared to actually used." />
          </div>
          <div className="text-sm font-bold text-emerald-900">
            {summary.allocation_overshoot_x ? `${summary.allocation_overshoot_x.toFixed(1)}x` : "N/A"}
          </div>
        </div>
        <div className="rounded border bg-purple-50 border-purple-200 px-2 py-1">
          <div className="text-[9px] uppercase text-purple-600 leading-tight">Delivery Win</div>
          <div className="text-sm font-bold text-purple-900">
            {typeof deliveryWinRatePct === "number" ? `${deliveryWinRatePct.toFixed(2)}%` : "N/A"}
          </div>
        </div>
        <div className="rounded border bg-cyan-50 border-cyan-100 px-2 py-1">
          <div className="text-[9px] text-cyan-600 uppercase leading-tight">Auction Win</div>
          <div className="text-sm font-semibold">
            {summary.auction_win_rate_over_bids_pct != null
              ? `${summary.auction_win_rate_over_bids_pct.toFixed(2)}%`
              : "N/A"}
          </div>
          <div className="text-[9px] text-gray-400">{formatNum(auctionsWon)}/{formatNum(bids)}</div>
        </div>
        <div className="rounded border bg-orange-50 border-orange-100 px-2 py-1">
          <div className="text-[9px] text-orange-600 uppercase leading-tight">Filtered</div>
          <div className="text-sm font-semibold">
            {summary.filtered_bid_rate_pct != null
              ? `${summary.filtered_bid_rate_pct.toFixed(2)}%`
              : "N/A"}
          </div>
          <div className="text-[9px] text-gray-400">{formatNum(filteredBids)}</div>
        </div>
        <div className="rounded border bg-gray-50 border-gray-200 px-2 py-1">
          <div className="text-[9px] text-gray-500 uppercase leading-tight">PTGT Loss</div>
          <div className="text-sm font-semibold">
            {bridge.pretargeting_loss_pct !== null ? `${bridge.pretargeting_loss_pct.toFixed(1)}%` : "N/A"}
          </div>
          <div className="text-[9px] text-gray-400">
            Cap: {bridge.supply_capture_pct !== null ? `${bridge.supply_capture_pct.toFixed(1)}%` : "N/A"}
          </div>
        </div>
      </div>

      {/* Funnel bridge - collapsed into compact row */}
      <div className="flex items-center gap-3 px-2 py-1.5 rounded border bg-gray-50 text-[11px]">
        <span className="text-gray-500 font-medium">Funnel:</span>
        <span>Avail {formatNum(bridge.available_impressions)}</span>
        <span className="text-gray-300">|</span>
        <span>Matched {formatNum(bridge.inventory_matches)}</span>
        <span className="text-gray-300">|</span>
        <span>Filtered {formatNum(bridge.filtered_impressions)}</span>
        <span className="text-gray-300">|</span>
        <span className="text-[10px] text-gray-400">
          Source: {bridge.available_impressions_proxy_source}
        </span>
      </div>
    </section>
  );
}
