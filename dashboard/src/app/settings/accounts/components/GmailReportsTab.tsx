"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle,
  Loader2,
  AlertTriangle,
  Mail,
  RefreshCw,
  ExternalLink,
  X,
  Inbox,
  Search,
  Download,
  Database,
} from "lucide-react";
import { getGmailStatus, triggerGmailImport } from "@/lib/api";
import { cn } from "@/lib/utils";

// Import progress phases
const IMPORT_PHASES = [
  { id: 'connecting', label: 'Connecting to Gmail', icon: Mail, duration: 2000 },
  { id: 'searching', label: 'Searching for report emails', icon: Search, duration: 3000 },
  { id: 'downloading', label: 'Downloading attachments', icon: Download, duration: 8000 },
  { id: 'importing', label: 'Importing CSV data', icon: Database, duration: 5000 },
] as const;

type ImportPhase = typeof IMPORT_PHASES[number]['id'] | 'idle' | 'complete';

/**
 * Gmail Reports configuration tab.
 * Allows users to connect Gmail and auto-import Authorized Buyers reports.
 */
export function GmailReportsTab() {
  const queryClient = useQueryClient();
  const [importMessage, setImportMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [importPhase, setImportPhase] = useState<ImportPhase>('idle');
  const phaseTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [pollStatus, setPollStatus] = useState(false);

  const { data: gmailStatus, isLoading: statusLoading, refetch: refetchStatus } = useQuery({
    queryKey: ["gmailStatus"],
    queryFn: getGmailStatus,
    refetchInterval: pollStatus ? 5000 : false,
  });

  // Cycle through phases while importing
  useEffect(() => {
    if (importPhase === 'idle' || importPhase === 'complete') {
      return;
    }

    const currentIndex = IMPORT_PHASES.findIndex(p => p.id === importPhase);
    if (currentIndex === -1) return;

    const currentPhase = IMPORT_PHASES[currentIndex];

    // Move to next phase after duration
    phaseTimerRef.current = setTimeout(() => {
      const nextIndex = currentIndex + 1;
      if (nextIndex < IMPORT_PHASES.length) {
        setImportPhase(IMPORT_PHASES[nextIndex].id);
      }
      // Stay on last phase until complete
    }, currentPhase.duration);

    return () => {
      if (phaseTimerRef.current) {
        clearTimeout(phaseTimerRef.current);
      }
    };
  }, [importPhase]);

  const importMutation = useMutation({
    mutationFn: triggerGmailImport,
    onMutate: () => {
      setImportPhase('connecting');
      setPollStatus(true);
    },
    onSuccess: (data) => {
      setImportPhase('complete');
      if (data.queued) {
        setImportMessage({ type: "success", text: data.message || "Import started in the background" });
      } else if (data.success) {
        if (data.files_imported > 0) {
          setImportMessage({ type: "success", text: `Imported ${data.files_imported} file(s) from ${data.emails_processed} email(s)` });
        } else if (data.emails_processed === 0) {
          setImportMessage({ type: "success", text: "No new report emails found" });
        } else {
          setImportMessage({ type: "success", text: `Processed ${data.emails_processed} email(s), no new files to import` });
        }
      } else {
        setImportMessage({ type: "error", text: data.errors?.[0] || "Import failed" });
      }
      refetchStatus();
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      setTimeout(() => {
        setImportMessage(null);
        setImportPhase('idle');
      }, 8000);
    },
    onError: (error) => {
      setImportPhase('idle');
      setImportMessage({ type: "error", text: error instanceof Error ? error.message : "Import failed" });
      setPollStatus(false);
      setTimeout(() => setImportMessage(null), 8000);
    },
  });

  const formatRelativeTime = (isoString: string | null) => {
    if (!isoString) return "Never";
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? "" : "s"} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
    return date.toLocaleDateString();
  };

  const isConfigured = gmailStatus?.configured === true;
  const isAuthorized = gmailStatus?.authorized === true;
  const isConnected = isConfigured && isAuthorized;
  const isImportRunning = gmailStatus?.running === true;

  useEffect(() => {
    if (isImportRunning) {
      setPollStatus(true);
    } else {
      setPollStatus(false);
    }
  }, [isImportRunning]);

  return (
    <div className="space-y-6">
      {/* Import Message */}
      {importMessage && (
        <div className={cn(
          "p-4 rounded-lg flex items-start justify-between",
          importMessage.type === "success" ? "bg-green-50" : "bg-red-50"
        )}>
          <div className="flex items-start">
            {importMessage.type === "success" ? (
              <CheckCircle className="h-5 w-5 text-green-400 mt-0.5" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-red-400 mt-0.5" />
            )}
            <p className={cn(
              "ml-3 text-sm font-medium",
              importMessage.type === "success" ? "text-green-800" : "text-red-800"
            )}>
              {importMessage.text}
            </p>
          </div>
          <button onClick={() => setImportMessage(null)} className="text-gray-400 hover:text-gray-600">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

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
          {statusLoading ? (
            <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
          ) : (
            <span className={cn(
              "px-2 py-1 text-xs font-medium rounded",
              isConnected ? "bg-green-100 text-green-800" :
              isConfigured ? "bg-yellow-100 text-yellow-800" :
              "bg-gray-100 text-gray-600"
            )}>
              {isConnected ? "Connected" : isConfigured ? "Not authorized" : "Not configured"}
            </span>
          )}
        </div>

        {isConnected ? (
          <div className="space-y-4">
            {/* Status display */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 mb-1">Last Import</p>
                <p className="font-medium text-gray-900">
                  {isImportRunning ? "Import in progress" : formatRelativeTime(gmailStatus?.last_run || null)}
                </p>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 mb-1">Last Success</p>
                <p className="font-medium text-green-600">{formatRelativeTime(gmailStatus?.last_success || null)}</p>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 mb-1">Total Imports</p>
                <p className="font-bold text-xl text-gray-900">{gmailStatus?.total_imports || 0}</p>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 mb-1">Schedule</p>
                <p className="font-medium text-gray-900">Daily (cron)</p>
              </div>
            </div>

            {/* Last error if any */}
            {gmailStatus?.last_error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5" />
                  <div className="text-sm text-red-800">
                    <strong>Last error:</strong> {gmailStatus.last_error}
                  </div>
                </div>
              </div>
            )}

            {/* Import Now button */}
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-4">
                <button
                  onClick={() => importMutation.mutate()}
                  disabled={importMutation.isPending || isImportRunning}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg font-medium",
                    "bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                  )}
                >
                  {importMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Importing...
                    </>
                  ) : isImportRunning ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Import in progress...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-4 w-4" />
                      Import Now
                    </>
                  )}
                </button>
                {!importMutation.isPending && !isImportRunning && (
                  <p className="text-sm text-gray-500">
                    Check for new report emails and import them immediately
                  </p>
                )}
              </div>

              {/* Progress indicator with phases */}
              {importMutation.isPending && importPhase !== 'idle' && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center gap-3 mb-3">
                    <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />
                    <span className="font-medium text-blue-900">Import in progress...</span>
                  </div>

                  {/* Phase steps */}
                  <div className="space-y-2">
                    {IMPORT_PHASES.map((phase, index) => {
                      const currentIndex = IMPORT_PHASES.findIndex(p => p.id === importPhase);
                      const isComplete = index < currentIndex;
                      const isCurrent = phase.id === importPhase;
                      const isPending = index > currentIndex;
                      const PhaseIcon = phase.icon;

                      return (
                        <div
                          key={phase.id}
                          className={cn(
                            "flex items-center gap-3 text-sm py-1.5 px-2 rounded",
                            isCurrent && "bg-blue-100",
                            isComplete && "text-green-700",
                            isPending && "text-gray-400"
                          )}
                        >
                          {isComplete ? (
                            <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />
                          ) : isCurrent ? (
                            <Loader2 className="h-4 w-4 text-blue-600 animate-spin flex-shrink-0" />
                          ) : (
                            <PhaseIcon className="h-4 w-4 text-gray-300 flex-shrink-0" />
                          )}
                          <span className={cn(
                            isCurrent && "font-medium text-blue-800"
                          )}>
                            {phase.label}
                            {isCurrent && "..."}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  <p className="text-xs text-blue-600 mt-3">
                    This may take a minute depending on the number of report emails.
                  </p>
                </div>
              )}
            </div>

          </div>
        ) : (
          <div className="p-6 border-2 border-dashed border-gray-200 rounded-lg text-center">
            <Inbox className="h-10 w-10 text-gray-300 mx-auto mb-3" />
            <h5 className="font-medium text-gray-700 mb-2">
              {isConfigured ? "Gmail Authorization Required" : "Gmail Not Configured"}
            </h5>
            <p className="text-sm text-gray-500 mb-4 max-w-md mx-auto">
              {isConfigured ? (
                <>Run the import script manually first to complete OAuth authorization:<br />
                <code className="bg-gray-100 px-2 py-1 rounded text-xs">python scripts/gmail_import.py</code></>
              ) : (
                <>Follow the INSTALL.md guide to set up Gmail API credentials.<br />
                Upload <code className="bg-gray-100 px-1 rounded">gmail-oauth-client.json</code> to <code className="bg-gray-100 px-1 rounded">~/.catscan/credentials/</code></>
              )}
            </p>
            <a
              href="https://github.com/yourorg/rtbcat-platform/blob/main/INSTALL.md#automatic-report-import-gmail"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
            >
              View Setup Guide
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
