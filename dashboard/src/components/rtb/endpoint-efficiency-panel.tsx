"use client";

import type { EndpointEfficiencyResponse } from "@/lib/api/analytics";

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

export function EndpointEfficiencyPanel({ data }: { data: EndpointEfficiencyResponse }) {
  const summary = data.summary;
  const recon = data.endpoint_reconciliation;
  const bridge = data.funnel_breakout;

  return (
    <section className="bg-white rounded-lg border p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Endpoint Efficiency</h3>
        <span className="text-xs text-gray-500">
          {data.window.start_date} to {data.window.end_date}
        </span>
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
          <div className="text-[11px] uppercase text-blue-700">Allocated QPS Cap</div>
          <div className="text-xl font-bold text-blue-900">{summary.allocated_qps.toLocaleString()}</div>
        </div>
        <div className={`rounded border p-3 ${summary.endpoint_delivery_state === "missing" ? "bg-red-50 border-red-200" : "bg-slate-50 border-slate-200"}`}>
          <div className="text-[11px] uppercase text-slate-600">Observed Endpoint QPS</div>
          {summary.observed_query_rate_qps !== null ? (
            <div className="text-xl font-bold text-slate-900">{summary.observed_query_rate_qps.toLocaleString()} QPS</div>
          ) : (
            <div className="text-sm font-medium text-red-700">Feed missing</div>
          )}
          <div className="text-[10px] text-gray-400 mt-1">Funnel proxy: {summary.funnel_proxy_qps_avg.toLocaleString()} QPS</div>
        </div>
        <div className="rounded border bg-amber-50 border-amber-200 p-3">
          <div className="text-[11px] uppercase text-amber-700">Utilization</div>
          <div className="text-xl font-bold text-amber-900">
            {summary.qps_utilization_pct !== null ? `${summary.qps_utilization_pct.toFixed(2)}%` : "N/A"}
          </div>
        </div>
        <div className="rounded border bg-emerald-50 border-emerald-200 p-3">
          <div className="text-[11px] uppercase text-emerald-700">Overshoot</div>
          <div className="text-xl font-bold text-emerald-900">
            {summary.allocation_overshoot_x ? `${summary.allocation_overshoot_x.toFixed(1)}x` : "N/A"}
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
                <th className="py-2">Status</th>
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
                      {row.mapping_status}
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
        </div>
      </div>
    </section>
  );
}
