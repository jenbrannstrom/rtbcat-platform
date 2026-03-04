"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  X,
  Pencil,
  Trash2,
  TrendingUp,
  Eye,
  MousePointer,
  DollarSign,
  Target,
  Sparkles,
} from "lucide-react";
import {
  getAICampaign,
  getAICampaignCreatives,
  getAICampaignPerformance,
  getAICampaignDailyTrend,
  removeCreativeFromAICampaign,
  updateAICampaign,
  deleteAICampaign,
  getCreative,
  type AICampaign,
  type AICampaignPerformance,
} from "@/lib/api";
import { CreativeCard } from "@/components/creative-card";
import { PreviewModal } from "@/components/preview-modal";
import { formatNumber } from "@/lib/utils";
import type { Creative } from "@/types/api";
import { useAccount } from "@/contexts/account-context";
import { useTranslation } from "@/contexts/i18n-context";
import { toBuyerScopedPath } from "@/lib/buyer-routes";

interface DailyTrend {
  date: string;
  impressions: number;
  clicks: number;
  spend: number;
}

function asNumber(value: unknown, fallback = 0): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

export default function CampaignDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { selectedBuyerId } = useAccount();
  const { t, language } = useTranslation();
  const campaignId = parseInt(params.id as string);
  const campaignsHref = toBuyerScopedPath("/campaigns", selectedBuyerId);
  const clustersHref = toBuyerScopedPath("/clusters", selectedBuyerId);

  const [campaign, setCampaign] = useState<AICampaign | null>(null);
  const [creatives, setCreatives] = useState<Creative[]>([]);
  const [performance, setPerformance] = useState<AICampaignPerformance | null>(null);
  const [dailyTrend, setDailyTrend] = useState<DailyTrend[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewCreative, setPreviewCreative] = useState<Creative | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [period, setPeriod] = useState("7d");
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");

  const formatTrendDate = (value: string | undefined): string => {
    if (!value) return "";
    const parsed = new Date(`${value}T00:00:00`);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(language);
  };

  const formatCampaignStatus = (status: string): string => {
    switch (status.toLowerCase()) {
      case "draft":
        return t.campaigns.statusDraft;
      case "paused":
        return t.campaigns.statusPaused;
      case "inactive":
        return t.campaigns.statusInactive;
      case "archived":
        return t.campaigns.statusArchived;
      default:
        return status;
    }
  };

  async function fetchCampaignData() {
    setLoading(true);
    setError(null);

    try {
      // Fetch campaign details and creatives in parallel
      const [campaignData, creativesData, perfData, trendData] = await Promise.all([
        getAICampaign(campaignId),
        getAICampaignCreatives(campaignId),
        getAICampaignPerformance(campaignId, period),
        getAICampaignDailyTrend(campaignId, period === "all" ? 365 : parseInt(period)),
      ]);

      setCampaign(campaignData);
      setPerformance(perfData);
      setDailyTrend(trendData.trend || []);
      setEditName(campaignData.name);
      setEditDescription(campaignData.description || "");

      // Fetch full creative details for each ID
      if (creativesData.creative_ids.length > 0) {
        const creativeDetails = await Promise.all(
          creativesData.creative_ids.map((id) =>
            getCreative(id).catch(() => null)
          )
        );
        setCreatives(creativeDetails.filter((c): c is Creative => c !== null));
      } else {
        setCreatives([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t.campaigns.failedToLoadCampaign);
    }

    setLoading(false);
  }

  useEffect(() => {
    if (campaignId) {
      fetchCampaignData();
    }
  }, [campaignId, period]);

  const handleRemoveCreative = async (creativeId: string) => {
    if (!confirm(t.campaigns.confirmRemoveCreative)) return;

    setRemovingId(creativeId);
    try {
      await removeCreativeFromAICampaign(campaignId, creativeId);
      setCreatives((prev) => prev.filter((c) => c.id !== creativeId));
      if (campaign) {
        setCampaign({ ...campaign, creative_count: campaign.creative_count - 1 });
      }
    } catch (err) {
      alert(t.campaigns.failedToRemoveCreative);
    }
    setRemovingId(null);
  };

  const handleSaveEdit = async () => {
    try {
      await updateAICampaign(campaignId, {
        name: editName,
        description: editDescription || undefined,
      });
      setCampaign((prev) =>
        prev ? { ...prev, name: editName, description: editDescription } : null
      );
      setEditing(false);
    } catch (err) {
      alert(t.campaigns.failedToUpdateCampaign);
    }
  };

  const handleDeleteCampaign = async () => {
    if (!confirm(t.campaigns.confirmDeleteCampaign)) return;

    try {
      await deleteAICampaign(campaignId);
      router.push(campaignsHref);
    } catch (err) {
      alert(t.campaigns.failedToDeleteCampaign);
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-4" />
          <div className="h-4 bg-gray-200 rounded w-1/3 mb-8" />
          <div className="grid grid-cols-4 gap-4 mb-8">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 bg-gray-100 rounded-lg" />
            ))}
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-48 bg-gray-100 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error || !campaign) {
    return (
      <div className="p-8">
        <Link
          href={campaignsHref}
          className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          {t.campaigns.backToCreativeClusters}
        </Link>
        <div className="text-center py-12">
          <p className="text-red-600">{error || t.campaigns.campaignNotFound}</p>
          <button
            onClick={fetchCampaignData}
            className="mt-4 btn-primary"
          >
            {t.common.retry}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6">
        <Link
          href={campaignsHref}
          className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          {t.campaigns.backToCreativeClusters}
        </Link>

        <div className="flex justify-between items-start">
          <div className="flex-1">
            {editing ? (
              <div className="space-y-3 max-w-lg">
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="text-2xl font-bold w-full border rounded px-3 py-2"
                  placeholder={t.campaigns.campaignNamePlaceholder}
                />
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  className="w-full border rounded px-3 py-2 text-sm"
                  placeholder={t.campaigns.descriptionOptionalPlaceholder}
                  rows={2}
                />
                <div className="flex gap-2">
                  <button onClick={handleSaveEdit} className="btn-primary text-sm">
                    {t.common.save}
                  </button>
                  <button
                    onClick={() => {
                      setEditing(false);
                      setEditName(campaign.name);
                      setEditDescription(campaign.description || "");
                    }}
                    className="px-4 py-2 border rounded text-sm hover:bg-gray-50"
                  >
                    {t.common.cancel}
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold text-gray-900">{campaign.name}</h1>
                  {campaign.ai_generated && (
                    <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-purple-100 text-purple-700">
                      <Sparkles className="h-3 w-3" />
                      {t.campaigns.aiGenerated}
                      {campaign.ai_confidence && (
                        <span className="text-purple-500">
                          ({Math.round(campaign.ai_confidence * 100)}%)
                        </span>
                      )}
                    </span>
                  )}
                  {campaign.status !== "active" && (
                    <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600">
                      {formatCampaignStatus(campaign.status)}
                    </span>
                  )}
                </div>
                {campaign.description && (
                  <p className="mt-1 text-gray-600">{campaign.description}</p>
                )}
                <p className="mt-1 text-sm text-gray-500">
                  {campaign.clustering_method && `${campaign.clustering_method} - `}
                  {creatives.length !== 1
                    ? t.campaigns.creativeCountPlural.replace("{count}", formatNumber(creatives.length))
                    : t.campaigns.creativeCount.replace("{count}", formatNumber(creatives.length))}
                </p>
              </>
            )}
          </div>

          {!editing && (
            <div className="flex items-center gap-3">
              <select
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                className="border rounded px-3 py-2 text-sm"
              >
                <option value="1d">{t.campaigns.periodYesterday}</option>
                <option value="7d">{t.campaigns.periodLast7Days}</option>
                <option value="30d">{t.campaigns.periodLast30Days}</option>
                <option value="all">{t.campaigns.periodAllTime}</option>
              </select>
              <button
                onClick={() => setEditing(true)}
                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded"
                title={t.campaigns.editCampaign}
              >
                <Pencil className="h-4 w-4" />
              </button>
              <button
                onClick={handleDeleteCampaign}
                className="p-2 text-red-500 hover:text-red-700 hover:bg-red-50 rounded"
                title={t.campaigns.deleteCampaign}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Performance Metrics */}
      {performance && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="card p-4">
            <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
              <DollarSign className="h-4 w-4" />
              {t.campaigns.spend}
            </div>
            <p className="text-2xl font-bold text-gray-900">
              ${performance.spend.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </p>
          </div>
          <div className="card p-4">
            <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
              <Eye className="h-4 w-4" />
              {t.campaigns.impressions}
            </div>
            <p className="text-2xl font-bold text-gray-900">
              {formatNumber(performance.impressions)}
            </p>
          </div>
          <div className="card p-4">
            <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
              <MousePointer className="h-4 w-4" />
              {t.campaigns.clicks}
            </div>
            <p className="text-2xl font-bold text-gray-900">
              {formatNumber(performance.clicks)}
            </p>
            {performance.ctr !== null && (
              <p className="text-xs text-gray-500">{asNumber(performance.ctr).toFixed(2)}% {t.creatives.ctr}</p>
            )}
          </div>
          <div className="card p-4">
            <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
              <Target className="h-4 w-4" />
              {t.dashboard.winRate}
            </div>
            <p className="text-2xl font-bold text-gray-900">
              {performance.win_rate !== null
                ? `${asNumber(performance.win_rate).toFixed(2)}%`
                : t.campaigns.notAvailable}
            </p>
            {performance.cpm !== null && (
              <p className="text-xs text-gray-500">${asNumber(performance.cpm).toFixed(2)} {t.creatives.cpm}</p>
            )}
          </div>
        </div>
      )}

      {/* Daily Trend Mini Chart */}
      {dailyTrend.length > 0 && (
        <div className="card p-4 mb-8">
          <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            {t.campaigns.dailyPerformance}
          </h3>
          <div className="h-24 flex items-end gap-1">
            {dailyTrend.slice(-14).map((day, i) => {
              const maxSpend = Math.max(...dailyTrend.map((d) => d.spend), 1);
              const height = (day.spend / maxSpend) * 100;
              return (
                <div
                  key={day.date}
                  className="flex-1 bg-primary-100 hover:bg-primary-200 rounded-t transition-colors"
                  style={{ height: `${Math.max(height, 2)}%` }}
                  title={t.campaigns.dailyTrendTooltip
                    .replace("{date}", formatTrendDate(day.date))
                    .replace("{spend}", day.spend.toFixed(2))
                    .replace("{impressions}", formatNumber(day.impressions))
                    .replace("{impsLabel}", t.creatives.impsShort)}
                />
              );
            })}
          </div>
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>{formatTrendDate(dailyTrend[Math.max(0, dailyTrend.length - 14)]?.date)}</span>
            <span>{formatTrendDate(dailyTrend[dailyTrend.length - 1]?.date)}</span>
          </div>
        </div>
      )}

      {/* Creatives Grid */}
      <h3 className="text-lg font-medium text-gray-900 mb-4">
        {t.creatives.title} ({creatives.length})
      </h3>

      {creatives.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {creatives.map((creative) => (
            <div key={creative.id} className="relative">
              <CreativeCard creative={creative} onPreview={setPreviewCreative} />
              <button
                onClick={() => handleRemoveCreative(creative.id)}
                disabled={removingId === creative.id}
                className="absolute top-2 right-2 p-1.5 bg-white/90 hover:bg-red-50 text-gray-500 hover:text-red-600 rounded-full shadow-sm border border-gray-200 transition-colors disabled:opacity-50"
                title={t.campaigns.removeFromCampaign}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <p className="text-gray-500">{t.campaigns.noCreativesInCampaign}</p>
          <Link href={clustersHref} className="btn-primary mt-4 inline-flex">
            {t.campaigns.browseCreatives}
          </Link>
        </div>
      )}

      {/* Preview Modal */}
      {previewCreative && (
        <PreviewModal
          creative={previewCreative}
          onClose={() => setPreviewCreative(null)}
        />
      )}
    </div>
  );
}
