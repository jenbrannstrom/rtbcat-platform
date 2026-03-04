"use client";

import Link from "next/link";
import { useAccount } from "@/contexts/account-context";
import { useTranslation } from "@/contexts/i18n-context";
import { toBuyerScopedPath } from "@/lib/buyer-routes";

interface CampaignPerformance {
  impressions: number;
  clicks: number;
  spend: number;
  queries: number;
  win_rate: number | null;
  ctr: number | null;
  cpm: number | null;
}

interface Campaign {
  id: number;
  name: string;
  description?: string;
  creative_count: number;
  ai_generated: boolean;
  ai_confidence?: number;
  clustering_method?: string;
  status: string;
  performance?: CampaignPerformance;
}

interface CampaignCardProps {
  campaign: Campaign;
  period: string;
}

function asNumber(value: unknown, fallback = 0): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function formatNumber(num: number): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`;
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`;
  }
  return num.toLocaleString();
}

function formatCurrency(amount: number): string {
  if (amount >= 1000) {
    return `$${(amount / 1000).toFixed(1)}K`;
  }
  return `$${amount.toFixed(2)}`;
}

export function CampaignCard({ campaign, period }: CampaignCardProps) {
  const { selectedBuyerId } = useAccount();
  const { t } = useTranslation();
  const perf = campaign.performance;
  const campaignHref = toBuyerScopedPath(`/campaigns/${campaign.id}`, selectedBuyerId);

  return (
    <Link href={campaignHref}>
      <div className="bg-white border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer">
        <div className="flex justify-between items-start mb-3">
          <h3 className="font-semibold text-lg text-gray-900 truncate flex-1 mr-2">
            {campaign.name}
          </h3>
          <div className="flex gap-1">
            {campaign.ai_generated && campaign.ai_confidence && (
              <span
                className="text-xs px-2 py-1 rounded bg-purple-100 text-purple-700"
                title={t.campaigns.aiConfidenceTooltip.replace(
                  "{pct}",
                  String(Math.round(campaign.ai_confidence * 100))
                )}
              >
                {t.campaigns.aiBadgeShort}
              </span>
            )}
            {campaign.status !== "active" && (
              <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600">
                {campaign.status}
              </span>
            )}
          </div>
        </div>

        <p className="text-sm text-gray-500 mb-4">
          {campaign.creative_count !== 1
            ? t.campaigns.creativeCountPlural.replace("{count}", String(campaign.creative_count))
            : t.campaigns.creativeCount.replace("{count}", String(campaign.creative_count))}
          {campaign.clustering_method && (
            <span className="text-gray-400 ml-2">
              ({campaign.clustering_method})
            </span>
          )}
        </p>

        {perf && (
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-gray-500 block">{t.campaigns.spend}</span>
              <p className="font-medium text-gray-900">
                {formatCurrency(perf.spend)}
              </p>
            </div>
            <div>
              <span className="text-gray-500 block">{t.campaigns.impressions}</span>
              <p className="font-medium text-gray-900">
                {formatNumber(perf.impressions)}
              </p>
            </div>
            {perf.win_rate !== null && (
              <div>
                <span className="text-gray-500 block">{t.dashboard.winRate}</span>
                <p className="font-medium text-gray-900">
                  {asNumber(perf.win_rate).toFixed(2)}%
                </p>
              </div>
            )}
            {perf.ctr !== null && (
              <div>
                <span className="text-gray-500 block">{t.creatives.ctr}</span>
                <p className="font-medium text-gray-900">
                  {asNumber(perf.ctr).toFixed(2)}%
                </p>
              </div>
            )}
          </div>
        )}

        {!perf && (
          <div className="text-sm text-gray-400 italic">
            {t.campaigns.noPerformanceDataForPeriod.replace("{period}", period)}
          </div>
        )}
      </div>
    </Link>
  );
}

interface AutoClusterButtonProps {
  onClick: () => void;
  loading?: boolean;
  disabled?: boolean;
}

export function AutoClusterButton({
  onClick,
  loading = false,
  disabled = false,
}: AutoClusterButtonProps) {
  const { t } = useTranslation();
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
    >
      {loading ? (
        <>
          <span className="animate-spin">&#9696;</span>
          {t.campaigns.clustering}
        </>
      ) : (
        <>
          <span>&#128300;</span>
          {t.campaigns.autoClusterWithAi}
        </>
      )}
    </button>
  );
}
