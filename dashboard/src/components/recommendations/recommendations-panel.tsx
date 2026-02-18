'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, RefreshCw, Sparkles } from 'lucide-react';
import {
  getRecommendations,
  getRecommendationSummary,
  resolveRecommendation,
  getPretargetingConfigs,
  createPendingChange,
  type Action,
  type Recommendation,
} from '@/lib/api';
import { useAccount } from '@/contexts/account-context';
import { RecommendationCard } from './recommendation-card';

interface RecommendationsPanelProps {
  days?: number;
  minSeverity?: string;
}

type PendingChangeMapping = {
  change_type: string;
  field_name: string;
  value: string;
};

function mapActionToPendingChange(action: Action): PendingChangeMapping | null {
  const rawTarget = (action.target_id || action.target_name || '').trim();
  if (!rawTarget) return null;

  const target = rawTarget.replace(/^format-/i, '');
  const actionType = action.action_type.toLowerCase();
  const targetType = action.target_type.toLowerCase();
  const field = (action.pretargeting_field || '').toLowerCase();

  if (targetType === 'size') {
    return {
      change_type: actionType === 'add' ? 'add_size' : 'remove_size',
      field_name: 'included_sizes',
      value: target,
    };
  }

  if (targetType === 'geo') {
    return actionType === 'add'
      ? { change_type: 'add_geo', field_name: 'included_geos', value: target }
      : { change_type: 'add_excluded_geo', field_name: 'excluded_geos', value: target };
  }

  if (targetType === 'publisher' || targetType === 'app') {
    return {
      change_type: actionType === 'remove' ? 'remove_publisher' : 'add_publisher',
      field_name: 'publisher_targeting_values',
      value: target,
    };
  }

  if (targetType === 'config') {
    if (field.includes('format')) {
      return {
        change_type: actionType === 'add' ? 'add_format' : 'remove_format',
        field_name: 'included_formats',
        value: target,
      };
    }
    if (field.includes('geo')) {
      return actionType === 'add'
        ? { change_type: 'add_geo', field_name: 'included_geos', value: target }
        : { change_type: 'add_excluded_geo', field_name: 'excluded_geos', value: target };
    }
    if (field.includes('publisher')) {
      return {
        change_type: actionType === 'remove' ? 'remove_publisher' : 'add_publisher',
        field_name: 'publisher_targeting_values',
        value: target,
      };
    }
  }

  return null;
}

export function RecommendationsPanel({
  days = 7,
  minSeverity = 'low'
}: RecommendationsPanelProps) {
  const queryClient = useQueryClient();
  const { selectedBuyerId } = useAccount();
  const [applyFeedback, setApplyFeedback] = useState<Record<string, { message: string; error: boolean }>>({});

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

  const { data: pretargetingConfigs = [] } = useQuery({
    queryKey: ['recommendation-config-options', selectedBuyerId],
    queryFn: () => getPretargetingConfigs({ buyer_id: selectedBuyerId || undefined }),
    enabled: !!selectedBuyerId,
    staleTime: 60_000,
  });

  const applyMutation = useMutation({
    mutationFn: async ({
      recommendation,
      billingId,
    }: {
      recommendation: Recommendation;
      billingId: string;
    }) => {
      let staged = 0;
      for (const action of recommendation.actions) {
        const mapped = mapActionToPendingChange(action);
        if (!mapped) continue;
        await createPendingChange({
          billing_id: billingId,
          change_type: mapped.change_type,
          field_name: mapped.field_name,
          value: mapped.value,
          reason: `Recommendation ${recommendation.id}: ${recommendation.title}`,
        });
        staged += 1;
      }
      if (staged === 0) {
        throw new Error('No compatible pretargeting actions found for this recommendation.');
      }
      return { staged };
    },
    onSuccess: ({ staged }, variables) => {
      setApplyFeedback((prev) => ({
        ...prev,
        [variables.recommendation.id]: {
          message: `Staged ${staged} pending change${staged === 1 ? '' : 's'} for ${variables.billingId}. Review and push in Settings.`,
          error: false,
        },
      }));
      queryClient.invalidateQueries({ queryKey: ['pending-changes'] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail'] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
    },
    onError: (error, variables) => {
      setApplyFeedback((prev) => ({
        ...prev,
        [variables.recommendation.id]: {
          message: error instanceof Error ? error.message : 'Failed to stage pending changes.',
          error: true,
        },
      }));
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
  const configOptions = pretargetingConfigs.map((config) => ({
    billing_id: config.billing_id || config.config_id,
    name: config.user_name || config.display_name || `Config ${config.billing_id || config.config_id}`,
  }));

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
            <div key={rec.id} className="space-y-2">
              <RecommendationCard
                recommendation={rec}
                onResolve={(id) => resolveMutation.mutate(id)}
                onDismiss={(id) => resolveMutation.mutate(id)}
                onApply={(recommendation, billingId) => applyMutation.mutate({ recommendation, billingId })}
                configOptions={configOptions}
                isApplying={applyMutation.isPending && applyMutation.variables?.recommendation.id === rec.id}
              />
              {applyFeedback[rec.id] && (
                <div
                  className={
                    applyFeedback[rec.id].error
                      ? "px-3 py-2 rounded border border-red-200 bg-red-50 text-xs text-red-700"
                      : "px-3 py-2 rounded border border-amber-200 bg-amber-50 text-xs text-amber-800"
                  }
                >
                  {applyFeedback[rec.id].message}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
