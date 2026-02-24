/**
 * Troubleshooting tips for large file imports.
 */
import { useTranslation } from "@/contexts/i18n-context";

export function TroubleshootingSection() {
  const { t } = useTranslation();

  return (
    <div className="space-y-4 text-sm">
      <p className="text-gray-700">
        {t.import.troubleshootingIfCsvTooLarge}
      </p>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
        <h4 className="font-semibold text-yellow-800 mb-2">{t.import.splitByDateKeepAllData}</h4>
        <p className="text-gray-700 mb-2">
          {t.import.splitByDateKeepAllDataDesc}
        </p>
        <ul className="space-y-1 text-gray-600 ml-4">
          <li>• {t.import.reportAExample}</li>
          <li>• {t.import.reportBExample}</li>
          <li>• {t.import.reportEtc}</li>
        </ul>
        <p className="text-gray-600 mt-2">
          {t.import.uploadEachFileSeparatelyMergeByCreativeId}
        </p>
      </div>

      <div className="bg-red-50 border border-red-200 rounded-lg p-3">
        <h4 className="font-semibold text-red-800 mb-2">{t.import.doNotSplitByMetrics}</h4>
        <p className="text-gray-700">
          {t.import.doNotSplitByMetricsDesc}
        </p>
      </div>

      <div>
        <h4 className="font-semibold text-gray-900 mb-1">{t.import.streamingUpload}</h4>
        <p className="text-gray-600">
          {t.import.streamingUploadDesc}
        </p>
      </div>
    </div>
  );
}
