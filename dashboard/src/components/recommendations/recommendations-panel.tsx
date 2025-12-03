'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, RefreshCw, Sparkles } from 'lucide-react';
import { getRecommendations, getRecommendationSummary, resolveRecommendation } from '@/lib/api';
import { RecommendationCard } from './recommendation-card';

interface RecommendationsPanelProps {
  days?: number;
  minSeverity?: string;
}

export function RecommendationsPanel({
  days = 7,
  minSeverity = 'low'
}: RecommendationsPanelProps) {
  const queryClient = useQueryClient();

  const {
    data: recommendations,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['recommendations', days, minSeverity],
    queryFn: () => getRecommendations({ days, min_severity: minSeverity }),
  });

  const { data: summary } = useQuery({
    queryKey: ['recommendations-summary', days],
    queryFn: () => getRecommendationSummary(days),
  });

  const resolveMutation = useMutation({
    mutationFn: (id: string) => resolveRecommendation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations'] });
      queryClient.invalidateQueries({ queryKey: ['recommendations-summary'] });
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-32 bg-gray-100 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-center gap-2 text-red-700">
          <AlertTriangle className="h-5 w-5" />
          <span>Failed to load recommendations</span>
        </div>
        <button
          onClick={() => refetch()}
          className="mt-2 text-sm text-red-600 underline"
        >
          Try again
        </button>
      </div>
    );
  }

  const recs = recommendations || [];
  const counts = summary?.recommendation_count || { critical: 0, high: 0, medium: 0, low: 0 };

  return (
    <div>
      {/* Summary Bar */}
      <div className="mb-6 p-4 bg-white rounded-lg border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-6">
            <div>
              <div className="text-2xl font-bold text-gray-900">
                {recs.length}
              </div>
              <div className="text-sm text-gray-500">recommendations</div>
            </div>

            <div className="flex gap-3">
              {counts.critical > 0 && (
                <span className="px-2 py-1 bg-red-100 text-red-800 text-sm font-medium rounded-full">
                  {counts.critical} critical
                </span>
              )}
              {counts.high > 0 && (
                <span className="px-2 py-1 bg-orange-100 text-orange-800 text-sm font-medium rounded-full">
                  {counts.high} high
                </span>
              )}
              {counts.medium > 0 && (
                <span className="px-2 py-1 bg-yellow-100 text-yellow-800 text-sm font-medium rounded-full">
                  {counts.medium} medium
                </span>
              )}
              {counts.low > 0 && (
                <span className="px-2 py-1 bg-blue-100 text-blue-800 text-sm font-medium rounded-full">
                  {counts.low} low
                </span>
              )}
            </div>

            {summary && summary.total_spend_usd > 0 && (
              <div className="text-sm text-gray-600">
                <strong>${summary.total_spend_usd.toFixed(2)}</strong> total spend analyzed
              </div>
            )}
          </div>

          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <RefreshCw className="h-4 w-4" />
            Re-analyze
          </button>
        </div>
      </div>

      {/* Recommendations List */}
      {recs.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg border border-gray-200">
          <Sparkles className="h-12 w-12 text-green-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900">No issues detected!</h3>
          <p className="text-sm text-gray-500 mt-1">
            Your RTB configuration looks efficient. Check back after more data is collected.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {recs.map(rec => (
            <RecommendationCard
              key={rec.id}
              recommendation={rec}
              onResolve={(id) => resolveMutation.mutate(id)}
              onDismiss={(id) => resolveMutation.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
