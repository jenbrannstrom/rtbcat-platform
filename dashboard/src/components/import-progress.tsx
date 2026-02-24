"use client";

import { Cloud, Loader2 } from "lucide-react";
import { useTranslation } from "@/contexts/i18n-context";

interface ImportProgressProps {
  progress: number; // 0-100
}

export function ImportProgress({ progress }: ImportProgressProps) {
  const { t } = useTranslation();
  return (
    <div className="bg-white border rounded-lg p-8">
      <div className="text-center mb-6">
        <div className="flex justify-center mb-4">
          {progress < 100 ? (
            <Loader2 className="h-12 w-12 text-primary-500 animate-spin" />
          ) : (
            <Cloud className="h-12 w-12 text-primary-500" />
          )}
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          {t.import.importingData}
        </h3>
        <p className="text-sm text-gray-600">
          {t.import.pleaseWaitProcessingFile}
        </p>
      </div>

      <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
        <div
          className="bg-primary-600 h-full transition-all duration-300 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="text-center mt-3 text-sm text-gray-600">{progress}%</div>
    </div>
  );
}
