"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle,
  AlertTriangle,
  Loader2,
  X,
  Sparkles,
  Eye,
  EyeOff,
  Key,
  Trash2,
} from "lucide-react";
import {
  getGeminiKeyStatus,
  updateGeminiKey,
  deleteGeminiKey,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/contexts/i18n-context";

/**
 * Gemini API Key management section.
 * Allows users to configure their Gemini API key for AI language detection.
 */
export function GeminiApiKeySection() {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const [showKey, setShowKey] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const { data: keyStatus, isLoading } = useQuery({
    queryKey: ["geminiKeyStatus"],
    queryFn: getGeminiKeyStatus,
  });

  const updateMutation = useMutation({
    mutationFn: (apiKey: string) => updateGeminiKey(apiKey),
    onSuccess: (data) => {
      setMessage({ type: "success", text: data.message });
      queryClient.invalidateQueries({ queryKey: ["geminiKeyStatus"] });
      setIsEditing(false);
      setNewKey("");
      setTimeout(() => setMessage(null), 5000);
    },
    onError: (error) => {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : t.setup.geminiFailedToSaveApiKey,
      });
      setTimeout(() => setMessage(null), 5000);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteGeminiKey,
    onSuccess: (data) => {
      setMessage({ type: "success", text: data.message });
      queryClient.invalidateQueries({ queryKey: ["geminiKeyStatus"] });
      setTimeout(() => setMessage(null), 5000);
    },
    onError: (error) => {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : t.setup.geminiFailedToRemoveApiKey,
      });
      setTimeout(() => setMessage(null), 5000);
    },
  });

  const handleSave = () => {
    if (!newKey.trim()) {
      setMessage({ type: "error", text: t.setup.geminiEnterApiKey });
      return;
    }
    updateMutation.mutate(newKey.trim());
  };

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={cn(
            "w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold",
            keyStatus?.configured ? "bg-green-500 text-white" : "bg-gray-200 text-gray-500"
          )}>
            {keyStatus?.configured ? <CheckCircle className="w-5 h-5" /> : <Sparkles className="w-5 h-5" />}
          </div>
          <div>
            <h3 className="text-lg font-medium text-gray-900">{t.setup.geminiLanguageDetection}</h3>
            <p className="text-sm text-gray-500">{t.setup.geminiLanguageDetectionDesc}</p>
          </div>
        </div>
      </div>

      {/* Status Message */}
      {message && (
        <div className={cn(
          "p-3 rounded-lg flex items-center justify-between mb-4",
          message.type === "success" ? "bg-green-50" : "bg-red-50"
        )}>
          <div className="flex items-center gap-2">
            {message.type === "success" ? (
              <CheckCircle className="h-4 w-4 text-green-500" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-red-500" />
            )}
            <span className={cn(
              "text-sm",
              message.type === "success" ? "text-green-800" : "text-red-800"
            )}>
              {message.text}
            </span>
          </div>
          <button onClick={() => setMessage(null)} className="text-gray-400 hover:text-gray-600">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

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
                <p className="font-medium text-green-900">{t.setup.geminiApiKeyConfigured}</p>
                <p className="text-sm text-green-700 font-mono">
                  {showKey ? keyStatus.masked_key : "••••••••••••"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowKey(!showKey)}
                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded"
                title={showKey ? t.setup.geminiHideKey : t.setup.geminiShowKey}
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
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
                className="p-2 text-red-500 hover:text-red-700 hover:bg-red-50 rounded"
                title={t.setup.geminiRemoveApiKey}
              >
                {deleteMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>
          <p className="text-sm text-gray-500">
            {t.setup.geminiEnabledHelp}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t.setup.geminiApiKeyLabel}
            </label>
            <div className="flex gap-2">
              <input
                type="password"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                placeholder="AIza..."
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
                disabled={updateMutation.isPending || !newKey.trim()}
                className="btn-primary px-4"
              >
                {updateMutation.isPending ? (
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
              {t.setup.geminiGetApiKeyFrom}{" "}
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                {t.setup.geminiGoogleAiStudio}
              </a>
            </p>
          </div>
          {!keyStatus?.configured && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5" />
                <p className="text-sm text-amber-800">
                  {t.setup.geminiMissingWarning}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
