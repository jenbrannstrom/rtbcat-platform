"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { FolderKanban, ChevronRight, Image } from "lucide-react";
import { getCampaigns } from "@/lib/api";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import { formatNumber } from "@/lib/utils";

export default function CampaignsPage() {
  const {
    data: campaigns,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => getCampaigns({ limit: 100 }),
  });

  if (isLoading) {
    return <LoadingPage />;
  }

  if (error) {
    return (
      <ErrorPage
        message={
          error instanceof Error ? error.message : "Failed to load campaigns"
        }
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Campaigns</h1>
        <p className="mt-1 text-sm text-gray-500">
          AI-clustered campaign groups based on creative similarity
        </p>
      </div>

      {campaigns && campaigns.length > 0 ? (
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
                <h3 className="font-medium text-gray-900">{campaign.name}</h3>
                <p className="text-sm text-gray-500">
                  Source: {campaign.source}
                </p>
              </div>
              <div className="flex items-center text-gray-500">
                <Image className="h-4 w-4 mr-1" />
                <span className="text-sm">
                  {formatNumber(campaign.creative_count)} creatives
                </span>
                <ChevronRight className="h-5 w-5 ml-4" />
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="text-center py-12">
          <FolderKanban className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900">
            No campaigns yet
          </h3>
          <p className="mt-2 text-sm text-gray-500">
            Campaigns are created when creatives are clustered using AI.
          </p>
          <p className="mt-1 text-sm text-gray-500">
            Run{" "}
            <code className="px-1 py-0.5 bg-gray-100 rounded">
              python main.py cluster
            </code>{" "}
            to group creatives.
          </p>
        </div>
      )}

      <div className="mt-6 text-sm text-gray-500">
        {campaigns?.length ?? 0} campaigns total
      </div>
    </div>
  );
}
