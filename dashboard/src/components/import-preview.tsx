import type { PerformanceRow } from "@/lib/types/import";

interface ImportPreviewProps {
  data: PerformanceRow[];
}

export function ImportPreview({ data }: ImportPreviewProps) {
  if (data.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">No data to preview</div>
    );
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-4 py-3 border-b">
        <h3 className="font-semibold text-gray-900">
          Preview (first {data.length} rows)
        </h3>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Creative ID
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Date
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                Impressions
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                Clicks
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                Spend
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Geo
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {data.map((row, index) => (
              <tr key={index} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-sm text-gray-900">
                  {row.creative_id}
                </td>
                <td className="px-4 py-3 text-sm text-gray-900">{row.date}</td>
                <td className="px-4 py-3 text-sm text-gray-900 text-right">
                  {row.impressions.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm text-gray-900 text-right">
                  {row.clicks.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm text-gray-900 text-right">
                  ${row.spend.toFixed(2)}
                </td>
                <td className="px-4 py-3 text-sm text-gray-900">
                  {row.geography || "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
