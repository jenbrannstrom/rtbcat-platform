import { describe, expect, it } from "vitest";

import { getSetupQueryEnablement } from "@/lib/setup-query-gating";

describe("getSetupQueryEnablement", () => {
  it("disables all buyer-scoped setup queries when buyer context is not ready", () => {
    const gates = getSetupQueryEnablement({
      buyerContextReady: false,
      firstActiveModelId: "mdl_1",
    });

    expect(gates.dataHealth).toBe(false);
    expect(gates.optimizerModels).toBe(false);
    expect(gates.modelValidation).toBe(false);
    expect(gates.conversionReadiness).toBe(false);
  });

  it("keeps model validation disabled until an active model exists", () => {
    const gates = getSetupQueryEnablement({
      buyerContextReady: true,
      firstActiveModelId: "",
    });

    expect(gates.dataHealth).toBe(true);
    expect(gates.optimizerModels).toBe(true);
    expect(gates.modelValidation).toBe(false);
    expect(gates.conversionReadiness).toBe(true);
  });

  it("enables all setup buyer-scoped queries when context and model are valid", () => {
    const gates = getSetupQueryEnablement({
      buyerContextReady: true,
      firstActiveModelId: "mdl_1",
    });

    expect(gates.dataHealth).toBe(true);
    expect(gates.optimizerModels).toBe(true);
    expect(gates.modelValidation).toBe(true);
    expect(gates.conversionReadiness).toBe(true);
  });
});
