import { CheckCircle } from "lucide-react";
import { useTranslation } from "@/contexts/i18n-context";

interface ColumnMappingCardProps {
  columns: Record<string, string>;
}

/**
 * Displays detected column mappings from CSV import.
 */
export function ColumnMappingCard({ columns }: ColumnMappingCardProps) {
  const { t } = useTranslation();
  const mappedColumns = Object.entries(columns).filter(([, v]) => v);

  return (
    <div className="bg-green-50 border border-green-200 rounded-lg p-4">
      <div className="flex items-start gap-2">
        <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
        <div className="flex-1">
          <p className="font-medium text-green-900">{t.import.columnsDetectedAndMapped}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {mappedColumns.map(([key, value]) => (
              <span key={key} className="inline-flex items-center px-2 py-1 bg-green-100 text-green-800 text-xs rounded">
                <span className="font-mono">{value}</span>
                <span className="mx-1 text-green-600">→</span>
                <span>{key}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
