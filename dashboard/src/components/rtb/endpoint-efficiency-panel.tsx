"use client";

import type { EndpointEfficiencyResponse } from "@/lib/api/analytics";
import { Info } from "lucide-react";

function formatNum(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toLocaleString();
}

function formatLocation(location: string | null): string {
  if (!location) return "Unknown";
  const map: Record<string, string> = {
    US_WEST: "US West",
    US_EAST: "US East",
    EUROPE: "Europe",
    ASIA: "Asia",
  };
  return map[location] || location;
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

function statusLabel(status: "mapped" | "missing_in_google" | "extra_in_google"): string {
  if (status === "mapped") return "Mapped";
  if (status === "missing_in_google") return "Missing in feed";
  return "Extra in feed";
}

export function EndpointEfficiencyPanel({ data }: { data: EndpointEfficiencyResponse }) {
  const summary = data.summary;
  const recon = data.endpoint_reconciliation;
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
    <section className="bg-white rounded-lg border p-4 space-y-4 overflow-visible">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">Endpoint Efficiency</h3>
          <div className="text-xs text-gray-500">
            Requested window: {requestedWindow?.start_date ?? data.window.start_date} to {requestedWindow?.end_date ?? data.window.end_date}
          </div>
          <div className="text-xs text-amber-700">
            Delivery data: {deliveryCoverage?.start_date || "N/A"} to {deliveryCoverage?.end_date || "N/A"} ({deliveryCoverage?.days_with_data ?? 0}/{requestedDays} days)
          </div>
          <div className="text-xs text-indigo-700">
            Auction-funnel data: {bidstreamCoverage?.start_date || "N/A"} to {bidstreamCoverage?.end_date || "N/A"} ({bidstreamCoverage?.days_with_data ?? 0}/{requestedDays} days)
          </div>
        </div>
        <span className="text-xs text-gray-500">Endpoint feed rows: {endpointFeedRows}</span>
      </div>

      {data.alerts.length > 0 && (
        <div className="space-y-2">
          {data.alerts.map((alert) => (
            <div
              key={alert.code}
              className={
                alert.severity === "high"
                  ? "px-3 py-2 rounded border border-red-200 bg-red-50 text-red-800 text-sm"
                  : "px-3 py-2 rounded border border-yellow-200 bg-yellow-50 text-yellow-800 text-sm"
              }
            >
              {alert.message}
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="rounded border bg-blue-50 border-blue-100 p-3">
          <div className="text-[11px] uppercase text-blue-700">
            Allocated QPS Cap
            <InfoTooltip text="Total configured endpoint capacity in Cat-Scan (sum of maximum_qps)." />
          </div>
          <div className="text-xl font-bold text-blue-900">{summary.allocated_qps.toLocaleString()}</div>
        </div>
        <div className={`rounded border p-3 ${summary.endpoint_delivery_state === "missing" ? "bg-red-50 border-red-200" : "bg-slate-50 border-slate-200"}`}>
          <div className="text-[11px] uppercase text-slate-600">
            Observed Endpoint QPS
            <InfoTooltip text="Measured endpoint delivery rate from rtb_endpoints_current. This is the observed feed, not configuration." />
          </div>
          {summary.observed_query_rate_qps !== null ? (
            <div className="text-xl font-bold text-slate-900">{summary.observed_query_rate_qps.toLocaleString()} QPS</div>
          ) : (
            <div className="text-sm font-medium text-red-700">Feed missing</div>
          )}
          <div className="text-[10px] text-gray-400 mt-1">
            Funnel proxy: {summary.funnel_proxy_qps_avg.toLocaleString()} QPS
            <InfoTooltip text="Proxy computed from reached queries in the selected period. Useful context, but not endpoint feed truth." />
          </div>
        </div>
        <div className="rounded border bg-amber-50 border-amber-200 p-3">
          <div className="text-[11px] uppercase text-amber-700">
            Utilization
            <InfoTooltip text="Observed Endpoint QPS divided by Allocated QPS Cap. Low values mean allocated capacity is underused." />
          </div>
          <div className="text-xl font-bold text-amber-900">
            {summary.qps_utilization_pct !== null ? `${summary.qps_utilization_pct.toFixed(2)}%` : "N/A"}
          </div>
        </div>
        <div className="rounded border bg-emerald-50 border-emerald-200 p-3">
          <div className="text-[11px] uppercase text-emerald-700">
            Reserved vs Used
            <InfoTooltip text="This shows how much capacity you reserved compared to what was actually used. Example: 607.5x means you reserved about 607.5 units for each 1 unit used." />
          </div>
          <div className="text-xl font-bold text-emerald-900">
            {summary.allocation_overshoot_x ? `${summary.allocation_overshoot_x.toFixed(1)}x` : "N/A"}
          </div>
          {usedPctFromOvershoot !== null && (
            <div className="text-[12px] text-emerald-800 mt-1">
              Used: {usedPctFromOvershoot.toFixed(2)}%
            </div>
          )}
        </div>
      </div>

      <div className="rounded border p-3">
        <div className="text-sm font-medium text-gray-900 mb-2">
          Formula Clarity (AB Parity)
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div className="rounded bg-purple-50 border border-purple-100 p-2">
            <div className="text-xs text-purple-700 uppercase">Delivery Win</div>
            <div className="font-semibold">
              {typeof deliveryWinRatePct === "number" ? `${deliveryWinRatePct.toFixed(2)}%` : "N/A"}
            </div>
            <div className="text-[11px] text-gray-600">Impressions / Reached Queries</div>
          </div>
          <div className="rounded bg-cyan-50 border border-cyan-100 p-2">
            <div className="text-xs text-cyan-700 uppercase">Auction Win</div>
            <div className="font-semibold">
              {summary.auction_win_rate_over_bids_pct != null
                ? `${summary.auction_win_rate_over_bids_pct.toFixed(2)}%`
                : "N/A"}
            </div>
            <div className="text-[11px] text-gray-600">
              Auctions Won / Bids ({formatNum(auctionsWon)} / {formatNum(bids)})
            </div>
          </div>
          <div className="rounded bg-orange-50 border border-orange-100 p-2">
            <div className="text-xs text-orange-700 uppercase">Filtered Bid Rate</div>
            <div className="font-semibold">
              {summary.filtered_bid_rate_pct != null
                ? `${summary.filtered_bid_rate_pct.toFixed(2)}%`
                : "N/A"}
            </div>
            <div className="text-[11px] text-gray-600">
              (Bids - Bids in Auction) / Bids ({formatNum(filteredBids)})
            </div>
          </div>
        </div>
      </div>

      <div className="rounded border p-3">
        <div className="text-sm font-medium text-gray-900 mb-2">
          Endpoint Reconciliation
        </div>
        <div className="text-xs text-gray-600 mb-3">
          CatScan endpoints: {recon.counts.catscan_endpoints} | Observed rows: {recon.counts.google_delivery_rows} | Missing: {recon.counts.missing_in_google}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b">
                <th className="py-2 pr-3">Location</th>
                <th className="py-2 pr-3">Allocated QPS</th>
                <th className="py-2 pr-3">Observed QPS</th>
                <th className="py-2">
                  Status
                  <InfoTooltip text="Mapped: configured endpoint has matching observed feed row. Missing in feed: configured endpoint has no observed row. Extra in feed: observed row exists without matching configured endpoint." />
                </th>
              </tr>
            </thead>
            <tbody>
              {recon.rows.map((row, idx) => (
                <tr key={`${row.catscan_endpoint_id || "extra"}-${idx}`} className="border-b last:border-0">
                  <td className="py-2 pr-3 text-gray-800">
                    {formatLocation(row.catscan_location || row.google_location)}
                  </td>
                  <td className="py-2 pr-3 text-gray-700">
                    {row.allocated_qps !== null ? row.allocated_qps.toLocaleString() : "—"}
                  </td>
                  <td className="py-2 pr-3 text-gray-700">
                    {row.google_current_qps !== null ? row.google_current_qps.toFixed(1) : "—"}
                  </td>
                  <td className="py-2">
                    <span
                      className={
                        row.mapping_status === "mapped"
                          ? "text-green-700"
                          : row.mapping_status === "missing_in_google"
                            ? "text-red-700"
                            : "text-amber-700"
                      }
                    >
                      {statusLabel(row.mapping_status)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded border p-3">
        <div className="text-sm font-medium text-gray-900 mb-2">Funnel Bridge (proxy)</div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
          <div>
            <div className="text-xs text-gray-500">Available Impressions</div>
            <div className="font-semibold">{formatNum(bridge.available_impressions)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Inventory Matches</div>
            <div className="font-semibold">{formatNum(bridge.inventory_matches)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Filtered Impressions</div>
            <div className="font-semibold">{formatNum(bridge.filtered_impressions)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Pretargeting Loss</div>
            <div className="font-semibold">
              {bridge.pretargeting_loss_pct !== null ? `${bridge.pretargeting_loss_pct.toFixed(1)}%` : "N/A"}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Supply Capture</div>
            <div className="font-semibold">
              {bridge.supply_capture_pct !== null ? `${bridge.supply_capture_pct.toFixed(1)}%` : "N/A"}
            </div>
          </div>
        </div>
        <div className="text-xs text-gray-500 mt-2">
          Available impressions proxy source: <code>{bridge.available_impressions_proxy_source}</code>.
          <InfoTooltip text="This value is estimated from bid requests in precomputed seat-level data, used as an availability proxy in the funnel bridge." />
        </div>
      </div>
    </section>
  );
}
