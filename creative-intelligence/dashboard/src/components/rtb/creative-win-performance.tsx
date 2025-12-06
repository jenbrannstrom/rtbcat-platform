'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { cn, formatNumber } from '@/lib/utils';
import { AlertTriangle, CheckCircle, AlertCircle } from 'lucide-react';

interface CreativeData {
  creative_id: string;
  reached: number;
  bids: number;
  impressions: number;
  win_rate_pct: number;
  waste_pct: number;
  status: 'great' | 'ok' | 'review';
}

interface CreativeSummary {
  total_creatives: number;
  great_performers: number;
  ok_performers: number;
  underperformers: number;
}

interface CreativeWinPerformanceResponse {
  period_days: number;
  creatives: CreativeData[];
  summary: CreativeSummary;
}

type FilterType = 'all' | 'great' | 'ok' | 'review';

export function CreativeWinPerformance() {
  const [filter, setFilter] = useState<FilterType>('all');

  const { data, isLoading, error } = useQuery<CreativeWinPerformanceResponse>({
    queryKey: ['rtb-funnel-creatives'],
    queryFn: async () => {
      const res = await fetch('http://localhost:8000/analytics/rtb-funnel/creatives');
      if (!res.ok) throw new Error('Failed to fetch');
      return res.json();
    },
  });

  if (isLoading) {
    return <div className="animate-pulse h-64 bg-gray-100 rounded-lg" />;
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-600 text-sm">
        Failed to load creative performance data
      </div>
    );
  }

  if (!data?.creatives?.length) {
    return (
      <div className="bg-gray-50 border rounded-lg p-4 text-gray-500 text-sm">
        No creative data available. Import ADX bidding metrics CSV.
      </div>
    );
  }

  const filtered =
    filter === 'all'
      ? data.creatives
      : data.creatives.filter((c) => c.status === filter);

  return (
    <div className="bg-white rounded-lg border p-6">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold">Creative Win Performance</h3>
          <p className="text-sm text-gray-500">
            Win rate metrics (NOT clicks/CTR - that's media buyer's job)
          </p>
        </div>

        {/* Summary badges */}
        <div className="flex gap-2">
          <FilterBadge
            label={`${data.summary.great_performers} Great`}
            active={filter === 'great'}
            color="green"
            onClick={() => setFilter(filter === 'great' ? 'all' : 'great')}
          />
          <FilterBadge
            label={`${data.summary.ok_performers} OK`}
            active={filter === 'ok'}
            color="yellow"
            onClick={() => setFilter(filter === 'ok' ? 'all' : 'ok')}
          />
          <FilterBadge
            label={`${data.summary.underperformers} Review`}
            active={filter === 'review'}
            color="red"
            onClick={() => setFilter(filter === 'review' ? 'all' : 'review')}
          />
        </div>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left">
            <th className="py-2">Creative</th>
            <th className="py-2 text-right">Reached</th>
            <th className="py-2 text-right">Bids</th>
            <th className="py-2 text-right">Won</th>
            <th className="py-2 text-right">Win Rate</th>
            <th className="py-2 text-right">Waste</th>
            <th className="py-2 text-center">Status</th>
          </tr>
        </thead>
        <tbody>
          {filtered.slice(0, 20).map((creative) => (
            <tr key={creative.creative_id} className="border-b hover:bg-gray-50">
              <td className="py-3 font-mono">{creative.creative_id}</td>
              <td className="py-3 text-right">{formatNumber(creative.reached)}</td>
              <td className="py-3 text-right">{formatNumber(creative.bids)}</td>
              <td className="py-3 text-right">{formatNumber(creative.impressions)}</td>
              <td className="py-3 text-right font-medium">
                <span
                  className={cn(
                    creative.win_rate_pct >= 50 && 'text-green-600',
                    creative.win_rate_pct >= 20 &&
                      creative.win_rate_pct < 50 &&
                      'text-yellow-600',
                    creative.win_rate_pct < 20 && 'text-red-600'
                  )}
                >
                  {creative.win_rate_pct.toFixed(1)}%
                </span>
              </td>
              <td className="py-3 text-right text-gray-500">
                {creative.waste_pct.toFixed(1)}%
              </td>
              <td className="py-3 text-center">
                <StatusIcon status={creative.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {filtered.length > 20 && (
        <div className="mt-4 text-center text-sm text-gray-500">
          Showing 20 of {filtered.length} creatives
        </div>
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'great':
      return <CheckCircle className="h-5 w-5 text-green-500 mx-auto" />;
    case 'ok':
      return <AlertCircle className="h-5 w-5 text-yellow-500 mx-auto" />;
    case 'review':
      return <AlertTriangle className="h-5 w-5 text-red-500 mx-auto" />;
    default:
      return null;
  }
}

function FilterBadge({
  label,
  active,
  color,
  onClick,
}: {
  label: string;
  active: boolean;
  color: 'green' | 'yellow' | 'red';
  onClick: () => void;
}) {
  const colors = {
    green: active
      ? 'bg-green-100 text-green-800 ring-green-500'
      : 'bg-green-50 text-green-600',
    yellow: active
      ? 'bg-yellow-100 text-yellow-800 ring-yellow-500'
      : 'bg-yellow-50 text-yellow-600',
    red: active ? 'bg-red-100 text-red-800 ring-red-500' : 'bg-red-50 text-red-600',
  };

  return (
    <button
      onClick={onClick}
      className={cn(
        'px-3 py-1 rounded-full text-xs font-medium transition-all',
        colors[color],
        active && 'ring-2'
      )}
    >
      {label}
    </button>
  );
}
