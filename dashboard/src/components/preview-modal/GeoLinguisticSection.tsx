"use client";

import { useState, useEffect } from "react";
import { Loader2, RefreshCw, AlertTriangle, CheckCircle, HelpCircle, ShieldAlert } from "lucide-react";
import type { GeoLinguisticReport } from "@/types/api";
import { analyzeGeoLinguistic, getGeoLinguisticReport } from "@/lib/api";
import { useTranslation } from "@/contexts/i18n-context";
import { cn } from "@/lib/utils";

interface GeoLinguisticSectionProps {
  creativeId: string;
}

const NO_REPORT_MESSAGE = "No geo-linguistic analysis found for this creative";

const SEVERITY_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-gray-100 text-gray-600",
};

export function GeoLinguisticSection({ creativeId }: GeoLinguisticSectionProps) {
  const { t, language } = useTranslation();
  const [report, setReport] = useState<GeoLinguisticReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);

  useEffect(() => {
    setIsLoading(true);
    setLoadError(null);
    getGeoLinguisticReport(creativeId)
      .then((data) => setReport(data))
      .catch((err) => {
        const message = err instanceof Error ? err.message : t.previewModal.geoLinguisticFailedToLoad;
        setReport(null);
        if (message !== NO_REPORT_MESSAGE) {
          setLoadError(message);
        }
      })
      .finally(() => setIsLoading(false));
  }, [creativeId, reloadNonce, t.previewModal.geoLinguisticFailedToLoad]);

  const handleAnalyze = async (force: boolean = false) => {
    setIsAnalyzing(true);
    setError(null);
    try {
      const result = await analyzeGeoLinguistic(creativeId, force);
      setReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.previewModal.geoLinguisticAnalysisFailed);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const decisionConfig: Record<string, { icon: typeof CheckCircle; bg: string; text: string; label: string }> = {
    match: { icon: CheckCircle, bg: "bg-green-50 border-green-200", text: "text-green-700", label: t.previewModal.match },
    mismatch: { icon: ShieldAlert, bg: "bg-red-50 border-red-200", text: "text-red-700", label: t.previewModal.mismatch },
    needs_review: { icon: HelpCircle, bg: "bg-amber-50 border-amber-200", text: "text-amber-700", label: t.previewModal.needsReview },
  };
  const severityLabels: Record<string, string> = {
    high: t.previewModal.severityHigh,
    medium: t.previewModal.severityMedium,
    low: t.previewModal.severityLow,
  };

  if (isLoading) {
    return (
      <div className="bg-gray-50 rounded-lg p-3">
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
          <ShieldAlert className="h-3 w-3" />
          {t.previewModal.geoLinguisticAnalysisTitle}
        </h4>
        <div className="flex items-center gap-1 text-xs text-gray-400">
          <Loader2 className="h-3 w-3 animate-spin" />
          {t.previewModal.geoLinguisticLoading}
        </div>
      </div>
    );
  }

  const config = report ? decisionConfig[report.decision] || decisionConfig.needs_review : null;
  const DecisionIcon = config?.icon || HelpCircle;

  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
        <ShieldAlert className="h-3 w-3" />
        {t.previewModal.geoLinguisticAnalysisTitle}
      </h4>

      <p className="mb-2 text-[11px] text-gray-500">
        {t.previewModal.geoLinguisticAnalysisDescription}
      </p>

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
              {t.previewModal.geoLinguisticRisk}: {Math.round((report.risk_score || 0) * 100)}%
            </span>
            <span className="text-xs text-gray-400">
              ({Math.round((report.confidence || 0) * 100)}% {t.previewModal.confidence})
            </span>
          </div>

          {/* Languages */}
          {report.primary_languages.length > 0 && (
            <div className="text-xs text-gray-600">
              <span className="text-gray-500">{t.previewModal.geoLinguisticLanguages}: </span>
              <span className="font-medium">{report.primary_languages.join(", ")}</span>
              {report.secondary_languages.length > 0 && (
                <span className="text-gray-400"> + {report.secondary_languages.join(", ")}</span>
              )}
            </div>
          )}

          {/* Currencies */}
          {report.detected_currencies.length > 0 && (
            <div className="text-xs text-gray-600">
              <span className="text-gray-500">{t.previewModal.geoLinguisticCurrencies}: </span>
              <span className="font-medium">{report.detected_currencies.join(", ")}</span>
            </div>
          )}

          {/* Serving countries */}
          {report.serving_countries.length > 0 && (
            <div className="text-xs text-gray-600">
              <span className="text-gray-500">{t.previewModal.geoLinguisticServing}: </span>
              <span className="font-medium">{report.serving_countries.join(", ")}</span>
            </div>
          )}

          {/* Findings */}
          {report.findings.length > 0 && (
            <div className="space-y-1 pt-1">
              {report.findings.map((finding, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <span className={cn("px-1.5 py-0.5 rounded shrink-0", SEVERITY_COLORS[finding.severity] || SEVERITY_COLORS.low)}>
                    {severityLabels[finding.severity] || finding.severity}
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
              {report.evidence_summary.text_length > 0 && (
                <span>{t.previewModal.geoLinguisticCharsAnalyzed.replace("{count}", String(report.evidence_summary.text_length))}</span>
              )}
              {report.evidence_summary.ocr_texts_count > 0 && (
                <span>· {t.previewModal.geoLinguisticOcrExtractions.replace("{count}", String(report.evidence_summary.ocr_texts_count))}</span>
              )}
              {report.evidence_summary.video_frames_count > 0 && (
                <span>· {t.previewModal.geoLinguisticVideoFrames.replace("{count}", String(report.evidence_summary.video_frames_count))}</span>
              )}
              {report.evidence_summary.has_screenshot && <span>· {t.previewModal.geoLinguisticHtmlScreenshot}</span>}
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
              {t.previewModal.geoLinguisticReanalyze}
            </button>
            {report.completed_at && (
              <span className="text-xs text-gray-400">
                {new Date(report.completed_at).toLocaleString(language)}
              </span>
            )}
          </div>
        </div>
      ) : report && report.status === "failed" ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 p-2 rounded border bg-red-50 border-red-200">
            <AlertTriangle className="h-4 w-4 text-red-600" />
            <span className="text-xs text-red-700">{report.error_message || t.previewModal.geoLinguisticAnalysisFailed}</span>
          </div>
          <button
            onClick={() => handleAnalyze(true)}
            disabled={isAnalyzing}
            className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
          >
            {isAnalyzing ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
            {t.previewModal.geoLinguisticRetry}
          </button>
        </div>
      ) : loadError ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 p-2 rounded border bg-red-50 border-red-200">
            <AlertTriangle className="h-4 w-4 text-red-600" />
            <span className="text-xs text-red-700">{loadError}</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setReloadNonce((value) => value + 1)}
              disabled={isLoading}
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
            >
              {isLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
              {t.previewModal.geoLinguisticRetryLoad}
            </button>
            <button
              onClick={() => handleAnalyze(false)}
              disabled={isAnalyzing}
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
            >
              {isAnalyzing ? <Loader2 className="h-3 w-3 animate-spin" /> : <ShieldAlert className="h-3 w-3" />}
              {t.previewModal.geoLinguisticRunAnalysis}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-gray-400 italic">{t.previewModal.geoLinguisticNoReportYet}</p>
          <button
            onClick={() => handleAnalyze(false)}
            disabled={isAnalyzing}
            className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
          >
              {isAnalyzing ? <Loader2 className="h-3 w-3 animate-spin" /> : <ShieldAlert className="h-3 w-3" />}
            {t.previewModal.geoLinguisticRunAnalysis}
          </button>
        </div>
      )}
    </div>
  );
}
