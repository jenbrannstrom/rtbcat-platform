"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  CheckCircle,
  AlertCircle,
  Loader2,
  RefreshCw,
  Shield,
  Users,
  FileJson,
  X,
  ArrowRight,
  Database,
} from "lucide-react";
import { getHealth, getSeats, syncSeat, getCredentialsStatus, uploadCredentials, discoverSeats, getSystemStatus } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { BuyerSeat } from "@/types/api";

type SetupStep = 1 | 2 | 3;

function StepIndicator({ currentStep, totalSteps }: { currentStep: SetupStep; totalSteps: number }) {
  return (
    <div className="flex items-center justify-center mb-8">
      {Array.from({ length: totalSteps }, (_, i) => {
        const step = i + 1;
        const isComplete = step < currentStep;
        const isCurrent = step === currentStep;
        return (
          <div key={step} className="flex items-center">
            <div
              className={cn(
                "w-10 h-10 rounded-full flex items-center justify-center font-semibold text-sm transition-colors",
                isComplete && "bg-green-500 text-white",
                isCurrent && "bg-primary-600 text-white",
                !isComplete && !isCurrent && "bg-gray-200 text-gray-500"
              )}
            >
              {isComplete ? <CheckCircle className="w-5 h-5" /> : step}
            </div>
            {step < totalSteps && (
              <div
                className={cn(
                  "w-16 h-1 mx-2",
                  step < currentStep ? "bg-green-500" : "bg-gray-200"
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function ConnectPage() {
  const router = useRouter();
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  // Check if API is configured
  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  // Get credentials details
  const { data: credentialsStatus } = useQuery({
    queryKey: ["credentialsStatus"],
    queryFn: getCredentialsStatus,
    enabled: health?.configured === true,
  });

  // Get seats if configured
  const { data: seats, isLoading: seatsLoading } = useQuery({
    queryKey: ["seats"],
    queryFn: () => getSeats({ active_only: false }),
    enabled: health?.configured === true,
  });

  // Check system requirements
  const { data: systemStatus } = useQuery({
    queryKey: ["systemStatus"],
    queryFn: getSystemStatus,
  });

  // Track if we've attempted discovery
  const [discoveryAttempted, setDiscoveryAttempted] = useState(false);

  // Discover seats mutation
  const discoverMutation = useMutation({
    mutationFn: (bidderId: string) => discoverSeats({ bidder_id: bidderId }),
    onSuccess: (data) => {
      setMessage({
        type: "success",
        text: `Discovered ${data.seats_discovered} buyer seat(s)`
      });
      queryClient.invalidateQueries({ queryKey: ["seats"] });
      setTimeout(() => setMessage(null), 5000);
    },
    onError: (error) => {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Failed to discover seats"
      });
      setTimeout(() => setMessage(null), 5000);
    },
  });

  // Auto-discover seats when credentials are configured but no seats found
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

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const contents = await file.text();

      // Validate JSON structure locally first
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

      // Upload to backend
      return uploadCredentials(contents);
    },
    onSuccess: (data) => {
      setMessage({
        type: "success",
        text: `Connected as ${data.client_email}`
      });
      queryClient.invalidateQueries({ queryKey: ["health"] });
      queryClient.invalidateQueries({ queryKey: ["credentialsStatus"] });
      queryClient.invalidateQueries({ queryKey: ["seats"] });
      refetchHealth();
    },
    onError: (error) => {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Upload failed"
      });
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
    if (file) {
      handleFileSelect(file);
    }
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
    if (file) {
      handleFileSelect(file);
    }
  }, [handleFileSelect]);

  if (healthLoading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  const isConfigured = health?.configured === true;
  const hasSeats = seats && seats.length > 0;
  const hasSyncedCreatives = seats?.some((s: BuyerSeat) => s.creative_count > 0);

  // Determine current step
  let currentStep: SetupStep = 1;
  if (isConfigured) currentStep = 2;
  if (isConfigured && hasSyncedCreatives) currentStep = 3;

  const stepTitles = [
    "Upload Credentials",
    "Sync Creatives",
    "Ready to Go"
  ];

  return (
    <div className="p-8 max-w-3xl mx-auto">
      {/* Header */}
      <div className="text-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          {currentStep === 3 ? "Setup Complete!" : "Set Up Cat-Scan"}
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          {currentStep === 3
            ? "Your account is connected and ready to analyze"
            : `Step ${currentStep} of 3: ${stepTitles[currentStep - 1]}`}
        </p>
      </div>

      {/* Step Indicator */}
      <StepIndicator currentStep={currentStep} totalSteps={3} />

      {/* Requirements Notice */}
      {systemStatus && !systemStatus.ffmpeg_available && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <h3 className="font-medium text-yellow-800 mb-1">Optional: Install ffmpeg</h3>
          <p className="text-sm text-yellow-700 mb-2">
            ffmpeg is required for video thumbnail generation. Without it, video creatives will show placeholder icons instead of preview frames.
          </p>
          <code className="block bg-yellow-100 p-2 rounded text-sm font-mono text-yellow-900">
            sudo apt install ffmpeg
          </code>
        </div>
      )}

      {/* Status Message */}
      {message && (
        <div
          className={cn(
            "mb-6 p-4 rounded-lg flex items-start justify-between",
            message.type === "success" ? "bg-green-50" : "bg-red-50"
          )}
        >
          <div className="flex items-start">
            {message.type === "success" ? (
              <CheckCircle className="h-5 w-5 text-green-400 mt-0.5" />
            ) : (
              <AlertCircle className="h-5 w-5 text-red-400 mt-0.5" />
            )}
            <p className={cn(
              "ml-3 text-sm font-medium",
              message.type === "success" ? "text-green-800" : "text-red-800"
            )}>
              {message.text}
            </p>
          </div>
          <button
            onClick={() => setMessage(null)}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="space-y-6">
        {/* Step 1: Credentials */}
        <div className={cn(
          "card p-6 transition-opacity",
          currentStep > 1 && "opacity-60"
        )}>
          <div className="flex items-center mb-4">
            <div className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center mr-3 text-sm font-semibold",
              currentStep > 1 ? "bg-green-500 text-white" : "bg-primary-600 text-white"
            )}>
              {currentStep > 1 ? <CheckCircle className="w-5 h-5" /> : "1"}
            </div>
            <div className="flex items-center">
              <Shield className="h-5 w-5 text-gray-400 mr-2" />
              <h2 className="text-lg font-medium text-gray-900">Google Credentials</h2>
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
              {/* Upload UI */}
              <div
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                className={cn(
                  "border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer",
                  isDragging
                    ? "border-primary-500 bg-primary-50"
                    : "border-gray-300 hover:border-primary-400",
                  uploadMutation.isPending && "opacity-50 pointer-events-none"
                )}
              >
                {uploadMutation.isPending ? (
                  <>
                    <Loader2 className="h-10 w-10 text-primary-600 mx-auto mb-3 animate-spin" />
                    <p className="font-medium text-gray-700">Uploading...</p>
                  </>
                ) : (
                  <>
                    <FileJson className={cn(
                      "h-10 w-10 mx-auto mb-3",
                      isDragging ? "text-primary-600" : "text-gray-400"
                    )} />
                    <p className="font-medium text-gray-700">
                      {isDragging ? "Drop file here" : "Upload Service Account JSON"}
                    </p>
                    <p className="text-sm text-gray-500 mt-1">
                      Drag and drop or click to browse
                    </p>
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

              {/* Collapsible Help Section */}
              <details className="border border-gray-200 rounded-lg">
                <summary className="px-4 py-3 cursor-pointer text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg">
                  How to get a service account key
                </summary>
                <div className="px-4 pb-4 text-sm text-gray-600 space-y-3">
                  <ol className="list-decimal list-inside space-y-2">
                    <li>
                      Go to the{" "}
                      <a
                        href="https://console.cloud.google.com/iam-admin/serviceaccounts"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary-600 underline"
                      >
                        GCP Service Accounts page
                      </a>
                    </li>
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
                      <strong>Important:</strong> You also need to add the service account email as a user in your{" "}
                      <a
                        href="https://authorizedbuyers.google.com"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="underline"
                      >
                        Authorized Buyers account
                      </a>
                      {" "}with RTB access.
                    </p>
                  </div>
                </div>
              </details>
            </div>
          )}
        </div>

        {/* Step 2: Sync Creatives */}
        <div className={cn(
          "card p-6 transition-opacity",
          currentStep < 2 && "opacity-40 pointer-events-none",
          currentStep > 2 && "opacity-60"
        )}>
          <div className="flex items-center mb-4">
            <div className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center mr-3 text-sm font-semibold",
              currentStep > 2 ? "bg-green-500 text-white" :
              currentStep === 2 ? "bg-primary-600 text-white" :
              "bg-gray-200 text-gray-500"
            )}>
              {currentStep > 2 ? <CheckCircle className="w-5 h-5" /> : "2"}
            </div>
            <div className="flex items-center">
              <Database className="h-5 w-5 text-gray-400 mr-2" />
              <h2 className="text-lg font-medium text-gray-900">Sync Creatives</h2>
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
                  <div
                    key={seat.buyer_id}
                    className="flex items-center justify-between py-3 px-4 bg-gray-50 rounded-lg"
                  >
                    <div>
                      <p className="font-medium text-gray-900">
                        {seat.display_name || `Account ${seat.buyer_id}`}
                      </p>
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
                        "bg-primary-600 text-white hover:bg-primary-700",
                        "disabled:opacity-50"
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

        {/* Step 3: Ready / Complete */}
        <div className={cn(
          "card p-6 transition-opacity",
          currentStep < 3 && "opacity-40"
        )}>
          <div className="flex items-center mb-4">
            <div className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center mr-3 text-sm font-semibold",
              currentStep === 3 ? "bg-green-500 text-white" : "bg-gray-200 text-gray-500"
            )}>
              {currentStep === 3 ? <CheckCircle className="w-5 h-5" /> : "3"}
            </div>
            <h2 className="text-lg font-medium text-gray-900">Ready to Analyze</h2>
          </div>

          <div className="ml-11">
            {currentStep === 3 ? (
              <div className="space-y-4">
                <p className="text-gray-600">
                  Your account is set up and creatives are synced. You can now:
                </p>
                <ul className="text-sm text-gray-600 space-y-2 ml-4">
                  <li>• View creative status and approvals</li>
                  <li>• Import RTB performance data</li>
                  <li>• Analyze QPS waste and optimization opportunities</li>
                </ul>
                <button
                  onClick={() => router.push("/")}
                  className="mt-4 flex items-center gap-2 px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium"
                >
                  Go to Dashboard
                  <ArrowRight className="h-5 w-5" />
                </button>
              </div>
            ) : (
              <p className="text-gray-500 py-4">Complete steps 1 and 2 to continue</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
