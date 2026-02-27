"use client";

import { useState, useEffect } from "react";
import { Loader2, RefreshCw, AlertTriangle, CheckCircle, HelpCircle, ShieldAlert } from "lucide-react";
import type { GeoLinguisticReport } from "@/types/api";
import { analyzeGeoLinguistic, getGeoLinguisticReport } from "@/lib/api";
import { cn } from "@/lib/utils";

interface GeoLinguisticSectionProps {
  creativeId: string;
}

const DECISION_CONFIG: Record<string, { icon: typeof CheckCircle; bg: string; text: string; label: string }> = {
  match: { icon: CheckCircle, bg: "bg-green-50 border-green-200", text: "text-green-700", label: "Match" },
  mismatch: { icon: ShieldAlert, bg: "bg-red-50 border-red-200", text: "text-red-700", label: "Mismatch" },
  needs_review: { icon: HelpCircle, bg: "bg-amber-50 border-amber-200", text: "text-amber-700", label: "Needs Review" },
};

const SEVERITY_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-gray-100 text-gray-600",
};

export function GeoLinguisticSection({ creativeId }: GeoLinguisticSectionProps) {
  const [report, setReport] = useState<GeoLinguisticReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    getGeoLinguisticReport(creativeId)
      .then((data) => setReport(data))
      .catch(() => setReport(null))
      .finally(() => setIsLoading(false));
  }, [creativeId]);

  const handleAnalyze = async (force: boolean = false) => {
    setIsAnalyzing(true);
    setError(null);
    try {
      const result = await analyzeGeoLinguistic(creativeId, force);
      setReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="bg-gray-50 rounded-lg p-3">
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
          <ShieldAlert className="h-3 w-3" />
          Geo-Linguistic Analysis
        </h4>
        <div className="flex items-center gap-1 text-xs text-gray-400">
          <Loader2 className="h-3 w-3 animate-spin" />
          Loading...
        </div>
      </div>
    );
  }

  const config = report ? DECISION_CONFIG[report.decision] || DECISION_CONFIG.needs_review : null;
  const DecisionIcon = config?.icon || HelpCircle;

  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
        <ShieldAlert className="h-3 w-3" />
        Geo-Linguistic Analysis
      </h4>

      {error && (
        <div className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded mb-2">{error}</div>
      )}

      {report && report.status === "completed" ? (
        <div className="space-y-2">
          {/* Decision badge */}
          <div className={cn("flex items-center gap-2 p-2 rounded border", config?.bg)}>
            <DecisionIcon className={cn("h-4 w-4", config?.text)} />
            <span className={cn("text-sm font-medium", config?.text)}>{config?.label}</span>
            <span className="ml-auto text-xs text-gray-500">
              Risk: {Math.round((report.risk_score || 0) * 100)}%
            </span>
            <span className="text-xs text-gray-400">
              ({Math.round((report.confidence || 0) * 100)}% confidence)
            </span>
          </div>

          {/* Languages */}
          {report.primary_languages.length > 0 && (
            <div className="text-xs text-gray-600">
              <span className="text-gray-500">Languages: </span>
              <span className="font-medium">{report.primary_languages.join(", ")}</span>
              {report.secondary_languages.length > 0 && (
                <span className="text-gray-400"> + {report.secondary_languages.join(", ")}</span>
              )}
            </div>
          )}

          {/* Currencies */}
          {report.detected_currencies.length > 0 && (
            <div className="text-xs text-gray-600">
              <span className="text-gray-500">Currencies: </span>
              <span className="font-medium">{report.detected_currencies.join(", ")}</span>
            </div>
          )}

          {/* Serving countries */}
          {report.serving_countries.length > 0 && (
            <div className="text-xs text-gray-600">
              <span className="text-gray-500">Serving: </span>
              <span className="font-medium">{report.serving_countries.join(", ")}</span>
            </div>
          )}

          {/* Findings */}
          {report.findings.length > 0 && (
            <div className="space-y-1 pt-1">
              {report.findings.map((finding, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <span className={cn("px-1.5 py-0.5 rounded shrink-0", SEVERITY_COLORS[finding.severity] || SEVERITY_COLORS.low)}>
                    {finding.severity}
                  </span>
                  <div>
                    <span className="text-gray-700">{finding.description}</span>
                    {finding.evidence && (
                      <span className="text-gray-400 ml-1">({finding.evidence})</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Evidence summary */}
          {report.evidence_summary && (
            <div className="text-xs text-gray-400 flex flex-wrap gap-2 pt-1">
              {report.evidence_summary.text_length > 0 && <span>{report.evidence_summary.text_length} chars analyzed</span>}
              {report.evidence_summary.ocr_texts_count > 0 && <span>· {report.evidence_summary.ocr_texts_count} OCR extractions</span>}
              {report.evidence_summary.video_frames_count > 0 && <span>· {report.evidence_summary.video_frames_count} video frames</span>}
              {report.evidence_summary.has_screenshot && <span>· HTML screenshot</span>}
            </div>
          )}

          {/* Timestamp + re-run */}
          <div className="flex items-center gap-3 pt-1">
            <button
              onClick={() => handleAnalyze(true)}
              disabled={isAnalyzing}
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
            >
              {isAnalyzing ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
              Re-analyze
            </button>
            {report.completed_at && (
              <span className="text-xs text-gray-400">
                {new Date(report.completed_at).toLocaleString()}
              </span>
            )}
          </div>
        </div>
      ) : report && report.status === "failed" ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 p-2 rounded border bg-red-50 border-red-200">
            <AlertTriangle className="h-4 w-4 text-red-600" />
            <span className="text-xs text-red-700">{report.error_message || "Analysis failed"}</span>
          </div>
          <button
            onClick={() => handleAnalyze(true)}
            disabled={isAnalyzing}
            className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
          >
            {isAnalyzing ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
            Retry
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-gray-400 italic">No geo-linguistic analysis available.</p>
          <button
            onClick={() => handleAnalyze(false)}
            disabled={isAnalyzing}
            className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
          >
            {isAnalyzing ? <Loader2 className="h-3 w-3 animate-spin" /> : <ShieldAlert className="h-3 w-3" />}
            Run Analysis
          </button>
        </div>
      )}
    </div>
  );
}
