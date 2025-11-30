"use client";

import type { CsvType } from "./csv-type-selector";

interface ImportInstructionsProps {
  csvType: CsvType;
}

export function ImportInstructions({ csvType }: ImportInstructionsProps) {
  const isVideo = csvType === "video";

  return (
    <div
      className={`border rounded-lg p-4 mb-4 ${
        isVideo
          ? "bg-purple-50 border-purple-200"
          : "bg-blue-50 border-blue-200"
      }`}
    >
      <h3
        className={`font-semibold mb-2 ${
          isVideo ? "text-purple-900" : "text-blue-900"
        }`}
      >
        {isVideo ? "🎬 Video CSV" : "📊 Performance CSV"} Requirements
      </h3>

      <div className={`text-sm ${isVideo ? "text-purple-800" : "text-blue-800"}`}>
        <p className="mb-2">
          <strong>Required columns:</strong>
        </p>
        <ul className="list-disc list-inside mb-3 space-y-1">
          <li>Date (Day, #Day)</li>
          <li>Creative ID (#Creative ID)</li>
          <li>Country</li>
          <li>Impressions, Clicks, Spend</li>
          <li>Reached queries (for QPS analysis)</li>
          {isVideo && (
            <>
              <li>Video starts</li>
              <li>Video completions</li>
            </>
          )}
        </ul>

        <p className="mb-2">
          <strong>Helpful columns:</strong>
        </p>
        <ul className="list-disc list-inside mb-3 space-y-1">
          <li>Mobile app name / ID</li>
          <li>Platform</li>
          <li>Publisher name / ID</li>
          {isVideo && <li>Video quartiles (25%, 50%, 75%)</li>}
        </ul>

        <p className="mb-2">
          <strong>Seat identification (parsed once):</strong>
        </p>
        <ul className="list-disc list-inside mb-3 space-y-1">
          <li>Billing ID</li>
          <li>Buyer account name / ID</li>
        </ul>

        <p
          className={`text-xs ${isVideo ? "text-purple-600" : "text-blue-600"}`}
        >
          Google Authorized Buyers format is automatically detected and
          converted.
        </p>
      </div>

      <div className="mt-4 pt-4 border-t border-opacity-20 border-current">
        <p
          className={`text-xs ${isVideo ? "text-purple-700" : "text-blue-700"}`}
        >
          <strong>Suggested file naming:</strong>
        </p>
        <div
          className={`font-mono text-xs mt-1 ${
            isVideo ? "text-purple-600" : "text-blue-600"
          }`}
        >
          {isVideo ? (
            <span>{"{seat-name}_video_{YYYY-MM-DD}.csv"}</span>
          ) : (
            <span>{"{seat-name}_performance_{YYYY-MM-DD}.csv"}</span>
          )}
        </div>
      </div>
    </div>
  );
}
