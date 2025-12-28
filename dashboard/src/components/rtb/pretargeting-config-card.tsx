'use client';

import { useState, useRef, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { setPretargetingName } from '@/lib/api';
import { ChevronRight, Pencil, Check, X, AlertTriangle, AlertCircle, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SnapshotComparisonPanel } from './snapshot-comparison-panel';
import { PretargetingSettingsEditor } from './pretargeting-settings-editor';

export interface PretargetingConfig {
  billing_id: string;
  name: string;              // resolved: user_name || display_name || 'Config {id}'
  display_name: string | null;
  user_name: string | null;
  state: 'ACTIVE' | 'SUSPENDED';
  formats: string[];         // ['HTML', 'VAST']
  platforms: string[];       // ['PHONE', 'TABLET']
  sizes: string[];           // ['300x250', '320x50']
  included_geos: string[];   // country codes
  reached: number;
  impressions: number;
  win_rate: number;
  waste_rate: number;
}

interface PretargetingConfigCardProps {
  config: PretargetingConfig;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

// Format large numbers
function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

// Google Ads geo criterion ID to ISO 3166-1 alpha-3 country code mapping
// Reference: https://developers.google.com/google-ads/api/reference/data/geotargets
const GEO_ID_TO_COUNTRY: Record<string, string> = {
  '2004': 'AFG', '2008': 'ALB', '2012': 'DZA', '2016': 'ASM', '2020': 'AND',
  '2024': 'AGO', '2028': 'ATG', '2031': 'AZE', '2032': 'ARG', '2036': 'AUS',
  '2040': 'AUT', '2044': 'BHS', '2048': 'BHR', '2050': 'BGD', '2051': 'ARM',
  '2052': 'BRB', '2056': 'BEL', '2060': 'BMU', '2064': 'BTN', '2068': 'BOL',
  '2070': 'BIH', '2072': 'BWA', '2076': 'BRA', '2084': 'BLZ', '2090': 'SLB',
  '2092': 'VGB', '2096': 'BRN', '2100': 'BGR', '2104': 'MMR', '2108': 'BDI',
  '2112': 'BLR', '2116': 'KHM', '2120': 'CMR', '2124': 'CAN', '2132': 'CPV',
  '2136': 'CYM', '2140': 'CAF', '2144': 'LKA', '2148': 'TCD', '2152': 'CHL',
  '2156': 'CHN', '2158': 'TWN', '2162': 'CXI', '2166': 'CCK', '2170': 'COL',
  '2174': 'COM', '2175': 'MYT', '2178': 'COG', '2180': 'COD', '2184': 'COK',
  '2188': 'CRI', '2191': 'HRV', '2192': 'CUB', '2196': 'CYP', '2203': 'CZE',
  '2204': 'BEN', '2208': 'DNK', '2212': 'DMA', '2214': 'DOM', '2218': 'ECU',
  '2222': 'SLV', '2226': 'GNQ', '2231': 'ETH', '2232': 'ERI', '2233': 'EST',
  '2234': 'FRO', '2238': 'FLK', '2242': 'FJI', '2246': 'FIN', '2250': 'FRA',
  '2254': 'GUF', '2258': 'PYF', '2262': 'DJI', '2266': 'GAB', '2268': 'GEO',
  '2270': 'GMB', '2276': 'DEU', '2288': 'GHA', '2292': 'GIB', '2296': 'KIR',
  '2300': 'GRC', '2304': 'GRL', '2308': 'GRD', '2312': 'GLP', '2316': 'GUM',
  '2320': 'GTM', '2324': 'GIN', '2328': 'GUY', '2332': 'HTI', '2336': 'VAT',
  '2340': 'HND', '2344': 'HKG', '2348': 'HUN', '2352': 'ISL', '2356': 'IND',
  '2360': 'IDN', '2364': 'IRN', '2368': 'IRQ', '2372': 'IRL', '2376': 'ISR',
  '2380': 'ITA', '2384': 'CIV', '2388': 'JAM', '2392': 'JPN', '2398': 'KAZ',
  '2400': 'JOR', '2404': 'KEN', '2408': 'PRK', '2410': 'KOR', '2414': 'KWT',
  '2417': 'KGZ', '2418': 'LAO', '2422': 'LBN', '2426': 'LSO', '2428': 'LVA',
  '2430': 'LBR', '2434': 'LBY', '2438': 'LIE', '2440': 'LTU', '2442': 'LUX',
  '2446': 'MAC', '2450': 'MDG', '2454': 'MWI', '2458': 'MYS', '2462': 'MDV',
  '2466': 'MLI', '2470': 'MLT', '2474': 'MTQ', '2478': 'MRT', '2480': 'MUS',
  '2484': 'MEX', '2492': 'MCO', '2496': 'MNG', '2498': 'MDA', '2499': 'MNE',
  '2500': 'MSR', '2504': 'MAR', '2508': 'MOZ', '2512': 'OMN', '2516': 'NAM',
  '2520': 'NRU', '2524': 'NPL', '2528': 'NLD', '2531': 'CUW', '2533': 'ABW',
  '2534': 'SXM', '2535': 'BES', '2540': 'NCL', '2548': 'VUT', '2554': 'NZL',
  '2558': 'NIC', '2562': 'NER', '2566': 'NGA', '2570': 'NIU', '2574': 'NFK',
  '2578': 'NOR', '2580': 'MNP', '2583': 'FSM', '2584': 'MHL', '2585': 'PLW',
  '2586': 'PAK', '2591': 'PAN', '2598': 'PNG', '2600': 'PRY', '2604': 'PER',
  '2608': 'PHL', '2612': 'PCN', '2616': 'POL', '2620': 'PRT', '2624': 'GNB',
  '2626': 'TLS', '2630': 'PRI', '2634': 'QAT', '2638': 'REU', '2642': 'ROU',
  '2643': 'RUS', '2646': 'RWA', '2652': 'BLM', '2654': 'SHN', '2659': 'KNA',
  '2660': 'AIA', '2662': 'LCA', '2663': 'MAF', '2666': 'SPM', '2670': 'VCT',
  '2674': 'SMR', '2678': 'STP', '2682': 'SAU', '2686': 'SEN', '2688': 'SRB',
  '2690': 'SYC', '2694': 'SLE', '2702': 'SGP', '2703': 'SVK', '2704': 'VNM',
  '2705': 'SVN', '2706': 'SOM', '2710': 'ZAF', '2716': 'ZWE', '2724': 'ESP',
  '2728': 'SSD', '2729': 'SDN', '2732': 'ESH', '2736': 'SUR', '2740': 'SJM',
  '2744': 'SWZ', '2748': 'SWE', '2752': 'CHE', '2760': 'SYR', '2762': 'TJK',
  '2764': 'THA', '2768': 'TGO', '2772': 'TKL', '2776': 'TON', '2780': 'TTO',
  '2784': 'ARE', '2788': 'TUN', '2792': 'TUR', '2795': 'TKM', '2796': 'TCA',
  '2798': 'TUV', '2800': 'UGA', '2804': 'UKR', '2807': 'MKD', '2818': 'EGY',
  '2826': 'GBR', '2831': 'GGY', '2832': 'JEY', '2833': 'IMN', '2834': 'TZA',
  '2840': 'USA', '2850': 'VIR', '2854': 'BFA', '2858': 'URY', '2860': 'UZB',
  '2862': 'VEN', '2876': 'WLF', '2882': 'WSM', '2887': 'YEM', '2894': 'ZMB',
};

// Convert geo ID to country code
function formatGeoCode(geoId: string): string {
  // If it's already a 2 or 3 letter code, return as-is
  if (/^[A-Z]{2,3}$/i.test(geoId)) {
    return geoId.toUpperCase();
  }
  // Look up the country code
  return GEO_ID_TO_COUNTRY[geoId] || geoId;
}

// Pill component for settings
function SettingPill({ label, values, max = 3, formatValue }: {
  label: string;
  values: string[];
  max?: number;
  formatValue?: (v: string) => string;
}) {
  if (!values?.length) return null;

  const displayValues = values.slice(0, max);
  const remaining = values.length - max;
  const formatter = formatValue || ((v: string) => v);

  return (
    <div className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-600">
      <span className="text-gray-400">{label}:</span>
      <span>{displayValues.map(formatter).join(', ')}</span>
      {remaining > 0 && <span className="text-gray-400">+{remaining}</span>}
    </div>
  );
}

// Mini progress bar for waste
function WasteMiniBar({ pct }: { pct: number }) {
  return (
    <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
      <div
        className={cn(
          'h-full transition-all',
          pct < 50 && 'bg-green-400',
          pct >= 50 && pct < 70 && 'bg-yellow-400',
          pct >= 70 && pct < 90 && 'bg-orange-400',
          pct >= 90 && 'bg-red-500'
        )}
        style={{ width: `${Math.min(pct, 100)}%` }}
      />
    </div>
  );
}

export function PretargetingConfigCard({ config, isExpanded, onToggleExpand }: PretargetingConfigCardProps) {
  // Support both controlled and uncontrolled expansion
  const [internalExpanded, setInternalExpanded] = useState(false);
  const expanded = isExpanded !== undefined ? isExpanded : internalExpanded;
  const handleToggle = onToggleExpand || (() => setInternalExpanded(!internalExpanded));
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(config.name);
  const [showSettingsEditor, setShowSettingsEditor] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const nameMutation = useMutation({
    mutationFn: ({ billingId, userName }: { billingId: string; userName: string }) =>
      setPretargetingName(billingId, userName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
      setIsEditing(false);
    },
  });

  // Focus input when editing starts
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleStartEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditValue(config.user_name || config.display_name || '');
    setIsEditing(true);
  };

  const handleSave = () => {
    if (editValue.trim() && editValue !== config.user_name) {
      nameMutation.mutate({ billingId: config.billing_id, userName: editValue.trim() });
    } else {
      setIsEditing(false);
    }
  };

  const handleCancel = () => {
    setEditValue(config.name);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  // Determine status indicator
  const isHighWaste = config.waste_rate >= 70;
  const isCriticalWaste = config.waste_rate >= 90;
  const isGoodWinRate = config.win_rate >= 50;

  // Check if using display_name from Google (not user-defined)
  const isGoogleName = !config.user_name && config.display_name;

  return (
    <div
      className={cn(
        'border rounded-lg transition-all',
        config.state === 'SUSPENDED' && 'opacity-60 bg-gray-50 border-gray-300',
        config.state === 'ACTIVE' && 'bg-green-50/50 border-green-300',
        config.state === 'ACTIVE' && isCriticalWaste && 'border-l-4 border-l-red-400',
        config.state === 'ACTIVE' && isHighWaste && !isCriticalWaste && 'border-l-4 border-l-orange-400'
      )}
    >
      {/* Main row - clickable to expand */}
      <div
        role="button"
        tabIndex={0}
        onClick={handleToggle}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleToggle(); }}
        className="w-full px-4 py-3 flex items-center gap-3 text-left cursor-pointer hover:bg-gray-50/50"
      >
        <ChevronRight
          className={cn(
            'h-4 w-4 text-gray-400 transition-transform shrink-0',
            expanded && 'rotate-90'
          )}
        />

        {/* Status indicator */}
        <div className="shrink-0">
          {isCriticalWaste && <AlertCircle className="h-4 w-4 text-red-500" />}
          {isHighWaste && !isCriticalWaste && <AlertTriangle className="h-4 w-4 text-orange-500" />}
          {isGoodWinRate && !isHighWaste && <Check className="h-4 w-4 text-green-500" />}
          {!isGoodWinRate && !isHighWaste && <div className="w-4" />}
        </div>

        {/* Billing ID */}
        <span className="font-mono text-xs text-gray-400 w-24 shrink-0">
          {config.billing_id}
        </span>

        {/* Name - editable */}
        <div className="flex-1 min-w-0" onClick={(e) => e.stopPropagation()}>
          {isEditing ? (
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={handleKeyDown}
                onBlur={handleSave}
                className="flex-1 px-2 py-0.5 text-sm font-medium border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={nameMutation.isPending}
              />
              <button
                onClick={handleSave}
                disabled={nameMutation.isPending}
                className="p-1 text-green-600 hover:bg-green-50 rounded"
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                onClick={handleCancel}
                disabled={nameMutation.isPending}
                className="p-1 text-gray-400 hover:bg-gray-100 rounded"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 group">
              <span className="font-medium text-gray-900 truncate">
                {config.name}
              </span>
              {isGoogleName && (
                <span className="text-xs text-gray-400">(from Google)</span>
              )}
              <button
                onClick={handleStartEdit}
                className="p-1 text-gray-400 opacity-0 group-hover:opacity-100 hover:text-gray-600 transition-opacity"
              >
                <Pencil className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>

        {/* State badge */}
        {config.state === 'SUSPENDED' && (
          <span className="px-2 py-0.5 bg-gray-200 text-gray-600 text-xs rounded">
            Paused
          </span>
        )}

        {/* Metrics summary */}
        <div className="flex items-center gap-4 text-xs shrink-0">
          <span className="text-gray-600 w-16 text-right">
            {formatNumber(config.reached)}
          </span>
          <span
            className={cn(
              'w-14 text-right font-medium',
              config.win_rate >= 50 && 'text-green-600',
              config.win_rate >= 30 && config.win_rate < 50 && 'text-yellow-600',
              config.win_rate < 30 && 'text-red-600'
            )}
          >
            {config.win_rate.toFixed(1)}% win
          </span>
          <span
            className={cn(
              'w-14 text-right',
              config.waste_rate < 50 && 'text-gray-500',
              config.waste_rate >= 50 && config.waste_rate < 70 && 'text-yellow-600',
              config.waste_rate >= 70 && config.waste_rate < 90 && 'text-orange-600',
              config.waste_rate >= 90 && 'text-red-600 font-medium'
            )}
          >
            {config.waste_rate.toFixed(1)}%
          </span>
          <WasteMiniBar pct={config.waste_rate} />
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t bg-gray-50/50">
          {/* Settings pills with Edit button */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex flex-wrap gap-2">
              <SettingPill label="Geos" values={config.included_geos} max={5} formatValue={formatGeoCode} />
              <SettingPill label="Formats" values={config.formats} />
              <SettingPill label="Platforms" values={config.platforms} />
              <SettingPill label="Sizes" values={config.sizes} max={4} />
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowSettingsEditor(!showSettingsEditor);
              }}
              className={cn(
                'flex items-center gap-1 px-2 py-1 text-xs font-medium rounded transition-colors',
                showSettingsEditor
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              )}
            >
              <Settings className="h-3 w-3" />
              {showSettingsEditor ? 'Hide Settings' : 'Edit Settings'}
            </button>
          </div>

          {/* Settings Editor */}
          {showSettingsEditor && (
            <div className="mb-4 -mx-4 border-y">
              <PretargetingSettingsEditor
                billing_id={config.billing_id}
                configName={config.name}
                onClose={() => setShowSettingsEditor(false)}
              />
            </div>
          )}

          {/* Detailed metrics */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-white rounded-lg p-3 border">
              <div className="text-xs text-gray-500 mb-1">Reached</div>
              <div className="text-xl font-bold text-gray-900">
                {formatNumber(config.reached)}
              </div>
            </div>
            <div className="bg-white rounded-lg p-3 border">
              <div className="text-xs text-gray-500 mb-1">Impressions</div>
              <div className="text-xl font-bold text-gray-900">
                {formatNumber(config.impressions)}
              </div>
            </div>
            <div className="bg-white rounded-lg p-3 border">
              <div className="text-xs text-gray-500 mb-1">Win Rate</div>
              <div
                className={cn(
                  'text-xl font-bold',
                  config.win_rate >= 50 && 'text-green-600',
                  config.win_rate >= 30 && config.win_rate < 50 && 'text-yellow-600',
                  config.win_rate < 30 && 'text-red-600'
                )}
              >
                {config.win_rate.toFixed(1)}%
              </div>
            </div>
            <div className="bg-white rounded-lg p-3 border">
              <div className="text-xs text-gray-500 mb-1">Waste Rate</div>
              <div
                className={cn(
                  'text-xl font-bold',
                  config.waste_rate < 50 && 'text-gray-700',
                  config.waste_rate >= 50 && config.waste_rate < 70 && 'text-yellow-600',
                  config.waste_rate >= 70 && config.waste_rate < 90 && 'text-orange-600',
                  config.waste_rate >= 90 && 'text-red-600'
                )}
              >
                {config.waste_rate.toFixed(1)}%
              </div>
            </div>
          </div>

          {/* A/B Comparison Panel */}
          <div className="mt-4">
            <SnapshotComparisonPanel
              billing_id={config.billing_id}
              configName={config.name}
            />
          </div>
        </div>
      )}
    </div>
  );
}
