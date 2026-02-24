/**
 * Information about required columns for each CSV report type.
 * Based on DATA_MODEL.md specifications.
 */
import { useTranslation } from "@/contexts/i18n-context";

export function RequiredColumnsTable() {
  const { t } = useTranslation();
  const rows = [
    {
      reportName: t.import.requiredTableReportBidsInAuction,
      targetTable: t.import.targetTableRtbDaily,
      columns: t.import.requiredTableColumnsBidsInAuction,
      rowClassName: "",
      reportClassName: "text-blue-700",
    },
    {
      reportName: t.import.requiredTableReportQuality,
      targetTable: t.import.targetTableRtbDaily,
      columns: t.import.requiredTableColumnsQuality,
      rowClassName: "bg-gray-50",
      reportClassName: "text-purple-700",
    },
    {
      reportName: t.import.requiredTableReportPipelineGeo,
      targetTable: t.import.targetTableRtbBidstream,
      columns: t.import.requiredTableColumnsPipelineGeo,
      rowClassName: "",
      reportClassName: "text-green-700",
    },
    {
      reportName: t.import.requiredTableReportPipeline,
      targetTable: t.import.targetTableRtbBidstream,
      columns: t.import.requiredTableColumnsPipeline,
      rowClassName: "bg-gray-50",
      reportClassName: "text-orange-700",
    },
    {
      reportName: t.import.requiredTableReportBidFiltering,
      targetTable: t.import.targetTableRtbBidFiltering,
      columns: t.import.requiredTableColumnsBidFiltering,
      rowClassName: "",
      reportClassName: "text-red-700",
    },
  ];

  return (
    <div className="space-y-4 text-sm">
      <p className="text-gray-600">
        {t.import.requiredColumnsIntro}
      </p>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-100">
              <th className="p-2 border font-medium">{t.import.reportName}</th>
              <th className="p-2 border font-medium">{t.import.targetTable}</th>
              <th className="p-2 border font-medium">{t.import.requiredColumnsHeader}</th>
            </tr>
          </thead>
          <tbody className="text-xs">
            {rows.map((row) => (
              <tr key={row.reportName} className={row.rowClassName}>
                <td className={`p-2 border font-medium ${row.reportClassName}`}>{row.reportName}</td>
                <td className="p-2 border">{row.targetTable}</td>
                <td className="p-2 border">{row.columns}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="bg-gray-50 p-3 rounded-lg">
        <p className="text-gray-700">
          <strong>{t.import.autoDetectionLogic}</strong>
        </p>
        <ul className="text-gray-600 mt-1 space-y-1 text-xs">
          <li>• {t.import.autoDetectionRuleBidFiltering}</li>
          <li>• {t.import.autoDetectionRuleBidsInAuction}</li>
          <li>• {t.import.autoDetectionRuleQuality}</li>
          <li>• {t.import.autoDetectionRulePipeline}</li>
          <li>• {t.import.autoDetectionRulePipelineGeo}</li>
        </ul>
      </div>
    </div>
  );
}
