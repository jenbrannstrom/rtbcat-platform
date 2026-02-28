"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, CircleDashed } from "lucide-react";

import {
  getSeats,
  getSystemDataHealth,
  getOptimizerModels,
  getOptimizerSetup,
} from "@/lib/api";
import { ErrorPage } from "@/components/error";
import { LoadingPage } from "@/components/loading";
import { cn } from "@/lib/utils";


interface SetupItem {
  key: string;
  title: string;
  description: string;
  href: string;
  done: boolean;
}


export default function SetupPage() {
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
    queryKey: ["setupDataHealth"],
    queryFn: () =>
      getSystemDataHealth({
        days: 14,
        limit: 5,
      }),
  });

  const {
    data: optimizerModels,
    isLoading: modelsLoading,
    error: modelsError,
  } = useQuery({
    queryKey: ["setupOptimizerModels"],
    queryFn: () =>
      getOptimizerModels({
        include_inactive: true,
        limit: 200,
        offset: 0,
      }),
  });

  const {
    data: optimizerSetup,
    isLoading: optimizerSetupLoading,
    error: optimizerSetupError,
  } = useQuery({
    queryKey: ["setupOptimizer"],
    queryFn: getOptimizerSetup,
  });

  if (seatsLoading || dataHealthLoading || modelsLoading || optimizerSetupLoading) {
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

  const seatsReady = (seats?.length || 0) > 0;
  const reportCompletenessHealthy =
    dataHealth?.optimizer_readiness?.report_completeness?.availability_state === "healthy";
  const qualityFreshnessHealthy =
    dataHealth?.optimizer_readiness?.rtb_quality_freshness?.availability_state === "healthy";
  const seatDayCompleteness = Number(
    dataHealth?.optimizer_readiness?.seat_day_completeness?.summary?.avg_completeness_pct || 0,
  );
  const dataReadinessReady = reportCompletenessHealthy && qualityFreshnessHealthy && seatDayCompleteness >= 80;
  const activeModels = (optimizerModels?.rows || []).filter((row) => row.is_active);
  const modelsReady = activeModels.length > 0;
  const hostingCostReady = (optimizerSetup?.monthly_hosting_cost_usd || 0) > 0;

  const items: SetupItem[] = [
    {
      key: "accounts",
      title: "Connect Buyer Accounts",
      description: "Add and validate at least one active buyer seat.",
      href: "/settings/accounts",
      done: seatsReady,
    },
    {
      key: "data-health",
      title: "Validate Optimizer Readiness",
      description: "Ensure report completeness/freshness is healthy for decisioning.",
      href: "/settings/system",
      done: dataReadinessReady,
    },
    {
      key: "models",
      title: "Register an Active Model",
      description: "Create at least one active BYOM model for scoring and proposals.",
      href: "/settings/system",
      done: modelsReady,
    },
    {
      key: "costs",
      title: "Set Hosting Cost Baseline",
      description: "Save monthly hosting cost so effective CPM context is enabled.",
      href: "/settings/system",
      done: hostingCostReady,
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
