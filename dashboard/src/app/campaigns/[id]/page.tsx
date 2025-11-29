"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowLeft, X } from "lucide-react";
import { getCampaign, getCreatives, removeCreativeFromCampaign } from "@/lib/api";
import { CreativeCard } from "@/components/creative-card";
import { PreviewModal } from "@/components/preview-modal";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import type { Creative } from "@/types/api";

function RemovableCreativeCard({
  creative,
  onPreview,
  onRemove,
  isRemoving,
}: {
  creative: Creative;
  onPreview: (creative: Creative) => void;
  onRemove: (id: string) => void;
  isRemoving: boolean;
}) {
  return (
    <div className="relative">
      <CreativeCard creative={creative} onPreview={onPreview} />
      <button
        onClick={() => onRemove(creative.id)}
        disabled={isRemoving}
        className="absolute top-2 right-2 p-1.5 bg-white/90 hover:bg-red-50 text-gray-500 hover:text-red-600 rounded-full shadow-sm border border-gray-200 transition-colors disabled:opacity-50"
        title="Remove from Campaign"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export default function CampaignDetailPage() {
  const params = useParams();
  const campaignId = params.id as string;
  const queryClient = useQueryClient();
  const [previewCreative, setPreviewCreative] = useState<Creative | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const {
    data: campaign,
    isLoading: campaignLoading,
    error: campaignError,
  } = useQuery({
    queryKey: ["campaign", campaignId],
    queryFn: () => getCampaign(campaignId),
    enabled: !!campaignId,
  });

  const {
    data: creatives,
    isLoading: creativesLoading,
    error: creativesError,
    refetch,
  } = useQuery({
    queryKey: ["creatives", { campaign_id: campaignId }],
    queryFn: () => getCreatives({ campaign_id: campaignId, limit: 1000 }),
    enabled: !!campaignId,
  });

  const removeMutation = useMutation({
    mutationFn: removeCreativeFromCampaign,
    onMutate: (id) => {
      setRemovingId(id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["creatives", { campaign_id: campaignId }] });
      queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    },
    onSettled: () => {
      setRemovingId(null);
    },
  });

  const handleRemove = (id: string) => {
    if (confirm("Remove this creative from the campaign?")) {
      removeMutation.mutate(id);
    }
  };

  if (campaignLoading || creativesLoading) {
    return <LoadingPage />;
  }

  if (campaignError || creativesError) {
    const error = campaignError || creativesError;
    return (
      <ErrorPage
        message={error instanceof Error ? error.message : "Failed to load campaign"}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/campaigns"
          className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Campaigns
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">{campaign?.name}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {creatives?.length ?? 0} creatives in this campaign
        </p>
      </div>

      {/* Creatives Grid */}
      {creatives && creatives.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {creatives.map((creative) => (
            <RemovableCreativeCard
              key={creative.id}
              creative={creative}
              onPreview={setPreviewCreative}
              onRemove={handleRemove}
              isRemoving={removingId === creative.id}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-12">
          <p className="text-gray-500">No creatives in this campaign</p>
          <Link href="/creatives" className="btn-primary mt-4 inline-flex">
            Browse Creatives
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
