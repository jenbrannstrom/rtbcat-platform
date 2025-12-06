'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { ChevronRight } from 'lucide-react';

// Local formatNumber since the main utils might not have it
function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

interface SizePerformance {
  size: string;
  reached: number;
  impressions: number;
  win_rate_pct: number;
  waste_pct: number;
}

interface ConfigSettings {
  format: string;
  geos: string[];
  platforms: string[];
  qps_limit: number | null;
  budget_usd: number | null;
}

interface ConfigData {
  billing_id: string;
  name: string;
  reached: number;
  bids: number;
  impressions: number;
  win_rate_pct: number;
  waste_pct: number;
  settings: ConfigSettings;
  sizes: SizePerformance[];
}

interface ConfigPerformanceResponse {
  period_days: number;
  configs: ConfigData[];
  total_reached: number;
  total_impressions: number;
  overall_win_rate_pct: number;
  overall_waste_pct: number;
}

export function ConfigPerformanceSection() {
  const { data, isLoading, error } = useQuery<ConfigPerformanceResponse>({
    queryKey: ['rtb-funnel-configs'],
    queryFn: async () => {
      const res = await fetch('http://localhost:8000/analytics/rtb-funnel/configs');
      if (!res.ok) throw new Error('Failed to fetch');
      return res.json();
    },
  });

  if (isLoading) {
    return <div className="animate-pulse h-32 bg-gray-100 rounded-lg" />;
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-600 text-sm">
        Failed to load config performance data
      </div>
    );
  }

  if (!data?.configs?.length) {
    return (
      <div className="bg-gray-50 border rounded-lg p-4 text-gray-500 text-sm">
        No config data available. Import bidding metrics CSV with billing_id dimension.
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border p-4">
      <h3 className="text-lg font-semibold mb-1">Pretargeting Configs</h3>
      <p className="text-xs text-gray-500 mb-3">
        Click to expand settings and size breakdown
      </p>

      <div className="space-y-1">
        {data.configs.map((config) => (
          <ConfigRow key={config.billing_id} config={config} />
        ))}
      </div>

      <div className="mt-3 pt-3 border-t flex justify-between text-sm">
        <span className="text-gray-500">Total</span>
        <div className="flex gap-6">
          <span>{formatNumber(data.total_reached)} reached</span>
          <span
            className={cn(
              data.overall_win_rate_pct >= 40 && 'text-green-600',
              data.overall_win_rate_pct < 40 &&
                data.overall_win_rate_pct >= 20 &&
                'text-yellow-600',
              data.overall_win_rate_pct < 20 && 'text-red-600'
            )}
          >
            {data.overall_win_rate_pct.toFixed(1)}% win
          </span>
          <span className="text-red-600">{data.overall_waste_pct.toFixed(1)}% waste</span>
        </div>
      </div>
    </div>
  );
}

function ConfigRow({ config }: { config: ConfigData }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border rounded">
      {/* Collapsed row - compact */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-3 py-2 flex items-center gap-3 hover:bg-gray-50 text-sm"
      >
        <ChevronRight
          className={cn(
            'h-4 w-4 text-gray-400 transition-transform',
            expanded && 'rotate-90'
          )}
        />

        {/* Show name if different from billing_id, otherwise just show billing_id */}
        {config.name && config.name !== config.billing_id && !config.name.startsWith('Config ') ? (
          <>
            <span className="font-mono text-xs text-gray-400 w-20 shrink-0">{config.billing_id}</span>
            <span className="font-medium flex-1 text-left truncate">{config.name}</span>
          </>
        ) : (
          <span className="font-mono text-sm text-gray-700 flex-1 text-left">
            Config {config.billing_id}
          </span>
        )}

        <div className="flex gap-4 text-xs">
          <span className="text-gray-600 w-20 text-right">
            {formatNumber(config.reached)}
          </span>
          <span
            className={cn(
              'w-16 text-right',
              config.win_rate_pct >= 40 && 'text-green-600',
              config.win_rate_pct < 40 && config.win_rate_pct >= 20 && 'text-yellow-600',
              config.win_rate_pct < 20 && 'text-red-600'
            )}
          >
            {config.win_rate_pct.toFixed(1)}% win
          </span>
          <span className="text-red-600 w-16 text-right">
            {config.waste_pct.toFixed(1)}%
          </span>
          <WasteMiniBar pct={config.waste_pct} />
        </div>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t bg-gray-50">
          {/* Settings row - compact horizontal */}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs mb-3">
            <SettingChip label="Format" value={config.settings.format} />
            <SettingChip
              label="Geos"
              value={
                config.settings.geos.slice(0, 5).join(', ') +
                (config.settings.geos.length > 5 ? '...' : '')
              }
            />
            <SettingChip label="Platform" value={config.settings.platforms.join(', ')} />
            {config.settings.qps_limit && (
              <SettingChip label="QPS" value={config.settings.qps_limit.toString()} />
            )}
            {config.settings.budget_usd && (
              <SettingChip label="Budget" value={`$${config.settings.budget_usd}/d`} />
            )}
          </div>

          {/* Size performance - compact table */}
          {config.sizes.length > 0 && (
            <div className="bg-white rounded border">
              <div className="grid grid-cols-5 gap-2 px-2 py-1 border-b text-xs text-gray-500">
                <span>Size</span>
                <span className="text-right">Reached</span>
                <span className="text-right">Win%</span>
                <span className="text-right">Waste</span>
                <span></span>
              </div>
              {config.sizes.map((size) => (
                <div
                  key={size.size}
                  className="grid grid-cols-5 gap-2 px-2 py-1 text-xs border-b last:border-0"
                >
                  <span className="font-mono">{size.size}</span>
                  <span className="text-right text-gray-600">
                    {formatNumber(size.reached)}
                  </span>
                  <span
                    className={cn(
                      'text-right',
                      size.win_rate_pct >= 40 && 'text-green-600',
                      size.win_rate_pct < 40 && size.win_rate_pct >= 20 && 'text-yellow-600',
                      size.win_rate_pct < 20 && 'text-red-600'
                    )}
                  >
                    {size.win_rate_pct.toFixed(1)}%
                  </span>
                  <span className="text-right text-red-500">{size.waste_pct.toFixed(1)}%</span>
                  <WasteMiniBar pct={size.waste_pct} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SettingChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="text-gray-500">
      <span className="text-gray-400">{label}:</span> {value}
    </span>
  );
}

function WasteMiniBar({ pct }: { pct: number }) {
  return (
    <div className="w-12 h-2 bg-gray-200 rounded-full overflow-hidden">
      <div
        className={cn(
          'h-full',
          pct < 50 && 'bg-green-400',
          pct >= 50 && pct < 70 && 'bg-yellow-400',
          pct >= 70 && 'bg-red-400'
        )}
        style={{ width: `${Math.min(pct, 100)}%` }}
      />
    </div>
  );
}
