"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { FolderKanban, ChevronRight, Sparkles, RefreshCw } from "lucide-react";
import { formatNumber } from "@/lib/utils";

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

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [clustering, setClustering] = useState(false);
  const [period, setPeriod] = useState("7d");
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  useEffect(() => {
    fetchCampaigns();
  }, [period]);

  const fetchCampaigns = async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `/api/ai-campaigns?include_performance=true&period=${period}`
      );
      if (res.ok) {
        const data = await res.json();
        setCampaigns(data);
      }
    } catch (error) {
      console.error("Error fetching campaigns:", error);
    }
    setLoading(false);
  };

  const handleAutoCluster = async () => {
    setClustering(true);
    setMessage(null);

    try {
      const res = await fetch("/api/ai-campaigns/auto-cluster", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_ai: true, min_cluster_size: 3 }),
      });

      const result = await res.json();

      if (res.ok) {
        if (result.campaigns_created > 0) {
          setMessage({
            type: "success",
            text: `Created ${result.campaigns_created} campaigns with ${result.creatives_categorized} creatives!`,
          });
          fetchCampaigns();
        } else {
          setMessage({
            type: "success",
            text: "All creatives are already categorized.",
          });
        }
      } else {
        setMessage({
          type: "error",
          text: result.detail || "Clustering failed",
        });
      }
    } catch (error) {
      setMessage({
        type: "error",
        text: "Failed to run auto-clustering",
      });
    }

    setClustering(false);
  };

  const totalCreatives = campaigns.reduce((sum, c) => sum + c.creative_count, 0);
  const totalSpend = campaigns.reduce(
    (sum, c) => sum + (c.performance?.spend || 0),
    0
  );

  return (
    <div className="p-8">
      <div className="flex justify-between items-start mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI Campaigns</h1>
          <p className="mt-1 text-sm text-gray-500">
            {campaigns.length} campaigns, {formatNumber(totalCreatives)} creatives
            {totalSpend > 0 && ` - $${formatNumber(totalSpend)} spend`}
          </p>
        </div>

        <div className="flex gap-3 items-center">
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="border rounded px-3 py-2 text-sm"
          >
            <option value="1d">Yesterday</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="all">All time</option>
          </select>

          <button
            onClick={handleAutoCluster}
            disabled={clustering}
            className="btn-primary flex items-center gap-2 disabled:opacity-50"
          >
            {clustering ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                Clustering...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Auto-Cluster with AI
              </>
            )}
          </button>
        </div>
      </div>

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

      {loading ? (
        <div className="animate-pulse space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="card p-4 h-20 bg-gray-100" />
          ))}
        </div>
      ) : campaigns.length > 0 ? (
        <div className="space-y-4">
          {campaigns.map((campaign) => (
            <Link
              key={campaign.id}
              href={`/campaigns/${campaign.id}`}
              className="card p-4 flex items-center hover:shadow-md transition-shadow"
            >
              <div className="p-3 bg-primary-50 rounded-lg">
                <FolderKanban className="h-6 w-6 text-primary-600" />
              </div>
              <div className="ml-4 flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium text-gray-900">{campaign.name}</h3>
                  {campaign.ai_generated && campaign.ai_confidence && (
                    <span
                      className="text-xs px-2 py-0.5 rounded bg-purple-100 text-purple-700"
                      title={`AI confidence: ${Math.round(campaign.ai_confidence * 100)}%`}
                    >
                      AI
                    </span>
                  )}
                  {campaign.status !== "active" && (
                    <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                      {campaign.status}
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-500">
                  {campaign.clustering_method && `${campaign.clustering_method} - `}
                  {formatNumber(campaign.creative_count)} creative{campaign.creative_count !== 1 ? "s" : ""}
                </p>
              </div>
              <div className="flex items-center gap-6 text-sm">
                {campaign.performance && (
                  <>
                    <div className="text-right">
                      <span className="text-gray-500 block text-xs">Spend</span>
                      <span className="font-medium">
                        ${campaign.performance.spend.toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </span>
                    </div>
                    <div className="text-right">
                      <span className="text-gray-500 block text-xs">Impressions</span>
                      <span className="font-medium">
                        {formatNumber(campaign.performance.impressions)}
                      </span>
                    </div>
                    {campaign.performance.win_rate !== null && (
                      <div className="text-right">
                        <span className="text-gray-500 block text-xs">Win Rate</span>
                        <span className="font-medium">
                          {campaign.performance.win_rate.toFixed(2)}%
                        </span>
                      </div>
                    )}
                  </>
                )}
                <ChevronRight className="h-5 w-5 text-gray-400" />
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState onAutoCluster={handleAutoCluster} loading={clustering} />
      )}
    </div>
  );
}

interface EmptyStateProps {
  onAutoCluster: () => void;
  loading: boolean;
}

function EmptyState({ onAutoCluster, loading }: EmptyStateProps) {
  return (
    <div className="text-center py-12 bg-gray-50 rounded-lg">
      <FolderKanban className="mx-auto h-12 w-12 text-gray-400" />
      <h3 className="mt-4 text-lg font-medium text-gray-900">
        No campaigns yet
      </h3>
      <p className="mt-2 text-sm text-gray-500 max-w-md mx-auto">
        Your creatives haven&apos;t been organized into campaigns yet. Use AI to
        automatically group similar creatives into meaningful campaigns.
      </p>
      <button
        onClick={onAutoCluster}
        disabled={loading}
        className="mt-6 btn-primary flex items-center gap-2 mx-auto disabled:opacity-50"
      >
        {loading ? (
          <>
            <RefreshCw className="h-4 w-4 animate-spin" />
            Clustering...
          </>
        ) : (
          <>
            <Sparkles className="h-4 w-4" />
            Auto-Cluster with AI
          </>
        )}
      </button>
    </div>
  );
}
