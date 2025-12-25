'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Settings, ChevronDown, ChevronUp, Copy, Check, Globe, LayoutGrid, Video, Image, FileText } from 'lucide-react';
import { getPretargetingRecommendations, type PretargetingConfig } from '@/lib/api';
import { cn } from '@/lib/utils';

interface PretargetingPanelProps {
  days?: number;
}

const formatIcons: Record<string, typeof Video> = {
  VIDEO: Video,
  NATIVE: Image,
  HTML: FileText,
};

function ConfigCard({ config, index }: { config: PretargetingConfig; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const copyGeoConfig = () => {
    const text = JSON.stringify({
      includedGeos: config.targeting.geos.included,
      excludedGeos: config.targeting.geos.excluded,
    }, null, 2);
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={cn(
      "bg-white rounded-lg border p-4",
      index === 0 ? "border-blue-300 ring-1 ring-blue-100" : "border-gray-200"
    )}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={cn(
            "w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold",
            index === 0 ? "bg-blue-600 text-white" : "bg-gray-200 text-gray-600"
          )}>
            {config.priority}
          </div>
          <div>
            <h4 className="font-semibold text-gray-900">{config.name}</h4>
            <p className="text-sm text-gray-500">{config.description}</p>
          </div>
        </div>
        <div className="text-right">
          {config.estimated_impact.waste_reduction_pct > 0 && (
            <div className="text-green-600 font-semibold">
              -{config.estimated_impact.waste_reduction_pct}% waste
            </div>
          )}
          <div className="text-sm text-gray-500">
            {config.estimated_impact.impressions.toLocaleString()} imps
          </div>
        </div>
      </div>

      {/* Targeting Summary */}
      <div className="mt-4 flex flex-wrap gap-2">
        {/* Formats */}
        {config.targeting.formats.map(fmt => {
          const Icon = formatIcons[fmt] || FileText;
          return (
            <span key={fmt} className="inline-flex items-center gap-1 px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-medium">
              <Icon className="h-3 w-3" />
              {fmt}
            </span>
          );
        })}

        {/* Sizes */}
        {config.targeting.sizes.total_count > 0 && (
          <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">
            <LayoutGrid className="h-3 w-3" />
            {config.targeting.sizes.total_count} sizes
          </span>
        )}

        {/* Geos */}
        <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
          <Globe className="h-3 w-3" />
          {config.targeting.geos.included_count} geos included
        </span>

        {config.targeting.geos.excluded.length > 0 && (
          <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-medium">
            <Globe className="h-3 w-3" />
            {config.targeting.geos.excluded.length} excluded
          </span>
        )}
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
            Show targeting details
          </>
        )}
      </button>

      {/* Expanded Details */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-gray-200 space-y-4">
          {/* Included Sizes */}
          {config.targeting.sizes.included.length > 0 && (
            <div>
              <h5 className="text-sm font-medium text-gray-700 mb-2">Included Sizes</h5>
              <div className="flex flex-wrap gap-1">
                {config.targeting.sizes.included.map(size => (
                  <span key={size} className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-mono">
                    {size}
                  </span>
                ))}
                {config.targeting.sizes.total_count > config.targeting.sizes.included.length && (
                  <span className="px-2 py-0.5 text-gray-500 text-xs">
                    +{config.targeting.sizes.total_count - config.targeting.sizes.included.length} more
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Included Geos */}
          <div>
            <h5 className="text-sm font-medium text-gray-700 mb-2">Included Geos</h5>
            <div className="flex flex-wrap gap-1">
              {config.targeting.geos.included.map(geo => (
                <span key={geo} className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">
                  {geo}
                </span>
              ))}
            </div>
          </div>

          {/* Excluded Geos */}
          {config.targeting.geos.excluded.length > 0 && (
            <div>
              <h5 className="text-sm font-medium text-gray-700 mb-2">Excluded Geos</h5>
              <div className="flex flex-wrap gap-1">
                {config.targeting.geos.excluded.map(geo => (
                  <span key={geo} className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs font-medium">
                    {geo}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Copy Button */}
          <button
            onClick={copyGeoConfig}
            className="flex items-center gap-2 px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded text-sm text-gray-700"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4 text-green-600" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                Copy geo config as JSON
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}

export function PretargetingPanel({ days = 7 }: PretargetingPanelProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['pretargeting-recommendations', days],
    queryFn: () => getPretargetingRecommendations(days),
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3" />
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-24 bg-gray-100 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-center gap-2 text-red-700">
          <AlertTriangle className="h-5 w-5" />
          <span>Failed to load pretargeting recommendations</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Settings className="h-5 w-5 text-purple-600" />
            Pretargeting Configurations
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            {data.summary}
          </p>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-500">
            {data.configs.length} / {data.config_limit} configs
          </div>
          {data.total_waste_reduction_pct > 0 && (
            <div className="text-green-600 font-semibold">
              -{data.total_waste_reduction_pct}% total waste reduction
            </div>
          )}
        </div>
      </div>

      {/* Config Cards */}
      <div className="space-y-4">
        {data.configs.map((config, index) => (
          <ConfigCard key={config.name} config={config} index={index} />
        ))}
      </div>

      {data.configs.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          No pretargeting recommendations available.
          <br />
          <span className="text-sm">Need more traffic data to analyze.</span>
        </div>
      )}
    </div>
  );
}
