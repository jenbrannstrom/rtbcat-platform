"use client";

import { useState, useEffect } from "react";
import { AlertTriangle, Save, Info } from "lucide-react";
import { useTranslation } from "@/contexts/i18n-context";

interface RetentionConfig {
  raw_retention_days: number;
  summary_retention_days: number;
  auto_aggregate_after_days: number;
}

interface StorageStats {
  raw_rows: number;
  raw_earliest_date: string | null;
  raw_latest_date: string | null;
  summary_rows: number;
  summary_earliest_date: string | null;
  summary_latest_date: string | null;
}

export default function RetentionSettingsPage() {
  const { t } = useTranslation();
  const [rawDays, setRawDays] = useState(90);
  const [summaryDays, setSummaryDays] = useState(365);
  const [autoAggregateDays, setAutoAggregateDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [stats, setStats] = useState<StorageStats | null>(null);

  // Load current config
  useEffect(() => {
    async function loadConfig() {
      try {
        const response = await fetch("/api/retention/config");
        if (response.ok) {
          const config: RetentionConfig = await response.json();
          setRawDays(config.raw_retention_days);
          setSummaryDays(config.summary_retention_days);
          setAutoAggregateDays(config.auto_aggregate_after_days);
        }
      } catch (error) {
        console.error("Failed to load retention config:", error);
      }

      try {
        const statsResponse = await fetch("/api/retention/stats");
        if (statsResponse.ok) {
          const statsData = await statsResponse.json();
          setStats(statsData);
        }
      } catch (error) {
        console.error("Failed to load storage stats:", error);
      }

      setLoading(false);
    }
    loadConfig();
  }, []);

  const saveRetentionSettings = async () => {
    setSaving(true);
    setMessage(null);

    try {
      const response = await fetch("/api/retention/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          raw_retention_days: rawDays,
          summary_retention_days: summaryDays,
          auto_aggregate_after_days: autoAggregateDays,
        }),
      });

      if (response.ok) {
        setMessage({ type: "success", text: t.retentionPage.saveSuccess });
      } else {
        throw new Error(t.retentionPage.saveFailed);
      }
    } catch {
      setMessage({ type: "error", text: t.retentionPage.saveFailed });
    } finally {
      setSaving(false);
    }
  };

  const runRetentionJob = async () => {
    setSaving(true);
    setMessage(null);

    try {
      const response = await fetch("/api/retention/run", {
        method: "POST",
      });

      if (response.ok) {
        const result = await response.json();
        setMessage({
          type: "success",
          text: t.retentionPage.runCompleted.replace(
            "{aggregatedRows}",
            String(result.aggregated_rows)
          ).replace("{deletedRawRows}", String(result.deleted_raw_rows)),
        });
        // Reload stats
        const statsResponse = await fetch("/api/retention/stats");
        if (statsResponse.ok) {
          setStats(await statsResponse.json());
        }
      } else {
        throw new Error(t.retentionPage.runFailed);
      }
    } catch {
      setMessage({ type: "error", text: t.retentionPage.runFailed });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/3"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          <div className="h-32 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">{t.retentionPage.title}</h1>
      <p className="text-gray-600 mb-6">
        {t.retentionPage.subtitle}
      </p>

      {/* Storage Stats */}
      {stats && (
        <div className="bg-gray-50 rounded-lg p-4 mb-6">
          <h2 className="font-semibold text-gray-900 mb-3">{t.retentionPage.currentStorage}</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-gray-600">{t.retentionPage.rawPerformanceRows}</p>
              <p className="font-medium text-gray-900">
                {stats.raw_rows?.toLocaleString() || 0}
              </p>
              {stats.raw_earliest_date && stats.raw_latest_date && (
                <p className="text-xs text-gray-500">
                  {t.retentionPage.dateRangeSpan
                    .replace("{start}", stats.raw_earliest_date)
                    .replace("{end}", stats.raw_latest_date)}
                </p>
              )}
            </div>
            <div>
              <p className="text-gray-600">{t.retentionPage.dailySummaryRows}</p>
              <p className="font-medium text-gray-900">
                {stats.summary_rows?.toLocaleString() || 0}
              </p>
              {stats.summary_earliest_date && stats.summary_latest_date && (
                <p className="text-xs text-gray-500">
                  {t.retentionPage.dateRangeSpan
                    .replace("{start}", stats.summary_earliest_date)
                    .replace("{end}", stats.summary_latest_date)}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Message */}
      {message && (
        <div
          className={`mb-6 p-4 rounded-lg ${
            message.type === "success"
              ? "bg-green-50 border border-green-200 text-green-800"
              : "bg-red-50 border border-red-200 text-red-800"
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="space-y-6">
        {/* Raw Data Retention */}
        <div>
          <label className="block text-sm font-medium mb-2">
            {t.retentionPage.keepDetailedDataFor}
          </label>
          <select
            value={rawDays}
            onChange={(e) => setRawDays(Number(e.target.value))}
            className="border rounded px-3 py-2 w-full"
          >
            <option value={30}>{t.retentionPage.option30Days}</option>
            <option value={60}>{t.retentionPage.option60Days}</option>
            <option value={90}>{t.retentionPage.option90DaysRecommended}</option>
            <option value={180}>{t.retentionPage.option180Days}</option>
            <option value={365}>{t.retentionPage.option1Year}</option>
          </select>
          <p className="text-sm text-gray-500 mt-1">
            {t.retentionPage.detailedDataHelp}
          </p>
        </div>

        {/* Summary Retention */}
        <div>
          <label className="block text-sm font-medium mb-2">
            {t.retentionPage.keepDailySummariesFor}
          </label>
          <select
            value={summaryDays}
            onChange={(e) => setSummaryDays(Number(e.target.value))}
            className="border rounded px-3 py-2 w-full"
          >
            <option value={180}>{t.retentionPage.option6Months}</option>
            <option value={365}>{t.retentionPage.option1YearRecommended}</option>
            <option value={730}>{t.retentionPage.option2Years}</option>
            <option value={-1}>{t.retentionPage.optionForever}</option>
          </select>
          <p className="text-sm text-gray-500 mt-1">
            {t.retentionPage.summaryDataHelp}
          </p>
        </div>

        {/* Auto-Aggregation */}
        <div>
          <label className="block text-sm font-medium mb-2">
            {t.retentionPage.autoAggregateAfter}
          </label>
          <select
            value={autoAggregateDays}
            onChange={(e) => setAutoAggregateDays(Number(e.target.value))}
            className="border rounded px-3 py-2 w-full"
          >
            <option value={7}>{t.retentionPage.option7Days}</option>
            <option value={14}>{t.retentionPage.option14Days}</option>
            <option value={30}>{t.retentionPage.option30DaysRecommended}</option>
            <option value={60}>{t.retentionPage.option60Days}</option>
          </select>
          <p className="text-sm text-gray-500 mt-1">
            {t.retentionPage.autoAggregateHelp}
          </p>
        </div>

        {/* Warning */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
            <p className="text-sm text-yellow-800">
              {t.retentionPage.warningIrreversible}
            </p>
          </div>
        </div>

        {/* Info Box */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start gap-2">
            <Info className="h-5 w-5 text-blue-600 mt-0.5" />
            <div className="text-sm text-blue-800">
              <p className="font-medium mb-1">{t.retentionPage.howItWorks}</p>
              <ul className="list-disc list-inside space-y-1 text-blue-700">
                <li>{t.retentionPage.howItWorksItem1}</li>
                <li>{t.retentionPage.howItWorksItem2}</li>
                <li>{t.retentionPage.howItWorksItem3}</li>
                <li>{t.retentionPage.howItWorksItem4}</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={saveRetentionSettings}
            disabled={saving}
            className="btn-primary disabled:opacity-50 flex items-center gap-2"
          >
            <Save className="h-4 w-4" />
            {saving ? t.retentionPage.saving : t.retentionPage.saveSettings}
          </button>
          <button
            onClick={runRetentionJob}
            disabled={saving}
            className="btn-secondary disabled:opacity-50"
          >
            {saving ? t.retentionPage.running : t.retentionPage.runRetentionJobNow}
          </button>
        </div>
      </div>
    </div>
  );
}
