/**
 * Troubleshooting tips for large file imports.
 */
export function TroubleshootingSection() {
  return (
    <div className="space-y-4 text-sm">
      <p className="text-gray-700">
        If your CSV export is too large (over 100MB or times out):
      </p>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
        <h4 className="font-semibold text-yellow-800 mb-2">Split by Date, Keep ALL Data</h4>
        <p className="text-gray-700 mb-2">
          Create multiple scheduled reports for different date ranges, but keep ALL dimensions and metrics in each:
        </p>
        <ul className="space-y-1 text-gray-600 ml-4">
          <li>• Report A: Yesterday (Day 1)</li>
          <li>• Report B: 2 days ago (Day 2)</li>
          <li>• etc.</li>
        </ul>
        <p className="text-gray-600 mt-2">
          Upload each file separately. Cat-Scan will merge them using <strong>Creative ID</strong> as the key.
        </p>
      </div>

      <div className="bg-red-50 border border-red-200 rounded-lg p-3">
        <h4 className="font-semibold text-red-800 mb-2">Do NOT split by metrics</h4>
        <p className="text-gray-700">
          Never create separate exports for different metrics (e.g., one for video, one for display).
          This breaks the data model. Always export ALL metrics together.
        </p>
      </div>

      <div>
        <h4 className="font-semibold text-gray-900 mb-1">Streaming upload</h4>
        <p className="text-gray-600">
          Files over 5MB are automatically uploaded using streaming mode with progress tracking.
          This handles files up to 500MB.
        </p>
      </div>
    </div>
  );
}
