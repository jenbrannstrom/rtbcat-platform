export interface SystemQueryEnablementInput {
  buyerContextReady: boolean;
  selectedProposalHistoryId?: string | null;
  rollbackBillingId?: string | null;
}

export interface SystemQueryEnablement {
  dataHealth: boolean;
  optimizerModels: boolean;
  optimizerScores: boolean;
  optimizerProposals: boolean;
  optimizerEffectiveCpm: boolean;
  optimizerEfficiencySummary: boolean;
  optimizerProposalHistory: boolean;
  conversionHealth: boolean;
  conversionIngestionStats: boolean;
  conversionReadiness: boolean;
  qpsPageLoadSummary: boolean;
  rollbackSnapshots: boolean;
}

export function getSystemQueryEnablement(
  input: SystemQueryEnablementInput
): SystemQueryEnablement {
  const buyerScopedEnabled = !!input.buyerContextReady;
  return {
    dataHealth: buyerScopedEnabled,
    optimizerModels: buyerScopedEnabled,
    optimizerScores: buyerScopedEnabled,
    optimizerProposals: buyerScopedEnabled,
    optimizerEffectiveCpm: buyerScopedEnabled,
    optimizerEfficiencySummary: buyerScopedEnabled,
    optimizerProposalHistory: buyerScopedEnabled && !!input.selectedProposalHistoryId,
    conversionHealth: buyerScopedEnabled,
    conversionIngestionStats: buyerScopedEnabled,
    conversionReadiness: buyerScopedEnabled,
    qpsPageLoadSummary: buyerScopedEnabled,
    rollbackSnapshots: buyerScopedEnabled && !!input.rollbackBillingId,
  };
}
