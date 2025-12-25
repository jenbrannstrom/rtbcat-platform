'use client';

import { useState } from 'react';
import {
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Globe,
  Image,
  Settings,
  Shield,
  Ban,
  XCircle
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Recommendation } from '@/lib/api';

const severityConfig = {
  critical: {
    icon: AlertTriangle,
    color: 'text-red-600',
    bg: 'bg-red-50',
    border: 'border-red-200',
    badge: 'bg-red-100 text-red-800'
  },
  high: {
    icon: AlertCircle,
    color: 'text-orange-600',
    bg: 'bg-orange-50',
    border: 'border-orange-200',
    badge: 'bg-orange-100 text-orange-800'
  },
  medium: {
    icon: Info,
    color: 'text-yellow-600',
    bg: 'bg-yellow-50',
    border: 'border-yellow-200',
    badge: 'bg-yellow-100 text-yellow-800'
  },
  low: {
    icon: Info,
    color: 'text-blue-600',
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    badge: 'bg-blue-100 text-blue-800'
  },
};

const typeIcons: Record<string, typeof Globe> = {
  size_mismatch: Image,
  geo_exclusion: Globe,
  publisher_block: Ban,
  config_inefficiency: Settings,
  creative_pause: XCircle,
  creative_review: AlertCircle,
  fraud_alert: Shield,
};

interface RecommendationCardProps {
  recommendation: Recommendation;
  onResolve?: (id: string) => void;
  onDismiss?: (id: string) => void;
}

export function RecommendationCard({
  recommendation,
  onResolve,
  onDismiss
}: RecommendationCardProps) {
  const [expanded, setExpanded] = useState(false);

  const config = severityConfig[recommendation.severity as keyof typeof severityConfig] || severityConfig.low;
  const SeverityIcon = config.icon;
  const TypeIcon = typeIcons[recommendation.type] || Info;

  const impact = recommendation.impact;

  return (
    <div className={cn(
      "rounded-lg border p-4 transition-all",
      config.bg,
      config.border,
      expanded && "ring-2 ring-offset-1",
    )}>
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className={cn("p-2 rounded-lg", config.bg)}>
          <SeverityIcon className={cn("h-5 w-5", config.color)} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full", config.badge)}>
              {recommendation.severity.toUpperCase()}
            </span>
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <TypeIcon className="h-3 w-3" />
              {recommendation.type.replace(/_/g, ' ')}
            </span>
          </div>

          <h3 className="font-semibold text-gray-900 mt-1">
            {recommendation.title}
          </h3>

          <p className="text-sm text-gray-600 mt-1">
            {recommendation.description}
          </p>
        </div>

        {/* Impact Badge */}
        <div className="text-right flex-shrink-0">
          {impact.wasted_spend_usd > 0 ? (
            <>
              <div className="text-lg font-bold text-gray-900">
                ${impact.wasted_spend_usd.toFixed(2)}
              </div>
              <div className="text-xs text-gray-500">
                wasted
              </div>
            </>
          ) : impact.wasted_qps > 0 ? (
            <>
              <div className="text-lg font-bold text-gray-900">
                {impact.wasted_qps.toFixed(1)} QPS
              </div>
              <div className="text-xs text-gray-500">
                wasted
              </div>
            </>
          ) : (
            <>
              <div className="text-lg font-bold text-green-600">
                ${impact.potential_savings_monthly.toFixed(0)}
              </div>
              <div className="text-xs text-gray-500">
                potential savings
              </div>
            </>
          )}
        </div>
      </div>

      {/* Expand/Collapse */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="mt-3 flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
      >
        {expanded ? (
          <>
            <ChevronUp className="h-4 w-4" />
            Hide details
          </>
        ) : (
          <>
            <ChevronDown className="h-4 w-4" />
            Show details & actions
          </>
        )}
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-gray-200 space-y-4">
          {/* Impact Details */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">Impact</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-white rounded p-2 text-center">
                <div className="text-lg font-semibold">{impact.wasted_queries_daily.toLocaleString()}</div>
                <div className="text-xs text-gray-500">queries/day</div>
              </div>
              <div className="bg-white rounded p-2 text-center">
                <div className="text-lg font-semibold">${impact.wasted_spend_usd.toFixed(2)}</div>
                <div className="text-xs text-gray-500">wasted spend</div>
              </div>
              <div className="bg-white rounded p-2 text-center">
                <div className="text-lg font-semibold">{impact.percent_of_total_waste.toFixed(1)}%</div>
                <div className="text-xs text-gray-500">of total waste</div>
              </div>
              <div className="bg-white rounded p-2 text-center">
                <div className="text-lg font-semibold">${impact.potential_savings_monthly.toFixed(0)}</div>
                <div className="text-xs text-gray-500">savings/month</div>
              </div>
            </div>
          </div>

          {/* Evidence */}
          {recommendation.evidence.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Evidence</h4>
              <ul className="space-y-1">
                {recommendation.evidence.map((e, i) => (
                  <li key={i} className="text-sm text-gray-600 flex items-center gap-2">
                    <CheckCircle2 className="h-3 w-3 text-green-500" />
                    <span>
                      {e.metric_name}: <strong>{e.metric_value.toLocaleString(undefined, { maximumFractionDigits: 2 })}</strong>
                      {' '}({e.comparison} threshold of {e.threshold.toLocaleString(undefined, { maximumFractionDigits: 2 })})
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Actions */}
          {recommendation.actions.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Recommended Actions</h4>
              <div className="space-y-2">
                {recommendation.actions.map((action, i) => (
                  <div key={i} className="bg-white rounded p-3 border border-gray-200">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-sm font-medium capitalize">
                          {action.action_type}
                        </span>
                        <span className="text-sm text-gray-600">
                          {' '}{action.target_type}: <strong>{action.target_name}</strong>
                        </span>
                      </div>
                      {action.pretargeting_field && (
                        <span className="text-xs bg-gray-100 px-2 py-1 rounded">
                          {action.pretargeting_field}
                        </span>
                      )}
                    </div>
                    {action.api_example && (
                      <pre className="mt-2 text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                        {action.api_example}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-2 pt-2">
            <button
              onClick={() => onResolve?.(recommendation.id)}
              className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700"
            >
              Mark Resolved
            </button>
            <button
              onClick={() => onDismiss?.(recommendation.id)}
              className="px-4 py-2 bg-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-300"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
