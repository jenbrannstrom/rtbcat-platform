"use client";

import { useTranslation } from "@/contexts/i18n-context";

interface ImportPreviewProps {
  headers: string[];
  rows: Record<string, string>[];
}

export function ImportPreview({ headers, rows }: ImportPreviewProps) {
  const { t } = useTranslation();
  if (rows.length === 0 || headers.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">{t.import.noDataToPreview}</div>
    );
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-4 py-3 border-b">
        <h3 className="font-semibold text-gray-900">
          {t.import.previewFirstRowsCount.replace("{count}", String(rows.length))}
        </h3>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {headers.map((header) => (
                <th
                  key={header}
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {rows.map((row, index) => (
              <tr key={index} className="hover:bg-gray-50">
                {headers.map((header) => (
                  <td key={header} className="px-4 py-3 text-sm text-gray-900">
                    {row[header] ?? ""}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
