'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Target,
  AlertTriangle,
  TrendingDown,
  Lightbulb,
  ChevronDown,
  Check,
  X,
  ExternalLink,
  Copy,
  CheckCircle,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { AIControlSettings, useAIControlMode, type AIControlMode } from './ai-control-settings';
import { useAccount } from '@/contexts/account-context';
import {
  getPretargetingConfigs,
  getQPSSizeCoverage,
  getRTBFunnelConfigs,
  createPendingChange,
  type PretargetingRecommendation,
  type SizeGap,
  type ConfigPerformanceItem,
} from '@/lib/api';

interface RecommendedOptimizationsPanelProps {
  days?: number;
  onConfigSelect?: (billingId: string) => void;
}

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toLocaleString();
}

// Individual recommendation card
function RecommendationCard({
  recommendation,
  configs,
  onApprove,
  onDismiss,
  isApplying,
}: {
  recommendation: PretargetingRecommendation;
  configs: { billing_id: string; name: string }[];
  onApprove: (billingId: string) => void;
  onDismiss: () => void;
  isApplying: boolean;
}) {
  const [showDetails, setShowDetails] = useState(false);
  const [selectedConfig, setSelectedConfig] = useState<string>('');
  const [showConfigDropdown, setShowConfigDropdown] = useState(false);
  const [copied, setCopied] = useState(false);

  // Determine icon and color based on type
  const getTypeStyles = () => {
    switch (recommendation.type) {
      case 'size_mismatch':
        return {
          icon: AlertTriangle,
          color: 'text-red-600',
          bgColor: 'bg-red-50',
          borderColor: 'border-red-200',
          label: 'HIGH IMPACT',
        };
      case 'config_underperforming':
        return {
          icon: TrendingDown,
          color: 'text-orange-600',
          bgColor: 'bg-orange-50',
          borderColor: 'border-orange-200',
          label: 'INVESTIGATE',
        };
      case 'opportunity':
        return {
          icon: Lightbulb,
          color: 'text-blue-600',
          bgColor: 'bg-blue-50',
          borderColor: 'border-blue-200',
          label: 'OPPORTUNITY',
        };
      default:
        return {
          icon: Target,
          color: 'text-gray-600',
          bgColor: 'bg-gray-50',
          borderColor: 'border-gray-200',
          label: 'SUGGESTION',
        };
    }
  };

  const styles = getTypeStyles();
  const Icon = styles.icon;

  const handleCopy = () => {
    if (recommendation.data?.sizes) {
      navigator.clipboard.writeText(recommendation.data.sizes.join(', '));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleApply = () => {
    if (selectedConfig) {
      onApprove(selectedConfig);
    }
  };

  return (
    <div className={cn('border rounded-lg', styles.borderColor, styles.bgColor)}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className={cn('p-2 rounded-lg', styles.bgColor)}>
              <Icon className={cn('h-5 w-5', styles.color)} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className={cn('text-xs font-semibold uppercase', styles.color)}>
                  {styles.label}
                </span>
              </div>
              <h4 className="font-medium text-gray-900">{recommendation.title}</h4>
              <p className="text-sm text-gray-600 mt-1">{recommendation.description}</p>

              {recommendation.estimated_savings && (
                <div className="mt-2 inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
                  Save {formatNumber(recommendation.estimated_savings.qps_per_day)} QPS/day
                  {recommendation.estimated_savings.usd_per_month && (
                    <span>(${recommendation.estimated_savings.usd_per_month}/mo)</span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-white/50 rounded transition-colors"
            >
              {showDetails ? 'Hide' : 'Details'}
            </button>

            {recommendation.type === 'size_mismatch' && (
              <div className="relative">
                <button
                  onClick={() => setShowConfigDropdown(!showConfigDropdown)}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium bg-white border border-gray-300 rounded hover:bg-gray-50"
                >
                  Apply to
                  <ChevronDown className="h-3 w-3" />
                </button>
                {showConfigDropdown && (
                  <div className="absolute right-0 mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-10">
                    <div className="p-2 border-b text-xs text-gray-500">
                      Select config to apply size filter
                    </div>
                    <div className="max-h-48 overflow-y-auto">
                      {configs.map((config) => (
                        <button
                          key={config.billing_id}
                          onClick={() => {
                            setSelectedConfig(config.billing_id);
                            setShowConfigDropdown(false);
                          }}
                          className={cn(
                            'w-full text-left px-3 py-2 text-sm hover:bg-gray-50',
                            selectedConfig === config.billing_id && 'bg-blue-50 text-blue-700'
                          )}
                        >
                          <div className="font-medium truncate">{config.name}</div>
                          <div className="text-xs text-gray-500 font-mono">
                            {config.billing_id}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            <button
              onClick={handleApply}
              disabled={!selectedConfig || isApplying}
              className={cn(
                'flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded transition-colors',
                selectedConfig
                  ? 'bg-green-600 text-white hover:bg-green-700'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              )}
            >
              {isApplying ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              Approve
            </button>

            <button
              onClick={onDismiss}
              className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-white/50 rounded transition-colors"
              title="Dismiss"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Expanded details */}
        {showDetails && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            {recommendation.data?.sizes && (
              <div className="mb-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700">
                    Sizes to block ({recommendation.data.sizes.length})
                  </span>
                  <button
                    onClick={handleCopy}
                    className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
                  >
                    {copied ? <CheckCircle className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    {copied ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <div className="flex flex-wrap gap-1">
                  {recommendation.data.sizes.map((size: string) => (
                    <span
                      key={size}
                      className="px-2 py-0.5 bg-white border border-gray-200 rounded text-xs font-mono"
                    >
                      {size}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {recommendation.reasoning && (
              <div className="text-sm text-gray-600">
                <span className="font-medium">Why: </span>
                {recommendation.reasoning}
              </div>
            )}

            {recommendation.type === 'size_mismatch' && (
              <div className="mt-3 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
                <strong>Note:</strong> Size filtering is INCLUDE-only. Adding sizes to a config
                will exclude all unlisted sizes.{' '}
                <a
                  href="https://developers.google.com/authorized-buyers/apis/guides/rtb-api/pretargeting-configs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-0.5 text-amber-700 underline"
                >
                  Learn more <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function RecommendedOptimizationsPanel({
  days = 7,
  onConfigSelect,
}: RecommendedOptimizationsPanelProps) {
  const aiMode = useAIControlMode();
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();

  // Fetch size coverage to generate size mismatch recommendations
  const { data: sizeCoverage, isLoading: sizeLoading } = useQuery({
    queryKey: ['size-coverage', days],
    queryFn: () => getQPSSizeCoverage(days),
    enabled: aiMode !== 'manual',
  });

  // Fetch config performance for underperforming recommendations
  const { data: configPerformance, isLoading: configPerfLoading } = useQuery({
    queryKey: ['rtb-funnel-configs', days],
    queryFn: () => getRTBFunnelConfigs(days),
    enabled: aiMode !== 'manual',
  });

  const recsLoading = sizeLoading || configPerfLoading;

  // Generate recommendations from size coverage and config performance
  const recommendations: PretargetingRecommendation[] = [];

  // Size mismatch recommendations
  if (sizeCoverage?.gaps && sizeCoverage.gaps.length > 0) {
    const highPriorityGaps = sizeCoverage.gaps.filter(
      (g: SizeGap) => g.recommendation === 'BLOCK_IN_PRETARGETING'
    );
    if (highPriorityGaps.length > 0) {
      const totalQps = highPriorityGaps.reduce(
        (sum: number, g: SizeGap) => sum + (g.daily_estimate || g.queries_received),
        0
      );
      recommendations.push({
        id: 'size-mismatch-1',
        type: 'size_mismatch',
        title: `Block ${highPriorityGaps.length} sizes without creatives`,
        description: `You're receiving traffic for ${highPriorityGaps.length} sizes you can't serve.`,
        reasoning:
          'These sizes have high daily traffic but no approved creatives. Blocking them in pretargeting will reduce wasted QPS.',
        estimated_savings: {
          qps_per_day: totalQps,
          usd_per_month: Math.round(totalQps * 0.002 * 30), // Rough estimate
        },
        data: {
          sizes: highPriorityGaps.map((g: SizeGap) => g.size),
        },
      });
    }
  }

  // Config underperforming recommendations
  if (configPerformance?.configs && configPerformance.configs.length > 0) {
    const avgWinRate =
      configPerformance.configs.reduce((sum: number, c: ConfigPerformanceItem) => sum + (c.win_rate || 0), 0) /
      configPerformance.configs.length;
    const underperforming = configPerformance.configs.filter(
      (c: ConfigPerformanceItem) => c.win_rate < avgWinRate * 0.7 && c.reached_queries > 1000
    );
    for (const config of underperforming.slice(0, 2)) {
      recommendations.push({
        id: `config-underperforming-${config.billing_id}`,
        type: 'config_underperforming',
        title: `${config.config_name || config.billing_id} performing below threshold`,
        description: `Win rate ${config.win_rate?.toFixed(1)}% vs account avg ${avgWinRate.toFixed(1)}%`,
        reasoning:
          'This config has significantly lower win rate. Consider narrowing geo targeting or reviewing size coverage.',
        data: {
          billing_id: config.billing_id,
          config_name: config.config_name,
          current_win_rate: config.win_rate,
          avg_win_rate: avgWinRate,
        },
      });
    }
  }

  // Opportunity recommendations (sizes with high traffic we could serve)
  if (sizeCoverage?.gaps) {
    const opportunities = sizeCoverage.gaps.filter(
      (g: SizeGap) =>
        g.recommendation === 'CONSIDER_ADDING_CREATIVE' && (g.daily_estimate || g.queries_received) > 5000
    );
    if (opportunities.length > 0) {
      const topOpp = opportunities[0];
      const dailyQps = topOpp.daily_estimate || topOpp.queries_received;
      recommendations.push({
        id: 'opportunity-size-1',
        type: 'opportunity',
        title: `${topOpp.size} has ${formatNumber(dailyQps)} QPS/day`,
        description: 'Create creative for this size to capture additional traffic.',
        reasoning: `This size has significant daily traffic. Adding a creative would allow you to bid on this inventory.`,
        data: {
          sizes: [topOpp.size],
        },
      });
    }
  }

  const { selectedServiceAccountId } = useAccount();

  // Fetch configs for the dropdown
  const { data: configs } = useQuery({
    queryKey: ['pretargeting-configs', selectedServiceAccountId],
    queryFn: () => getPretargetingConfigs({ service_account_id: selectedServiceAccountId || undefined }),
  });

  // Mutation to apply recommendation
  const applyMutation = useMutation({
    mutationFn: async ({
      billingId,
      recommendation,
    }: {
      billingId: string;
      recommendation: PretargetingRecommendation;
    }) => {
      // Create pending changes for each size to block
      if (recommendation.type === 'size_mismatch' && recommendation.data?.sizes) {
        for (const size of recommendation.data.sizes) {
          await createPendingChange({
            billing_id: billingId,
            change_type: 'remove_size',
            field_name: 'included_sizes',
            value: size,
            reason: `AI recommendation: ${recommendation.title}`,
          });
        }
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail'] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-recommendations'] });
    },
  });

  const handleDismiss = (id: string) => {
    setDismissedIds((prev) => new Set([...prev, id]));
  };

  const handleApprove = (billingId: string, recommendation: PretargetingRecommendation) => {
    applyMutation.mutate({ billingId, recommendation });
    handleDismiss(recommendation.id);
  };

  // Filter out dismissed recommendations
  const visibleRecs = (recommendations || []).filter((r) => !dismissedIds.has(r.id));

  // In manual mode, show minimal UI
  if (aiMode === 'manual') {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Target className="h-5 w-5 text-gray-400" />
            <h3 className="font-semibold text-gray-900">Recommended Optimizations</h3>
          </div>
          <AIControlSettings compact />
        </div>
        <div className="text-center py-8 text-gray-500">
          <p>AI recommendations are disabled in manual mode.</p>
          <p className="text-sm mt-1">Switch to "AI proposes" to see optimization suggestions.</p>
        </div>
      </div>
    );
  }

  const configOptions = (configs || []).map((c) => ({
    billing_id: c.billing_id || c.config_id,
    name: c.user_name || c.display_name || `Config ${c.billing_id || c.config_id}`,
  }));

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Target className="h-5 w-5 text-blue-600" />
          <h3 className="font-semibold text-gray-900">Recommended Optimizations</h3>
          {visibleRecs.length > 0 && (
            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs font-medium rounded-full">
              {visibleRecs.length} action{visibleRecs.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <AIControlSettings compact />
      </div>

      {recsLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : visibleRecs.length === 0 ? (
        <div className="text-center py-8">
          <CheckCircle className="h-10 w-10 text-green-500 mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No optimization recommendations</p>
          <p className="text-sm text-gray-500 mt-1">
            Your pretargeting configs are performing well based on {days}-day analysis.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-gray-600 mb-4">
            Based on {days}-day analysis, here's where to cut waste:
          </p>
          {visibleRecs.map((rec, index) => (
            <RecommendationCard
              key={rec.id}
              recommendation={{ ...rec, id: rec.id || `rec-${index}` }}
              configs={configOptions}
              onApprove={(billingId) => handleApprove(billingId, rec)}
              onDismiss={() => handleDismiss(rec.id || `rec-${index}`)}
              isApplying={applyMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* AI Control Settings (expanded) */}
      <div className="mt-6 pt-4 border-t border-gray-200">
        <AIControlSettings onModeChange={() => {}} />
      </div>
    </div>
  );
}
