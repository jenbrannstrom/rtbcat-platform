'use client';

import { Check } from 'lucide-react';
import { useTranslation } from '@/contexts/i18n-context';
import type { ClusterSuggestion } from './types';
import { generateClusterName } from './utils';

interface SuggestionsPanelProps {
  suggestions: ClusterSuggestion[];
  showAllSuggestions: boolean;
  setShowAllSuggestions: (show: boolean) => void;
  createdSuggestions: Set<string>;
  applyingId: string | null;
  onApplySuggestion: (suggestion: ClusterSuggestion) => void;
  onDismiss: () => void;
}

/**
 * Panel showing auto-cluster suggestions.
 */
export function SuggestionsPanel({
  suggestions,
  showAllSuggestions,
  setShowAllSuggestions,
  createdSuggestions,
  applyingId,
  onApplySuggestion,
  onDismiss,
}: SuggestionsPanelProps) {
  const { t } = useTranslation();
  const creativeCountUnit = (count: number) =>
    count === 1 ? t.campaigns.creativeNounSingular : t.campaigns.creativeNounPlural;

  if (suggestions.length === 0) return null;

  return (
    <div className="mb-8 bg-purple-50/50 border border-purple-200 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-purple-900">
          {t.campaigns.suggestedClusters} ({suggestions.length})
        </h2>
        <button
          onClick={onDismiss}
          className="text-sm text-purple-600 hover:text-purple-800"
        >
          {t.campaigns.dismiss}
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {(showAllSuggestions ? suggestions : suggestions.slice(0, 9)).map((suggestion, index) => {
          const suggestionKey = suggestion.suggested_name ||
            suggestion.domain ||
            suggestion.creative_ids.join(',');
          const isCreated = createdSuggestions.has(suggestionKey);
          const isApplying = applyingId === suggestionKey;
          const displayName = suggestion.suggested_name || generateClusterName(suggestion.domain);

          return (
            <div
              key={`${index}-${suggestionKey}`}
              className={`border rounded-xl p-4 ${isCreated ? 'bg-green-50 border-green-200' : 'bg-purple-50 border-purple-200'}`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex-1 min-w-0">
                  <h4 className={`font-medium truncate ${isCreated ? 'text-green-900' : 'text-purple-900'}`}>
                    {displayName}
                  </h4>
                  {suggestion.domain && suggestion.domain !== displayName && (
                    <p className="text-xs text-gray-500 truncate max-w-[200px]">
                      {suggestion.domain}
                    </p>
                  )}
                </div>
                {isCreated ? (
                  <span className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg flex items-center gap-1">
                    <Check className="h-3 w-3" />
                    {t.campaigns.created}
                  </span>
                ) : (
                  <button
                    onClick={() => onApplySuggestion(suggestion)}
                    disabled={isApplying}
                    className="px-3 py-1.5 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 disabled:opacity-50"
                  >
                    {isApplying ? t.campaigns.creating : t.campaigns.create}
                  </button>
                )}
              </div>
              <p className={`text-sm ${isCreated ? 'text-green-700' : 'text-purple-700'}`}>
                {suggestion.creative_ids.length} {creativeCountUnit(suggestion.creative_ids.length)}
              </p>
            </div>
          );
        })}
      </div>
      {suggestions.length > 9 && (
        <button
          onClick={() => setShowAllSuggestions(!showAllSuggestions)}
          className="mt-3 text-sm text-purple-600 hover:text-purple-800 text-center w-full"
        >
          {showAllSuggestions ? t.campaigns.showLess : t.campaigns.moreSuggestions.replace('{count}', String(suggestions.length - 9))}
        </button>
      )}
    </div>
  );
}
