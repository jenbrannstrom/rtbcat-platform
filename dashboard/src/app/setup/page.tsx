"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  Settings,
  CheckCircle,
  XCircle,
  Database,
  Server,
  Users,
  Clock,
  ChevronRight,
  Video,
  Loader2,
  AlertTriangle,
  Image,
  Link2,
  Upload,
  Mail,
  Shield,
  FileJson,
  RefreshCw,
  ArrowRight,
  ExternalLink,
  ChevronDown,
  HardDrive,
  Cpu,
  X,
  Calendar,
  Inbox,
} from "lucide-react";
import {
  getHealth,
  getStats,
  getThumbnailStatus,
  generateThumbnailsBatch,
  getSystemStatus,
  getSeats,
  syncSeat,
  getCredentialsStatus,
  uploadCredentials,
  discoverSeats,
} from "@/lib/api";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import { ImportDropzone } from "@/components/import-dropzone";
import { ImportPreview } from "@/components/import-preview";
import { ImportProgress } from "@/components/import-progress";
import { ValidationErrors } from "@/components/validation-errors";
import {
  validatePerformanceCSV,
  type ExtendedValidationResult,
  groupAnomaliesByType,
  getTopAnomalyApps,
  formatAnomalyType,
} from "@/lib/csv-validator";
import type { AnomalyType } from "@/lib/types/import";
import { parseCSV } from "@/lib/csv-parser";
import { importPerformanceData } from "@/lib/api";
import {
  uploadChunkedCSV,
  previewCSV,
  type UploadProgress,
} from "@/lib/chunked-uploader";
import { extractSeatFromPreview, formatSeatInfo, type SeatInfo } from "@/lib/seat-extractor";
import type { ImportResponse } from "@/lib/types/import";
import { cn } from "@/lib/utils";
import type { BuyerSeat } from "@/types/api";

type SetupTab = "api" | "gmail" | "import" | "system";

const TABS: { id: SetupTab; label: string; icon: React.ElementType; description: string }[] = [
  { id: "api", label: "Connect API", icon: Link2, description: "Google Authorized Buyers" },
  { id: "gmail", label: "Gmail Reports", icon: Mail, description: "Auto-fetch scheduled reports" },
  { id: "import", label: "Manual Import", icon: Upload, description: "Upload CSV files" },
  { id: "system", label: "System", icon: Settings, description: "Status & settings" },
];

export default function SetupPage() {
  const [activeTab, setActiveTab] = useState<SetupTab>("api");
  const queryClient = useQueryClient();

  const {
    data: health,
    isLoading: healthLoading,
    error: healthError,
    refetch: refetchHealth,
  } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  if (healthLoading) {
    return <LoadingPage />;
  }

  if (healthError) {
    return (
      <ErrorPage
        message={
          healthError instanceof Error
            ? healthError.message
            : "Failed to check API status"
        }
        onRetry={() => refetchHealth()}
      />
    );
  }

  const isConfigured = health?.configured === true;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Setup</h1>
        <p className="text-gray-600 mt-1">
          Configure data sources and system settings
        </p>
      </div>

      {/* Quick Status Bar */}
      <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <div className={cn(
                "w-2 h-2 rounded-full",
                isConfigured ? "bg-green-500" : "bg-yellow-500"
              )} />
              <span className="text-sm text-gray-600">
                API: {isConfigured ? "Connected" : "Not connected"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-gray-400" />
              <span className="text-sm text-gray-600">
                Gmail: Not configured
              </span>
            </div>
          </div>
          <a
            href="/waste-analysis"
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            Go to Waste Optimizer →
          </a>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-1" aria-label="Setup tabs">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors",
                  isActive
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="min-h-[500px]">
        {activeTab === "api" && <ApiConnectionTab />}
        {activeTab === "gmail" && <GmailReportsTab />}
        {activeTab === "import" && <ManualImportTab />}
        {activeTab === "system" && <SystemTab />}
      </div>
    </div>
  );
}

// ============================================================================
// API Connection Tab
// ============================================================================

function ApiConnectionTab() {
  const queryClient = useQueryClient();
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: health, refetch: refetchHealth } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  const { data: credentialsStatus } = useQuery({
    queryKey: ["credentialsStatus"],
    queryFn: getCredentialsStatus,
    enabled: health?.configured === true,
  });

  const { data: seats, isLoading: seatsLoading } = useQuery({
    queryKey: ["seats"],
    queryFn: () => getSeats({ active_only: false }),
    enabled: health?.configured === true,
  });

  const [discoveryAttempted, setDiscoveryAttempted] = useState(false);

  const discoverMutation = useMutation({
    mutationFn: (bidderId: string) => discoverSeats({ bidder_id: bidderId }),
    onSuccess: (data) => {
      setMessage({ type: "success", text: `Discovered ${data.seats_discovered} buyer seat(s)` });
      queryClient.invalidateQueries({ queryKey: ["seats"] });
      setTimeout(() => setMessage(null), 5000);
    },
    onError: (error) => {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to discover seats" });
      setTimeout(() => setMessage(null), 5000);
    },
  });

  useEffect(() => {
    const isConfigured = health?.configured === true;
    const noSeats = seats !== undefined && seats.length === 0;
    const notLoading = !seatsLoading && !discoverMutation.isPending;
    const hasAccountId = !!credentialsStatus?.account_id;

    if (isConfigured && noSeats && notLoading && !discoveryAttempted && hasAccountId) {
      setDiscoveryAttempted(true);
      discoverMutation.mutate(credentialsStatus.account_id!);
    }
  }, [health, seats, seatsLoading, discoveryAttempted, credentialsStatus, discoverMutation]);

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const contents = await file.text();
      let json;
      try {
        json = JSON.parse(contents);
      } catch {
        throw new Error("Invalid JSON file. Please upload a valid service account key.");
      }
      if (!json.type || !json.client_email || !json.private_key) {
        throw new Error("Invalid service account format. Missing required fields.");
      }
      if (json.type !== "service_account") {
        throw new Error(`Invalid credential type: "${json.type}". Expected "service_account".`);
      }
      return uploadCredentials(contents);
    },
    onSuccess: (data) => {
      setMessage({ type: "success", text: `Connected as ${data.client_email}` });
      queryClient.invalidateQueries({ queryKey: ["health"] });
      queryClient.invalidateQueries({ queryKey: ["credentialsStatus"] });
      queryClient.invalidateQueries({ queryKey: ["seats"] });
      refetchHealth();
    },
    onError: (error) => {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Upload failed" });
    },
  });

  const syncMutation = useMutation({
    mutationFn: (buyerId: string) => syncSeat(buyerId),
    onSuccess: (data) => {
      setMessage({ type: "success", text: `Synced ${data.creatives_synced} creatives` });
      queryClient.invalidateQueries({ queryKey: ["creatives"] });
      queryClient.invalidateQueries({ queryKey: ["seats"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      setSyncingId(null);
      setTimeout(() => setMessage(null), 5000);
    },
    onError: (error) => {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Sync failed" });
      setSyncingId(null);
      setTimeout(() => setMessage(null), 5000);
    },
  });

  const handleSync = (buyerId: string) => {
    setSyncingId(buyerId);
    syncMutation.mutate(buyerId);
  };

  const handleFileSelect = useCallback((file: File) => {
    if (!file.name.endsWith(".json")) {
      setMessage({ type: "error", text: "Please select a JSON file" });
      return;
    }
    uploadMutation.mutate(file);
  }, [uploadMutation]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  }, [handleFileSelect]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileSelect(file);
  }, [handleFileSelect]);

  const isConfigured = health?.configured === true;
  const hasSeats = seats && seats.length > 0;

  return (
    <div className="space-y-6">
      {/* Status Message */}
      {message && (
        <div className={cn(
          "p-4 rounded-lg flex items-start justify-between",
          message.type === "success" ? "bg-green-50" : "bg-red-50"
        )}>
          <div className="flex items-start">
            {message.type === "success" ? (
              <CheckCircle className="h-5 w-5 text-green-400 mt-0.5" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-red-400 mt-0.5" />
            )}
            <p className={cn(
              "ml-3 text-sm font-medium",
              message.type === "success" ? "text-green-800" : "text-red-800"
            )}>
              {message.text}
            </p>
          </div>
          <button onClick={() => setMessage(null)} className="text-gray-400 hover:text-gray-600">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Step 1: Credentials */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className={cn(
            "w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold",
            isConfigured ? "bg-green-500 text-white" : "bg-blue-600 text-white"
          )}>
            {isConfigured ? <CheckCircle className="w-5 h-5" /> : "1"}
          </div>
          <div>
            <h3 className="text-lg font-medium text-gray-900">Google Service Account</h3>
            <p className="text-sm text-gray-500">Required to access Authorized Buyers API</p>
          </div>
        </div>

        {isConfigured ? (
          <div className="ml-11 space-y-3">
            <div className="flex items-center justify-between py-3 px-4 bg-green-50 rounded-lg border border-green-200">
              <div className="flex items-center">
                <CheckCircle className="h-5 w-5 text-green-500 mr-3" />
                <div>
                  <p className="font-medium text-green-800">Connected</p>
                  <p className="text-sm text-green-600">
                    {credentialsStatus?.client_email || "Service account configured"}
                  </p>
                </div>
              </div>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="text-sm text-green-700 hover:text-green-800 underline"
              >
                Change
              </button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,application/json"
              onChange={handleInputChange}
              className="hidden"
            />
          </div>
        ) : (
          <div className="ml-11 space-y-4">
            <div
              onClick={() => fileInputRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              className={cn(
                "border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer",
                isDragging ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-blue-400",
                uploadMutation.isPending && "opacity-50 pointer-events-none"
              )}
            >
              {uploadMutation.isPending ? (
                <>
                  <Loader2 className="h-10 w-10 text-blue-600 mx-auto mb-3 animate-spin" />
                  <p className="font-medium text-gray-700">Uploading...</p>
                </>
              ) : (
                <>
                  <FileJson className={cn("h-10 w-10 mx-auto mb-3", isDragging ? "text-blue-600" : "text-gray-400")} />
                  <p className="font-medium text-gray-700">
                    {isDragging ? "Drop file here" : "Upload Service Account JSON"}
                  </p>
                  <p className="text-sm text-gray-500 mt-1">Drag and drop or click to browse</p>
                </>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,application/json"
              onChange={handleInputChange}
              className="hidden"
            />

            <details className="border border-gray-200 rounded-lg">
              <summary className="px-4 py-3 cursor-pointer text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg">
                How to get a service account key
              </summary>
              <div className="px-4 pb-4 text-sm text-gray-600 space-y-3">
                <ol className="list-decimal list-inside space-y-2">
                  <li>Go to the <a href="https://console.cloud.google.com/iam-admin/serviceaccounts" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">GCP Service Accounts page</a></li>
                  <li>Select your project (or create one)</li>
                  <li>Click <strong>+ Create Service Account</strong></li>
                  <li>Name it (e.g., &quot;catscan-service-account&quot;)</li>
                  <li>Click <strong>Create and Continue</strong>, skip roles, click <strong>Done</strong></li>
                  <li>Click on the new service account email</li>
                  <li>Go to <strong>Keys</strong> tab → <strong>Add Key</strong> → <strong>Create new key</strong></li>
                  <li>Select <strong>JSON</strong> and click <strong>Create</strong></li>
                  <li>Upload the downloaded file above</li>
                </ol>
                <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <p className="text-sm text-yellow-800">
                    <strong>Important:</strong> Add the service account email as a user in your{" "}
                    <a href="https://authorizedbuyers.google.com" target="_blank" rel="noopener noreferrer" className="underline">
                      Authorized Buyers account
                    </a> with RTB access.
                  </p>
                </div>
              </div>
            </details>
          </div>
        )}
      </div>

      {/* Step 2: Sync Creatives */}
      <div className={cn("card p-6 transition-opacity", !isConfigured && "opacity-50")}>
        <div className="flex items-center gap-3 mb-4">
          <div className={cn(
            "w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold",
            hasSeats && seats.some((s: BuyerSeat) => s.creative_count > 0)
              ? "bg-green-500 text-white"
              : isConfigured
                ? "bg-blue-600 text-white"
                : "bg-gray-200 text-gray-500"
          )}>
            {hasSeats && seats.some((s: BuyerSeat) => s.creative_count > 0) ? <CheckCircle className="w-5 h-5" /> : "2"}
          </div>
          <div>
            <h3 className="text-lg font-medium text-gray-900">Sync Buyer Seats</h3>
            <p className="text-sm text-gray-500">Fetch creatives from your Authorized Buyers account</p>
          </div>
        </div>

        <div className="ml-11">
          {seatsLoading ? (
            <div className="py-8 flex justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          ) : hasSeats ? (
            <div className="space-y-3">
              {seats.map((seat: BuyerSeat) => (
                <div key={seat.buyer_id} className="flex items-center justify-between py-3 px-4 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium text-gray-900">{seat.display_name || `Account ${seat.buyer_id}`}</p>
                    <p className="text-sm text-gray-500">
                      {seat.creative_count} creatives
                      {seat.last_synced && ` · Last synced ${new Date(seat.last_synced).toLocaleDateString()}`}
                    </p>
                  </div>
                  <button
                    onClick={() => handleSync(seat.buyer_id)}
                    disabled={syncingId === seat.buyer_id}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium",
                      "bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                    )}
                  >
                    <RefreshCw className={cn("h-4 w-4", syncingId === seat.buyer_id && "animate-spin")} />
                    {syncingId === seat.buyer_id ? "Syncing..." : "Sync Now"}
                  </button>
                </div>
              ))}
            </div>
          ) : isConfigured ? (
            <div className="text-center py-6">
              <Users className="h-10 w-10 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">No buyer seats found</p>
              <p className="text-sm text-gray-400 mt-1">
                Make sure the service account has access to your Authorized Buyers account
              </p>
            </div>
          ) : (
            <p className="text-gray-500 py-4">Complete step 1 to sync your creatives</p>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Gmail Reports Tab
// ============================================================================

function GmailReportsTab() {
  return (
    <div className="space-y-6">
      {/* Intro */}
      <div className="card p-6">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-blue-100 rounded-lg">
            <Mail className="h-6 w-6 text-blue-600" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-medium text-gray-900">Auto-fetch Reports from Gmail</h3>
            <p className="text-sm text-gray-600 mt-1">
              Google Authorized Buyers can email scheduled reports directly to you.
              Configure Gmail access to automatically import these reports.
            </p>
          </div>
        </div>
      </div>

      {/* How it works */}
      <div className="card p-6">
        <h4 className="font-medium text-gray-900 mb-4">How it works</h4>
        <div className="grid md:grid-cols-3 gap-4">
          <div className="p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold">1</span>
              <span className="font-medium text-gray-900">Schedule Reports</span>
            </div>
            <p className="text-sm text-gray-600">
              In Authorized Buyers, create scheduled reports with email delivery to your Gmail.
            </p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold">2</span>
              <span className="font-medium text-gray-900">Connect Gmail</span>
            </div>
            <p className="text-sm text-gray-600">
              Grant Cat-Scan read-only access to your Gmail to fetch report attachments.
            </p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold">3</span>
              <span className="font-medium text-gray-900">Auto Import</span>
            </div>
            <p className="text-sm text-gray-600">
              Cat-Scan checks your inbox daily and imports new CSV attachments automatically.
            </p>
          </div>
        </div>
      </div>

      {/* Gmail Connection Status */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h4 className="font-medium text-gray-900">Gmail Connection</h4>
          <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs font-medium rounded">Not configured</span>
        </div>

        <div className="p-6 border-2 border-dashed border-gray-200 rounded-lg text-center">
          <Inbox className="h-10 w-10 text-gray-300 mx-auto mb-3" />
          <h5 className="font-medium text-gray-700 mb-2">Gmail Integration Coming Soon</h5>
          <p className="text-sm text-gray-500 mb-4 max-w-md mx-auto">
            Automatic Gmail report fetching is in development. For now, use Manual Import
            to upload your scheduled report CSVs.
          </p>
          <button
            disabled
            className="px-4 py-2 bg-gray-100 text-gray-400 rounded-lg cursor-not-allowed"
          >
            Connect Gmail Account
          </button>
        </div>
      </div>

      {/* Expected Reports */}
      <div className="card p-6">
        <h4 className="font-medium text-gray-900 mb-4">Reports to Schedule in Authorized Buyers</h4>
        <p className="text-sm text-gray-600 mb-4">
          Create these scheduled reports in Google Authorized Buyers and set them to email you daily.
          Name them exactly as shown to help Cat-Scan identify them.
        </p>

        <div className="space-y-4">
          {/* Report 1 */}
          <ReportSpecCard
            reportNumber={1}
            title="Billing Config Performance"
            filename="catscan-billing-config"
            dimensions={["Day", "Billing ID", "Creative ID", "Creative size", "Creative format"]}
            metrics={["Reached queries", "Impressions"]}
            purpose="Shows waste per pretargeting config"
            color="blue"
          />

          {/* Report 2 */}
          <ReportSpecCard
            reportNumber={2}
            title="Creative Bidding Activity"
            filename="catscan-creative-bids"
            dimensions={["Day", "Creative ID", "Country"]}
            metrics={["Bids", "Bids in auction", "Reached queries"]}
            purpose="Shows bidding activity per creative by geo"
            color="purple"
          />

          {/* Report 3 */}
          <ReportSpecCard
            reportNumber={3}
            title="Publisher Performance"
            filename="catscan-publisher-perf"
            dimensions={["Publisher ID", "Publisher name"]}
            metrics={["Bid requests", "Reached queries", "Bids", "Successful responses", "Impressions"]}
            purpose="Shows publisher-level funnel metrics"
            color="green"
            optional
          />
        </div>

        <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="flex items-start gap-2">
            <Calendar className="h-5 w-5 text-amber-600 mt-0.5" />
            <div className="text-sm text-amber-800">
              <strong>Schedule Settings for All Reports:</strong>
              <ul className="mt-2 space-y-1">
                <li>• Date range: <strong>Yesterday</strong></li>
                <li>• Schedule: <strong>Daily</strong></li>
                <li>• File format: <strong>CSV</strong></li>
                <li>• Delivery: <strong>Email</strong> (to your Gmail)</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ReportSpecCard({
  reportNumber,
  title,
  filename,
  dimensions,
  metrics,
  purpose,
  color,
  optional = false,
}: {
  reportNumber: number;
  title: string;
  filename: string;
  dimensions: string[];
  metrics: string[];
  purpose: string;
  color: "blue" | "purple" | "green";
  optional?: boolean;
}) {
  const colorClasses = {
    blue: { bg: "bg-blue-100", text: "text-blue-800", badge: "bg-blue-100 text-blue-800" },
    purple: { bg: "bg-purple-100", text: "text-purple-800", badge: "bg-purple-100 text-purple-800" },
    green: { bg: "bg-green-100", text: "text-green-800", badge: "bg-green-100 text-green-800" },
  }[color];

  return (
    <div className={cn("border border-gray-200 rounded-lg p-4", optional && "bg-gray-50")}>
      <div className="flex items-center gap-2 mb-3">
        <span className={cn("text-xs font-bold px-2 py-1 rounded", colorClasses.badge)}>
          Report {reportNumber}
        </span>
        <h5 className="font-semibold text-gray-900">{title}</h5>
        {optional && <span className="text-xs text-gray-500">(optional)</span>}
      </div>
      <p className="text-sm text-gray-600 mb-3">{purpose}</p>

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Dimensions (in order)</p>
          <ol className="space-y-1 text-sm text-gray-700 list-decimal list-inside">
            {dimensions.map((dim) => (
              <li key={dim}>{dim}</li>
            ))}
          </ol>
        </div>
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Metrics</p>
          <ul className="space-y-1 text-sm text-gray-700">
            {metrics.map((metric) => (
              <li key={metric} className="flex items-center gap-2">
                <span className="text-green-600">✓</span> {metric}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-200">
        <p className="text-xs text-gray-500">
          Save as: <code className="bg-gray-100 px-1 rounded">{filename}.csv</code>
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// Manual Import Tab
// ============================================================================

type ImportStep = "upload" | "preview" | "importing" | "success" | "error";
const CHUNKED_UPLOAD_THRESHOLD = 5 * 1024 * 1024;

function ManualImportTab() {
  const abortControllerRef = useRef<AbortController | null>(null);
  const [step, setStep] = useState<ImportStep>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [validationResult, setValidationResult] = useState<ExtendedValidationResult | null>(null);
  const [importResult, setImportResult] = useState<ImportResponse | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isLargeFile, setIsLargeFile] = useState(false);
  const [chunkedProgress, setChunkedProgress] = useState<UploadProgress | null>(null);
  const [seatInfo, setSeatInfo] = useState<SeatInfo | null>(null);
  const [previewData, setPreviewData] = useState<{
    headers: string[];
    rows: Record<string, string>[];
    columnMappings: Record<string, string>;
    estimatedRowCount: number;
  } | null>(null);

  const handleFileSelect = async (selectedFile: File) => {
    setFile(selectedFile);
    setStep("preview");
    setIsLargeFile(selectedFile.size > CHUNKED_UPLOAD_THRESHOLD);

    try {
      if (selectedFile.size > CHUNKED_UPLOAD_THRESHOLD) {
        const preview = await previewCSV(selectedFile, 10);
        setPreviewData(preview);
        const seat = extractSeatFromPreview(preview.rows);
        setSeatInfo(seat);
        const hasRequiredCols = !!(preview.columnMappings.creative_id && preview.columnMappings.date);
        setValidationResult({
          valid: hasRequiredCols,
          errors: hasRequiredCols ? [] : [{
            row: 0,
            field: "columns",
            error: `Missing required columns. Detected: ${Object.entries(preview.columnMappings)
              .filter(([, v]) => v)
              .map(([k, v]) => `${v} → ${k}`)
              .join(", ") || "none"}`,
            value: null,
          }],
          warnings: [],
          anomalies: [],
          rowCount: preview.estimatedRowCount,
          data: [],
          detectedColumns: preview.columnMappings,
          hasHourlyData: preview.headers.some(h => h.toLowerCase().includes("hour")),
        });
      } else {
        const parseResult = await parseCSV(selectedFile);
        const validation = validatePerformanceCSV(parseResult);
        setValidationResult(validation);
      }
    } catch (error) {
      console.error("CSV parsing error:", error);
      setValidationResult({
        valid: false,
        errors: [{ row: 0, field: "file", error: "Failed to parse CSV file.", value: null }],
        warnings: [],
        anomalies: [],
        rowCount: 0,
        data: [],
      });
    }
  };

  const handleChunkedProgress = useCallback((progress: UploadProgress) => {
    setChunkedProgress(progress);
    setUploadProgress(progress.progress);
  }, []);

  const handleImport = async () => {
    if (!file) return;
    setStep("importing");
    setUploadProgress(0);
    setChunkedProgress(null);
    abortControllerRef.current = new AbortController();

    try {
      if (isLargeFile) {
        const result = await uploadChunkedCSV(file, {
          onProgress: handleChunkedProgress,
          signal: abortControllerRef.current.signal,
        });
        setImportResult({
          success: result.success,
          imported: result.imported,
          duplicates: result.skipped,
          error_details: result.errors.map(e => ({ row: e.row || 0, field: e.field || "unknown", error: e.error, value: e.value })),
          date_range: result.dateRange,
          total_spend: result.totalSpend,
        });
        setStep(result.success || result.imported > 0 ? "success" : "error");
      } else {
        const result = await importPerformanceData(file, (progress) => setUploadProgress(progress));
        setImportResult(result);
        setStep("success");
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Import failed";
      if (errorMessage === "Upload cancelled") {
        setStep("upload");
        return;
      }
      setImportResult({
        success: false,
        imported: chunkedProgress?.rowsImported || 0,
        error: errorMessage,
      });
      setStep("error");
    } finally {
      abortControllerRef.current = null;
    }
  };

  const handleCancel = () => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    resetForm();
  };

  const resetForm = () => {
    setFile(null);
    setValidationResult(null);
    setImportResult(null);
    setUploadProgress(0);
    setIsLargeFile(false);
    setChunkedProgress(null);
    setPreviewData(null);
    setSeatInfo(null);
    setStep("upload");
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-6">
      {step === "upload" && (
        <>
          <div className="card p-6">
            <ImportDropzone onFileSelect={handleFileSelect} maxSizeMB={500} />
          </div>

          <details className="card">
            <summary className="p-4 cursor-pointer hover:bg-gray-50 font-medium text-gray-900 flex items-center justify-between">
              <span>Expected CSV Format</span>
              <ChevronDown className="h-5 w-5 text-gray-500" />
            </summary>
            <div className="p-4 pt-0 border-t border-gray-200">
              <p className="text-sm text-gray-600 mb-4">
                Upload one of the three report types. Cat-Scan auto-detects the report type from column headers.
              </p>
              <div className="space-y-3">
                <ReportSpecCard
                  reportNumber={1}
                  title="Billing Config Performance"
                  filename="catscan-billing-config"
                  dimensions={["Day", "Billing ID", "Creative ID", "Creative size", "Creative format"]}
                  metrics={["Reached queries", "Impressions"]}
                  purpose="Shows waste per pretargeting config"
                  color="blue"
                />
                <ReportSpecCard
                  reportNumber={2}
                  title="Creative Bidding Activity"
                  filename="catscan-creative-bids"
                  dimensions={["Day", "Creative ID", "Country"]}
                  metrics={["Bids", "Bids in auction", "Reached queries"]}
                  purpose="Shows bidding activity per creative by geo"
                  color="purple"
                />
              </div>
            </div>
          </details>
        </>
      )}

      {step === "preview" && validationResult && (
        <div className="space-y-4">
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">{file?.name}</p>
                <p className="text-sm text-gray-600">
                  {formatFileSize(file?.size || 0)} · {validationResult.rowCount.toLocaleString()} rows
                  {isLargeFile && " (estimated)"}
                </p>
              </div>
              <button onClick={resetForm} className="text-sm text-gray-600 hover:text-gray-800">Remove</button>
            </div>
          </div>

          {seatInfo && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-start gap-2">
                <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                <div>
                  <p className="font-medium text-green-900">Seat detected</p>
                  <p className="text-sm text-green-800 mt-1">{formatSeatInfo(seatInfo)}</p>
                </div>
              </div>
            </div>
          )}

          {!validationResult.valid && <ValidationErrors errors={validationResult.errors} />}

          {validationResult.valid && validationResult.detectedColumns && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-start gap-2">
                <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium text-green-900">Columns detected</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {Object.entries(validationResult.detectedColumns)
                      .filter(([, v]) => v)
                      .map(([key, value]) => (
                        <span key={key} className="inline-flex items-center px-2 py-1 bg-green-100 text-green-800 text-xs rounded">
                          <span className="font-mono">{value}</span>
                          <span className="mx-1 text-green-600">→</span>
                          <span>{key}</span>
                        </span>
                      ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {validationResult.valid && (
            <div className="flex gap-3 justify-end">
              <button onClick={resetForm} className="btn-secondary">Cancel</button>
              <button onClick={handleImport} className="btn-primary">
                Import {validationResult.rowCount.toLocaleString()} Rows
                <ArrowRight className="ml-1 h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      )}

      {step === "importing" && (
        <div className="space-y-6">
          <ImportProgress progress={uploadProgress} />
          {isLargeFile && chunkedProgress && (
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-gray-900">{chunkedProgress.rowsProcessed.toLocaleString()}</p>
                  <p className="text-sm text-gray-600">Rows Processed</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-green-600">{chunkedProgress.rowsImported.toLocaleString()}</p>
                  <p className="text-sm text-gray-600">Imported</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-500">{chunkedProgress.batchesSent}</p>
                  <p className="text-sm text-gray-600">Batches</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-700">{chunkedProgress.currentPhase}</p>
                  <p className="text-xs text-gray-500 mt-1">Phase</p>
                </div>
              </div>
            </div>
          )}
          {isLargeFile && (
            <div className="flex justify-center">
              <button onClick={handleCancel} className="btn-secondary text-red-600 hover:text-red-700">
                Cancel Import
              </button>
            </div>
          )}
        </div>
      )}

      {step === "success" && importResult && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <CheckCircle className="h-6 w-6 text-green-600 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-green-900 text-lg mb-4">Import Successful</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
                <div>
                  <p className="text-gray-500 text-sm">Rows imported</p>
                  <p className="font-bold text-xl text-green-700">{(importResult.imported ?? 0).toLocaleString()}</p>
                </div>
                {importResult.duplicates !== undefined && importResult.duplicates > 0 && (
                  <div>
                    <p className="text-gray-500 text-sm">Duplicates skipped</p>
                    <p className="font-medium text-gray-600">{importResult.duplicates.toLocaleString()}</p>
                  </div>
                )}
                {importResult.date_range && (
                  <div>
                    <p className="text-gray-500 text-sm">Date range</p>
                    <p className="font-medium text-gray-700">{importResult.date_range.start} → {importResult.date_range.end}</p>
                  </div>
                )}
              </div>
              <div className="flex gap-3">
                <a href="/waste-analysis" className="btn-primary">
                  View Waste Analysis <ArrowRight className="ml-1 h-4 w-4" />
                </a>
                <button onClick={resetForm} className="btn-secondary">Import More</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {step === "error" && importResult && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <XCircle className="h-6 w-6 text-red-600 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-red-900 text-lg mb-2">Import Failed</h3>
              {importResult.error && <p className="text-red-800">{importResult.error}</p>}
              {importResult.error_details && importResult.error_details.length > 0 && (
                <div className="mt-4"><ValidationErrors errors={importResult.error_details} /></div>
              )}
              <div className="mt-4">
                <button onClick={resetForm} className="btn-primary">Try Again</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// System Tab
// ============================================================================

function SystemTab() {
  const queryClient = useQueryClient();
  const [batchLimit, setBatchLimit] = useState(50);
  const [forceRetry, setForceRetry] = useState(false);

  const { data: health } = useQuery({ queryKey: ["health"], queryFn: getHealth });
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: getStats });
  const { data: thumbnailStatus, isLoading: thumbnailStatusLoading } = useQuery({
    queryKey: ["thumbnailStatus"],
    queryFn: getThumbnailStatus,
  });
  const { data: systemStatus, isLoading: systemStatusLoading } = useQuery({
    queryKey: ["systemStatus"],
    queryFn: getSystemStatus,
  });

  const generateMutation = useMutation({
    mutationFn: () => generateThumbnailsBatch({ limit: batchLimit, force: forceRetry }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["thumbnailStatus"] }),
  });

  return (
    <div className="space-y-6">
      {/* API Status */}
      <div className="card p-6">
        <div className="flex items-center mb-4">
          <Server className="h-5 w-5 text-gray-400 mr-2" />
          <h3 className="text-lg font-medium text-gray-900">API Status</h3>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">Status</p>
            <p className="font-medium text-green-600 flex items-center gap-1">
              <CheckCircle className="h-4 w-4" /> {health?.status}
            </p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">Version</p>
            <p className="font-medium text-gray-900">{health?.version}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">Configured</p>
            <p className={cn("font-medium", health?.configured ? "text-green-600" : "text-red-600")}>
              {health?.configured ? "Yes" : "No"}
            </p>
          </div>
        </div>
      </div>

      {/* System Status */}
      <div className="card p-6">
        <div className="flex items-center mb-4">
          <Cpu className="h-5 w-5 text-gray-400 mr-2" />
          <h3 className="text-lg font-medium text-gray-900">System Status</h3>
        </div>
        {systemStatusLoading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
          </div>
        ) : systemStatus ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">Python</p>
              <p className="font-medium text-gray-900">{systemStatus.python_version}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">ffmpeg</p>
              <p className={cn("font-medium", systemStatus.ffmpeg_available ? "text-green-600" : "text-yellow-600")}>
                {systemStatus.ffmpeg_available ? "Installed" : "Not installed"}
              </p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">Disk Space</p>
              <p className="font-medium text-gray-900">{systemStatus.disk_space_gb} GB free</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">Database</p>
              <p className="font-medium text-gray-900">{systemStatus.database_size_mb} MB</p>
            </div>
          </div>
        ) : null}
      </div>

      {/* Database */}
      <div className="card p-6">
        <div className="flex items-center mb-4">
          <Database className="h-5 w-5 text-gray-400 mr-2" />
          <h3 className="text-lg font-medium text-gray-900">Database</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">Creatives</p>
            <p className="font-bold text-xl text-gray-900">{stats?.creative_count ?? 0}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">Campaigns</p>
            <p className="font-bold text-xl text-gray-900">{stats?.campaign_count ?? 0}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">Clusters</p>
            <p className="font-bold text-xl text-gray-900">{stats?.cluster_count ?? 0}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">Path</p>
            <p className="text-xs font-mono text-gray-600 truncate" title={stats?.db_path}>{stats?.db_path || "N/A"}</p>
          </div>
        </div>
      </div>

      {/* Video Thumbnails */}
      <div className="card p-6">
        <div className="flex items-center mb-4">
          <Video className="h-5 w-5 text-gray-400 mr-2" />
          <h3 className="text-lg font-medium text-gray-900">Video Thumbnails</h3>
        </div>
        {thumbnailStatusLoading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
          </div>
        ) : thumbnailStatus ? (
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <div className="text-xl font-bold text-gray-900">{thumbnailStatus.total_videos}</div>
                <div className="text-xs text-gray-500">Total Videos</div>
              </div>
              <div className="text-center p-3 bg-green-50 rounded-lg">
                <div className="text-xl font-bold text-green-600">{thumbnailStatus.with_thumbnails}</div>
                <div className="text-xs text-gray-500">With Thumbnails</div>
              </div>
              <div className="text-center p-3 bg-yellow-50 rounded-lg">
                <div className="text-xl font-bold text-yellow-600">{thumbnailStatus.pending}</div>
                <div className="text-xs text-gray-500">Pending</div>
              </div>
              <div className="text-center p-3 bg-red-50 rounded-lg">
                <div className="text-xl font-bold text-red-600">{thumbnailStatus.failed}</div>
                <div className="text-xs text-gray-500">Failed</div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Coverage</span>
                <span className="font-medium">{thumbnailStatus.coverage_percent}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div className="bg-green-500 h-2 rounded-full transition-all" style={{ width: `${thumbnailStatus.coverage_percent}%` }} />
              </div>
            </div>

            {thumbnailStatus.ffmpeg_available && thumbnailStatus.pending > 0 && (
              <div className="pt-4 border-t border-gray-100">
                <div className="flex items-center gap-4 mb-3">
                  <label className="text-sm text-gray-600">
                    Batch size:
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
                    Retry failed
                  </label>
                </div>
                <button
                  onClick={() => generateMutation.mutate()}
                  disabled={generateMutation.isPending}
                  className={cn("btn-primary w-full", generateMutation.isPending && "opacity-50")}
                >
                  {generateMutation.isPending ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Generating...</>
                  ) : (
                    <><Image className="h-4 w-4 mr-2" />Generate Thumbnails</>
                  )}
                </button>
              </div>
            )}

            {!thumbnailStatus.ffmpeg_available && (
              <div className="p-3 bg-yellow-50 rounded-lg text-sm text-yellow-800">
                <strong>ffmpeg not found.</strong> Install to generate video thumbnails:
                <code className="block mt-1 bg-yellow-100 p-2 rounded font-mono text-xs">sudo apt install ffmpeg</code>
              </div>
            )}
          </div>
        ) : null}
      </div>

      {/* Management Links */}
      <div className="card p-6">
        <div className="flex items-center mb-4">
          <Users className="h-5 w-5 text-gray-400 mr-2" />
          <h3 className="text-lg font-medium text-gray-900">Manage</h3>
        </div>
        <div className="space-y-2">
          <Link href="/settings/seats" className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 border border-gray-200">
            <div className="flex items-center">
              <Users className="h-5 w-5 text-blue-600 mr-3" />
              <div>
                <div className="font-medium text-gray-900">Buyer Seats</div>
                <div className="text-sm text-gray-500">Manage seat display names</div>
              </div>
            </div>
            <ChevronRight className="h-5 w-5 text-gray-400" />
          </Link>
          <Link href="/settings/retention" className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 border border-gray-200">
            <div className="flex items-center">
              <Clock className="h-5 w-5 text-blue-600 mr-3" />
              <div>
                <div className="font-medium text-gray-900">Data Retention</div>
                <div className="text-sm text-gray-500">Configure cleanup schedules</div>
              </div>
            </div>
            <ChevronRight className="h-5 w-5 text-gray-400" />
          </Link>
        </div>
      </div>
    </div>
  );
}
