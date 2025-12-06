'use client';

import { useQuery } from '@tanstack/react-query';
import { ConfigPerformanceSection } from '@/components/rtb/config-performance';
import { CreativeWinPerformance } from '@/components/rtb/creative-win-performance';

interface FunnelData {
  has_data: boolean;
  total_reached_queries: number;
  total_impressions: number;
  win_rate: number;
}

interface FunnelResponse {
  funnel: FunnelData;
}

export default function WasteAnalysisPage() {
  const { data: funnelData } = useQuery<FunnelResponse>({
    queryKey: ['rtb-funnel'],
    queryFn: async () => {
      const res = await fetch('http://localhost:8000/analytics/rtb-funnel');
      if (!res.ok) throw new Error('Failed to fetch');
      return res.json();
    },
  });

  const wasteRate =
    funnelData?.funnel?.has_data && funnelData.funnel.win_rate
      ? 100 - funnelData.funnel.win_rate
      : 66.1; // Default from spec

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <header className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Waste Analysis</h1>
          <p className="text-gray-600 mt-1">
            Identify WHERE the {wasteRate.toFixed(1)}% waste originates across configs,
            creatives, and geos
          </p>
        </header>

        {/* RTB Funnel Summary */}
        {funnelData?.funnel?.has_data && (
          <section className="mb-8">
            <div className="bg-white rounded-lg border p-6">
              <h2 className="text-lg font-semibold mb-4">RTB Funnel Overview</h2>
              <div className="grid grid-cols-4 gap-6">
                <FunnelMetric
                  label="Reached"
                  value={formatNumber(funnelData.funnel.total_reached_queries)}
                  subtitle="queries"
                />
                <FunnelMetric
                  label="Won"
                  value={formatNumber(funnelData.funnel.total_impressions)}
                  subtitle="impressions"
                />
                <FunnelMetric
                  label="Win Rate"
                  value={`${funnelData.funnel.win_rate.toFixed(1)}%`}
                  subtitle="conversion"
                  className="text-green-600"
                />
                <FunnelMetric
                  label="Waste"
                  value={`${wasteRate.toFixed(1)}%`}
                  subtitle="lost traffic"
                  className="text-red-600"
                />
              </div>
            </div>
          </section>
        )}

        {/* Pretargeting Configs */}
        <section className="mb-8">
          <ConfigPerformanceSection />
        </section>

        {/* Creative Win Performance */}
        <section className="mb-8">
          <CreativeWinPerformance />
        </section>

        {/* Footer note */}
        <footer className="text-center text-sm text-gray-500 mt-12">
          <p>
            Phase 29: Multi-View Waste Analysis - Triangulating where waste originates
          </p>
        </footer>
      </div>
    </div>
  );
}

function FunnelMetric({
  label,
  value,
  subtitle,
  className,
}: {
  label: string;
  value: string;
  subtitle: string;
  className?: string;
}) {
  return (
    <div className="text-center">
      <div className="text-sm text-gray-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${className || 'text-gray-900'}`}>{value}</div>
      <div className="text-xs text-gray-400">{subtitle}</div>
    </div>
  );
}

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}
