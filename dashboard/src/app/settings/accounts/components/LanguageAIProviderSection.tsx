"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle,
  Eye,
  EyeOff,
  Key,
  Loader2,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import {
  deleteLanguageAIProviderKey,
  getLanguageAIProviderConfig,
  updateLanguageAIProvider,
  updateLanguageAIProviderKey,
  type LanguageAIProvider,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/contexts/i18n-context";

const PROVIDER_META: Record<
  LanguageAIProvider,
  { label: string; placeholder: string; docsLabel: string; docsUrl: string }
> = {
  gemini: {
    label: "Gemini",
    placeholder: "AIza...",
    docsLabel: "Google AI Studio",
    docsUrl: "https://aistudio.google.com/app/apikey",
  },
  claude: {
    label: "Claude",
    placeholder: "sk-ant-...",
    docsLabel: "Anthropic Console",
    docsUrl: "https://console.anthropic.com/settings/keys",
  },
  grok: {
    label: "Grok",
    placeholder: "xai-...",
    docsLabel: "xAI Console",
    docsUrl: "https://console.x.ai/",
  },
};

export function LanguageAIProviderSection() {
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  const [showKey, setShowKey] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<LanguageAIProvider>("gemini");
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(
    null
  );

  const { data: providerConfig, isLoading } = useQuery({
    queryKey: ["languageAIProviderConfig"],
    queryFn: getLanguageAIProviderConfig,
  });

  useEffect(() => {
    if (providerConfig?.provider) {
      setSelectedProvider(providerConfig.provider);
    }
  }, [providerConfig?.provider]);

  const setProviderMutation = useMutation({
    mutationFn: (provider: LanguageAIProvider) => updateLanguageAIProvider(provider),
    onSuccess: (data) => {
      setMessage({ type: "success", text: data.message });
      queryClient.invalidateQueries({ queryKey: ["languageAIProviderConfig"] });
      setTimeout(() => setMessage(null), 3500);
    },
    onError: (error) => {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Failed to update provider",
      });
      setTimeout(() => setMessage(null), 5000);
    },
  });

  const updateKeyMutation = useMutation({
    mutationFn: (payload: { provider: LanguageAIProvider; apiKey: string }) =>
      updateLanguageAIProviderKey(payload.provider, payload.apiKey),
    onSuccess: (data) => {
      setMessage({ type: "success", text: data.message });
      queryClient.invalidateQueries({ queryKey: ["languageAIProviderConfig"] });
      setIsEditing(false);
      setNewKey("");
      setTimeout(() => setMessage(null), 4000);
    },
    onError: (error) => {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Failed to save API key",
      });
      setTimeout(() => setMessage(null), 5000);
    },
  });

  const deleteKeyMutation = useMutation({
    mutationFn: (provider: LanguageAIProvider) => deleteLanguageAIProviderKey(provider),
    onSuccess: (data) => {
      setMessage({ type: "success", text: data.message });
      queryClient.invalidateQueries({ queryKey: ["languageAIProviderConfig"] });
      setTimeout(() => setMessage(null), 4000);
    },
    onError: (error) => {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Failed to remove API key",
      });
      setTimeout(() => setMessage(null), 5000);
    },
  });

  const handleSave = () => {
    if (!newKey.trim()) {
      setMessage({ type: "error", text: "Please enter an API key" });
      return;
    }
    updateKeyMutation.mutate({ provider: selectedProvider, apiKey: newKey.trim() });
  };

  const keyStatus = providerConfig?.providers?.[selectedProvider];
  const providerMeta = PROVIDER_META[selectedProvider];

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold",
              keyStatus?.configured ? "bg-green-500 text-white" : "bg-gray-200 text-gray-500"
            )}
          >
            {keyStatus?.configured ? (
              <CheckCircle className="w-5 h-5" />
            ) : (
              <Sparkles className="w-5 h-5" />
            )}
          </div>
          <div>
            <h3 className="text-lg font-medium text-gray-900">AI Language Detection</h3>
            <p className="text-sm text-gray-500">
              Choose provider and key for language + geo mismatch analysis.
            </p>
          </div>
        </div>
      </div>

      {message && (
        <div
          className={cn(
            "p-3 rounded-lg flex items-center justify-between mb-4",
            message.type === "success" ? "bg-green-50" : "bg-red-50"
          )}
        >
          <div className="flex items-center gap-2">
            {message.type === "success" ? (
              <CheckCircle className="h-4 w-4 text-green-500" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-red-500" />
            )}
            <span
              className={cn(
                "text-sm",
                message.type === "success" ? "text-green-800" : "text-red-800"
              )}
            >
              {message.text}
            </span>
          </div>
          <button onClick={() => setMessage(null)} className="text-gray-400 hover:text-gray-600">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">Provider</label>
        <select
          className="input max-w-xs"
          value={selectedProvider}
          onChange={(e) => {
            const provider = e.target.value as LanguageAIProvider;
            setSelectedProvider(provider);
            setIsEditing(false);
            setNewKey("");
            setProviderMutation.mutate(provider);
          }}
          disabled={setProviderMutation.isPending}
        >
          {providerConfig?.available_providers?.map((provider) => (
            <option key={provider} value={provider}>
              {PROVIDER_META[provider].label}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="py-4 flex justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
        </div>
      ) : keyStatus?.configured && !isEditing ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between py-3 px-4 bg-green-50 rounded-lg border border-green-200">
            <div className="flex items-center gap-3">
              <Key className="h-5 w-5 text-green-600" />
              <div>
                <p className="font-medium text-green-900">{providerMeta.label} key configured</p>
                <p className="text-sm text-green-700 font-mono">
                  {showKey ? keyStatus.masked_key : "••••••••••••"}
                </p>
                {keyStatus.source && (
                  <p className="text-xs text-green-700 mt-0.5">Source: {keyStatus.source}</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowKey(!showKey)}
                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded"
                title={showKey ? "Hide key" : "Show key"}
              >
                {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
              <button
                onClick={() => setIsEditing(true)}
                className="px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50 rounded font-medium"
              >
                {t.connect.change}
              </button>
              <button
                onClick={() => deleteKeyMutation.mutate(selectedProvider)}
                disabled={deleteKeyMutation.isPending}
                className="p-2 text-red-500 hover:text-red-700 hover:bg-red-50 rounded"
                title="Remove API key"
              >
                {deleteKeyMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>
          <p className="text-sm text-gray-500">
            Provider: <span className="font-medium">{providerMeta.label}</span>. Creatives will
            use this provider for language detection and geo mismatch analysis.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {providerMeta.label} API Key
            </label>
            <div className="flex gap-2">
              <input
                type="password"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                placeholder={providerMeta.placeholder}
                className="flex-1 input"
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSave();
                  if (e.key === "Escape") {
                    setIsEditing(false);
                    setNewKey("");
                  }
                }}
              />
              <button
                onClick={handleSave}
                disabled={updateKeyMutation.isPending || !newKey.trim()}
                className="btn-primary px-4"
              >
                {updateKeyMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  t.common.save
                )}
              </button>
              {isEditing && (
                <button
                  onClick={() => {
                    setIsEditing(false);
                    setNewKey("");
                  }}
                  className="px-3 py-2 text-gray-600 hover:bg-gray-100 rounded"
                >
                  {t.common.cancel}
                </button>
              )}
            </div>
            <p className="mt-2 text-xs text-gray-500">
              Get your API key from{" "}
              <a
                href={providerMeta.docsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                {providerMeta.docsLabel}
              </a>
            </p>
          </div>
          {!keyStatus?.configured && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5" />
                <p className="text-sm text-amber-800">
                  {providerMeta.label} is selected but no key is configured. Analysis will be
                  skipped until a key is added.
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
