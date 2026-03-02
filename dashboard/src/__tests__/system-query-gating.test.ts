import { describe, expect, it } from "vitest";

import { getSystemQueryEnablement } from "@/lib/system-query-gating";

describe("getSystemQueryEnablement", () => {
  it("disables all buyer-scoped system queries when buyer context is not ready", () => {
    const gates = getSystemQueryEnablement({
      buyerContextReady: false,
      selectedProposalHistoryId: "prp_1",
      rollbackBillingId: "123",
    });

    expect(gates.dataHealth).toBe(false);
    expect(gates.optimizerModels).toBe(false);
    expect(gates.optimizerScores).toBe(false);
    expect(gates.optimizerProposals).toBe(false);
    expect(gates.optimizerEffectiveCpm).toBe(false);
    expect(gates.optimizerEfficiencySummary).toBe(false);
    expect(gates.optimizerProposalHistory).toBe(false);
    expect(gates.conversionHealth).toBe(false);
    expect(gates.conversionIngestionStats).toBe(false);
    expect(gates.conversionReadiness).toBe(false);
    expect(gates.qpsPageLoadSummary).toBe(false);
    expect(gates.rollbackSnapshots).toBe(false);
  });

  it("enables base buyer-scoped queries but keeps dependent queries off without IDs", () => {
    const gates = getSystemQueryEnablement({
      buyerContextReady: true,
      selectedProposalHistoryId: "",
      rollbackBillingId: "",
    });

    expect(gates.dataHealth).toBe(true);
    expect(gates.optimizerModels).toBe(true);
    expect(gates.optimizerScores).toBe(true);
    expect(gates.optimizerProposals).toBe(true);
    expect(gates.optimizerEffectiveCpm).toBe(true);
    expect(gates.optimizerEfficiencySummary).toBe(true);
    expect(gates.optimizerProposalHistory).toBe(false);
    expect(gates.conversionHealth).toBe(true);
    expect(gates.conversionIngestionStats).toBe(true);
    expect(gates.conversionReadiness).toBe(true);
    expect(gates.qpsPageLoadSummary).toBe(true);
    expect(gates.rollbackSnapshots).toBe(false);
  });

  it("enables proposal-history and rollback snapshot queries only when IDs are present", () => {
    const gates = getSystemQueryEnablement({
      buyerContextReady: true,
      selectedProposalHistoryId: "prp_1",
      rollbackBillingId: "123",
    });

    expect(gates.optimizerProposalHistory).toBe(true);
    expect(gates.rollbackSnapshots).toBe(true);
  });
});
