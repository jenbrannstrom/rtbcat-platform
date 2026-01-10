/**
 * Information about required columns for CSV import.
 */
export function RequiredColumnsTable() {
  return (
    <div className="space-y-4 text-sm">
      <p className="text-gray-600">
        Cat-Scan imports <strong>all recognized columns</strong> from your CSV.
        The more data you export, the better the analysis.
      </p>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
        <p className="text-blue-800">
          <strong>Creative ID</strong> is the key field that links performance data to your creative inventory.
          Every row must have a Creative ID.
        </p>
      </div>

      <div className="bg-gray-50 p-3 rounded-lg">
        <p className="text-gray-700">
          <strong>Column auto-detection:</strong> Cat-Scan automatically maps Google{"'"}s column names
          (e.g., <code className="bg-gray-200 px-1 rounded">#Creative ID</code> → <code className="bg-gray-200 px-1 rounded">creative_id</code>).
          Unknown columns are safely ignored.
        </p>
      </div>
    </div>
  );
}
