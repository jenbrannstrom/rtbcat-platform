"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { collectCreativesSync } from "@/lib/api";
import type { CollectResponse } from "@/types/api";

export default function CollectPage() {
  const [accountId, setAccountId] = useState("");
  const [filterQuery, setFilterQuery] = useState("");
  const [result, setResult] = useState<CollectResponse | null>(null);
  const queryClient = useQueryClient();

  const collectMutation = useMutation({
    mutationFn: collectCreativesSync,
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["creatives"] });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!accountId.trim()) return;
    setResult(null);
    collectMutation.mutate({
      account_id: accountId.trim(),
      filter_query: filterQuery.trim() || undefined,
    });
  };

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Collect Creatives</h1>
        <p className="mt-1 text-sm text-gray-500">
          Fetch creatives from Google Authorized Buyers API
        </p>
      </div>

      <div className="max-w-2xl">
        <form onSubmit={handleSubmit} className="card p-6 space-y-6">
          <div>
            <label
              htmlFor="accountId"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Account ID *
            </label>
            <input
              id="accountId"
              type="text"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              placeholder="12345"
              className="input"
              required
            />
            <p className="mt-1 text-xs text-gray-500">
              Your Authorized Buyers bidder account ID
            </p>
          </div>

          <div>
            <label
              htmlFor="filterQuery"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Filter Query (optional)
            </label>
            <input
              id="filterQuery"
              type="text"
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              placeholder="creativeServingDecision.networkPolicyCompliance.status=APPROVED"
              className="input"
            />
            <p className="mt-1 text-xs text-gray-500">
              API filter string to narrow results
            </p>
          </div>

          <button
            type="submit"
            disabled={!accountId.trim() || collectMutation.isPending}
            className="btn-primary w-full"
          >
            {collectMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Collecting...
              </>
            ) : (
              <>
                <Download className="mr-2 h-4 w-4" />
                Start Collection
              </>
            )}
          </button>
        </form>

        {collectMutation.isError && (
          <div className="mt-6 p-4 bg-red-50 rounded-lg flex items-start">
            <AlertCircle className="h-5 w-5 text-red-400 mt-0.5" />
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">
                Collection Failed
              </h3>
              <p className="mt-1 text-sm text-red-700">
                {collectMutation.error instanceof Error
                  ? collectMutation.error.message
                  : "An error occurred"}
              </p>
            </div>
          </div>
        )}

        {result && (
          <div className="mt-6 p-4 bg-green-50 rounded-lg flex items-start">
            <CheckCircle className="h-5 w-5 text-green-400 mt-0.5" />
            <div className="ml-3">
              <h3 className="text-sm font-medium text-green-800">
                Collection Complete
              </h3>
              <p className="mt-1 text-sm text-green-700">{result.message}</p>
              {result.creatives_collected !== null && (
                <p className="mt-2 text-sm text-green-700">
                  <strong>{result.creatives_collected}</strong> creatives saved
                  to database
                </p>
              )}
            </div>
          </div>
        )}

        <div className="mt-8 p-4 bg-gray-50 rounded-lg">
          <h3 className="text-sm font-medium text-gray-900 mb-2">
            Common Filters
          </h3>
          <div className="space-y-2">
            <button
              type="button"
              onClick={() =>
                setFilterQuery(
                  "creativeServingDecision.networkPolicyCompliance.status=APPROVED"
                )
              }
              className="block text-sm text-primary-600 hover:text-primary-700"
            >
              Approved creatives only
            </button>
            <button
              type="button"
              onClick={() => setFilterQuery("creativeFormat=HTML")}
              className="block text-sm text-primary-600 hover:text-primary-700"
            >
              HTML banners only
            </button>
            <button
              type="button"
              onClick={() => setFilterQuery("creativeFormat=VIDEO")}
              className="block text-sm text-primary-600 hover:text-primary-700"
            >
              Video creatives only
            </button>
            <button
              type="button"
              onClick={() => setFilterQuery("creativeFormat=NATIVE")}
              className="block text-sm text-primary-600 hover:text-primary-700"
            >
              Native ads only
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
