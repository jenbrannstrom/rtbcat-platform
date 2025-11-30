"use client";

export type CsvType = "performance" | "video";

interface CsvTypeSelectorProps {
  value: CsvType;
  onChange: (type: CsvType) => void;
  disabled?: boolean;
}

export function CsvTypeSelector({
  value,
  onChange,
  disabled = false,
}: CsvTypeSelectorProps) {
  return (
    <div className="mb-6">
      <label className="block text-sm font-medium text-gray-700 mb-3">
        Select CSV Type:
      </label>
      <div className="grid grid-cols-2 gap-4">
        <button
          type="button"
          onClick={() => onChange("performance")}
          disabled={disabled}
          className={`
            relative p-4 border-2 rounded-lg text-left transition-all
            ${
              value === "performance"
                ? "border-blue-500 bg-blue-50"
                : "border-gray-200 hover:border-gray-300 bg-white"
            }
            ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
          `}
        >
          <div className="flex items-center gap-3">
            <span className="text-2xl">📊</span>
            <div>
              <div className="font-semibold text-gray-900">Performance</div>
              <div className="text-sm text-gray-500">(Display/General)</div>
            </div>
          </div>
          {value === "performance" && (
            <div className="absolute top-2 right-2 w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center">
              <svg
                className="w-3 h-3 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={3}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
          )}
        </button>

        <button
          type="button"
          onClick={() => onChange("video")}
          disabled={disabled}
          className={`
            relative p-4 border-2 rounded-lg text-left transition-all
            ${
              value === "video"
                ? "border-purple-500 bg-purple-50"
                : "border-gray-200 hover:border-gray-300 bg-white"
            }
            ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
          `}
        >
          <div className="flex items-center gap-3">
            <span className="text-2xl">🎬</span>
            <div>
              <div className="font-semibold text-gray-900">Video</div>
              <div className="text-sm text-gray-500">(Video Ads)</div>
            </div>
          </div>
          {value === "video" && (
            <div className="absolute top-2 right-2 w-5 h-5 bg-purple-500 rounded-full flex items-center justify-center">
              <svg
                className="w-3 h-3 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={3}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
          )}
        </button>
      </div>
    </div>
  );
}
