export interface SetupQueryEnablementInput {
  buyerContextReady: boolean;
  firstActiveModelId?: string | null;
}

export interface SetupQueryEnablement {
  dataHealth: boolean;
  optimizerModels: boolean;
  modelValidation: boolean;
  conversionReadiness: boolean;
}

export function getSetupQueryEnablement(input: SetupQueryEnablementInput): SetupQueryEnablement {
  const buyerScopedEnabled = !!input.buyerContextReady;
  return {
    dataHealth: buyerScopedEnabled,
    optimizerModels: buyerScopedEnabled,
    modelValidation: buyerScopedEnabled && !!input.firstActiveModelId,
    conversionReadiness: buyerScopedEnabled,
  };
}
