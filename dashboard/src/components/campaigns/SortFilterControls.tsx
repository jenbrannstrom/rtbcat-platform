'use client';

import { ArrowDown, ArrowUp, Globe, X, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/contexts/i18n-context';
import type { SortField, SortDirection } from './types';

interface SortFilterControlsProps {
  pageSortField: SortField;
  pageSortDir: SortDirection;
  onSortChange: (field: SortField, dir: SortDirection) => void;
  countryFilter: string | null;
  onCountryFilterChange: (country: string | null) => void;
  allCountries: string[];
  showIssuesOnly: boolean;
  onShowIssuesOnlyChange: (show: boolean) => void;
}

/**
 * Sort and filter controls for campaigns page.
 */
export function SortFilterControls({
  pageSortField,
  pageSortDir,
  onSortChange,
  countryFilter,
  onCountryFilterChange,
  allCountries,
  showIssuesOnly,
  onShowIssuesOnlyChange,
}: SortFilterControlsProps) {
  const { t } = useTranslation();

  const handleSortClick = (field: SortField) => {
    if (pageSortField === field) {
      onSortChange(field, pageSortDir === 'desc' ? 'asc' : 'desc');
    } else {
      onSortChange(field, 'desc');
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3 mb-4 p-3 bg-gray-50 rounded-lg">
      <span className="text-sm text-gray-600 font-medium">{t.campaigns.sort}</span>
      {(['spend', 'impressions', 'clicks', 'creatives', 'name'] as const).map(field => (
        <button
          key={field}
          onClick={() => handleSortClick(field)}
          className={cn(
            "px-3 py-1 text-sm rounded flex items-center gap-1 transition-colors",
            pageSortField === field
              ? "bg-blue-100 text-blue-700 font-medium"
              : "hover:bg-gray-200 text-gray-600"
          )}
        >
          {field === 'spend' ? t.campaigns.spend :
           field === 'impressions' ? t.campaigns.impressions :
           field === 'clicks' ? t.campaigns.clicks :
           field === 'creatives' ? t.creatives.title :
           t.campaigns.name}
          {pageSortField === field && (
            pageSortDir === 'desc' ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />
          )}
        </button>
      ))}

      {/* Phase 29: Issues filter */}
      <button
        onClick={() => onShowIssuesOnlyChange(!showIssuesOnly)}
        className={cn(
          "px-3 py-1 text-sm rounded flex items-center gap-1 transition-colors",
          showIssuesOnly
            ? "bg-red-100 text-red-700 font-medium"
            : "hover:bg-gray-200 text-gray-600"
        )}
        title={showIssuesOnly ? "Showing campaigns with issues" : "Filter to campaigns with disapproved creatives"}
      >
        <AlertTriangle className="h-3 w-3" />
        Issues
      </button>

      {/* Country filter */}
      {allCountries.length > 0 && (
        <div className="ml-auto flex items-center gap-2">
          <Globe className="h-4 w-4 text-gray-400" />
          <select
            value={countryFilter || ''}
            onChange={e => onCountryFilterChange(e.target.value || null)}
            className="text-sm border border-gray-300 rounded-md px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">{t.campaigns.allCountries}</option>
            {allCountries.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          {countryFilter && (
            <button
              onClick={() => onCountryFilterChange(null)}
              className="p-1 text-gray-400 hover:text-gray-600"
              title={t.campaigns.clearFilter}
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
