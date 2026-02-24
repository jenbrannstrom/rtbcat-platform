import { AlertCircle } from "lucide-react";
import type { ValidationError } from "@/lib/types/import";
import { useTranslation } from "@/contexts/i18n-context";

interface ValidationErrorsProps {
  errors: ValidationError[];
  maxShow?: number;
}

export function ValidationErrors({ errors, maxShow = 10 }: ValidationErrorsProps) {
  const { t } = useTranslation();
  const displayErrors = errors.slice(0, maxShow);
  const remaining = errors.length - maxShow;

  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <AlertCircle className="h-5 w-5 text-red-600" />
        <h3 className="font-semibold text-red-900">
          {errors.length}{" "}
          {errors.length === 1 ? t.import.validationError : t.import.validationErrors}
        </h3>
      </div>

      <div className="space-y-2 max-h-60 overflow-y-auto">
        {displayErrors.map((error, index) => (
          <div key={index} className="text-sm text-red-800">
            <span className="font-medium">
              {t.import.rowLabel.replace("{row}", String(error.row))}
              {error.field && ` (${error.field})`}:
            </span>{" "}
            {error.error}
            {error.value !== null && error.value !== undefined && (
              <span className="text-red-600 ml-1">
                {t.import.gotValue.replace("{value}", JSON.stringify(error.value))}
              </span>
            )}
          </div>
        ))}
      </div>

      {remaining > 0 && (
        <div className="mt-3 text-sm text-red-700">
          {t.import.andMoreValidationErrors
            .replace("{count}", String(remaining))
            .replace("{suffix}", remaining === 1 ? "" : "s")}
        </div>
      )}
    </div>
  );
}
