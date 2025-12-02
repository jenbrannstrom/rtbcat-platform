"use client";

import { useState, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle,
  AlertCircle,
  Loader2,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Shield,
  Users,
  Upload,
  FileJson,
  X,
} from "lucide-react";
import { getHealth, getSeats, syncSeat, getCredentialsStatus, uploadCredentials } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { BuyerSeat } from "@/types/api";

export default function ConnectPage() {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [filterQuery, setFilterQuery] = useState("");
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
    mutationFn: (buyerId: string) => syncSeat(buyerId, filterQuery || undefined),
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

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Connect to Google Authorized Buyers</h1>
        <p className="mt-1 text-sm text-gray-500">
          Link your account to sync creatives and analyze performance
        </p>
      </div>

      <div className="max-w-2xl space-y-6">
        {/* Status Message */}
        {message && (
          <div
            className={cn(
              "p-4 rounded-lg flex items-start justify-between",
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

        {/* Credentials Section */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Shield className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">Google Credentials</h2>
          </div>

          {isConfigured ? (
            <div className="space-y-4">
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
                  Change Credentials
                </button>
              </div>
              {credentialsStatus?.project_id && (
                <p className="text-xs text-gray-500">
                  Project: <code className="bg-gray-100 px-1 py-0.5 rounded">{credentialsStatus.project_id}</code>
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between py-3 px-4 bg-yellow-50 rounded-lg border border-yellow-200">
                <div className="flex items-center">
                  <AlertCircle className="h-5 w-5 text-yellow-500 mr-3" />
                  <div>
                    <p className="font-medium text-yellow-800">Not Connected</p>
                    <p className="text-sm text-yellow-600">Upload your Google service account credentials</p>
                  </div>
                </div>
              </div>

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
                    <p className="text-xs text-gray-400 mt-3">
                      See <a href="/docs/SETUP_GUIDE.md" className="text-primary-600 underline" onClick={(e) => e.stopPropagation()}>Setup Guide</a> for instructions
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

              <p className="text-xs text-gray-500">
                Or configure via CLI: <code className="bg-gray-100 px-1 py-0.5 rounded">python main.py configure</code>
              </p>

              {/* Collapsible Help Section */}
              <details className="mt-4 border border-gray-200 rounded-lg">
                <summary className="px-4 py-3 cursor-pointer text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg">
                  How to get a JSON key
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
                    <li>Click <strong>Create and Continue</strong></li>
                    <li>Skip the optional roles, click <strong>Done</strong></li>
                    <li>Click on the new service account email</li>
                    <li>Go to <strong>Keys</strong> tab → <strong>Add Key</strong> → <strong>Create new key</strong></li>
                    <li>Select <strong>JSON</strong> and click <strong>Create</strong></li>
                    <li>Upload the downloaded file here</li>
                  </ol>
                  <p className="text-xs text-gray-500 mt-3">
                    Note: You&apos;ll also need to enable the Authorized Buyers API and grant RTB access to the service account email in your Authorized Buyers account.
                  </p>
                </div>
              </details>
            </div>
          )}

          {/* Hidden file input for reconfigure */}
          {isConfigured && (
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,application/json"
              onChange={handleInputChange}
              className="hidden"
            />
          )}
        </div>

        {/* Accounts Section - Only show when configured */}
        {isConfigured && (
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center">
                <Users className="h-5 w-5 text-gray-400 mr-2" />
                <h2 className="text-lg font-medium text-gray-900">Connected Accounts</h2>
              </div>
              <span className="text-sm text-gray-500">
                {seats?.length || 0} seat{seats?.length !== 1 ? "s" : ""}
              </span>
            </div>

            {seatsLoading ? (
              <div className="py-8 flex justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
              </div>
            ) : seats && seats.length > 0 ? (
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
                        "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium",
                        "bg-primary-600 text-white hover:bg-primary-700",
                        "disabled:opacity-50"
                      )}
                    >
                      <RefreshCw className={cn("h-4 w-4", syncingId === seat.buyer_id && "animate-spin")} />
                      {syncingId === seat.buyer_id ? "Syncing..." : "Sync"}
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Users className="h-10 w-10 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500">No seats discovered yet</p>
                <p className="text-sm text-gray-400 mt-1">
                  Go to <a href="/settings/seats" className="text-primary-600 underline">Settings → Seats</a> to discover accounts
                </p>
              </div>
            )}

            {/* Add Another Account - Future Feature */}
            <div className="mt-4 pt-4 border-t border-gray-100">
              <button
                type="button"
                disabled
                className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-gray-400 bg-gray-50 border border-dashed border-gray-300 rounded-lg cursor-not-allowed"
                title="Multi-account support coming soon"
              >
                <span className="text-lg">+</span>
                Add Another Account
              </button>
              <p className="text-xs text-gray-400 text-center mt-2">
                Multi-account support coming soon
              </p>
            </div>
          </div>
        )}

        {/* Advanced Options - Collapsible */}
        {isConfigured && (
          <div className="card overflow-hidden">
            <button
              onClick={() => setAdvancedOpen(!advancedOpen)}
              className="w-full flex items-center justify-between p-4 text-left hover:bg-gray-50 transition-colors"
            >
              <span className="font-medium text-gray-700">Advanced Options</span>
              {advancedOpen ? (
                <ChevronDown className="h-5 w-5 text-gray-400" />
              ) : (
                <ChevronRight className="h-5 w-5 text-gray-400" />
              )}
            </button>

            {advancedOpen && (
              <div className="px-4 pb-4 border-t border-gray-100 pt-4 space-y-4">
                <div>
                  <label
                    htmlFor="filterQuery"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Filter Query
                  </label>
                  <input
                    id="filterQuery"
                    type="text"
                    value={filterQuery}
                    onChange={(e) => setFilterQuery(e.target.value)}
                    placeholder="creativeServingDecision.networkPolicyCompliance.status=APPROVED"
                    className="input"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    API filter string applied when syncing (optional)
                  </p>
                </div>

                <div className="pt-2">
                  <p className="text-sm font-medium text-gray-700 mb-2">Common Filters</p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        setFilterQuery("creativeServingDecision.networkPolicyCompliance.status=APPROVED")
                      }
                      className="px-3 py-1 text-xs rounded-full bg-gray-100 text-gray-700 hover:bg-gray-200"
                    >
                      Approved only
                    </button>
                    <button
                      type="button"
                      onClick={() => setFilterQuery("creativeFormat=HTML")}
                      className="px-3 py-1 text-xs rounded-full bg-gray-100 text-gray-700 hover:bg-gray-200"
                    >
                      HTML
                    </button>
                    <button
                      type="button"
                      onClick={() => setFilterQuery("creativeFormat=VIDEO")}
                      className="px-3 py-1 text-xs rounded-full bg-gray-100 text-gray-700 hover:bg-gray-200"
                    >
                      Video
                    </button>
                    <button
                      type="button"
                      onClick={() => setFilterQuery("creativeFormat=NATIVE")}
                      className="px-3 py-1 text-xs rounded-full bg-gray-100 text-gray-700 hover:bg-gray-200"
                    >
                      Native
                    </button>
                    {filterQuery && (
                      <button
                        type="button"
                        onClick={() => setFilterQuery("")}
                        className="px-3 py-1 text-xs rounded-full bg-red-100 text-red-700 hover:bg-red-200"
                      >
                        Clear
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
