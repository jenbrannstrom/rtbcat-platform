"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, CircleDashed } from "lucide-react";

import {
  getSeats,
  getSystemDataHealth,
  getOptimizerModels,
  getOptimizerSetup,
  validateOptimizerModelEndpoint,
  getConversionReadiness,
} from "@/lib/api";
import { ErrorPage } from "@/components/error";
import { LoadingPage } from "@/components/loading";
import { cn } from "@/lib/utils";
import { useAccount } from "@/contexts/account-context";


interface SetupItem {
  key: string;
  title: string;
  description: string;
  href: string;
  done: boolean;
}


export default function SetupPage() {
  const { selectedBuyerId } = useAccount();
  const buyerContextReady = !!selectedBuyerId;
  const buyerSelectionHint = "Select a buyer context in the header to evaluate buyer-specific setup steps.";

  const {
    data: seats,
    isLoading: seatsLoading,
    error: seatsError,
  } = useQuery({
    queryKey: ["setupSeats"],
    queryFn: () => getSeats({ active_only: true }),
  });

  const {
    data: dataHealth,
    isLoading: dataHealthLoading,
    error: dataHealthError,
  } = useQuery({
    queryKey: ["setupDataHealth", selectedBuyerId],
    queryFn: () =>
      getSystemDataHealth({
        days: 14,
        limit: 5,
        buyer_id: selectedBuyerId || undefined,
      }),
    enabled: buyerContextReady,
  });

  const {
    data: optimizerModels,
    isLoading: modelsLoading,
    error: modelsError,
  } = useQuery({
    queryKey: ["setupOptimizerModels", selectedBuyerId],
    queryFn: () =>
      getOptimizerModels({
        buyer_id: selectedBuyerId || undefined,
        include_inactive: true,
        limit: 200,
        offset: 0,
      }),
    enabled: buyerContextReady,
  });
  const firstActiveModelId =
    (optimizerModels?.rows || []).find((row) => row.is_active)?.model_id || "";

  const {
    data: modelValidation,
    isLoading: modelValidationLoading,
    error: modelValidationError,
  } = useQuery({
    queryKey: ["setupModelValidation", selectedBuyerId, firstActiveModelId],
    queryFn: () =>
      validateOptimizerModelEndpoint(firstActiveModelId, {
        buyer_id: selectedBuyerId || undefined,
        timeout_seconds: 10,
      }),
    enabled: buyerContextReady && !!firstActiveModelId,
    retry: false,
  });

  const {
    data: optimizerSetup,
    isLoading: optimizerSetupLoading,
    error: optimizerSetupError,
  } = useQuery({
    queryKey: ["setupOptimizer"],
    queryFn: getOptimizerSetup,
  });

  const {
    data: conversionReadiness,
    isLoading: conversionReadinessLoading,
    error: conversionReadinessError,
  } = useQuery({
    queryKey: ["setupConversionReadiness", selectedBuyerId],
    queryFn: () =>
      getConversionReadiness({
        days: 14,
        freshness_hours: 72,
        buyer_id: selectedBuyerId || undefined,
      }),
    enabled: buyerContextReady,
    retry: false,
  });

  if (
    seatsLoading ||
    dataHealthLoading ||
    modelsLoading ||
    optimizerSetupLoading ||
    conversionReadinessLoading ||
    modelValidationLoading
  ) {
    return <LoadingPage />;
  }

  const firstError =
    (seatsError as Error | null) ||
    (dataHealthError as Error | null) ||
    (modelsError as Error | null) ||
    (optimizerSetupError as Error | null);
  if (firstError) {
    return <ErrorPage message={firstError.message} />;
  }

  const activeSeatRows = seats || [];
  const hasAnyActiveSeat = activeSeatRows.length > 0;
  const selectedBuyerConnected =
    !!selectedBuyerId && activeSeatRows.some((row) => row.buyer_id === selectedBuyerId);
  const seatsReady = hasAnyActiveSeat && selectedBuyerConnected;
  const accountsStepDescription = !hasAnyActiveSeat
    ? "Add and validate at least one active buyer seat."
    : !buyerContextReady
      ? "Active seats found. Select a buyer context in the header to continue setup."
      : !selectedBuyerConnected
        ? "Selected buyer is not an active seat. Choose an active buyer or activate it."
        : "Active buyer seat is connected and selected.";
  const reportCompletenessHealthy =
    dataHealth?.optimizer_readiness?.report_completeness?.availability_state === "healthy";
  const qualityFreshnessHealthy =
    dataHealth?.optimizer_readiness?.rtb_quality_freshness?.availability_state === "healthy";
  const seatDayCompleteness = Number(
    dataHealth?.optimizer_readiness?.seat_day_completeness?.summary?.avg_completeness_pct || 0,
  );
  const dataReadinessReady =
    buyerContextReady && reportCompletenessHealthy && qualityFreshnessHealthy && seatDayCompleteness >= 80;
  const activeModels = (optimizerModels?.rows || []).filter((row) => row.is_active);
  const modelsReady = buyerContextReady && activeModels.length > 0;
  const modelValidationReady =
    buyerContextReady && !!firstActiveModelId && !!(modelValidation?.valid || modelValidation?.skipped);
  const modelValidationUnavailable = !!modelValidationError;
  const hostingCostReady = (optimizerSetup?.monthly_hosting_cost_usd || 0) > 0;
  const conversionReadinessUnavailable = !!conversionReadinessError;
  const conversionWindowDays = conversionReadiness?.window_days ?? 14;
  const conversionAcceptedTotal = conversionReadiness?.accepted_total ?? 0;
  const conversionActiveSources = conversionReadiness?.active_sources ?? 0;
  const conversionLagHours = conversionReadiness?.ingestion_lag_hours ?? null;
  const conversionLagDisplay = conversionLagHours !== null ? `${conversionLagHours.toFixed(1)}h` : "unknown";
  const conversionSourcesReady =
    buyerContextReady &&
    !conversionReadinessUnavailable &&
    conversionReadiness?.state === "ready";
  const conversionSourcesDescription =
    !buyerContextReady
      ? buyerSelectionHint
      : conversionReadinessUnavailable
        ? "Conversion readiness check unavailable right now. Verify webhook or pixel setup in System."
        : conversionReadiness?.state === "ready"
          ? `Healthy conversion flow: ${conversionActiveSources} active source(s), ${conversionAcceptedTotal} accepted in last ${conversionWindowDays} days, lag ${conversionLagDisplay}.`
          : conversionReadiness?.reasons?.length
            ? conversionReadiness.reasons[0]
            : "Conversion source readiness is not complete yet.";

  const items: SetupItem[] = [
    {
      key: "accounts",
      title: "Connect Buyer Accounts",
      description: accountsStepDescription,
      href: "/settings/accounts",
      done: seatsReady,
    },
    {
      key: "data-health",
      title: "Validate Optimizer Readiness",
      description: buyerContextReady
        ? "Ensure report completeness/freshness is healthy for decisioning."
        : buyerSelectionHint,
      href: "/settings/system",
      done: dataReadinessReady,
    },
    {
      key: "models",
      title: "Register an Active Model",
      description: buyerContextReady
        ? "Create at least one active BYOM model for scoring and proposals."
        : buyerSelectionHint,
      href: "/settings/system",
      done: modelsReady,
    },
    {
      key: "model-validation",
      title: "Validate Model Endpoint",
      description: !buyerContextReady
        ? buyerSelectionHint
        : modelValidationUnavailable
          ? "Endpoint validation failed or unavailable. Re-check connectivity in System."
          : "Run endpoint validation for the active model before score/propose.",
      href: "/settings/system",
      done: modelValidationReady,
    },
    {
      key: "costs",
      title: "Set Hosting Cost Baseline",
      description: "Save monthly hosting cost so effective CPM context is enabled.",
      href: "/settings/system",
      done: hostingCostReady,
    },
    {
      key: "conversion-sources",
      title: "Connect Conversion Source",
      description: conversionSourcesDescription,
      href: "/settings/system",
      done: conversionSourcesReady,
    },
  ];

  const completed = items.filter((item) => item.done).length;
  const completionPct = Math.round((completed / items.length) * 100);
  const nextItem = items.find((item) => !item.done) || null;

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">v1 Setup Checklist</h1>
        <p className="mt-1 text-sm text-gray-500">
          Complete the core setup steps to run score, generate proposals, and apply changes safely.
        </p>
        <div
          className={cn(
            "mt-2 inline-flex items-center rounded px-2 py-1 text-xs font-medium",
            buyerContextReady ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700",
          )}
        >
          Buyer context: {selectedBuyerId || "Not selected"}
        </div>
      </div>

      <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium text-gray-700">
            Progress: {completed}/{items.length} complete
          </span>
          <span className="text-gray-500">{completionPct}%</span>
        </div>
        <div className="mt-2 h-2 rounded-full bg-gray-100">
          <div className="h-2 rounded-full bg-blue-600 transition-all" style={{ width: `${completionPct}%` }} />
        </div>
        {nextItem ? (
          <div className="mt-3 text-xs text-gray-600">
            Next recommended step: <span className="font-semibold text-gray-800">{nextItem.title}</span>
          </div>
        ) : (
          <div className="mt-3 text-xs font-medium text-green-700">
            All core setup steps are complete.
          </div>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {items.map((item) => (
          <div key={item.key} className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-sm font-semibold text-gray-900">{item.title}</div>
                <div className="mt-1 text-xs text-gray-600">{item.description}</div>
              </div>
              <span
                className={cn(
                  "inline-flex items-center rounded px-2 py-1 text-xs font-medium",
                  item.done ? "bg-green-50 text-green-700" : "bg-slate-100 text-slate-700",
                )}
              >
                {item.done ? (
                  <>
                    <CheckCircle2 className="mr-1 h-3 w-3" />
                    Done
                  </>
                ) : (
                  <>
                    <CircleDashed className="mr-1 h-3 w-3" />
                    Pending
                  </>
                )}
              </span>
            </div>
            <div className="mt-4">
              <Link href={item.href} className="inline-flex items-center text-xs font-medium text-blue-700 hover:text-blue-800">
                Open step
                <ArrowRight className="ml-1 h-3 w-3" />
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
