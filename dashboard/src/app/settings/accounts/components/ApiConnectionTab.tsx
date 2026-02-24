"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle,
  Users,
  Loader2,
  AlertTriangle,
  Upload,
  Shield,
  FileJson,
  RefreshCw,
  X,
  Pencil,
  Check,
} from "lucide-react";
import {
  getHealth,
  getSeats,
  syncSeat,
  discoverSeats,
  getServiceAccounts,
  addServiceAccount,
  deleteServiceAccount,
  syncRTBEndpoints,
  syncPretargetingConfigs,
  updateSeat,
} from "@/lib/api";
import type { ServiceAccount } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { BuyerSeat } from "@/types/api";
import { useTranslation } from "@/contexts/i18n-context";
import { GeminiApiKeySection } from "./GeminiApiKeySection";

/**
 * API Connection tab for service account and buyer seat management.
 * Handles service account upload, seat discovery, and creative syncing.
 */
export function ApiConnectionTab() {
  const queryClient = useQueryClient();
  const { t, language } = useTranslation();
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [showAddAccount, setShowAddAccount] = useState(false);
  const [deletingAccountId, setDeletingAccountId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Seat editing state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [savingSeat, setSavingSeat] = useState(false);

  const { data: health, refetch: refetchHealth } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  // Fetch all service accounts (multi-account support)
  const { data: serviceAccountsData, isLoading: accountsLoading } = useQuery({
    queryKey: ["serviceAccounts"],
    queryFn: () => getServiceAccounts(),
  });

  const serviceAccounts = serviceAccountsData?.accounts ?? [];
  const hasAccounts = serviceAccounts.length > 0;

  const { data: seats, isLoading: seatsLoading } = useQuery({
    queryKey: ["seats"],
    queryFn: () => getSeats({ active_only: false }),
    enabled: hasAccounts,
  });
  const showSeatLoadingNote =
    !seatsLoading && hasAccounts && (seats || []).some((seat) => seat.creative_count === 0);

  const [discoveryAttempted, setDiscoveryAttempted] = useState(false);

  const discoverMutation = useMutation({
    mutationFn: () => discoverSeats({ bidder_id: "auto" }),
    onSuccess: async (data) => {
      if (data.seats_discovered === 0) {
        setMessage({
          type: "error",
          text: t.setup.noBuyerSeatsFoundRoleHint,
        });
        setTimeout(() => setMessage(null), 10000);
        return;
      }
      setMessage({
        type: "success",
        text: t.setup.discoveredSeatsSyncingEndpoints.replace(
          "{count}",
          String(data.seats_discovered)
        ),
      });
      queryClient.invalidateQueries({ queryKey: ["seats"] });

      try {
        await syncRTBEndpoints();
        queryClient.invalidateQueries({ queryKey: ["rtb-endpoints"] });
      } catch (e) {
        // Silently fail endpoint sync
      }

      try {
        await syncPretargetingConfigs();
        queryClient.invalidateQueries({ queryKey: ["pretargeting-configs"] });
      } catch (e) {
        // Silently fail pretargeting sync
      }

      setMessage({
        type: "success",
        text: t.setup.discoveredSeatsAndSyncedCreatives
          .replace("{seats}", String(data.seats_discovered))
          .replace("{creatives}", String(data.sync_result?.creatives_synced || 0)),
      });
      setTimeout(() => setMessage(null), 5000);
    },
    onError: (error) => {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : t.connect.failedToDiscoverSeats,
      });
      setTimeout(() => setMessage(null), 8000);
    },
  });

  // Auto-discover seats when first account is added and no seats exist
  useEffect(() => {
    const noSeats = seats !== undefined && seats.length === 0;
    const notLoading = !seatsLoading && !discoverMutation.isPending;

    if (hasAccounts && noSeats && notLoading && !discoveryAttempted) {
      setDiscoveryAttempted(true);
      discoverMutation.mutate();
    }
  }, [hasAccounts, seats, seatsLoading, discoveryAttempted, discoverMutation]);

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const contents = await file.text();
      let json;
      try {
        json = JSON.parse(contents);
      } catch {
        throw new Error(t.connect.invalidJsonFile);
      }
      if (!json.type || !json.client_email || !json.private_key) {
        throw new Error(t.connect.invalidServiceAccountFormat);
      }
      if (json.type !== "service_account") {
        throw new Error(
          t.connect.invalidCredentialType.replace("{type}", String(json.type))
        );
      }
      return addServiceAccount(contents);
    },
    onSuccess: (data) => {
      setMessage({
        type: "success",
        text: t.connect.connectedAs.replace("{email}", data.client_email ?? ""),
      });
      queryClient.invalidateQueries({ queryKey: ["health"] });
      queryClient.invalidateQueries({ queryKey: ["serviceAccounts"] });
      queryClient.invalidateQueries({ queryKey: ["seats"] });
      setShowAddAccount(false);
      refetchHealth();
    },
    onError: (error) => {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : t.connect.uploadFailed,
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (accountId: string) => deleteServiceAccount(accountId),
    onSuccess: () => {
      setMessage({ type: "success", text: t.setup.serviceAccountRemoved });
      queryClient.invalidateQueries({ queryKey: ["health"] });
      queryClient.invalidateQueries({ queryKey: ["serviceAccounts"] });
      queryClient.invalidateQueries({ queryKey: ["seats"] });
      setDeletingAccountId(null);
      refetchHealth();
      setTimeout(() => setMessage(null), 5000);
    },
    onError: (error) => {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : t.setup.failedToRemoveAccount,
      });
      setDeletingAccountId(null);
      setTimeout(() => setMessage(null), 5000);
    },
  });

  const handleDeleteAccount = (accountId: string) => {
    setDeletingAccountId(accountId);
    deleteMutation.mutate(accountId);
  };

  const syncMutation = useMutation({
    mutationFn: (buyerId: string) => syncSeat(buyerId),
    onSuccess: (data) => {
      setMessage({
        type: "success",
        text: t.connect.syncedCreatives.replace("{count}", String(data.creatives_synced)),
      });
      queryClient.invalidateQueries({ queryKey: ["creatives"] });
      queryClient.invalidateQueries({ queryKey: ["seats"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      setSyncingId(null);
      setTimeout(() => setMessage(null), 5000);
    },
    onError: (error) => {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : t.connect.syncFailed,
      });
      setSyncingId(null);
      setTimeout(() => setMessage(null), 5000);
    },
  });

  const handleSync = (buyerId: string) => {
    setSyncingId(buyerId);
    syncMutation.mutate(buyerId);
  };

  // Seat name editing
  const handleStartEdit = (seat: BuyerSeat) => {
    setEditingId(seat.buyer_id);
    setEditValue(seat.display_name || "");
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditValue("");
  };

  const handleSaveEdit = async (buyerId: string) => {
    if (!editValue.trim()) {
      setMessage({ type: "error", text: t.setup.displayNameCannotBeEmpty });
      return;
    }

    setSavingSeat(true);
    try {
      await updateSeat(buyerId, { display_name: editValue.trim() });
      queryClient.invalidateQueries({ queryKey: ["seats"] });
      setEditingId(null);
      setMessage({ type: "success", text: t.setup.seatNameUpdated });
    } catch (error) {
      setMessage({ type: "error", text: t.setup.failedToUpdateSeatName });
    }
    setSavingSeat(false);
    setTimeout(() => setMessage(null), 3000);
  };

  const handleFileSelect = useCallback((file: File) => {
    if (!file.name.endsWith(".json")) {
      setMessage({ type: "error", text: t.connect.pleaseSelectJsonFile });
      return;
    }
    uploadMutation.mutate(file);
  }, [t, uploadMutation]);

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

  const isConfigured = hasAccounts;
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

      {/* Quick Start Guide - always visible */}
      <div className="card p-6 bg-blue-50 border-blue-200">
        <h3 className="text-lg font-semibold text-blue-900 mb-4">{t.setup.howToConnect}</h3>
        <div className="grid md:grid-cols-3 gap-4">
          <div className="bg-white rounded-lg p-4 border border-blue-200">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold">1</span>
              <span className="font-semibold text-gray-900">{t.setup.createServiceAccount}</span>
            </div>
            <p className="text-sm text-gray-600">
              {t.setup.createServiceAccountDesc}
            </p>
          </div>
          <div className="bg-white rounded-lg p-4 border border-blue-200">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold">2</span>
              <span className="font-semibold text-gray-900">{t.setup.grantRtbAccess}</span>
            </div>
            <p className="text-sm text-gray-600">
              {t.setup.grantRtbAccessDesc}
            </p>
          </div>
          <div className="bg-white rounded-lg p-4 border border-blue-200">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold">3</span>
              <span className="font-semibold text-gray-900">{t.setup.uploadKeyFile}</span>
            </div>
            <p className="text-sm text-gray-600">
              {t.setup.uploadKeyFileDesc}
            </p>
          </div>
        </div>
      </div>

      {/* Connected Accounts Section */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold",
              isConfigured ? "bg-green-500 text-white" : "bg-gray-200 text-gray-500"
            )}>
              {isConfigured ? <CheckCircle className="w-5 h-5" /> : <Shield className="w-5 h-5" />}
            </div>
            <div>
              <h3 className="text-lg font-medium text-gray-900">{t.setup.connectedAccounts}</h3>
              <p className="text-sm text-gray-500">{t.setup.connectedAccountsDesc}</p>
            </div>
          </div>
          {isConfigured && !showAddAccount && (
            <button
              onClick={() => setShowAddAccount(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
            >
              <Upload className="h-4 w-4" />
              {t.setup.addAccount}
            </button>
          )}
        </div>

        {accountsLoading ? (
          <div className="py-8 flex justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          </div>
        ) : isConfigured ? (
          <div className="space-y-4">
            {/* Connected account cards */}
            {serviceAccounts.map((account: ServiceAccount) => (
              <div
                key={account.id}
                className="flex items-center justify-between py-4 px-4 bg-green-50 rounded-lg border border-green-200 overflow-hidden"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <CheckCircle className="h-6 w-6 text-green-500 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-green-900 truncate">
                      {account.display_name || account.client_email}
                    </p>
                    <p className="text-sm text-green-700 truncate">
                      {account.client_email}
                      {account.project_id && ` · ${account.project_id}`}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteAccount(account.id)}
                  disabled={deletingAccountId === account.id}
                  className={cn(
                    "text-sm text-red-600 hover:text-red-700 font-medium flex-shrink-0 ml-4",
                    deletingAccountId === account.id && "opacity-50"
                  )}
                >
                  {deletingAccountId === account.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    t.setup.remove
                  )}
                </button>
              </div>
            ))}

            {/* Add another account form */}
            {showAddAccount && (
              <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-gray-900">{t.setup.addAnotherAccount}</h4>
                  <button onClick={() => setShowAddAccount(false)} className="text-gray-400 hover:text-gray-600">
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  className={cn(
                    "border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer",
                    isDragging ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-blue-400 bg-white",
                    uploadMutation.isPending && "opacity-50 pointer-events-none"
                  )}
                >
                  {uploadMutation.isPending ? (
                    <>
                      <Loader2 className="h-8 w-8 text-blue-600 mx-auto mb-2 animate-spin" />
                      <p className="text-sm text-gray-700">{t.setup.uploading}</p>
                    </>
                  ) : (
                    <>
                      <FileJson className={cn("h-8 w-8 mx-auto mb-2", isDragging ? "text-blue-600" : "text-gray-400")} />
                      <p className="text-sm font-medium text-gray-700">
                        {isDragging ? t.setup.dropFileHere : t.setup.uploadServiceAccountJson}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">{t.setup.dragAndDropOrClick}</p>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
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
                  <p className="font-medium text-gray-700">{t.setup.uploading}</p>
                </>
              ) : (
                <>
                  <FileJson className={cn("h-10 w-10 mx-auto mb-3", isDragging ? "text-blue-600" : "text-gray-400")} />
                  <p className="font-medium text-gray-700">
                    {isDragging ? t.setup.dropFileHere : t.setup.uploadServiceAccountJson}
                  </p>
                  <p className="text-sm text-gray-500 mt-1">{t.setup.dragAndDropOrClick}</p>
                </>
              )}
            </div>

            <details className="border border-gray-200 rounded-lg">
              <summary className="px-4 py-3 cursor-pointer text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg">
                {t.setup.detailedSetupInstructions}
              </summary>
              <div className="px-4 pb-4 text-sm text-gray-600 space-y-3">
                <ol className="list-decimal list-inside space-y-2">
                  <li>{t.connect.goToGcpServiceAccounts}</li>
                  <li>{t.connect.selectYourProject}</li>
                  <li>{t.connect.clickCreateServiceAccount}</li>
                  <li>{t.connect.nameIt}</li>
                  <li>{t.connect.clickCreateContinue}</li>
                  <li>{t.connect.clickOnServiceAccountEmail}</li>
                  <li>{t.connect.goToKeysTab}</li>
                  <li>{t.connect.selectJsonClick}</li>
                  <li>{t.connect.uploadDownloadedFile}</li>
                </ol>
                <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <p className="text-sm text-yellow-800">
                    {t.connect.importantAddServiceAccount}
                  </p>
                </div>
              </div>
            </details>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept=".json,application/json"
          onChange={handleInputChange}
          className="hidden"
        />
      </div>

      {/* Buyer Seats Section */}
      <div className={cn("card p-6 transition-opacity", !isConfigured && "opacity-50")}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold",
              hasSeats && seats.some((s: BuyerSeat) => s.creative_count > 0)
                ? "bg-green-500 text-white"
                : isConfigured
                  ? "bg-blue-600 text-white"
                  : "bg-gray-200 text-gray-500"
            )}>
              {hasSeats && seats.some((s: BuyerSeat) => s.creative_count > 0) ? <CheckCircle className="w-5 h-5" /> : <Users className="w-5 h-5" />}
            </div>
            <div>
              <h3 className="text-lg font-medium text-gray-900">{t.setup.buyerSeats}</h3>
              <p className="text-sm text-gray-500">{t.setup.buyerSeatsDesc}</p>
            </div>
          </div>
          {isConfigured && (
            <button
              onClick={() => discoverMutation.mutate()}
              disabled={discoverMutation.isPending}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium",
                "bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
              )}
            >
              {discoverMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t.setup.discovering}
                </>
              ) : (
                <>
                  <RefreshCw className="h-4 w-4" />
                  {t.setup.discoverSeats}
                </>
              )}
            </button>
          )}
        </div>

        {seatsLoading ? (
          <div className="py-8 flex justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          </div>
        ) : isConfigured ? (
          <div className="space-y-4">
            {showSeatLoadingNote && (
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-start gap-3">
                  <Loader2 className="h-5 w-5 text-blue-600 mt-0.5 animate-spin" />
                  <div>
                    <p className="font-medium text-blue-900">{t.setup.seatDataPopulating}</p>
                    <p className="text-sm text-blue-700 mt-1">
                      {t.setup.seatDataPopulatingHelp}
                    </p>
                  </div>
                </div>
              </div>
            )}
            {hasSeats ? (
              <div className="space-y-3">
                {seats.map((seat: BuyerSeat) => (
                  <div key={seat.buyer_id} className="flex items-center justify-between py-3 px-4 bg-gray-50 rounded-lg group">
                    <div className="flex-1 min-w-0">
                      {editingId === seat.buyer_id ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            className="border rounded px-2 py-1 text-sm w-48"
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleSaveEdit(seat.buyer_id);
                              if (e.key === "Escape") handleCancelEdit();
                            }}
                          />
                          <button
                            onClick={() => handleSaveEdit(seat.buyer_id)}
                            disabled={savingSeat}
                            className="p-1 text-green-600 hover:bg-green-50 rounded"
                          >
                            <Check className="h-4 w-4" />
                          </button>
                          <button
                            onClick={handleCancelEdit}
                            className="p-1 text-gray-400 hover:bg-gray-100 rounded"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <p className="font-medium text-gray-900">
                            {seat.display_name || t.setup.buyerSeatNameFallback.replace("{buyerId}", seat.buyer_id)}
                          </p>
                          <button
                            onClick={() => handleStartEdit(seat)}
                            className="p-1 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                            title={t.setup.editSeatName}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )}
                      <p className="text-sm text-gray-500">
                        {t.setup.creativesCount.replace("{count}", String(seat.creative_count))}
                        {syncingId === seat.buyer_id
                          ? ` · ${t.setup.syncInProgress}`
                          : seat.last_synced
                            ? ` · ${t.setup.lastSyncedShort.replace("{date}", new Date(seat.last_synced).toLocaleDateString(language))}`
                            : ""}
                      </p>
                    </div>
                    {editingId !== seat.buyer_id && (
                      <button
                        onClick={() => handleSync(seat.buyer_id)}
                        disabled={syncingId === seat.buyer_id}
                        className={cn(
                          "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium",
                          "bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                        )}
                      >
                        <RefreshCw className={cn("h-4 w-4", syncingId === seat.buyer_id && "animate-spin")} />
                        {syncingId === seat.buyer_id ? t.setup.syncing : t.setup.syncNow}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-yellow-800">{t.setup.noBuyerSeatsFound}</p>
                    <p className="text-sm text-yellow-700 mt-1">
                      {t.setup.noBuyerSeatsVerifyAccessPrefix}{" "}
                      <a href="https://authorizedbuyers.google.com" target="_blank" rel="noopener noreferrer" className="underline">Authorized Buyers</a>{" "}
                      {t.setup.noBuyerSeatsVerifyAccessSuffix} <strong>Account Manager</strong> {t.setup.orLabel}{" "}
                      <strong>RTB Troubleshooter</strong> {t.setup.roleLabel}.
                    </p>
                    {serviceAccounts[0]?.client_email && (
                      <p className="text-sm text-yellow-700 mt-2">
                        {t.setup.serviceAccountToAddLabel}: <code className="bg-yellow-100 px-1 rounded text-xs">{serviceAccounts[0].client_email}</code>
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-gray-500 py-4">{t.setup.connectServiceAccount}</p>
        )}
      </div>

      {/* Gemini API Key Section */}
      <GeminiApiKeySection />
    </div>
  );
}
