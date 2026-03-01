"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Server, Database, Video, Loader2, CheckCircle, XCircle, AlertTriangle, Image, Cpu, BarChart3 } from "lucide-react";
import {
  getHealth,
  getStats,
  getThumbnailStatus,
  generateThumbnailsBatch,
  getSystemStatus,
  getSystemDataHealth,
  getOptimizerModels,
  createOptimizerModel,
  updateOptimizerModel,
  activateOptimizerModel,
  deactivateOptimizerModel,
  listOptimizerSegmentScores,
  listOptimizerProposals,
  listOptimizerProposalHistory,
  runOptimizerScoreAndPropose,
  validateOptimizerModelEndpoint,
  approveOptimizerProposal,
  applyOptimizerProposal,
  syncOptimizerProposalApplyStatus,
  getOptimizerSetup,
  updateOptimizerSetup,
  getOptimizerEffectiveCpm,
  getOptimizerEfficiencySummary,
  getConversionHealth,
  getConversionReadiness,
  getConversionIngestionStats,
  getConversionWebhookSecurityStatus,
  getUiPageLoadMetricSummary,
  getSnapshots,
  rollbackSnapshot,
  type PretargetingSnapshot,
} from "@/lib/api";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/contexts/i18n-context";
import { useAccount } from "@/contexts/account-context";

type WorkflowPresetId = "safe" | "balanced" | "aggressive" | "custom";

const WORKFLOW_PRESETS: Record<
  Exclude<WorkflowPresetId, "custom">,
  {
    label: string;
    days: string;
    scoreLimit: string;
    proposalLimit: string;
    minConfidence: string;
    maxDelta: string;
  }
> = {
  safe: {
    label: "Safe",
    days: "14",
    scoreLimit: "500",
    proposalLimit: "100",
    minConfidence: "0.45",
    maxDelta: "0.20",
  },
  balanced: {
    label: "Balanced",
    days: "14",
    scoreLimit: "1000",
    proposalLimit: "200",
    minConfidence: "0.30",
    maxDelta: "0.30",
  },
  aggressive: {
    label: "Aggressive",
    days: "7",
    scoreLimit: "2000",
    proposalLimit: "400",
    minConfidence: "0.20",
    maxDelta: "0.50",
  },
};

const QPS_PAGE_P95_FIRST_ROW_SLO_MS = 6000;
const QPS_PAGE_P95_HYDRATED_SLO_MS = 8000;

export default function SystemStatusPage() {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const { selectedBuyerId } = useAccount();
  const [batchLimit, setBatchLimit] = useState(50);
  const [forceRetry, setForceRetry] = useState(false);
  const [healthDays, setHealthDays] = useState(7);
  const [healthLimit, setHealthLimit] = useState(20);
  const [healthStateFilter, setHealthStateFilter] = useState<"all" | "healthy" | "degraded" | "unavailable">("all");
  const [minCompleteness, setMinCompleteness] = useState<string>("");
  const [selectedModelId, setSelectedModelId] = useState<string>("");
  const [modelValidationPayloadInput, setModelValidationPayloadInput] = useState<string>("");
  const [workflowDaysInput, setWorkflowDaysInput] = useState<string>("14");
  const [workflowScoreLimitInput, setWorkflowScoreLimitInput] = useState<string>("1000");
  const [workflowProposalLimitInput, setWorkflowProposalLimitInput] = useState<string>("200");
  const [workflowMinConfidenceInput, setWorkflowMinConfidenceInput] = useState<string>("0.3");
  const [workflowMaxDeltaInput, setWorkflowMaxDeltaInput] = useState<string>("0.3");
  const [workflowPreset, setWorkflowPreset] = useState<WorkflowPresetId>("balanced");
  const [qpsPageSloSinceHours, setQpsPageSloSinceHours] = useState<number>(24);
  const [selectedProposalHistoryId, setSelectedProposalHistoryId] = useState<string>("");
  const [optimizerNotice, setOptimizerNotice] = useState<string>("");
  const [newModelName, setNewModelName] = useState<string>("");
  const [newModelDescription, setNewModelDescription] = useState<string>("");
  const [newModelType, setNewModelType] = useState<"api" | "rules" | "csv">("api");
  const [newModelEndpointUrl, setNewModelEndpointUrl] = useState<string>("");
  const [newModelAuthHeader, setNewModelAuthHeader] = useState<string>("");
  const [rollbackProposal, setRollbackProposal] = useState<{
    proposalId: string;
    billingId: string;
  } | null>(null);
  const [selectedRollbackSnapshotId, setSelectedRollbackSnapshotId] = useState<string>("");
  const [rollbackReason, setRollbackReason] = useState<string>("");
  const [rollbackPreview, setRollbackPreview] = useState<{
    message: string;
    changes_made: string[];
  } | null>(null);
  const [editModelName, setEditModelName] = useState<string>("");
  const [editModelDescription, setEditModelDescription] = useState<string>("");
  const [editModelEndpointUrl, setEditModelEndpointUrl] = useState<string>("");
  const [editModelAuthHeader, setEditModelAuthHeader] = useState<string>("");
  const [monthlyHostingCostInput, setMonthlyHostingCostInput] = useState<string>("");
  const parsedMinCompleteness = Number(minCompleteness);
  const normalizedMinCompleteness =
    minCompleteness.trim() === "" || !Number.isFinite(parsedMinCompleteness)
      ? undefined
      : Math.min(100, Math.max(0, parsedMinCompleteness));

  const {
    data: health,
    isLoading: healthLoading,
    error: healthError,
    refetch: refetchHealth,
  } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });

  const { data: thumbnailStatus, isLoading: thumbnailStatusLoading } = useQuery({
    queryKey: ["thumbnailStatus"],
    queryFn: () => getThumbnailStatus(),
  });

  const { data: systemStatus, isLoading: systemStatusLoading } = useQuery({
    queryKey: ["systemStatus"],
    queryFn: getSystemStatus,
  });

  const { data: dataHealth, isLoading: dataHealthLoading } = useQuery({
    queryKey: [
      "systemDataHealth",
      selectedBuyerId,
      healthDays,
      healthLimit,
      healthStateFilter,
      minCompleteness,
    ],
    queryFn: () =>
      getSystemDataHealth({
        days: healthDays,
        buyer_id: selectedBuyerId || undefined,
        limit: healthLimit,
        availability_state: healthStateFilter === "all" ? undefined : healthStateFilter,
        min_completeness_pct: normalizedMinCompleteness,
      }),
  });

  const {
    data: optimizerModels,
    isLoading: optimizerModelsLoading,
    error: optimizerModelsError,
  } = useQuery({
    queryKey: ["optimizerModels", selectedBuyerId],
    queryFn: () =>
      getOptimizerModels({
        buyer_id: selectedBuyerId || undefined,
        include_inactive: true,
        limit: 200,
        offset: 0,
      }),
  });

  const {
    data: optimizerScores,
    isLoading: optimizerScoresLoading,
    error: optimizerScoresError,
  } = useQuery({
    queryKey: ["optimizerScores", selectedBuyerId],
    queryFn: () =>
      listOptimizerSegmentScores({
        buyer_id: selectedBuyerId || undefined,
        days: 14,
        limit: 20,
        offset: 0,
      }),
  });

  const {
    data: optimizerProposals,
    isLoading: optimizerProposalsLoading,
    error: optimizerProposalsError,
  } = useQuery({
    queryKey: ["optimizerProposals", selectedBuyerId],
    queryFn: () =>
      listOptimizerProposals({
        buyer_id: selectedBuyerId || undefined,
        limit: 100,
        offset: 0,
      }),
  });

  const { data: optimizerSetup, isLoading: optimizerSetupLoading } = useQuery({
    queryKey: ["optimizerSetup"],
    queryFn: getOptimizerSetup,
  });

  const {
    data: optimizerEffectiveCpm,
    isLoading: optimizerEffectiveCpmLoading,
    error: optimizerEffectiveCpmError,
  } = useQuery({
    queryKey: ["optimizerEffectiveCpm", selectedBuyerId],
    queryFn: () =>
      getOptimizerEffectiveCpm({
        buyer_id: selectedBuyerId || undefined,
        days: 14,
      }),
  });

  const {
    data: optimizerEfficiencySummary,
    isLoading: optimizerEfficiencySummaryLoading,
    error: optimizerEfficiencySummaryError,
  } = useQuery({
    queryKey: ["optimizerEfficiencySummary", selectedBuyerId],
    queryFn: () =>
      getOptimizerEfficiencySummary({
        buyer_id: selectedBuyerId || undefined,
        days: 14,
      }),
  });

  const {
    data: optimizerProposalHistory,
    isLoading: optimizerProposalHistoryLoading,
    error: optimizerProposalHistoryError,
  } = useQuery({
    queryKey: ["optimizerProposalHistory", selectedBuyerId, selectedProposalHistoryId],
    queryFn: () =>
      listOptimizerProposalHistory(selectedProposalHistoryId, {
        buyer_id: selectedBuyerId || undefined,
        limit: 100,
        offset: 0,
      }),
    enabled: !!selectedProposalHistoryId,
  });

  const {
    data: conversionHealth,
    isLoading: conversionHealthLoading,
    error: conversionHealthError,
  } = useQuery({
    queryKey: ["conversionHealth", selectedBuyerId],
    queryFn: () =>
      getConversionHealth({
        buyer_id: selectedBuyerId || undefined,
      }),
    retry: false,
  });

  const {
    data: conversionIngestionStats,
    isLoading: conversionIngestionStatsLoading,
    error: conversionIngestionStatsError,
  } = useQuery({
    queryKey: ["conversionIngestionStats", selectedBuyerId],
    queryFn: () =>
      getConversionIngestionStats({
        buyer_id: selectedBuyerId || undefined,
        days: 7,
    }),
    retry: false,
  });

  const {
    data: conversionReadiness,
    isLoading: conversionReadinessLoading,
    error: conversionReadinessError,
  } = useQuery({
    queryKey: ["conversionReadiness", selectedBuyerId],
    queryFn: () =>
      getConversionReadiness({
        buyer_id: selectedBuyerId || undefined,
        days: 14,
        freshness_hours: 72,
      }),
    retry: false,
  });

  const {
    data: conversionWebhookSecurityStatus,
    isLoading: conversionWebhookSecurityStatusLoading,
    error: conversionWebhookSecurityStatusError,
  } = useQuery({
    queryKey: ["conversionWebhookSecurityStatus"],
    queryFn: getConversionWebhookSecurityStatus,
    retry: false,
  });

  const qpsPageSloBucketHours =
    qpsPageSloSinceHours <= 24 ? 1 : qpsPageSloSinceHours <= 72 ? 3 : 6;
  const qpsPageSloBucketLimit = Math.min(
    24,
    Math.max(1, Math.ceil(qpsPageSloSinceHours / qpsPageSloBucketHours)),
  );

  const {
    data: qpsPageLoadSummary,
    isLoading: qpsPageLoadSummaryLoading,
    error: qpsPageLoadSummaryError,
  } = useQuery({
    queryKey: ["qpsPageLoadSummary", selectedBuyerId, qpsPageSloSinceHours],
    queryFn: () =>
      getUiPageLoadMetricSummary({
        page: "qps_home",
        buyer_id: selectedBuyerId || undefined,
        since_hours: qpsPageSloSinceHours,
        latest_limit: 5,
        api_rollup_limit: 20,
        bucket_hours: qpsPageSloBucketHours,
        bucket_limit: qpsPageSloBucketLimit,
      }),
    enabled: !!selectedBuyerId,
    retry: false,
  });

  const {
    data: rollbackSnapshots,
    isLoading: rollbackSnapshotsLoading,
    error: rollbackSnapshotsError,
  } = useQuery({
    queryKey: ["rollbackSnapshots", rollbackProposal?.billingId],
    queryFn: () =>
      getSnapshots({
        billing_id: rollbackProposal?.billingId,
        limit: 25,
      }),
    enabled: !!rollbackProposal?.billingId,
  });

  useEffect(() => {
    const activeModels = (optimizerModels?.rows || []).filter((row) => row.is_active);
    if (selectedModelId && activeModels.some((row) => row.model_id === selectedModelId)) {
      return;
    }
    if (activeModels.length > 0) {
      setSelectedModelId(activeModels[0].model_id);
    }
  }, [optimizerModels, selectedModelId]);

  useEffect(() => {
    if (!selectedModelId) {
      setEditModelName("");
      setEditModelDescription("");
      setEditModelEndpointUrl("");
      setEditModelAuthHeader("");
      return;
    }
    const model = (optimizerModels?.rows || []).find((row) => row.model_id === selectedModelId);
    if (!model) {
      return;
    }
    setEditModelName(model.name || "");
    setEditModelDescription(model.description || "");
    setEditModelEndpointUrl(model.endpoint_url || "");
    setEditModelAuthHeader("");
  }, [optimizerModels, selectedModelId]);

  useEffect(() => {
    const proposals = optimizerProposals?.rows || [];
    if (!proposals.length) {
      if (selectedProposalHistoryId) {
        setSelectedProposalHistoryId("");
      }
      return;
    }
    if (selectedProposalHistoryId && proposals.some((row) => row.proposal_id === selectedProposalHistoryId)) {
      return;
    }
    setSelectedProposalHistoryId(proposals[0].proposal_id);
  }, [optimizerProposals, selectedProposalHistoryId]);

  useEffect(() => {
    if (!optimizerSetup) return;
    if (optimizerSetup.monthly_hosting_cost_usd === null) {
      setMonthlyHostingCostInput("");
      return;
    }
    setMonthlyHostingCostInput(String(optimizerSetup.monthly_hosting_cost_usd));
  }, [optimizerSetup]);

  useEffect(() => {
    if (!rollbackProposal) {
      setSelectedRollbackSnapshotId("");
      return;
    }
    if (!rollbackSnapshots?.length) {
      setSelectedRollbackSnapshotId("");
      return;
    }
    if (rollbackSnapshots.some((row) => String(row.id) === selectedRollbackSnapshotId)) {
      return;
    }
    setSelectedRollbackSnapshotId(String(rollbackSnapshots[0].id));
  }, [rollbackProposal, rollbackSnapshots, selectedRollbackSnapshotId]);

  const generateMutation = useMutation({
    mutationFn: () => generateThumbnailsBatch({ limit: batchLimit, force: forceRetry }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["thumbnailStatus"] });
    },
  });

  const saveOptimizerSetupMutation = useMutation({
    mutationFn: async () => {
      const value = Number(monthlyHostingCostInput);
      if (!Number.isFinite(value) || value < 0) {
        throw new Error("Monthly hosting cost must be a non-negative number.");
      }
      return updateOptimizerSetup({ monthly_hosting_cost_usd: value });
    },
    onSuccess: (payload) => {
      queryClient.invalidateQueries({ queryKey: ["optimizerSetup"] });
      queryClient.invalidateQueries({ queryKey: ["optimizerEffectiveCpm", selectedBuyerId] });
      setMonthlyHostingCostInput(
        payload.monthly_hosting_cost_usd === null
          ? ""
          : String(payload.monthly_hosting_cost_usd),
      );
      setOptimizerNotice("Optimizer setup saved.");
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to save optimizer setup.";
      setOptimizerNotice(msg);
    },
  });

  const createModelMutation = useMutation({
    mutationFn: async () => {
      const name = newModelName.trim();
      if (!name) {
        throw new Error("Model name is required.");
      }
      const endpoint = newModelEndpointUrl.trim();
      if (newModelType === "api" && !endpoint) {
        throw new Error("Endpoint URL is required for API model type.");
      }
      return createOptimizerModel({
        buyer_id: selectedBuyerId || undefined,
        name,
        description: newModelDescription.trim() || undefined,
        model_type: newModelType,
        endpoint_url: newModelType === "api" ? endpoint : undefined,
        auth_header_encrypted: newModelAuthHeader.trim() || undefined,
        input_schema: {},
        output_schema: {
          value_score: "number",
          confidence: "number",
        },
        is_active: true,
      });
    },
    onSuccess: (payload) => {
      queryClient.invalidateQueries({ queryKey: ["optimizerModels", selectedBuyerId] });
      setSelectedModelId(payload.model_id);
      setNewModelName("");
      setNewModelDescription("");
      setNewModelType("api");
      setNewModelEndpointUrl("");
      setNewModelAuthHeader("");
      setOptimizerNotice(`Model created: ${payload.name}`);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to create model.";
      setOptimizerNotice(msg);
    },
  });

  const modelActivationMutation = useMutation({
    mutationFn: async (params: { modelId: string; isActive: boolean }) => {
      if (params.isActive) {
        await deactivateOptimizerModel(params.modelId, { buyer_id: selectedBuyerId || undefined });
        return "Model deactivated.";
      }
      await activateOptimizerModel(params.modelId, { buyer_id: selectedBuyerId || undefined });
      return "Model activated.";
    },
    onSuccess: (message) => {
      queryClient.invalidateQueries({ queryKey: ["optimizerModels", selectedBuyerId] });
      setOptimizerNotice(message);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to update model status.";
      setOptimizerNotice(msg);
    },
  });

  const updateModelMutation = useMutation({
    mutationFn: async () => {
      if (!selectedModel) {
        throw new Error("Select a model before updating.");
      }
      const name = editModelName.trim();
      if (!name) {
        throw new Error("Model name cannot be empty.");
      }
      const endpoint = editModelEndpointUrl.trim();
      if (selectedModel.model_type === "api" && !endpoint) {
        throw new Error("Endpoint URL is required for API model type.");
      }
      return updateOptimizerModel(
        selectedModel.model_id,
        {
          name,
          description: editModelDescription.trim() || undefined,
          endpoint_url: selectedModel.model_type === "api" ? endpoint : undefined,
          auth_header_encrypted: editModelAuthHeader.trim() || undefined,
        },
        { buyer_id: selectedBuyerId || undefined },
      );
    },
    onSuccess: (payload) => {
      queryClient.invalidateQueries({ queryKey: ["optimizerModels", selectedBuyerId] });
      setEditModelName(payload.name || "");
      setEditModelDescription(payload.description || "");
      setEditModelEndpointUrl(payload.endpoint_url || "");
      setEditModelAuthHeader("");
      setOptimizerNotice(`Model updated: ${payload.name}`);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to update model.";
      setOptimizerNotice(msg);
    },
  });

  const validateModelMutation = useMutation({
    mutationFn: async () => {
      if (!selectedModelId) {
        throw new Error("Select an active model before validation.");
      }
      const rawPayload = modelValidationPayloadInput.trim();
      let samplePayload: Record<string, unknown> | undefined;
      if (rawPayload) {
        let parsed: unknown;
        try {
          parsed = JSON.parse(rawPayload);
        } catch {
          throw new Error("Validation payload must be valid JSON.");
        }
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          throw new Error("Validation payload must be a JSON object.");
        }
        samplePayload = parsed as Record<string, unknown>;
      }
      return validateOptimizerModelEndpoint(selectedModelId, {
        buyer_id: selectedBuyerId || undefined,
        timeout_seconds: 10,
        sample_payload: samplePayload,
      });
    },
    onSuccess: (payload) => {
      if (payload.valid) {
        setOptimizerNotice(
          `Model validation passed${payload.http_status ? ` (HTTP ${payload.http_status})` : ""}.`,
        );
        return;
      }
      const statusText = payload.http_status ? `HTTP ${payload.http_status}` : "validation failed";
      setOptimizerNotice(`Model validation failed (${statusText}): ${payload.message}`);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to validate model endpoint.";
      setOptimizerNotice(msg);
    },
  });

  const scoreAndProposeMutation = useMutation({
    mutationFn: async () => {
      if (!selectedModelId) {
        throw new Error("Select an active model before running score + propose.");
      }
      const parsedDays = Number(workflowDaysInput);
      const parsedScoreLimit = Number(workflowScoreLimitInput);
      const parsedProposalLimit = Number(workflowProposalLimitInput);
      const parsedMinConfidence = Number(workflowMinConfidenceInput);
      const parsedMaxDelta = Number(workflowMaxDeltaInput);

      if (!Number.isFinite(parsedDays) || parsedDays < 1 || parsedDays > 365) {
        throw new Error("Days must be between 1 and 365.");
      }
      if (!Number.isFinite(parsedScoreLimit) || parsedScoreLimit < 1 || parsedScoreLimit > 5000) {
        throw new Error("Score limit must be between 1 and 5000.");
      }
      if (!Number.isFinite(parsedProposalLimit) || parsedProposalLimit < 1 || parsedProposalLimit > 2000) {
        throw new Error("Proposal limit must be between 1 and 2000.");
      }
      if (!Number.isFinite(parsedMinConfidence) || parsedMinConfidence < 0 || parsedMinConfidence > 1) {
        throw new Error("Min confidence must be between 0 and 1.");
      }
      if (!Number.isFinite(parsedMaxDelta) || parsedMaxDelta < 0.05 || parsedMaxDelta > 1) {
        throw new Error("Max delta % must be between 0.05 and 1.");
      }

      const selectedProfile =
        workflowPreset === "custom" ? undefined : (workflowPreset as Exclude<WorkflowPresetId, "custom">);

      return runOptimizerScoreAndPropose({
        model_id: selectedModelId,
        buyer_id: selectedBuyerId || undefined,
        profile: selectedProfile,
        days: parsedDays,
        min_confidence: parsedMinConfidence,
        max_delta_pct: parsedMaxDelta,
        score_limit: parsedScoreLimit,
        proposal_limit: parsedProposalLimit,
      });
    },
    onSuccess: (payload) => {
      queryClient.invalidateQueries({ queryKey: ["optimizerScores", selectedBuyerId] });
      queryClient.invalidateQueries({ queryKey: ["optimizerProposals", selectedBuyerId] });
      setOptimizerNotice(
        `Score + propose completed: ${payload.score_run.scores_written} scores written, ${payload.proposal_run.proposals_created} proposals created.`,
      );
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to run score + propose workflow.";
      setOptimizerNotice(msg);
    },
  });

  const applyWorkflowPreset = (preset: Exclude<WorkflowPresetId, "custom">) => {
    const values = WORKFLOW_PRESETS[preset];
    setWorkflowDaysInput(values.days);
    setWorkflowScoreLimitInput(values.scoreLimit);
    setWorkflowProposalLimitInput(values.proposalLimit);
    setWorkflowMinConfidenceInput(values.minConfidence);
    setWorkflowMaxDeltaInput(values.maxDelta);
    setWorkflowPreset(preset);
  };

  const proposalActionMutation = useMutation({
    mutationFn: async (params: { proposalId: string; action: "approve" | "apply" | "sync" }) => {
      if (params.action === "approve") {
        await approveOptimizerProposal(params.proposalId, {
          buyer_id: selectedBuyerId || undefined,
        });
        return "Proposal approved.";
      }
      if (params.action === "apply") {
        await applyOptimizerProposal(params.proposalId, {
          buyer_id: selectedBuyerId || undefined,
          mode: "queue",
        });
        return "Proposal applied in queue mode.";
      }
      await syncOptimizerProposalApplyStatus(params.proposalId, {
        buyer_id: selectedBuyerId || undefined,
      });
      return "Proposal apply status synced.";
    },
    onSuccess: (message) => {
      queryClient.invalidateQueries({ queryKey: ["optimizerProposals", selectedBuyerId] });
      queryClient.invalidateQueries({ queryKey: ["optimizerProposalHistory", selectedBuyerId] });
      setOptimizerNotice(message);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to run proposal action.";
      setOptimizerNotice(msg);
    },
  });

  const rollbackPreviewMutation = useMutation({
    mutationFn: async () => {
      if (!rollbackProposal?.billingId) {
        throw new Error("No billing ID available for rollback.");
      }
      const snapshotId = Number(selectedRollbackSnapshotId);
      if (!Number.isFinite(snapshotId) || snapshotId <= 0) {
        throw new Error("Select a snapshot before previewing rollback.");
      }
      return rollbackSnapshot({
        billing_id: rollbackProposal.billingId,
        snapshot_id: snapshotId,
        dry_run: true,
      });
    },
    onSuccess: (payload) => {
      setRollbackPreview({
        message: payload.message,
        changes_made: payload.changes_made || [],
      });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to preview rollback.";
      setOptimizerNotice(msg);
    },
  });

  const rollbackExecuteMutation = useMutation({
    mutationFn: async () => {
      if (!rollbackProposal?.billingId) {
        throw new Error("No billing ID available for rollback.");
      }
      const snapshotId = Number(selectedRollbackSnapshotId);
      if (!Number.isFinite(snapshotId) || snapshotId <= 0) {
        throw new Error("Select a snapshot before rollback.");
      }
      return rollbackSnapshot({
        billing_id: rollbackProposal.billingId,
        snapshot_id: snapshotId,
        dry_run: false,
        reason: rollbackReason.trim(),
        proposal_id: rollbackProposal.proposalId,
      });
    },
    onSuccess: (payload) => {
      queryClient.invalidateQueries({ queryKey: ["optimizerProposals", selectedBuyerId] });
      queryClient.invalidateQueries({ queryKey: ["optimizerProposalHistory", selectedBuyerId] });
      queryClient.invalidateQueries({ queryKey: ["pretargeting-history"] });
      const suffix = payload.history_id ? ` (history #${payload.history_id})` : "";
      setOptimizerNotice(`Rollback executed: ${payload.message}${suffix}`);
      setRollbackProposal(null);
      setRollbackReason("");
      setRollbackPreview(null);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to execute rollback.";
      setOptimizerNotice(msg);
    },
  });

  const activeModelCount = optimizerModels?.rows.filter((row) => row.is_active).length ?? 0;
  const selectedModel = (optimizerModels?.rows || []).find((row) => row.model_id === selectedModelId) || null;
  const activeModels = (optimizerModels?.rows || []).filter((row) => row.is_active);
  const proposalRows = optimizerProposals?.rows ?? [];
  const proposalHistoryRows = optimizerProposalHistory?.rows || [];
  const proposalStatusCounts = proposalRows.reduce(
    (acc, row) => {
      const key = row.status || "draft";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );
  const optimizerPanelLoading =
    optimizerModelsLoading ||
    optimizerScoresLoading ||
    optimizerProposalsLoading ||
    optimizerSetupLoading;
  const optimizerPanelError =
    optimizerModelsError || optimizerScoresError || optimizerProposalsError;
  const pendingProposalId = proposalActionMutation.isPending
    ? proposalActionMutation.variables?.proposalId
    : null;
  const pendingModelId = modelActivationMutation.isPending
    ? modelActivationMutation.variables?.modelId
    : null;
  const selectedRollbackSnapshot: PretargetingSnapshot | null =
    (rollbackSnapshots || []).find((row) => String(row.id) === selectedRollbackSnapshotId) || null;
  const efficiencyBlockLoading = optimizerEffectiveCpmLoading || optimizerEfficiencySummaryLoading;
  const efficiencyBlockError = optimizerEffectiveCpmError || optimizerEfficiencySummaryError;
  const formatUsd = (value: number | null | undefined, decimals = 4) => {
    if (value === null || value === undefined || !Number.isFinite(value)) {
      return "-";
    }
    return `$${value.toFixed(decimals)}`;
  };
  const formatPct = (value: number | null | undefined) => {
    if (value === null || value === undefined || !Number.isFinite(value)) {
      return "-";
    }
    return `${(value * 100).toFixed(2)}%`;
  };
  const conversionSignalsLoading =
    conversionHealthLoading ||
    conversionIngestionStatsLoading ||
    conversionReadinessLoading ||
    conversionWebhookSecurityStatusLoading;
  const conversionSignalsError =
    conversionHealthError ||
    conversionIngestionStatsError ||
    conversionReadinessError ||
    conversionWebhookSecurityStatusError;
  const conversionReadinessState = String(conversionReadiness?.state || "").toLowerCase();
  const conversionReadinessTone =
    conversionReadinessState === "ready"
      ? "bg-green-50 text-green-700"
      : conversionReadinessState === "degraded"
        ? "bg-amber-50 text-amber-700"
        : conversionReadinessState === "not_ready" || conversionReadinessState === "unavailable"
          ? "bg-red-50 text-red-700"
          : "bg-slate-100 text-slate-700";
  const conversionReadinessReasons = (conversionReadiness?.reasons || []).filter((reason) => !!reason);
  const securityEnabledSources = (conversionWebhookSecurityStatus?.sources || []).filter(
    (row) => row.secret_enabled || row.hmac_enabled,
  ).length;
  const qpsPageLoadSummarySloPass =
    qpsPageLoadSummary &&
    qpsPageLoadSummary.sample_count > 0 &&
    qpsPageLoadSummary.p95_first_table_row_ms !== null &&
    qpsPageLoadSummary.p95_table_hydrated_ms !== null &&
    qpsPageLoadSummary.p95_first_table_row_ms <= QPS_PAGE_P95_FIRST_ROW_SLO_MS &&
    qpsPageLoadSummary.p95_table_hydrated_ms <= QPS_PAGE_P95_HYDRATED_SLO_MS;
  const qpsPageLoadSummarySloDegraded =
    qpsPageLoadSummary &&
    qpsPageLoadSummary.sample_count > 0 &&
    !qpsPageLoadSummarySloPass;
  const qpsApiLatencyRollupRows = qpsPageLoadSummary?.api_latency_rollup || [];
  const formatLatencyMs = (value: number | null | undefined) => {
    if (value === null || value === undefined || !Number.isFinite(value)) {
      return "-";
    }
    return `${Math.round(value)} ms`;
  };
  const latencyToneClass = (value: number | null | undefined, targetMs: number) => {
    if (value === null || value === undefined || !Number.isFinite(value)) {
      return "text-gray-700";
    }
    if (value > targetMs) return "text-red-700";
    return "text-green-700";
  };

  if (healthLoading) {
    return <LoadingPage />;
  }

  if (healthError) {
    return (
      <ErrorPage
        message={
          healthError instanceof Error
            ? healthError.message
            : t.settings.failedToCheckApiStatus
        }
        onRetry={() => refetchHealth()}
      />
    );
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">{t.settingsNav.systemStatus}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {t.settings.systemConfiguration}
        </p>
      </div>

      <div className="max-w-2xl space-y-6">
        {/* API Status */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Server className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">{t.settings.apiStatus}</h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{t.settings.status}</span>
              <span className="flex items-center text-sm font-medium text-green-600">
                <CheckCircle className="h-4 w-4 mr-1" />
                {health?.status}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{t.settings.version}</span>
              <span className="text-sm font-medium text-gray-900">
                {health?.version}
              </span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-sm text-gray-600">{t.settings.configured}</span>
              <span
                className={`flex items-center text-sm font-medium ${
                  health?.configured ? "text-green-600" : "text-red-600"
                }`}
              >
                {health?.configured ? (
                  <>
                    <CheckCircle className="h-4 w-4 mr-1" />
                    {t.settings.yes}
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4 mr-1" />
                    {t.settings.no}
                  </>
                )}
              </span>
            </div>
          </div>
        </div>

        {/* System Status Panel */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Cpu className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">{t.settings.systemStatus}</h2>
          </div>

          {systemStatusLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : systemStatus ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-gray-600">{t.settings.python}</span>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus.python_version}
                  </span>
                </div>

                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-gray-600">{t.settings.nodejs}</span>
                  <span className={cn(
                    "text-sm font-medium",
                    systemStatus.node_available ? "text-green-600" : "text-yellow-600"
                  )}>
                    {systemStatus.node_version || (systemStatus.node_available ? t.settings.installed : t.settings.notFound)}
                  </span>
                </div>

                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-gray-600">{t.settings.ffmpeg}</span>
                  <span className={cn(
                    "text-sm font-medium",
                    systemStatus.ffmpeg_available ? "text-green-600" : "text-yellow-600"
                  )}>
                    {systemStatus.ffmpeg_version || (systemStatus.ffmpeg_available ? t.settings.installed : t.settings.notInstalled)}
                  </span>
                </div>

                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-gray-600">{t.settings.diskSpace}</span>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus.disk_space_gb} {t.settings.gbFree}
                  </span>
                </div>
              </div>

              <div className="pt-3 border-t border-gray-100">
                <div className="flex items-center justify-between py-1">
                  <span className="text-sm text-gray-600">{t.settings.databaseSize}</span>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus.database_size_mb} {t.settings.mb}
                  </span>
                </div>
                <div className="flex items-center justify-between py-1">
                  <span className="text-sm text-gray-600">{t.settings.thumbnailsGenerated}</span>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus.thumbnails_count} / {systemStatus.videos_count} {t.settings.videos}
                  </span>
                </div>
              </div>

              {!systemStatus.ffmpeg_available && (
                <div className="p-3 bg-yellow-50 rounded-lg text-sm text-yellow-800">
                  <strong>{t.settings.ffmpegNotInstalled}</strong>
                  <code className="block mt-1 bg-yellow-100 p-2 rounded font-mono text-xs">
                    sudo apt install ffmpeg
                  </code>
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-500">{t.settings.systemStatusUnavailable}</div>
          )}
        </div>

        {/* Optimizer Control Plane Panel */}
        <div className="card p-6">
          <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center">
              <BarChart3 className="mr-2 h-5 w-5 text-gray-400" />
              <h2 className="text-lg font-medium text-gray-900">Optimizer Control Plane</h2>
            </div>
            <span
              className={cn(
                "inline-flex items-center rounded px-2 py-1 text-xs font-medium",
                selectedBuyerId ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700",
              )}
            >
              Buyer context: {selectedBuyerId || "Not selected"}
            </span>
          </div>
          {!selectedBuyerId ? (
            <div className="mb-4 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Select a buyer context in the header for buyer-scoped optimizer actions and telemetry.
            </div>
          ) : null}

          {optimizerPanelLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : optimizerPanelError ? (
            <div className="text-sm text-red-600">
              {optimizerPanelError instanceof Error
                ? optimizerPanelError.message
                : "Failed to load optimizer control plane data."}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Models</div>
                  <div className="mt-1 text-lg font-semibold text-gray-900">
                    {activeModelCount}/{optimizerModels?.meta.total ?? 0}
                  </div>
                  <div className="text-xs text-gray-500">active/total</div>
                </div>
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Scores (14d)</div>
                  <div className="mt-1 text-lg font-semibold text-gray-900">
                    {optimizerScores?.meta.total ?? 0}
                  </div>
                  <div className="text-xs text-gray-500">
                    latest: {optimizerScores?.rows[0]?.score_date || "-"}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Proposals</div>
                  <div className="mt-1 text-lg font-semibold text-gray-900">
                    {optimizerProposals?.meta.total ?? 0}
                  </div>
                  <div className="text-xs text-gray-500">
                    draft {proposalStatusCounts.draft || 0}, approved {proposalStatusCounts.approved || 0}, applied{" "}
                    {proposalStatusCounts.applied || 0}
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-gray-200 p-3">
                <div className="mb-3 text-xs font-semibold text-gray-600">Model Registry</div>
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-xs text-gray-600">
                    Model Name
                    <input
                      type="text"
                      value={newModelName}
                      onChange={(e) => setNewModelName(e.target.value)}
                      className="mt-1 block w-full input py-1 text-sm"
                      placeholder="e.g. Buyer API Model"
                      disabled={createModelMutation.isPending}
                    />
                  </label>
                  <label className="text-xs text-gray-600">
                    Model Type
                    <select
                      value={newModelType}
                      onChange={(e) => setNewModelType(e.target.value as "api" | "rules" | "csv")}
                      className="mt-1 block w-full input py-1 text-sm"
                      disabled={createModelMutation.isPending}
                    >
                      <option value="api">api</option>
                      <option value="rules">rules</option>
                      <option value="csv">csv</option>
                    </select>
                  </label>
                  <label className="text-xs text-gray-600 col-span-2">
                    Description
                    <input
                      type="text"
                      value={newModelDescription}
                      onChange={(e) => setNewModelDescription(e.target.value)}
                      className="mt-1 block w-full input py-1 text-sm"
                      placeholder="optional"
                      disabled={createModelMutation.isPending}
                    />
                  </label>
                  {newModelType === "api" ? (
                    <label className="text-xs text-gray-600 col-span-2">
                      Endpoint URL
                      <input
                        type="url"
                        value={newModelEndpointUrl}
                        onChange={(e) => setNewModelEndpointUrl(e.target.value)}
                        className="mt-1 block w-full input py-1 text-sm"
                        placeholder="https://example.com/score"
                        disabled={createModelMutation.isPending}
                      />
                    </label>
                  ) : null}
                  <label className="text-xs text-gray-600 col-span-2">
                    Authorization Header (optional)
                    <input
                      type="text"
                      value={newModelAuthHeader}
                      onChange={(e) => setNewModelAuthHeader(e.target.value)}
                      className="mt-1 block w-full input py-1 text-sm"
                      placeholder="Bearer <token>"
                      disabled={createModelMutation.isPending}
                    />
                  </label>
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <div className="text-[11px] text-gray-500">
                    Headers are stored encrypted when `CATSCAN_OPTIMIZER_MODEL_SECRET_KEY` is set.
                  </div>
                  <button
                    type="button"
                    onClick={() => createModelMutation.mutate()}
                    disabled={
                      createModelMutation.isPending ||
                      newModelName.trim() === "" ||
                      (newModelType === "api" && newModelEndpointUrl.trim() === "")
                    }
                    className={cn(
                      "btn-primary",
                      (createModelMutation.isPending ||
                        newModelName.trim() === "" ||
                        (newModelType === "api" && newModelEndpointUrl.trim() === "")) &&
                        "cursor-not-allowed opacity-50",
                    )}
                  >
                    {createModelMutation.isPending ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Creating...
                      </>
                    ) : (
                      "Create Model"
                    )}
                  </button>
                </div>
              </div>

              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-50">
                  Models
                </div>
                {optimizerModels?.rows.length ? (
                  <div className="max-h-48 overflow-auto">
                    <table className="min-w-full text-xs">
                      <thead className="bg-gray-50 text-gray-600">
                        <tr>
                          <th className="text-left px-3 py-2">Updated</th>
                          <th className="text-left px-3 py-2">Name</th>
                          <th className="text-left px-3 py-2">Type</th>
                          <th className="text-left px-3 py-2">Status</th>
                          <th className="text-left px-3 py-2">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {optimizerModels.rows.slice(0, 12).map((row) => (
                          <tr key={row.model_id} className="border-t border-gray-100">
                            <td className="px-3 py-2 text-gray-700">{row.updated_at || row.created_at || "-"}</td>
                            <td className="px-3 py-2 text-gray-700">{row.name}</td>
                            <td className="px-3 py-2 text-gray-700">{row.model_type}</td>
                            <td className="px-3 py-2">
                              <span
                                className={cn(
                                  "inline-flex rounded px-2 py-0.5 text-xs font-medium",
                                  row.is_active ? "bg-green-50 text-green-700" : "bg-slate-100 text-slate-700",
                                )}
                              >
                                {row.is_active ? "active" : "inactive"}
                              </span>
                            </td>
                            <td className="px-3 py-2">
                              <div className="flex items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => setSelectedModelId(row.model_id)}
                                  className={cn(
                                    "rounded px-2 py-1 text-xs font-medium",
                                    selectedModelId === row.model_id
                                      ? "bg-indigo-50 text-indigo-700"
                                      : "bg-slate-100 text-slate-700",
                                  )}
                                >
                                  Use
                                </button>
                                <button
                                  type="button"
                                  onClick={() =>
                                    modelActivationMutation.mutate({
                                      modelId: row.model_id,
                                      isActive: row.is_active,
                                    })
                                  }
                                  disabled={modelActivationMutation.isPending}
                                  className={cn(
                                    "rounded px-2 py-1 text-xs font-medium",
                                    row.is_active
                                      ? "bg-amber-50 text-amber-700"
                                      : "bg-blue-50 text-blue-700",
                                    modelActivationMutation.isPending &&
                                      pendingModelId === row.model_id &&
                                      "opacity-60",
                                  )}
                                >
                                  {row.is_active ? "Deactivate" : "Activate"}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="px-3 py-4 text-xs text-gray-500">No models found.</div>
                )}
              </div>

              <div className="rounded-lg border border-gray-200 p-3">
                <div className="mb-3 text-xs font-semibold text-gray-600">Selected Model Details</div>
                {!selectedModel ? (
                  <div className="text-xs text-gray-500">Select a model to edit details.</div>
                ) : (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <label className="text-xs text-gray-600">
                        Name
                        <input
                          type="text"
                          value={editModelName}
                          onChange={(e) => setEditModelName(e.target.value)}
                          className="mt-1 block w-full input py-1 text-sm"
                          disabled={updateModelMutation.isPending}
                        />
                      </label>
                      <label className="text-xs text-gray-600">
                        Type
                        <input
                          type="text"
                          value={selectedModel.model_type}
                          className="mt-1 block w-full input py-1 text-sm bg-gray-50"
                          disabled
                        />
                      </label>
                      <label className="text-xs text-gray-600 col-span-2">
                        Description
                        <input
                          type="text"
                          value={editModelDescription}
                          onChange={(e) => setEditModelDescription(e.target.value)}
                          className="mt-1 block w-full input py-1 text-sm"
                          disabled={updateModelMutation.isPending}
                        />
                      </label>
                      {selectedModel.model_type === "api" ? (
                        <label className="text-xs text-gray-600 col-span-2">
                          Endpoint URL
                          <input
                            type="url"
                            value={editModelEndpointUrl}
                            onChange={(e) => setEditModelEndpointUrl(e.target.value)}
                            className="mt-1 block w-full input py-1 text-sm"
                            disabled={updateModelMutation.isPending}
                          />
                        </label>
                      ) : null}
                      <label className="text-xs text-gray-600 col-span-2">
                        Replace Authorization Header (optional)
                        <input
                          type="text"
                          value={editModelAuthHeader}
                          onChange={(e) => setEditModelAuthHeader(e.target.value)}
                          className="mt-1 block w-full input py-1 text-sm"
                          placeholder={selectedModel.has_auth_header ? "Header currently set" : "Bearer <token>"}
                          disabled={updateModelMutation.isPending}
                        />
                      </label>
                    </div>

                    <div className="flex items-center justify-end">
                      <button
                        type="button"
                        onClick={() => updateModelMutation.mutate()}
                        disabled={
                          updateModelMutation.isPending ||
                          editModelName.trim() === "" ||
                          (selectedModel.model_type === "api" && editModelEndpointUrl.trim() === "")
                        }
                        className={cn(
                          "btn-primary",
                          (updateModelMutation.isPending ||
                            editModelName.trim() === "" ||
                            (selectedModel.model_type === "api" && editModelEndpointUrl.trim() === "")) &&
                            "cursor-not-allowed opacity-50",
                        )}
                      >
                        {updateModelMutation.isPending ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          "Save Model"
                        )}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-50">
                  Efficiency Context (14d)
                </div>
                {efficiencyBlockLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                  </div>
                ) : efficiencyBlockError ? (
                  <div className="px-3 py-4 text-xs text-red-600">
                    {efficiencyBlockError instanceof Error
                      ? efficiencyBlockError.message
                      : "Failed to load optimizer efficiency metrics."}
                  </div>
                ) : (
                  <div className="space-y-3 p-3">
                    <div className="grid grid-cols-3 gap-3">
                      <div className="rounded-lg border border-gray-200 p-2">
                        <div className="text-[11px] text-gray-500">Effective CPM</div>
                        <div className="mt-1 text-sm font-semibold text-gray-900">
                          {formatUsd(optimizerEffectiveCpm?.effective_cpm_usd, 4)}
                        </div>
                        <div className="text-[11px] text-gray-500">
                          media {formatUsd(optimizerEffectiveCpm?.media_cpm_usd, 4)}
                        </div>
                      </div>
                      <div className="rounded-lg border border-gray-200 p-2">
                        <div className="text-[11px] text-gray-500">QPS Efficiency</div>
                        <div className="mt-1 text-sm font-semibold text-gray-900">
                          {formatPct(optimizerEfficiencySummary?.qps_efficiency)}
                        </div>
                        <div className="text-[11px] text-gray-500">
                          impressions / bid requests
                        </div>
                      </div>
                      <div className="rounded-lg border border-gray-200 p-2">
                        <div className="text-[11px] text-gray-500">Assumed Value / QPS</div>
                        <div className="mt-1 text-sm font-semibold text-gray-900">
                          {optimizerEfficiencySummary?.assumed_value_per_qps === null ||
                          optimizerEfficiencySummary?.assumed_value_per_qps === undefined
                            ? "-"
                            : optimizerEfficiencySummary.assumed_value_per_qps.toFixed(6)}
                        </div>
                        <div className="text-[11px] text-gray-500">
                          score {optimizerEfficiencySummary?.assumed_value_score.toFixed(3) ?? "-"}
                        </div>
                      </div>
                    </div>

                    <div className="text-[11px] text-gray-500">
                      spend {formatUsd(optimizerEfficiencySummary?.spend_usd, 2)}, bid requests{" "}
                      {(optimizerEfficiencySummary?.bid_requests ?? 0).toLocaleString()}, reached{" "}
                      {(optimizerEfficiencySummary?.reached_queries ?? 0).toLocaleString()}, avg
                      allocated QPS{" "}
                      {optimizerEfficiencySummary?.avg_allocated_qps === null ||
                      optimizerEfficiencySummary?.avg_allocated_qps === undefined
                        ? "-"
                        : optimizerEfficiencySummary.avg_allocated_qps.toFixed(3)}
                    </div>
                  </div>
                )}
              </div>

              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-50">
                  Conversion Signal Health (7d)
                </div>
                {conversionSignalsLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                  </div>
                ) : conversionSignalsError ? (
                  <div className="px-3 py-4 text-xs text-red-600">
                    {conversionSignalsError instanceof Error
                      ? conversionSignalsError.message
                      : "Failed to load conversion signal health."}
                  </div>
                ) : (
                  <div className="space-y-3 p-3">
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                      <div className="rounded-lg border border-gray-200 p-2">
                        <div className="text-[11px] text-gray-500">Health State</div>
                        <div className="mt-1 text-sm font-semibold text-gray-900">
                          {conversionHealth?.state || "-"}
                        </div>
                        <div className="text-[11px] text-gray-500">
                          lag {conversionHealth?.ingestion?.lag_hours ?? "-"}h
                        </div>
                      </div>
                      <div className="rounded-lg border border-gray-200 p-2">
                        <div className="text-[11px] text-gray-500">Readiness (14d)</div>
                        <div className="mt-1">
                          <span className={cn("rounded px-2 py-0.5 text-xs font-medium", conversionReadinessTone)}>
                            {conversionReadiness?.state || "-"}
                          </span>
                        </div>
                        <div className="mt-1 text-[11px] text-gray-500">
                          active sources {(conversionReadiness?.active_sources ?? 0).toLocaleString()}
                        </div>
                      </div>
                      <div className="rounded-lg border border-gray-200 p-2">
                        <div className="text-[11px] text-gray-500">Accepted / Rejected</div>
                        <div className="mt-1 text-sm font-semibold text-gray-900">
                          {(conversionIngestionStats?.accepted_total ?? 0).toLocaleString()} /{" "}
                          {(conversionIngestionStats?.rejected_total ?? 0).toLocaleString()}
                        </div>
                        <div className="text-[11px] text-gray-500">
                          events {(conversionHealth?.ingestion?.total_events ?? 0).toLocaleString()}
                        </div>
                      </div>
                    </div>

                    {conversionReadinessReasons.length ? (
                      <div className="space-y-1 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
                        {conversionReadinessReasons.slice(0, 3).map((reason) => (
                          <div key={reason}>- {reason}</div>
                        ))}
                      </div>
                    ) : null}

                    {conversionWebhookSecurityStatus ? (
                      <div className="space-y-2 rounded border border-gray-200 p-2">
                        <div className="text-[11px] font-semibold text-gray-600">
                          Webhook Security Posture
                        </div>
                        <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                          <div className="rounded border border-gray-200 p-2">
                            <div className="text-[11px] text-gray-500">Source Coverage</div>
                            <div className="mt-1 text-sm font-semibold text-gray-900">
                              {securityEnabledSources}/{conversionWebhookSecurityStatus.sources.length}
                            </div>
                            <div className="text-[11px] text-gray-500">
                              sources with secret or HMAC enabled
                            </div>
                          </div>
                          <div className="rounded border border-gray-200 p-2">
                            <div className="text-[11px] text-gray-500">Freshness</div>
                            <div className="mt-1">
                              <span
                                className={cn(
                                  "rounded px-2 py-0.5 text-xs font-medium",
                                  conversionWebhookSecurityStatus.freshness_enforced
                                    ? "bg-green-50 text-green-700"
                                    : "bg-slate-100 text-slate-700",
                                )}
                              >
                                {conversionWebhookSecurityStatus.freshness_enforced ? "enforced" : "disabled"}
                              </span>
                            </div>
                            <div className="text-[11px] text-gray-500">
                              max skew {conversionWebhookSecurityStatus.max_skew_seconds}s
                            </div>
                          </div>
                          <div className="rounded border border-gray-200 p-2">
                            <div className="text-[11px] text-gray-500">Rate Limit</div>
                            <div className="mt-1">
                              <span
                                className={cn(
                                  "rounded px-2 py-0.5 text-xs font-medium",
                                  conversionWebhookSecurityStatus.rate_limit_enabled
                                    ? "bg-green-50 text-green-700"
                                    : "bg-slate-100 text-slate-700",
                                )}
                              >
                                {conversionWebhookSecurityStatus.rate_limit_enabled ? "enabled" : "disabled"}
                              </span>
                            </div>
                            <div className="text-[11px] text-gray-500">
                              {conversionWebhookSecurityStatus.rate_limit_per_window} /{" "}
                              {conversionWebhookSecurityStatus.rate_limit_window_seconds}s
                            </div>
                          </div>
                        </div>

                        <div className="max-h-36 overflow-auto">
                          <table className="min-w-full text-xs">
                            <thead className="bg-gray-50 text-gray-600">
                              <tr>
                                <th className="text-left px-2 py-1">Source</th>
                                <th className="text-left px-2 py-1">Plain Secret</th>
                                <th className="text-left px-2 py-1">HMAC</th>
                              </tr>
                            </thead>
                            <tbody>
                              {conversionWebhookSecurityStatus.sources.map((row) => (
                                <tr key={row.source_type} className="border-t border-gray-100">
                                  <td className="px-2 py-1 text-gray-700">{row.source_type}</td>
                                  <td className="px-2 py-1 text-gray-700">
                                    {row.secret_enabled
                                      ? `${row.secret_values_configured} key(s)${
                                          row.using_shared_secret ? " (shared)" : ""
                                        }`
                                      : "off"}
                                  </td>
                                  <td className="px-2 py-1 text-gray-700">
                                    {row.hmac_enabled
                                      ? `${row.hmac_values_configured} key(s)${
                                          row.using_shared_hmac ? " (shared)" : ""
                                        }`
                                      : "off"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ) : null}

                    {conversionIngestionStats?.rows?.length ? (
                      <div className="max-h-40 overflow-auto">
                        <table className="min-w-full text-xs">
                          <thead className="bg-gray-50 text-gray-600">
                            <tr>
                              <th className="text-left px-2 py-1">Source</th>
                              <th className="text-left px-2 py-1">Accepted</th>
                              <th className="text-left px-2 py-1">Rejected</th>
                            </tr>
                          </thead>
                          <tbody>
                            {conversionIngestionStats.rows.slice(0, 6).map((row) => (
                              <tr
                                key={`${row.metric_date || "na"}-${row.source_type}`}
                                className="border-t border-gray-100"
                              >
                                <td className="px-2 py-1 text-gray-700">{row.source_type}</td>
                                <td className="px-2 py-1 text-gray-700">
                                  {row.accepted_count.toLocaleString()}
                                </td>
                                <td className="px-2 py-1 text-gray-700">
                                  {row.rejected_count.toLocaleString()}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="text-xs text-gray-500">
                        No conversion ingestion events recorded in the selected window.
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="rounded-lg border border-gray-200 p-3">
                <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                  <label className="text-xs text-gray-600">
                    Monthly Hosting Cost (USD)
                    <input
                      type="number"
                      min={0}
                      step="0.01"
                      value={monthlyHostingCostInput}
                      onChange={(e) => setMonthlyHostingCostInput(e.target.value)}
                      className="mt-1 block min-w-52 input py-1 text-sm"
                      placeholder="0.00"
                      disabled={saveOptimizerSetupMutation.isPending}
                    />
                  </label>
                  <div className="flex items-center gap-2">
                    <div
                      className={cn(
                        "rounded px-2 py-1 text-xs font-medium",
                        optimizerSetup?.effective_cpm_enabled
                          ? "bg-green-50 text-green-700"
                          : "bg-slate-100 text-slate-600",
                      )}
                    >
                      Effective CPM {optimizerSetup?.effective_cpm_enabled ? "enabled" : "disabled"}
                    </div>
                    <button
                      type="button"
                      onClick={() => saveOptimizerSetupMutation.mutate()}
                      disabled={saveOptimizerSetupMutation.isPending || monthlyHostingCostInput.trim() === ""}
                      className={cn(
                        "btn-primary",
                        (saveOptimizerSetupMutation.isPending ||
                          monthlyHostingCostInput.trim() === "") &&
                          "cursor-not-allowed opacity-50",
                      )}
                    >
                      {saveOptimizerSetupMutation.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Saving...
                        </>
                      ) : (
                        "Save Cost"
                      )}
                    </button>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-gray-200 p-3">
                <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                  <label className="text-xs text-gray-600">
                    Active Model
                    <select
                      value={selectedModelId}
                      onChange={(e) => setSelectedModelId(e.target.value)}
                      className="mt-1 block min-w-52 input py-1 text-sm"
                      disabled={scoreAndProposeMutation.isPending || activeModels.length === 0}
                    >
                      {activeModels.length === 0 ? (
                        <option value="">No active models</option>
                      ) : (
                        activeModels.map((model) => (
                          <option key={model.model_id} value={model.model_id}>
                            {model.name} ({model.model_type})
                          </option>
                        ))
                      )}
                    </select>
                  </label>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => validateModelMutation.mutate()}
                      disabled={validateModelMutation.isPending || !selectedModelId}
                      className={cn(
                        "rounded border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700",
                        (validateModelMutation.isPending || !selectedModelId) &&
                          "cursor-not-allowed opacity-50",
                      )}
                    >
                      {validateModelMutation.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Validating...
                        </>
                      ) : (
                        "Validate Endpoint"
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => scoreAndProposeMutation.mutate()}
                      disabled={scoreAndProposeMutation.isPending || !selectedModelId}
                      className={cn(
                        "btn-primary",
                        (scoreAndProposeMutation.isPending || !selectedModelId) &&
                          "cursor-not-allowed opacity-50",
                      )}
                    >
                      {scoreAndProposeMutation.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Running...
                        </>
                      ) : (
                        "Run Score + Propose"
                      )}
                    </button>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span className="text-xs text-gray-600">Preset</span>
                  {(["safe", "balanced", "aggressive"] as const).map((presetKey) => (
                    <button
                      key={presetKey}
                      type="button"
                      onClick={() => applyWorkflowPreset(presetKey)}
                      disabled={scoreAndProposeMutation.isPending}
                      className={cn(
                        "rounded border px-2 py-1 text-xs font-medium",
                        workflowPreset === presetKey
                          ? "border-primary-500 bg-primary-50 text-primary-700"
                          : "border-slate-300 text-slate-700 hover:bg-slate-50",
                        scoreAndProposeMutation.isPending && "cursor-not-allowed opacity-50",
                      )}
                    >
                      {WORKFLOW_PRESETS[presetKey].label}
                    </button>
                  ))}
                  {workflowPreset === "custom" ? (
                    <span className="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700">
                      Custom
                    </span>
                  ) : null}
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                  <label className="text-xs text-gray-600">
                    Days
                    <input
                      type="number"
                      min={1}
                      max={365}
                      value={workflowDaysInput}
                      onChange={(e) => {
                        setWorkflowDaysInput(e.target.value);
                        setWorkflowPreset("custom");
                      }}
                      className="mt-1 input py-1 text-xs"
                      disabled={scoreAndProposeMutation.isPending}
                    />
                  </label>
                  <label className="text-xs text-gray-600">
                    Score Limit
                    <input
                      type="number"
                      min={1}
                      max={5000}
                      value={workflowScoreLimitInput}
                      onChange={(e) => {
                        setWorkflowScoreLimitInput(e.target.value);
                        setWorkflowPreset("custom");
                      }}
                      className="mt-1 input py-1 text-xs"
                      disabled={scoreAndProposeMutation.isPending}
                    />
                  </label>
                  <label className="text-xs text-gray-600">
                    Proposal Limit
                    <input
                      type="number"
                      min={1}
                      max={2000}
                      value={workflowProposalLimitInput}
                      onChange={(e) => {
                        setWorkflowProposalLimitInput(e.target.value);
                        setWorkflowPreset("custom");
                      }}
                      className="mt-1 input py-1 text-xs"
                      disabled={scoreAndProposeMutation.isPending}
                    />
                  </label>
                  <label className="text-xs text-gray-600">
                    Min Confidence
                    <input
                      type="number"
                      min={0}
                      max={1}
                      step="0.01"
                      value={workflowMinConfidenceInput}
                      onChange={(e) => {
                        setWorkflowMinConfidenceInput(e.target.value);
                        setWorkflowPreset("custom");
                      }}
                      className="mt-1 input py-1 text-xs"
                      disabled={scoreAndProposeMutation.isPending}
                    />
                  </label>
                  <label className="text-xs text-gray-600">
                    Max Delta %
                    <input
                      type="number"
                      min={0.05}
                      max={1}
                      step="0.01"
                      value={workflowMaxDeltaInput}
                      onChange={(e) => {
                        setWorkflowMaxDeltaInput(e.target.value);
                        setWorkflowPreset("custom");
                      }}
                      className="mt-1 input py-1 text-xs"
                      disabled={scoreAndProposeMutation.isPending}
                    />
                  </label>
                </div>
                <label className="mt-3 block text-xs text-gray-600">
                  Optional Validation Payload (JSON)
                  <textarea
                    value={modelValidationPayloadInput}
                    onChange={(e) => setModelValidationPayloadInput(e.target.value)}
                    rows={5}
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-xs text-gray-700 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                    placeholder='{"features":[{"feature_id":"f1","spend_usd":12.3}]}'
                    disabled={validateModelMutation.isPending}
                  />
                  <span className="mt-1 block text-[11px] text-gray-500">
                    Used only for endpoint validation; leave empty to use default ping payload.
                  </span>
                </label>
                {optimizerNotice ? (
                  <div className="mt-3 rounded bg-slate-50 px-3 py-2 text-xs text-slate-700">
                    {optimizerNotice}
                  </div>
                ) : null}
              </div>

              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-50 flex items-center justify-between gap-3">
                  <span>QPS Page-Load SLO</span>
                  <label className="flex items-center gap-2 text-[11px] font-medium text-gray-600">
                    Window
                    <select
                      value={qpsPageSloSinceHours}
                      onChange={(e) => setQpsPageSloSinceHours(Number(e.target.value))}
                      className="rounded border border-gray-300 bg-white px-1.5 py-0.5 text-[11px] text-gray-700"
                    >
                      <option value={24}>24h</option>
                      <option value={72}>72h</option>
                      <option value={168}>7d</option>
                    </select>
                  </label>
                </div>
                {!selectedBuyerId ? (
                  <div className="px-3 py-4 text-xs text-amber-700">
                    Select a buyer to view buyer-scoped QPS page-load SLO telemetry.
                  </div>
                ) : qpsPageLoadSummaryLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                  </div>
                ) : qpsPageLoadSummaryError ? (
                  <div className="px-3 py-4 text-xs text-red-600">
                    {qpsPageLoadSummaryError instanceof Error
                      ? qpsPageLoadSummaryError.message
                      : "Failed to load QPS page-load telemetry summary."}
                  </div>
                ) : qpsPageLoadSummary ? (
                  <div className="space-y-3 p-3">
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                      <div className="rounded-lg border border-gray-200 p-2">
                        <div className="text-[11px] text-gray-500">Samples</div>
                        <div className="mt-1 text-sm font-semibold text-gray-900">
                          {(qpsPageLoadSummary.sample_count || 0).toLocaleString()}
                        </div>
                        <div className="text-[11px] text-gray-500">
                          latest {qpsPageLoadSummary.last_sampled_at || "-"}
                        </div>
                      </div>
                      <div className="rounded-lg border border-gray-200 p-2">
                        <div className="text-[11px] text-gray-500">First Row</div>
                        <div className="mt-1 text-sm font-semibold text-gray-900">
                          p50 {formatLatencyMs(qpsPageLoadSummary.p50_first_table_row_ms)}
                        </div>
                        <div className="text-[11px] text-gray-500">
                          p95 {formatLatencyMs(qpsPageLoadSummary.p95_first_table_row_ms)} target{" "}
                          {QPS_PAGE_P95_FIRST_ROW_SLO_MS} ms
                        </div>
                      </div>
                      <div className="rounded-lg border border-gray-200 p-2">
                        <div className="text-[11px] text-gray-500">Table Hydrated</div>
                        <div className="mt-1 text-sm font-semibold text-gray-900">
                          p50 {formatLatencyMs(qpsPageLoadSummary.p50_table_hydrated_ms)}
                        </div>
                        <div className="text-[11px] text-gray-500">
                          p95 {formatLatencyMs(qpsPageLoadSummary.p95_table_hydrated_ms)} target{" "}
                          {QPS_PAGE_P95_HYDRATED_SLO_MS} ms
                        </div>
                      </div>
                      <div className="rounded-lg border border-gray-200 p-2">
                        <div className="text-[11px] text-gray-500">SLO Status</div>
                        <div className="mt-1">
                          <span
                            className={cn(
                              "rounded px-2 py-0.5 text-xs font-medium",
                              qpsPageLoadSummarySloPass
                                ? "bg-green-50 text-green-700"
                                : qpsPageLoadSummarySloDegraded
                                  ? "bg-amber-50 text-amber-700"
                                  : "bg-slate-100 text-slate-700",
                            )}
                          >
                            {qpsPageLoadSummarySloPass
                              ? "within target"
                              : qpsPageLoadSummarySloDegraded
                                ? "above target"
                                : "insufficient data"}
                          </span>
                        </div>
                      </div>
                    </div>

                    {qpsPageLoadSummary.latest_samples.length ? (
                      <div className="max-h-36 overflow-auto">
                        <table className="min-w-full text-xs">
                          <thead className="bg-gray-50 text-gray-600">
                            <tr>
                              <th className="text-left px-2 py-1">Sampled</th>
                              <th className="text-left px-2 py-1">Days</th>
                              <th className="text-left px-2 py-1">First Row</th>
                              <th className="text-left px-2 py-1">Hydrated</th>
                            </tr>
                          </thead>
                          <tbody>
                            {qpsPageLoadSummary.latest_samples.slice(0, 5).map((row) => (
                              <tr key={`${row.sampled_at}-${row.selected_days || 0}`} className="border-t border-gray-100">
                                <td className="px-2 py-1 text-gray-700">{row.sampled_at}</td>
                                <td className="px-2 py-1 text-gray-700">{row.selected_days ?? "-"}</td>
                                <td className="px-2 py-1 text-gray-700">
                                  {formatLatencyMs(row.time_to_first_table_row_ms)}
                                </td>
                                <td className="px-2 py-1 text-gray-700">
                                  {formatLatencyMs(row.time_to_table_hydrated_ms)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="text-xs text-gray-500">
                        No recorded QPS page-load samples in the selected window.
                      </div>
                    )}

                    {qpsApiLatencyRollupRows.length ? (
                      <div className="space-y-2 rounded border border-gray-200 p-2">
                        <div className="text-[11px] font-semibold text-gray-600">
                          API latency rollup (last 24h)
                        </div>
                        <div className="max-h-32 overflow-auto">
                          <table className="min-w-full text-xs">
                            <thead className="bg-gray-50 text-gray-600">
                              <tr>
                                <th className="text-left px-2 py-1">API</th>
                                <th className="text-left px-2 py-1">Samples</th>
                                <th className="text-left px-2 py-1">p50</th>
                                <th className="text-left px-2 py-1">p95</th>
                              </tr>
                            </thead>
                            <tbody>
                              {qpsApiLatencyRollupRows.map((row) => (
                                <tr key={row.api_path} className="border-t border-gray-100">
                                  <td className="px-2 py-1 font-mono text-gray-700">{row.api_path}</td>
                                  <td className="px-2 py-1 text-gray-700">
                                    {row.sample_count.toLocaleString()}
                                  </td>
                                  <td className="px-2 py-1 text-gray-700">
                                    {formatLatencyMs(row.p50_latency_ms)}
                                  </td>
                                  <td className="px-2 py-1 text-gray-700">
                                    {formatLatencyMs(row.p95_latency_ms)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ) : null}

                    {qpsPageLoadSummary.time_buckets.length ? (
                      <div className="space-y-2 rounded border border-gray-200 p-2">
                        <div className="text-[11px] font-semibold text-gray-600">
                          Latency trend buckets ({qpsPageSloBucketHours}h)
                        </div>
                        <div className="max-h-40 overflow-auto">
                          <table className="min-w-full text-xs">
                            <thead className="bg-gray-50 text-gray-600">
                              <tr>
                                <th className="text-left px-2 py-1">Bucket start</th>
                                <th className="text-left px-2 py-1">Samples</th>
                                <th className="text-left px-2 py-1">p95 first row</th>
                                <th className="text-left px-2 py-1">p95 hydrated</th>
                              </tr>
                            </thead>
                            <tbody>
                              {qpsPageLoadSummary.time_buckets.slice(0, 12).map((bucket) => (
                                <tr key={bucket.bucket_start} className="border-t border-gray-100">
                                  <td className="px-2 py-1 text-gray-700">{bucket.bucket_start}</td>
                                  <td className="px-2 py-1 text-gray-700">
                                    {bucket.sample_count.toLocaleString()}
                                  </td>
                                  <td
                                    className={cn(
                                      "px-2 py-1",
                                      latencyToneClass(
                                        bucket.p95_first_table_row_ms,
                                        QPS_PAGE_P95_FIRST_ROW_SLO_MS,
                                      ),
                                    )}
                                  >
                                    {formatLatencyMs(bucket.p95_first_table_row_ms)}
                                  </td>
                                  <td
                                    className={cn(
                                      "px-2 py-1",
                                      latencyToneClass(
                                        bucket.p95_table_hydrated_ms,
                                        QPS_PAGE_P95_HYDRATED_SLO_MS,
                                      ),
                                    )}
                                  >
                                    {formatLatencyMs(bucket.p95_table_hydrated_ms)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="px-3 py-4 text-xs text-gray-500">
                    QPS page-load telemetry summary unavailable.
                  </div>
                )}
              </div>

              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-50">
                  Recent Segment Scores
                </div>
                {optimizerScores?.rows.length ? (
                  <div className="max-h-52 overflow-auto">
                    <table className="min-w-full text-xs">
                      <thead className="bg-gray-50 text-gray-600">
                        <tr>
                          <th className="text-left px-3 py-2">Date</th>
                          <th className="text-left px-3 py-2">Billing</th>
                          <th className="text-left px-3 py-2">Score</th>
                          <th className="text-left px-3 py-2">Confidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {optimizerScores.rows.slice(0, 8).map((row) => (
                          <tr key={row.score_id} className="border-t border-gray-100">
                            <td className="px-3 py-2 text-gray-700">{row.score_date || "-"}</td>
                            <td className="px-3 py-2 font-mono text-gray-700">{row.billing_id || "-"}</td>
                            <td className="px-3 py-2 text-gray-700">{row.value_score.toFixed(3)}</td>
                            <td className="px-3 py-2 text-gray-700">{row.confidence.toFixed(3)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="px-3 py-4 text-xs text-gray-500">No segment scores found.</div>
                )}
              </div>

              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-50">
                  Recent QPS Proposals
                </div>
                {optimizerProposals?.rows.length ? (
                  <div className="max-h-52 overflow-auto">
                    <table className="min-w-full text-xs">
                      <thead className="bg-gray-50 text-gray-600">
                        <tr>
                          <th className="text-left px-3 py-2">Updated</th>
                          <th className="text-left px-3 py-2">Billing</th>
                          <th className="text-left px-3 py-2">Delta QPS</th>
                          <th className="text-left px-3 py-2">Status</th>
                          <th className="text-left px-3 py-2">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {optimizerProposals.rows.slice(0, 8).map((row) => (
                          <tr key={row.proposal_id} className="border-t border-gray-100">
                            <td className="px-3 py-2 text-gray-700">{row.updated_at || row.created_at || "-"}</td>
                            <td className="px-3 py-2 font-mono text-gray-700">{row.billing_id || "-"}</td>
                            <td
                              className={cn(
                                "px-3 py-2 font-medium",
                                row.delta_qps >= 0 ? "text-green-700" : "text-red-700",
                              )}
                            >
                              {row.delta_qps >= 0 ? "+" : ""}
                              {row.delta_qps.toFixed(2)}
                            </td>
                            <td className="px-3 py-2">
                              <span
                                className={cn(
                                  "inline-flex rounded px-2 py-0.5 text-xs font-medium",
                                  row.status === "draft" && "bg-slate-100 text-slate-700",
                                  row.status === "approved" && "bg-blue-50 text-blue-700",
                                  row.status === "applied" && "bg-green-50 text-green-700",
                                  row.status === "rejected" && "bg-red-50 text-red-700",
                                )}
                              >
                                {row.status}
                              </span>
                            </td>
                            <td className="px-3 py-2">
                              <div className="flex items-center gap-2">
                                {row.status === "draft" ? (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      proposalActionMutation.mutate({
                                        proposalId: row.proposal_id,
                                        action: "approve",
                                      })
                                    }
                                    disabled={proposalActionMutation.isPending}
                                    className={cn(
                                      "rounded bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700",
                                      proposalActionMutation.isPending &&
                                        pendingProposalId === row.proposal_id &&
                                        "opacity-60",
                                    )}
                                  >
                                    Approve
                                  </button>
                                ) : row.status === "approved" ? (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      proposalActionMutation.mutate({
                                        proposalId: row.proposal_id,
                                        action: "apply",
                                      })
                                    }
                                    disabled={proposalActionMutation.isPending}
                                    className={cn(
                                      "rounded bg-green-50 px-2 py-1 text-xs font-medium text-green-700",
                                      proposalActionMutation.isPending &&
                                        pendingProposalId === row.proposal_id &&
                                        "opacity-60",
                                    )}
                                  >
                                    Apply Queue
                                  </button>
                                ) : row.status === "applied" ? (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() =>
                                        proposalActionMutation.mutate({
                                          proposalId: row.proposal_id,
                                          action: "sync",
                                        })
                                      }
                                      disabled={proposalActionMutation.isPending}
                                      className={cn(
                                        "rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700",
                                        proposalActionMutation.isPending &&
                                          pendingProposalId === row.proposal_id &&
                                          "opacity-60",
                                      )}
                                    >
                                      Sync
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setRollbackProposal({
                                          proposalId: row.proposal_id,
                                          billingId: row.billing_id,
                                        });
                                        setRollbackReason("");
                                        setRollbackPreview(null);
                                      }}
                                      className="rounded bg-orange-50 px-2 py-1 text-xs font-medium text-orange-700"
                                    >
                                      Rollback
                                    </button>
                                  </>
                                ) : (
                                  <span className="text-xs text-gray-400">-</span>
                                )}
                                <button
                                  type="button"
                                  onClick={() => setSelectedProposalHistoryId(row.proposal_id)}
                                  className={cn(
                                    "rounded px-2 py-1 text-xs font-medium",
                                    selectedProposalHistoryId === row.proposal_id
                                      ? "bg-indigo-50 text-indigo-700"
                                      : "bg-slate-100 text-slate-700",
                                  )}
                                >
                                  History
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="px-3 py-4 text-xs text-gray-500">No proposals found.</div>
                )}
              </div>

              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-50">
                  Proposal History {selectedProposalHistoryId ? `(${selectedProposalHistoryId})` : ""}
                </div>
                {!selectedProposalHistoryId ? (
                  <div className="px-3 py-4 text-xs text-gray-500">Select a proposal to view workflow history.</div>
                ) : optimizerProposalHistoryLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                  </div>
                ) : optimizerProposalHistoryError ? (
                  <div className="px-3 py-4 text-xs text-red-600">
                    {optimizerProposalHistoryError instanceof Error
                      ? optimizerProposalHistoryError.message
                      : "Failed to load proposal history."}
                  </div>
                ) : proposalHistoryRows.length ? (
                  <div className="max-h-52 overflow-auto">
                    <table className="min-w-full text-xs">
                      <thead className="bg-gray-50 text-gray-600">
                        <tr>
                          <th className="text-left px-3 py-2">Created</th>
                          <th className="text-left px-3 py-2">Transition</th>
                          <th className="text-left px-3 py-2">Mode</th>
                          <th className="text-left px-3 py-2">By</th>
                        </tr>
                      </thead>
                      <tbody>
                        {proposalHistoryRows.slice(0, 12).map((row) => (
                          <tr key={row.event_id} className="border-t border-gray-100">
                            <td className="px-3 py-2 text-gray-700">{row.created_at || "-"}</td>
                            <td className="px-3 py-2 text-gray-700">
                              {row.from_status || "initial"} → {row.to_status}
                            </td>
                            <td className="px-3 py-2 text-gray-700">{row.apply_mode || "-"}</td>
                            <td className="px-3 py-2 text-gray-700">{row.changed_by || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="px-3 py-4 text-xs text-gray-500">No history events for this proposal.</div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Database Panel */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <BarChart3 className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">Optimizer Readiness</h2>
          </div>

          {dataHealthLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : dataHealth ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <label className="text-xs text-gray-600">
                  Window
                  <select
                    value={healthDays}
                    onChange={(e) => setHealthDays(Number(e.target.value))}
                    className="mt-1 block w-full input py-1 text-sm"
                  >
                    <option value={7}>7 days</option>
                    <option value={14}>14 days</option>
                    <option value={30}>30 days</option>
                  </select>
                </label>
                <label className="text-xs text-gray-600">
                  State Filter
                  <select
                    value={healthStateFilter}
                    onChange={(e) =>
                      setHealthStateFilter(
                        e.target.value as "all" | "healthy" | "degraded" | "unavailable"
                      )
                    }
                    className="mt-1 block w-full input py-1 text-sm"
                  >
                    <option value="all">all</option>
                    <option value="healthy">healthy</option>
                    <option value="degraded">degraded</option>
                    <option value="unavailable">unavailable</option>
                  </select>
                </label>
                <label className="text-xs text-gray-600">
                  Min Completeness %
                  <input
                    type="number"
                    min={0}
                    max={100}
                    placeholder="none"
                    value={minCompleteness}
                    onChange={(e) => setMinCompleteness(e.target.value)}
                    className="mt-1 block w-full input py-1 text-sm"
                  />
                </label>
                <label className="text-xs text-gray-600">
                  Row Limit
                  <select
                    value={healthLimit}
                    onChange={(e) => setHealthLimit(Number(e.target.value))}
                    className="mt-1 block w-full input py-1 text-sm"
                  >
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                </label>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Report Type Coverage</div>
                  <div className="mt-1 text-lg font-semibold text-gray-900">
                    {dataHealth.optimizer_readiness.report_completeness.available_report_types}/
                    {dataHealth.optimizer_readiness.report_completeness.expected_report_types}
                  </div>
                  <div className="text-xs text-gray-500">
                    {dataHealth.optimizer_readiness.report_completeness.coverage_pct}% available
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Quality Freshness</div>
                  <div className="mt-1 text-lg font-semibold text-gray-900">
                    {dataHealth.optimizer_readiness.rtb_quality_freshness.age_days ?? "-"} day(s)
                  </div>
                  <div className="text-xs text-gray-500">
                    state: {dataHealth.optimizer_readiness.rtb_quality_freshness.availability_state}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Bidstream Dimension Coverage</div>
                  <div className="mt-1 text-sm font-semibold text-gray-900">
                    platform {100 - dataHealth.optimizer_readiness.bidstream_dimension_coverage.platform_missing_pct}%
                  </div>
                  <div className="text-xs text-gray-500">
                    env {100 - dataHealth.optimizer_readiness.bidstream_dimension_coverage.environment_missing_pct}%,
                    deal {100 - dataHealth.optimizer_readiness.bidstream_dimension_coverage.transaction_type_missing_pct}%
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Seat-Day Completeness</div>
                  <div className="mt-1 text-lg font-semibold text-gray-900">
                    {dataHealth.optimizer_readiness.seat_day_completeness.summary.avg_completeness_pct}%
                  </div>
                  <div className="text-xs text-gray-500">
                    {dataHealth.optimizer_readiness.seat_day_completeness.summary.total_seat_days} seat-day rows
                  </div>
                </div>
              </div>

              <div className="text-xs text-gray-500">
                Seat-day rollup refreshed at:{" "}
                {dataHealth.optimizer_readiness.seat_day_completeness.refreshed_at || "unknown"}
              </div>

              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-50">
                  Latest Seat-Day Completeness Rows
                </div>
                <div className="max-h-56 overflow-auto">
                  <table className="min-w-full text-xs">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="text-left px-3 py-2">Date</th>
                        <th className="text-left px-3 py-2">Seat</th>
                        <th className="text-left px-3 py-2">Reports</th>
                        <th className="text-left px-3 py-2">Completeness</th>
                        <th className="text-left px-3 py-2">State</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dataHealth.optimizer_readiness.seat_day_completeness.rows.slice(0, 10).map((row) => (
                        <tr key={`${row.metric_date}-${row.buyer_account_id}`} className="border-t border-gray-100">
                          <td className="px-3 py-2 text-gray-700">{row.metric_date || "-"}</td>
                          <td className="px-3 py-2 font-mono text-gray-700">{row.buyer_account_id}</td>
                          <td className="px-3 py-2 text-gray-700">
                            {row.available_report_types}/{row.expected_report_types}
                          </td>
                          <td className="px-3 py-2 text-gray-700">{row.completeness_pct}%</td>
                          <td className="px-3 py-2">
                            <span
                              className={cn(
                                "inline-flex rounded px-2 py-0.5 text-xs font-medium",
                                row.availability_state === "healthy" && "bg-green-50 text-green-700",
                                row.availability_state === "degraded" && "bg-yellow-50 text-yellow-700",
                                row.availability_state === "unavailable" && "bg-red-50 text-red-700"
                              )}
                            >
                              {row.availability_state}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-gray-500">Data health details unavailable.</div>
          )}
        </div>

        {/* Database Panel */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Database className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">{t.settings.database}</h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{t.settings.path}</span>
              <span className="text-sm font-mono text-gray-900">
                {stats?.db_path || t.settings.notAvailable}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{t.settings.creatives}</span>
              <span className="text-sm font-medium text-gray-900">
                {stats?.creative_count ?? 0}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{t.settings.campaigns}</span>
              <span className="text-sm font-medium text-gray-900">
                {stats?.campaign_count ?? 0}
              </span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-sm text-gray-600">{t.settings.clusters}</span>
              <span className="text-sm font-medium text-gray-900">
                {stats?.cluster_count ?? 0}
              </span>
            </div>
          </div>
        </div>

        {/* Thumbnail Generation Panel */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Video className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">{t.settings.videoThumbnails}</h2>
          </div>

          {thumbnailStatusLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : thumbnailStatus ? (
            <div className="space-y-4">
              {/* Status Summary */}
              <div className="grid grid-cols-4 gap-4">
                <div className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">
                    {thumbnailStatus.total_videos}
                  </div>
                  <div className="text-xs text-gray-500">{t.settings.totalVideos}</div>
                </div>
                <div className="text-center p-3 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">
                    {thumbnailStatus.with_thumbnails}
                  </div>
                  <div className="text-xs text-gray-500">{t.settings.withThumbnails}</div>
                </div>
                <div className="text-center p-3 bg-yellow-50 rounded-lg">
                  <div className="text-2xl font-bold text-yellow-600">
                    {thumbnailStatus.pending}
                  </div>
                  <div className="text-xs text-gray-500">{t.settings.pending}</div>
                </div>
                <div className="text-center p-3 bg-red-50 rounded-lg">
                  <div className="text-2xl font-bold text-red-600">
                    {thumbnailStatus.failed}
                  </div>
                  <div className="text-xs text-gray-500">{t.settings.failed}</div>
                </div>
              </div>

              {/* Coverage Bar */}
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">{t.settings.coverage}</span>
                  <span className="font-medium">{thumbnailStatus.coverage_percent}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-green-500 h-2 rounded-full transition-all"
                    style={{ width: `${thumbnailStatus.coverage_percent}%` }}
                  />
                </div>
              </div>

              {/* ffmpeg Status */}
              <div className="flex items-center justify-between py-2 border-t border-gray-100">
                <span className="text-sm text-gray-600">{t.settings.ffmpegAvailable}</span>
                {thumbnailStatus.ffmpeg_available ? (
                  <span className="flex items-center text-sm font-medium text-green-600">
                    <CheckCircle className="h-4 w-4 mr-1" />
                    {t.settings.installed}
                  </span>
                ) : (
                  <span className="flex items-center text-sm font-medium text-red-600">
                    <AlertTriangle className="h-4 w-4 mr-1" />
                    {t.settings.notFound}
                  </span>
                )}
              </div>

              {/* Generation Controls */}
              {thumbnailStatus.ffmpeg_available && thumbnailStatus.pending > 0 && (
                <div className="pt-4 border-t border-gray-100">
                  <div className="flex items-center gap-4 mb-3">
                    <label className="text-sm text-gray-600">
                      {t.settings.batchSize}
                      <select
                        value={batchLimit}
                        onChange={(e) => setBatchLimit(Number(e.target.value))}
                        className="ml-2 input py-1 text-sm"
                        disabled={generateMutation.isPending}
                      >
                        <option value={10}>10</option>
                        <option value={25}>25</option>
                        <option value={50}>50</option>
                        <option value={100}>100</option>
                      </select>
                    </label>
                    <label className="flex items-center text-sm text-gray-600">
                      <input
                        type="checkbox"
                        checked={forceRetry}
                        onChange={(e) => setForceRetry(e.target.checked)}
                        className="mr-2"
                        disabled={generateMutation.isPending}
                      />
                      {t.settings.retryFailed}
                    </label>
                  </div>
                  <button
                    onClick={() => generateMutation.mutate()}
                    disabled={generateMutation.isPending}
                    className={cn(
                      "btn-primary w-full",
                      generateMutation.isPending && "opacity-50 cursor-not-allowed"
                    )}
                  >
                    {generateMutation.isPending ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        {t.settings.generating}
                      </>
                    ) : (
                      <>
                        <Image className="h-4 w-4 mr-2" />
                        {t.settings.generateThumbnails}
                      </>
                    )}
                  </button>

                  {/* Results */}
                  {generateMutation.data && (
                    <div className="mt-3 p-3 bg-gray-50 rounded-lg text-sm">
                      <div className="font-medium text-gray-900 mb-1">
                        {t.settings.processedVideos.replace('{count}', String(generateMutation.data.total_processed))}
                      </div>
                      <div className="text-gray-600">
                        {t.settings.succeededFailed
                          .replace('{success}', String(generateMutation.data.success_count))
                          .replace('{failed}', String(generateMutation.data.failed_count))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {!thumbnailStatus.ffmpeg_available && (
                <div className="p-3 bg-yellow-50 rounded-lg text-sm text-yellow-800">
                  <strong>{t.settings.ffmpegNotFoundInstall}</strong>
                  <code className="block mt-1 bg-yellow-100 p-2 rounded font-mono text-xs">
                    sudo apt install ffmpeg
                  </code>
                </div>
              )}

              {thumbnailStatus.pending === 0 && thumbnailStatus.with_thumbnails > 0 && (
                <div className="p-3 bg-green-50 rounded-lg text-sm text-green-800">
                  {t.settings.allThumbnailsGenerated}
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-500">{t.settings.noThumbnailData}</div>
          )}
        </div>
      </div>

      {rollbackProposal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-xl rounded-lg bg-white shadow-xl">
            <div className="border-b border-gray-200 px-4 py-3">
              <div className="text-sm font-semibold text-gray-900">
                Rollback Applied Proposal
              </div>
              <div className="mt-1 text-xs text-gray-500">
                proposal {rollbackProposal.proposalId}, billing {rollbackProposal.billingId}
              </div>
            </div>

            <div className="space-y-3 px-4 py-4">
              {rollbackSnapshotsLoading ? (
                <div className="flex items-center justify-center py-3">
                  <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                </div>
              ) : rollbackSnapshotsError ? (
                <div className="rounded bg-red-50 px-3 py-2 text-xs text-red-700">
                  {rollbackSnapshotsError instanceof Error
                    ? rollbackSnapshotsError.message
                    : "Failed to load snapshots."}
                </div>
              ) : rollbackSnapshots?.length ? (
                <>
                  <label className="text-xs text-gray-600">
                    Snapshot
                    <select
                      value={selectedRollbackSnapshotId}
                      onChange={(e) => setSelectedRollbackSnapshotId(e.target.value)}
                      className="mt-1 block w-full input py-1 text-sm"
                      disabled={rollbackPreviewMutation.isPending || rollbackExecuteMutation.isPending}
                    >
                      {rollbackSnapshots.map((row) => (
                        <option key={row.id} value={String(row.id)}>
                          #{row.id} {row.snapshot_name || row.snapshot_type} ({row.created_at})
                        </option>
                      ))}
                    </select>
                  </label>

                  {selectedRollbackSnapshot ? (
                    <div className="rounded border border-gray-200 px-3 py-2 text-xs text-gray-600">
                      selected snapshot: #{selectedRollbackSnapshot.id}{" "}
                      {selectedRollbackSnapshot.snapshot_name || selectedRollbackSnapshot.snapshot_type}
                    </div>
                  ) : null}

                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => rollbackPreviewMutation.mutate()}
                      disabled={
                        rollbackPreviewMutation.isPending ||
                        rollbackExecuteMutation.isPending ||
                        !selectedRollbackSnapshotId
                      }
                      className={cn(
                        "rounded border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700",
                        (rollbackPreviewMutation.isPending ||
                          rollbackExecuteMutation.isPending ||
                          !selectedRollbackSnapshotId) &&
                          "cursor-not-allowed opacity-50",
                      )}
                    >
                      {rollbackPreviewMutation.isPending ? "Previewing..." : "Preview Rollback"}
                    </button>
                  </div>

                  {rollbackPreview ? (
                    <div className="space-y-2 rounded border border-gray-200 px-3 py-2">
                      <div className="text-xs font-medium text-gray-700">{rollbackPreview.message}</div>
                      {rollbackPreview.changes_made.length ? (
                        <div className="max-h-28 overflow-auto space-y-1">
                          {rollbackPreview.changes_made.map((change, idx) => (
                            <div key={`${idx}-${change}`} className="text-[11px] font-mono text-gray-600">
                              {change}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-[11px] text-gray-500">No changes detected for rollback.</div>
                      )}
                    </div>
                  ) : null}

                  <label className="text-xs text-gray-600">
                    Reason
                    <input
                      type="text"
                      value={rollbackReason}
                      onChange={(e) => setRollbackReason(e.target.value)}
                      className="mt-1 block w-full input py-1 text-sm"
                      placeholder="why rollback is required"
                      disabled={rollbackExecuteMutation.isPending}
                    />
                  </label>
                </>
              ) : (
                <div className="rounded bg-slate-50 px-3 py-2 text-xs text-slate-700">
                  No snapshots found for this billing ID.
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-gray-200 px-4 py-3">
              <button
                type="button"
                onClick={() => {
                  setRollbackProposal(null);
                  setRollbackReason("");
                  setRollbackPreview(null);
                }}
                className="rounded px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
                disabled={rollbackExecuteMutation.isPending}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => rollbackExecuteMutation.mutate()}
                disabled={
                  rollbackExecuteMutation.isPending ||
                  !selectedRollbackSnapshotId ||
                  rollbackReason.trim() === ""
                }
                className={cn(
                  "rounded bg-orange-600 px-3 py-2 text-xs font-medium text-white",
                  (rollbackExecuteMutation.isPending ||
                    !selectedRollbackSnapshotId ||
                    rollbackReason.trim() === "") &&
                    "cursor-not-allowed opacity-50",
                )}
              >
                {rollbackExecuteMutation.isPending ? "Executing..." : "Rollback Now"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
